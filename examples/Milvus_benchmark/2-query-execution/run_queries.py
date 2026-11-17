"""Run vector benchmark queries and save one JSONL record per attempt"""

from __future__ import annotations
import argparse
import json
import sys
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from collections.abc import Sequence

    from dingo.io import Data
    from dingo.retrieval.backends.milvus import VectorHit
    from dingo.retrieval.search_client import SearchClient

DATASET_NAME = "sift-128-euclidean"
DEFAULT_CACHE_DIR = "~/.cache/dingo/ann_benchmarks"


def validate_queries(data: Data, start_row: int, count: int, top_k: int) -> None:
    """Check the selected query range and vector dimensions"""
    if start_row < 0 or count <= 0 or top_k <= 0:
        raise ValueError("Start row must be nonnegative; count and top-K must be positive")
    queries = data.queries
    if queries.ndim != 2 or queries.shape[1] <= 0:
        raise ValueError("Queries must be a two-dimensional array with positive vector width")
    if data.metadata.get("dimension") != queries.shape[1]:
        raise ValueError("Dimension metadata must match the query vector width")
    if start_row + count > len(queries):
        raise ValueError(f"Requested rows [{start_row}, {start_row + count}) exceed the {len(queries)} query rows")
    if not isinstance(data.metadata.get("name"), str) or not data.metadata["name"]:
        raise ValueError("Dataset metadata must contain a name")


def write_queries(
    client: SearchClient[Sequence[float], list[VectorHit]],
    data: Data,
    *,
    start_row: int,
    count: int,
    top_k: int,
    output: TextIO,
) -> int:
    """Run selected vectors while the loaded dataset context remains open"""
    from dingo.retrieval.backends.milvus import VectorHit

    validate_queries(data, start_row, count, top_k)
    for query_id in range(start_row, start_row + count):
        vector = data.queries[query_id:query_id + 1].astype(float, copy=False).tolist()[0]
        if not all(isfinite(value) for value in vector):
            raise ValueError(f"Query row {query_id} must contain finite numeric values")
        hits = []
        error = None
        start = perf_counter()
        try:
            response = client.search(vector, limit=top_k)
        except NotImplementedError:
            raise
        except Exception as exc:
            elapsed_ms = (perf_counter() - start) * 1000
            status = "timeout" if isinstance(exc, TimeoutError) else "error"
            error = str(exc) or type(exc).__name__
        else:
            elapsed_ms = (perf_counter() - start) * 1000
            try:
                if not isinstance(response, list):
                    raise ValueError("Search response must be a list of VectorHit records")
                for rank, hit in enumerate(response, 1):
                    if not isinstance(hit, VectorHit):
                        raise ValueError("Search response contains an invalid VectorHit record")
                    if type(hit.id) not in (int, str) or (isinstance(hit.id, str) and not hit.id.strip()):
                        raise ValueError("Search response contains an invalid hit ID")
                    if type(hit.distance) not in (int, float) or not isfinite(hit.distance):
                        raise ValueError("Search response contains an invalid hit distance")
                    hits.append({"id": hit.id, "rank": rank, "distance": float(hit.distance)})
            except (ValueError, TypeError, OverflowError) as exc:
                hits = []
                status = "error"
                error = str(exc)
            else:
                status = "ok" if hits else "empty"
        record = {
            "dataset": data.metadata["name"],
            "query_id": query_id,
            "backend": client.name,
            "top_k": top_k,
            "hits": hits,
            "elapsed_ms": elapsed_ms,
            "status": status,
            "error": error,
        }
        output.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", nargs="?", default=DATASET_NAME, choices=[DATASET_NAME])
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--start-row", type=int, default=0)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True, help="Path to a new JSONL file")
    options = parser.parse_args()
    if options.start_row < 0 or options.count <= 0 or options.top_k <= 0:
        parser.error("Start row must be nonnegative; count and top-K must be positive")
    if options.output.exists():
        parser.error(f"Output file already exists: {options.output}")

    # 直接运行脚本时使用当前开发仓库
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from dingo.config import InputArgs
    from dingo.data import dataset_map, datasource_map
    from dingo.retrieval.backends.milvus import MilvusSearchClient

    args = InputArgs(
        input_path=options.dataset,
        dataset={
            "source": "ann_benchmarks", "format": "ann_benchmarks",
            "ann_benchmarks_config": {"cache_dir": options.cache_dir},
        },
    )
    source = datasource_map["ann_benchmarks"](input_args=args)
    try:
        with dataset_map["ann_benchmarks"](source=source) as dataset:
            data = next(dataset.get_data())
            validate_queries(data, options.start_row, options.count, options.top_k)
            with options.output.open("x", encoding="utf-8") as output:
                written = write_queries(
                    MilvusSearchClient(), data, start_row=options.start_row,
                    count=options.count, top_k=options.top_k, output=output,
                )
    except FileExistsError:
        parser.error(f"Output file already exists: {options.output}")
    except ValueError as exc:
        parser.error(str(exc))
    except NotImplementedError as exc:
        raise SystemExit(str(exc) or "Milvus query interface is pending") from None
    print(f"Saved {written} query records")


if __name__ == "__main__":
    main()
