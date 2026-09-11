"""Utilities for search result JSONL evaluation examples."""

from __future__ import annotations
import argparse
import csv
import json
import math
import statistics
from pathlib import Path
from typing import Any


def load_query_result_jsonl(path: Path, max_queries: int | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            item = json.loads(line)
            query = item.get("query") or item.get("query_text") or item.get("q") or ""
            results = (
                item.get("results")
                or item.get("top_results")
                or item.get("top_api_results")
                or item.get("search_results")
                or item.get("hits")
                or (item.get("response") or {}).get("hits")
                or []
            )
            if isinstance(results, dict):
                results = results.get("results") or results.get("items") or []
            if not isinstance(results, list):
                raise ValueError(f"Line {line_no}: results must be a list.")
            if not query:
                raise ValueError(f"Line {line_no}: missing query/query_text.")
            items.append({**item, "query": str(query), "results": results})
            if max_queries and len(items) >= max_queries:
                break
    return items


def load_queries(path: Path, max_queries: int | None = None) -> list[str]:
    """Load unique queries from TXT, CSV, JSON, or JSONL input."""
    suffix = path.suffix.lower()
    queries: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        query = str(value or "").strip()
        if query and query not in seen:
            seen.add(query)
            queries.append(query)

    if suffix == ".txt":
        with path.open("r", encoding="utf-8-sig") as f:
            for line in f:
                add(line)
                if max_queries and len(queries) >= max_queries:
                    break
        return queries

    if suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                add(row.get("query") or row.get("query_text") or row.get("q"))
                if max_queries and len(queries) >= max_queries:
                    break
        return queries

    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = payload if isinstance(payload, list) else payload.get("queries", [])
        for row in rows:
            if isinstance(row, str):
                add(row)
            elif isinstance(row, dict):
                add(row.get("query") or row.get("query_text") or row.get("q"))
            if max_queries and len(queries) >= max_queries:
                break
        return queries

    with path.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if isinstance(row, str):
                add(row)
            elif isinstance(row, dict):
                add(row.get("query") or row.get("query_text") or row.get("q"))
            else:
                raise ValueError(f"Line {line_no}: query row must be a string or object.")
            if max_queries and len(queries) >= max_queries:
                break
    return queries


def get_title(result: dict[str, Any]) -> str:
    return str(result.get("title") or result.get("display_name") or "")


def rank_discounted_mean(values: list[float | None]) -> float | None:
    """Return a query-level weighted mean that gives higher ranks more weight."""
    if not values:
        return 0.0
    weights = [1.0 / math.log2(rank + 2) for rank in range(len(values))]
    valid = [(value, weight) for value, weight in zip(values, weights) if value is not None]
    if not valid:
        return None
    return sum(value * weight for value, weight in valid) / sum(weight for _, weight in valid)


def summarize(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}
    return {
        "count": len(values),
        "mean": round(statistics.mean(values), 5),
        "median": round(statistics.median(values), 5),
        "min": round(min(values), 5),
        "max": round(max(values), 5),
    }


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--input-jsonl",
        "--input-queries",
        dest="input_jsonl",
        type=Path,
        required=True,
        help="Precomputed query-result JSONL, or a TXT/CSV/JSON/JSONL query file in live retrieval mode.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/search_result_eval"))
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument("--save-good", action="store_true", help="Save good classified records under good/.")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_classified_jsonl(
    output_dir: Path,
    records: list[dict[str, Any]],
    *,
    save_good: bool = False,
    level: str | None = None,
) -> None:
    for record in records:
        status = "bad" if record.get("eval_status") else "good"
        if status == "good" and not save_good:
            continue
        labels = record.get("labels") or []
        if not labels:
            labels = ["QUALITY_GOOD.PASS"] if status == "good" else ["QUALITY_BAD.UNKNOWN"]
        for label in labels:
            parts = str(label).split(".")
            status_dir = output_dir / status
            if level:
                status_dir = status_dir / level
            if len(parts) > 1:
                path = status_dir / Path(*parts[:-1]) / f"{parts[-1]}.jsonl"
            else:
                path = status_dir / f"{parts[0]}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
