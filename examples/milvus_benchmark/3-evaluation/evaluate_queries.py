"""Evaluate saved vector query attempts with selected metrics"""

from __future__ import annotations
import argparse
import json
import sys
from collections.abc import Collection
from importlib import import_module
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dingo.config import InputArgs
    from dingo.io import Data

# TODO: Move evaluation orchestration into a reusable module
# TODO: Add QPS when query logs include the full run window
ATTEMPT_FIELDS = {"dataset", "query_id", "backend", "top_k", "hits", "elapsed_ms", "status", "error"}
DATA_METRIC_GROUPS = {"recall", "result_quality"}


def read_attempts(path: Path, *, top_k: int | None = None, dataset_id: str | None = None) -> list[dict[str, Any]]:
    """Read query attempts with line-specific validation errors"""
    attempts = []
    backend = None
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, 1):
            try:
                row = json.loads(line)
                if not isinstance(row, dict) or set(row) != ATTEMPT_FIELDS:
                    raise ValueError("Expected the current query-attempt fields")
                if not isinstance(row["dataset"], str) or not row["dataset"].strip():
                    raise ValueError("Dataset ID must be nonempty")
                if dataset_id is not None and row["dataset"] != dataset_id:
                    raise ValueError(f"Dataset ID must match {dataset_id!r}")
                if type(row["query_id"]) is not int or row["query_id"] < 0:
                    raise ValueError("query_id must be a nonnegative native integer")
                if not isinstance(row["backend"], str) or not row["backend"].strip():
                    raise ValueError("backend must be a nonempty string")
                if backend is not None and row["backend"] != backend:
                    raise ValueError("All attempts must use the same backend")
                if type(row["top_k"]) is not int or row["top_k"] <= 0:
                    raise ValueError("top_k must be a positive integer")
                if top_k is not None and row["top_k"] != top_k:
                    raise ValueError(f"top_k must match {top_k}")
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
            dataset_id = row["dataset"]
            top_k = row["top_k"]
            attempts.append(row)
    if not attempts:
        raise ValueError(f"{path}: no query attempts")
    return attempts


def score_attempts(
    attempts: list[dict[str, Any]], data: Data | None = None, *, metrics: Collection[str] | None = None,
) -> list[dict[str, Any]]:
    """Score the selected metrics using the original hit positions"""
    from dingo.retrieval.eval_utils import ANN_METRIC_GROUPS, compute_ann_result_quality, recall_at_k

    if not attempts:
        return []
    selected = ANN_METRIC_GROUPS if metrics is None else metrics
    if not DATA_METRIC_GROUPS.intersection(selected):
        return attempts
    if data is None:
        raise ValueError("Recall and result quality require an HDF5 input")
    if data.metadata.get("name") != attempts[0]["dataset"]:
        raise ValueError("HDF5 dataset ID must match the query log")
    base_count = data.base.shape[0]
    top_k = attempts[0]["top_k"]
    truth = getattr(data, "ground_truth", None)
    if "recall" in selected and (truth is None or truth.ndim != 2 or truth.shape[1] < top_k):
        raise ValueError(f"Ground truth must contain at least {top_k} neighbors per query")
    scored = []
    for line_number, attempt in enumerate(attempts, 1):
        row = dict(attempt)
        if "recall" in selected:
            query_id = attempt["query_id"]
            if type(query_id) is not int or not 0 <= query_id < len(truth):
                raise ValueError(f"line {line_number}: query_id {query_id} is outside ground-truth rows")
            gold = truth[query_id, :top_k].tolist()
            if len(set(gold)) != top_k or any(type(value) is not int or not 0 <= value < base_count for value in gold):
                raise ValueError(f"line {line_number}: top-{top_k} neighbors must be distinct valid base IDs")
            ranked = [
                str(hit["id"]) if type(hit["id"]) is int and 0 <= hit["id"] < base_count
                else f"__invalid_ann_slot__{rank}"
                for rank, hit in enumerate(attempt["hits"], 1)
            ]
            row[f"recall_at_{top_k}"] = recall_at_k({str(value) for value in gold}, top_k, ranked)
        if "result_quality" in selected:
            row["quality"] = compute_ann_result_quality(attempt["hits"], base_count=base_count, top_k=top_k)
        scored.append(row)
    return scored


def evaluate_attempts(
    attempts: list[dict[str, Any]], *, input_args: InputArgs | None = None, metrics: Collection[str] | None = None,
    base_key: str = "train", ground_truth_key: str = "neighbors", dataset_id: str | None = None,
) -> list[dict[str, Any]]:
    from dingo.retrieval.eval_utils import ANN_METRIC_GROUPS

    selected = ANN_METRIC_GROUPS if metrics is None else metrics
    if not DATA_METRIC_GROUPS.intersection(selected):
        return score_attempts(attempts, metrics=selected)
    if input_args is None:
        raise ValueError("Recall and result quality require an HDF5 input")
    hdf5_input = import_module("examples.milvus_benchmark.0-data-loading.hdf5_input")
    with hdf5_input.open_evaluation_data(
        input_args, base_key=base_key, ground_truth_key=ground_truth_key if "recall" in selected else None,
        dataset_id=dataset_id,
    ) as data:
        return score_attempts(attempts, data, metrics=selected)


def write_reports(
    attempts: list[dict[str, Any]], output_dir: Path, *, metrics: Collection[str] | None = None,
) -> dict[str, Any]:
    """Save evaluated attempts and the aggregate summary without overwriting"""
    from dingo.retrieval.eval_utils import ANN_METRIC_GROUPS, summarize_ann_metrics

    top_k = attempts[0]["top_k"]
    selected = ANN_METRIC_GROUPS if metrics is None else metrics
    summary = {
        "dataset": attempts[0]["dataset"],
        "backend": attempts[0]["backend"],
        "top_k": top_k,
        "metrics": summarize_ann_metrics(attempts, top_k=top_k, metrics=selected),
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
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from dingo.config import InputArgs
    from dingo.retrieval.eval_utils import ANN_METRIC_GROUPS

    hdf5_input = import_module("examples.milvus_benchmark.0-data-loading.hdf5_input")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Saved query-attempt JSONL")
    hdf5_input.add_hdf5_arguments(parser, required=False)
    parser.add_argument("--dataset-id", help="Dataset label to match in the query log")
    parser.add_argument("--top-k", type=int, help="Expected top-K in the query log")
    parser.add_argument("--metrics", nargs="+", choices=ANN_METRIC_GROUPS, default=ANN_METRIC_GROUPS)
    parser.add_argument("--base-key", default="train", help="HDF5 array containing all base vectors")
    parser.add_argument("--ground-truth-key", default="neighbors", help="HDF5 array containing neighbor IDs")
    parser.add_argument("--output-dir", type=Path, required=True)
    options = parser.parse_args()
    for filename in ("per_query.jsonl", "summary.json"):
        path = options.output_dir / filename
        if path.exists() or path.is_symlink():
            parser.error(f"Output file already exists: {path}")
    try:
        dataset_id = options.dataset_id.strip() if options.dataset_id is not None else None
        attempts = read_attempts(options.input, top_k=options.top_k, dataset_id=dataset_id)
        if DATA_METRIC_GROUPS.intersection(options.metrics):
            input_args = hdf5_input.build_input_args(options, output_path=options.output_dir)
        else:
            input_args = InputArgs(
                input_path=str(options.input), output_path=str(options.output_dir),
                dataset={"source": "local", "format": "jsonl"},
            )
        scored = evaluate_attempts(
            attempts, input_args=input_args, metrics=options.metrics, base_key=options.base_key,
            ground_truth_key=options.ground_truth_key, dataset_id=dataset_id,
        )
        write_reports(scored, Path(input_args.output_path), metrics=options.metrics)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Evaluated {len(scored)} query attempts")


if __name__ == "__main__":
    main()
