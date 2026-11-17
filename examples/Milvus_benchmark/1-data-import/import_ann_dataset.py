"""Preview ANN-Benchmarks base-vector import batches"""

from __future__ import annotations
import argparse
import sys
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dingo.io import Data
    from dingo.retrieval.import_client import ImportRecord

DATASET_NAME = "sift-128-euclidean"
DEFAULT_CACHE_DIR = "~/.cache/dingo/ann_benchmarks"


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", nargs="?", default=DATASET_NAME, choices=[DATASET_NAME])
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR,
                        help="HDF5 cache directory (default: %(default)s)")
    parser.add_argument("--start-row", type=int, default=0, help="Zero-based starting base row (default: 0)")
    parser.add_argument("--count", type=int, default=5, help="Number of base rows to preview (default: 5)")
    parser.add_argument("--batch-size", type=int, default=2, help="Maximum rows per batch (default: 2)")
    options = parser.parse_args()
    if options.start_row < 0:
        parser.error("Start row must be nonnegative")
    if options.count <= 0 or options.batch_size <= 0:
        parser.error("Count and batch size must be positive")

    # 直接运行脚本时使用当前开发仓库
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from dingo.config import InputArgs
    from dingo.data import dataset_map, datasource_map

    args = InputArgs(
        input_path=options.dataset,
        dataset={
            "source": "ann_benchmarks", "format": "ann_benchmarks",
            "ann_benchmarks_config": {"cache_dir": options.cache_dir},
        },
    )
    source = datasource_map["ann_benchmarks"](input_args=args)
    print(f"Dataset: {options.dataset}", flush=True)
    print(f"Cache: {options.cache_dir}", flush=True)
    total_records = total_batches = 0
    with dataset_map["ann_benchmarks"](source=source) as dataset:
        data = next(dataset.get_data())
        try:
            for index, batch in enumerate(iter_import_batches(
                data, options.start_row, options.count, options.batch_size,
            ), 1):
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
    print(f"Total: records={total_records}, batches={total_batches}")


if __name__ == "__main__":
    main()
