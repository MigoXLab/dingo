"""Load SIFT1M from an existing local or S3 HDF5 file"""

# Schema (SIFT1M)
# base: [1000000, 128]; queries: [10000, 128]
# ground_truth: [10000, 100], zero-based base row IDs
# distances: [10000, 100]; metadata: name, dimension, distance, path

import argparse
import sys
from importlib import import_module
from pathlib import Path


def main():
    # 直接运行脚本时使用当前开发仓库
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    hdf5_input = import_module("examples.milvus_benchmark.0-data-loading.hdf5_input")

    parser = argparse.ArgumentParser(description=__doc__)
    hdf5_input.add_hdf5_arguments(parser)
    options = parser.parse_args()
    with hdf5_input.open_ann_data(options) as data:
        print(f"Metadata: {data.metadata}")
        for name in ("base", "queries", "ground_truth", "distances"):
            array = getattr(data, name)
            print(f"{name}: shape={array.shape}, dtype={array.dtype}")
            print(f"First row (first 10 values): {array[0, :10].tolist()}")


if __name__ == "__main__":
    main()
