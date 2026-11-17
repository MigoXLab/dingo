"""Evaluate saved SIFT1M query attempts against an existing ANN cache"""

from __future__ import annotations
import argparse
import json
import sys
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dingo.io import Data

# TODO: Move evaluation orchestration into a reusable module
# TODO: Add QPS when query logs include the full run window
DATASET_NAME = "sift-128-euclidean"
DEFAULT_CACHE_DIR = "~/.cache/dingo/ann_benchmarks"
ATTEMPT_FIELDS = {"dataset", "query_id", "backend", "top_k", "hits", "elapsed_ms", "status", "error"}


def read_attempts(path: Path) -> list[dict[str, Any]]:
    """Read query attempts with line-specific validation errors"""
    attempts = []
    backend = None
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            try:
                row = json.loads(line)
                if not isinstance(row, dict) or set(row) != ATTEMPT_FIELDS:
                    raise ValueError("Expected the current query-attempt fields")
                if row["dataset"] != DATASET_NAME:
                    raise ValueError(f"Dataset must be {DATASET_NAME}")
                if type(row["query_id"]) is not int or row["query_id"] < 0:
                    raise ValueError("query_id must be a nonnegative native integer")
                if not isinstance(row["backend"], str) or not row["backend"].strip():
                    raise ValueError("backend must be a nonempty string")
                if backend is not None and row["backend"] != backend:
                    raise ValueError("All attempts must use the same backend")
                if type(row["top_k"]) is not int or row["top_k"] != 10:
                    raise ValueError("Recall@10 requires top_k=10")
                elapsed = row["elapsed_ms"]
                if type(elapsed) not in (int, float) or not isfinite(elapsed) or elapsed < 0:
                    raise ValueError("elapsed_ms must be finite and nonnegative")
                status, hits = row["status"], row["hits"]
                if status not in ("ok", "empty", "timeout", "error") or not isinstance(hits, list):
                    raise ValueError("Invalid status or hit list")
                if (status == "ok") != bool(hits):
                    raise ValueError("Only ok attempts must contain hits")
                if status in ("ok", "empty"):
                    if row["error"] is not None:
                        raise ValueError("Successful attempts must have error=null")
                elif not isinstance(row["error"], str):
                    raise ValueError("Failed attempts must contain an error string")
                for rank, hit in enumerate(hits, 1):
                    if not isinstance(hit, dict) or set(hit) != {"id", "rank", "distance"}:
                        raise ValueError(f"Hit {rank} must contain id, rank, distance")
                    if type(hit["id"]) not in (int, str):
                        raise ValueError(f"Hit {rank} ID must be an integer or string")
                    if type(hit["rank"]) is not int or hit["rank"] != rank:
                        raise ValueError("Hit ranks must match contiguous original positions")
                    if type(hit["distance"]) not in (int, float) or not isfinite(hit["distance"]):
                        raise ValueError(f"Hit {rank} distance must be finite and numeric")
            except (ValueError, TypeError, OverflowError) as exc:
                raise ValueError(f"{path}: line {line_number}: {exc}") from exc
            backend = row["backend"]
            attempts.append(row)
    if not attempts:
        raise ValueError(f"{path}: no query attempts")
    return attempts


def score_attempts(attempts: list[dict[str, Any]], data: Data) -> list[dict[str, Any]]:
    """Score original hit slots using the first ten official neighbor IDs"""
    from dingo.retrieval.eval_utils import compute_ann_result_quality, recall_at_k

    if data.metadata.get("name") != DATASET_NAME:
        raise ValueError(f"Cached dataset must be {DATASET_NAME}")
    base_count = data.base.shape[0]
    if data.ground_truth.ndim != 2 or data.ground_truth.shape[1] < 10:
        raise ValueError("Official ground truth must contain at least ten neighbors per query")
    scored = []
    for line_number, attempt in enumerate(attempts, 1):
        query_id = attempt["query_id"]
        if type(query_id) is not int or not 0 <= query_id < min(data.queries.shape[0], data.ground_truth.shape[0]):
            raise ValueError(f"line {line_number}: query_id {query_id} is outside cached query rows")
        gold = data.ground_truth[query_id, :10].tolist()
        if len(set(gold)) != 10 or any(type(value) is not int or not 0 <= value < base_count for value in gold):
            raise ValueError(f"line {line_number}: official top ten neighbors must be distinct valid base IDs")
        ranked = [
            str(hit["id"]) if type(hit["id"]) is int and 0 <= hit["id"] < base_count
            else f"__invalid_ann_slot__{rank}"
            for rank, hit in enumerate(attempt["hits"], 1)
        ]
        scored.append({
            **attempt,
            "recall_at_10": recall_at_k({str(value) for value in gold}, 10, ranked),
            "quality": compute_ann_result_quality(attempt["hits"], base_count=base_count, top_k=10),
        })
    return scored


def write_reports(attempts: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    """Save evaluated attempts and the aggregate summary without overwriting"""
    from dingo.retrieval.eval_utils import summarize_ann_metrics

    summary = {
        "dataset": attempts[0]["dataset"],
        "backend": attempts[0]["backend"],
        "top_k": 10,
        "metrics": summarize_ann_metrics(attempts),
        "units": {"rate_unit": "fraction", "recall_unit": "fraction", "latency_unit": "ms"},
        "populations": {"latency_population": "ok_and_empty", "has_results_denominator": "successful_attempts"},
    }
    per_query = output_dir / "per_query.jsonl"
    summary_path = output_dir / "summary.json"
    for path in (per_query, summary_path):
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Output file already exists: {path}")
    rows = [json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in attempts]
    summary_text = json.dumps(summary, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    output_dir.mkdir(parents=True, exist_ok=True)
    with (
        per_query.open("x", encoding="utf-8") as query_output,
        summary_path.open("x", encoding="utf-8") as summary_output,
    ):
        query_output.writelines(rows)
        summary_output.write(summary_text)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Saved query-attempt JSONL")
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output-dir", type=Path, required=True)
    options = parser.parse_args()
    for filename in ("per_query.jsonl", "summary.json"):
        path = options.output_dir / filename
        if path.exists() or path.is_symlink():
            parser.error(f"Output file already exists: {path}")
    try:
        attempts = read_attempts(options.input)
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        from dingo.config import InputArgs
        from dingo.data import dataset_map, datasource_map

        args = InputArgs(
            input_path=DATASET_NAME,
            dataset={
                "source": "ann_benchmarks", "format": "ann_benchmarks",
                "ann_benchmarks_config": {"cache_dir": options.cache_dir},
            },
        )
        source = datasource_map["ann_benchmarks"](input_args=args)
        if not source.path.is_file():
            raise FileNotFoundError(f"ANN cache is missing: {source.path}")
        with dataset_map["ann_benchmarks"](source=source) as dataset:
            scored = score_attempts(attempts, next(dataset.get_data()))
        write_reports(scored, options.output_dir)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Evaluated {len(scored)} query attempts")


if __name__ == "__main__":
    main()
