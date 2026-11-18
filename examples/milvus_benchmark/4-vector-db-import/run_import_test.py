"""Import ANN vectors into an empty test collection and verify every stored row"""

from __future__ import annotations
import argparse
import copy
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np


def import_example() -> Any:
    """Reuse the existing batch conversion and SDK connection helpers"""
    path = Path(__file__).resolve().parents[1] / "1-data-import/import_ann_dataset.py"
    spec = importlib.util.spec_from_file_location("ann_import_example", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def count_rows(client: Any, options: argparse.Namespace) -> int:
    rows = client.query(
        collection_name=options.milvus_collection, filter="", output_fields=["count(*)"],
        consistency_level="Strong", timeout=options.timeout,
    )
    if len(rows) != 1 or type(rows[0].get("count(*)")) is not int:
        raise ValueError("Invalid collection count response")
    return rows[0]["count(*)"]


def validate_collection(client: Any, options: argparse.Namespace, dimension: int) -> None:
    from pymilvus import DataType

    description = client.describe_collection(collection_name=options.milvus_collection, timeout=options.timeout)
    fields = {field["name"]: field for field in description["fields"]}
    primary = fields.get(options.milvus_id_field, {})
    vector = fields.get(options.milvus_vector_field, {})
    if description.get("auto_id") or not primary.get("is_primary") or primary.get("type") != DataType.INT64:
        raise ValueError("The collection requires an explicit INT64 primary key")
    if vector.get("type") != DataType.FLOAT_VECTOR or int(vector.get("params", {}).get("dim", 0)) != dimension:
        raise ValueError("The collection vector type and dimension must match the dataset")
    if count_rows(client, options) != 0:
        raise ValueError("The import check requires an empty collection")


def verify_rows(client: Any, data: Any, options: argparse.Namespace, example: Any) -> int:
    """Compare returned IDs and float32 vectors with the source batches"""
    verified = 0
    for batch in example.iter_import_batches(data, options.start_row, options.count, options.batch_size):
        ids = [record.source_id for record in batch]
        rows = client.query(
            collection_name=options.milvus_collection, ids=ids,
            output_fields=[options.milvus_id_field, options.milvus_vector_field],
            consistency_level="Strong", timeout=options.timeout,
        )
        by_id = {row[options.milvus_id_field]: row for row in rows}
        if len(rows) != len(ids) or set(by_id) != set(ids):
            raise ValueError("Readback IDs differ from the submitted source IDs")
        expected = np.asarray([record.vector for record in batch], dtype=np.float32)
        actual = np.asarray([by_id[row_id][options.milvus_vector_field] for row_id in ids], dtype=np.float32)
        if not np.array_equal(actual, expected):
            raise ValueError("Readback vectors differ from the source float32 vectors")
        verified += len(ids)
    return verified


def run_check(client: Any, baseline_client: Any, data: Any, options: argparse.Namespace, example: Any) -> dict:
    """Write through the adapter, verify stored rows, and retain an experiment report"""
    from dingo.retrieval.backends.importers.milvus import MilvusImportClient

    if options.milvus_db_name == "default":
        raise ValueError("Use a dedicated non-default database for the import check")
    # Validate the complete range before any write or output creation
    next(example.iter_import_batches(data, options.start_row, options.count, options.batch_size))
    importer = MilvusImportClient(
        client, collection_name=options.milvus_collection, id_field=options.milvus_id_field,
        vector_field=options.milvus_vector_field, timeout=options.timeout,
    )
    validate_collection(client, options, data.metadata["dimension"])
    before = sorted(baseline_client.list_collections(timeout=options.timeout))
    server_version = client.get_server_version(timeout=options.timeout)
    options.output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "experiment": "vector_import_check", "status": "failed",
        "started_at": datetime.now().astimezone().isoformat(),
        "dataset": data.metadata["name"], "dimension": data.metadata["dimension"],
        "server_version": server_version,
        "sdk_version": getattr(sys.modules.get("pymilvus"), "__version__", None),
        "initial_count": 0, "timing_unit": "ms", "timing_scope": "adapter_writes_and_readback",
        "uri": options.milvus_uri, "database": options.milvus_db_name, "collection": options.milvus_collection,
        "id_field": options.milvus_id_field, "vector_field": options.milvus_vector_field,
        "start_row": options.start_row, "requested_count": options.count, "batch_size": options.batch_size,
        "input_path": options.input_path, "timeout_seconds": options.timeout,
        "submitted": 0, "accepted": 0, "rejected": 0, "unknown": 0,
        "batch_count": 0, "verified_count": 0, "final_count": None,
        "adapter_write_ms": 0.0, "readback_ms": None,
        "default_collections_before": before, "default_collections_after": None,
        "default_collection_names_unchanged": None, "vector_comparison": "float32_exact", "error": None,
    }
    started = perf_counter()
    try:
        with (options.output_dir / "batches.jsonl").open("x", encoding="utf-8") as output:
            for index, batch in enumerate(example.iter_import_batches(
                data, options.start_row, options.count, options.batch_size,
            ), 1):
                tick = perf_counter()
                receipt = importer.write_batch(batch)
                elapsed = (perf_counter() - tick) * 1000
                row = {
                    "batch": index, "first_id": batch[0].source_id, "last_id": batch[-1].source_id,
                    "submitted": receipt.submitted, "accepted": receipt.accepted,
                    "rejected": receipt.rejected, "unknown": receipt.unknown,
                    "elapsed_ms": elapsed, "error": receipt.error,
                }
                output.write(json.dumps(row, allow_nan=False) + "\n")
                output.flush()
                for key in ("submitted", "accepted", "rejected", "unknown"):
                    report[key] += row[key]
                report["batch_count"] += 1
                report["adapter_write_ms"] += elapsed
                print(f"Batch {index}: accepted={receipt.accepted}/{receipt.submitted}, elapsed_ms={elapsed:.3f}",
                      flush=True)
                if receipt.accepted != receipt.submitted or receipt.error:
                    raise RuntimeError(receipt.error or "The batch was not fully acknowledged")
        tick = perf_counter()
        report["final_count"] = count_rows(client, options)
        if report["final_count"] != options.count:
            raise ValueError("Collection count differs from the requested import count")
        report["verified_count"] = verify_rows(client, data, options, example)
        report["readback_ms"] = (perf_counter() - tick) * 1000
        report["status"] = "passed"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        try:
            after = sorted(baseline_client.list_collections(timeout=options.timeout))
            report["default_collections_after"] = after
            report["default_collection_names_unchanged"] = before == after
            if before != after:
                report["status"] = "failed"
                report["error"] = report["error"] or "Default collection names changed during the check"
        except Exception as exc:
            report["status"] = "failed"
            report["error"] = report["error"] or f"Default verification failed: {exc}"
        report["elapsed_ms"] = (perf_counter() - started) * 1000
        (options.output_dir / "summary.json").write_text(
            json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8",
        )
    return report


def main(argv: list[str] | None = None) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    hdf5_input = importlib.import_module("examples.milvus_benchmark.0-data-loading.hdf5_input")

    example = import_example()
    parser = example.build_parser()
    parser.description = __doc__
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for this experiment")
    options = parser.parse_args(argv)
    if not options.write_milvus:
        parser.error("This check writes vectors; supply --write-milvus explicitly")
    if not all((options.milvus_uri, options.milvus_db_name, options.milvus_collection)):
        parser.error("Supply the Milvus URI, database, and collection")
    if options.milvus_db_name == "default":
        parser.error("Use a dedicated non-default database for the import check")
    if options.start_row < 0 or options.count <= 0 or options.batch_size <= 0:
        parser.error("Start row must be nonnegative; count and batch size must be positive")
    if options.output_dir.exists() or options.output_dir.is_symlink():
        parser.error("The experiment output directory must not already exist")
    client = baseline_client = None
    try:
        with hdf5_input.open_import_data(options) as data:
            next(example.iter_import_batches(data, options.start_row, options.count, options.batch_size))
            baseline_options = copy.copy(options)
            baseline_options.milvus_db_name = "default"
            baseline_client = example.create_milvus_client(baseline_options)
            client = example.create_milvus_client(options)
            report = run_check(client, baseline_client, data, options, example)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    finally:
        for sdk in (client, baseline_client):
            if sdk is not None:
                sdk.close()
    print(f"Import check: {report['status']}")
    print(f"Report: {options.output_dir / 'summary.json'}")
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
