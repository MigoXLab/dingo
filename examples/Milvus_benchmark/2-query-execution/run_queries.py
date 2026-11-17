"""Run vector benchmark queries and save one JSONL record per attempt"""

from __future__ import annotations
import argparse
import json
import os
import sys
from math import isfinite
from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pymilvus import MilvusClient

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


def positive_timeout(value: str) -> float:
    """Parse a positive finite timeout in seconds"""
    try:
        timeout = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Timeout must be a positive finite number") from None
    if not isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("Timeout must be a positive finite number")
    return timeout


def parse_search_params(value: str) -> dict:
    """Parse SDK search parameters as a JSON object"""
    try:
        params = json.loads(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Search parameters must be a JSON object") from None
    if not isinstance(params, dict):
        raise argparse.ArgumentTypeError("Search parameters must be a JSON object")
    return params


def create_milvus_client(options: argparse.Namespace) -> MilvusClient:
    """Create the optional SDK client for query execution"""
    try:
        from pymilvus import MilvusClient
    except ImportError:
        raise SystemExit("Milvus queries require pymilvus; install it with: pip install pymilvus") from None
    return MilvusClient(
        uri=options.milvus_uri, db_name=options.milvus_db_name,
        token=os.environ.get("MILVUS_TOKEN", ""), timeout=options.timeout,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", nargs="?", default=DATASET_NAME, choices=[DATASET_NAME])
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--start-row", type=int, default=0)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--output", type=Path, required=True, help="Path to a new JSONL file")
    parser.add_argument("--milvus-uri", required=True, help="Milvus URI")
    parser.add_argument("--milvus-db-name", required=True, help="Existing Milvus database")
    parser.add_argument("--milvus-collection", required=True, help="Existing Milvus collection")
    parser.add_argument("--milvus-id-field", default="id")
    parser.add_argument("--milvus-vector-field", default="vector")
    parser.add_argument("--timeout", type=positive_timeout, default=30.0, help="SDK timeout in seconds (default: 30)")
    parser.add_argument("--search-params", type=parse_search_params, help="SDK search parameters as a JSON object")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    options = parser.parse_args(argv)
    if options.start_row < 0 or options.count <= 0 or options.top_k <= 0:
        parser.error("Start row must be nonnegative; count and top-K must be positive")
    if options.output.exists() or options.output.is_symlink():
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
    sdk_client = None
    try:
        with dataset_map["ann_benchmarks"](source=source) as dataset:
            data = next(dataset.get_data())
            validate_queries(data, options.start_row, options.count, options.top_k)
            sdk_client = create_milvus_client(options)
            client = MilvusSearchClient(
                sdk_client, collection_name=options.milvus_collection,
                id_field=options.milvus_id_field, vector_field=options.milvus_vector_field,
                timeout=options.timeout, search_params=options.search_params,
            )
            with options.output.open("x", encoding="utf-8") as output:
                written = write_queries(
                    client, data, start_row=options.start_row,
                    count=options.count, top_k=options.top_k, output=output,
                )
    except FileExistsError:
        parser.error(f"Output file already exists: {options.output}")
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        if sdk_client is not None:
            sdk_client.close()
    print(f"Saved {written} query records")


if __name__ == "__main__":
    main()
