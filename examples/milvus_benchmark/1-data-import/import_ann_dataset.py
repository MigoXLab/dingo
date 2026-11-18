"""Preview HDF5 vector batches or write them to an existing Milvus collection"""

from __future__ import annotations
import argparse
import os
import sys
from collections.abc import Iterator, Sequence
from importlib import import_module
from math import isfinite
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymilvus import MilvusClient

    from dingo.config.input_args import RetrievalArgs
    from dingo.io import Data
    from dingo.retrieval.import_client import ImportRecord


def iter_import_batches(
    data: Data, start_row: int, count: int, batch_size: int,
) -> Iterator[Sequence[ImportRecord]]:
    """Yield batches of base vectors while the ANN dataset context is open"""
    from dingo.retrieval.import_client import ImportRecord

    if start_row < 0:
        raise ValueError("Start row must be nonnegative")
    if count <= 0 or batch_size <= 0:
        raise ValueError("Count and batch size must be positive")

    base = data.base
    end_row = start_row + count
    if end_row > len(base):
        raise ValueError(
            f"Requested rows [{start_row}, {end_row}) exceed the {len(base)} base rows"
        )
    if base.ndim != 2 or base.shape[1] <= 0 or data.metadata.get("dimension") != base.shape[1]:
        raise ValueError("Dimension metadata must match the base vector width")

    for batch_start in range(start_row, end_row, batch_size):
        batch_end = min(batch_start + batch_size, end_row)
        rows = base[batch_start:batch_end].astype(float, copy=False).tolist()
        yield [
            ImportRecord(source_id=row_id, vector=row)
            for row_id, row in enumerate(rows, batch_start)
        ]


def positive_timeout(value: str) -> float:
    """Parse a positive finite timeout in seconds"""
    try:
        timeout = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Timeout must be a positive finite number") from None
    if not isfinite(timeout) or timeout <= 0:
        raise argparse.ArgumentTypeError("Timeout must be a positive finite number")
    return timeout


def create_milvus_client(options: argparse.Namespace, retrieval: RetrievalArgs) -> MilvusClient:
    """Create the optional SDK client for an explicit write"""
    try:
        from pymilvus import MilvusClient
    except ImportError:
        raise SystemExit("Milvus writes require pymilvus; install it with: pip install pymilvus") from None
    return MilvusClient(
        uri=retrieval.api_url, db_name=options.milvus_db_name,
        token=os.environ.get("MILVUS_TOKEN", ""), timeout=retrieval.timeout,
    )


def build_parser() -> argparse.ArgumentParser:
    hdf5_input = import_module("examples.milvus_benchmark.0-data-loading.hdf5_input")

    parser = argparse.ArgumentParser(description=__doc__)
    hdf5_input.add_hdf5_arguments(parser)
    parser.add_argument("--vector-key", default="train", help="HDF5 array containing the vectors")
    parser.add_argument("--start-row", type=int, default=0, help="Zero-based starting base row (default: 0)")
    parser.add_argument("--count", type=int, default=5, help="Number of base rows to process (default: 5)")
    parser.add_argument("--batch-size", type=int, default=2, help="Maximum rows per batch (default: 2)")
    parser.add_argument("--write-milvus", action="store_true", help="Write batches to an existing collection")
    parser.add_argument("--milvus-uri", help="Milvus URI (required for writes)")
    parser.add_argument("--milvus-db-name", help="Existing Milvus database (required for writes)")
    parser.add_argument("--milvus-collection", help="Existing Milvus collection (required for writes)")
    parser.add_argument("--milvus-id-field", default="id")
    parser.add_argument("--milvus-vector-field", default="vector")
    parser.add_argument("--timeout", type=positive_timeout, default=30.0, help="SDK timeout in seconds (default: 30)")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    # 直接运行脚本时使用当前开发仓库
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    hdf5_input = import_module("examples.milvus_benchmark.0-data-loading.hdf5_input")

    parser = build_parser()
    options = parser.parse_args(argv)
    if options.write_milvus and not all((options.milvus_uri, options.milvus_db_name, options.milvus_collection)):
        parser.error("Writes require --milvus-uri, --milvus-db-name, and --milvus-collection")
    if options.start_row < 0:
        parser.error("Start row must be nonnegative")
    if options.count <= 0 or options.batch_size <= 0:
        parser.error("Count and batch size must be positive")

    print(f"Input: {options.input_path}", flush=True)
    total_records = total_batches = 0
    sdk_client = None
    try:
        input_args = hdf5_input.build_input_args(
            options, retrieval={"backend": "milvus", "api_url": options.milvus_uri or "", "timeout": options.timeout},
        )
        retrieval = input_args.executor.retrieval
        assert retrieval is not None
        with hdf5_input.open_vector_data(input_args, key=options.vector_key, field="base") as data:
            for index, batch in enumerate(iter_import_batches(
                data, options.start_row, options.count, options.batch_size,
            ), 1):
                if options.write_milvus and sdk_client is None:
                    from dingo.retrieval.backends.importers.milvus import MilvusImportClient

                    sdk_client = create_milvus_client(options, retrieval)
                    importer = MilvusImportClient(
                        sdk_client, collection_name=options.milvus_collection,
                        id_field=options.milvus_id_field, vector_field=options.milvus_vector_field,
                        timeout=retrieval.timeout,
                    )
                if options.write_milvus:
                    result = importer.write_batch(batch)
                    print(
                        f"Batch {index}: submitted={result.submitted}, accepted={result.accepted}, "
                        f"rejected={result.rejected}, unknown={result.unknown}", flush=True,
                    )
                    if result.accepted != result.submitted or result.error:
                        raise SystemExit("Milvus batch was not fully acknowledged; stopped without retrying")
                else:
                    first_id = batch[0].source_id
                    last_id = batch[-1].source_id
                    print(
                        f"Batch {index}: size={len(batch)}, source_ids={first_id}..{last_id}, "
                        f"dimension={len(batch[0].vector)}, first_vector_sample={batch[0].vector[:5]}"
                    )
                total_records += len(batch)
                total_batches += 1
    except ValueError as exc:
        parser.error(str(exc))
    finally:
        if sdk_client is not None:
            sdk_client.close()

    print(f"Total: records={total_records}, batches={total_batches}")


if __name__ == "__main__":
    main()
