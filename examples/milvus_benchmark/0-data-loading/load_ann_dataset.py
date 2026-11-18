"""Preview selected arrays in local or S3 HDF5 files"""

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
    parser.add_argument("--keys", nargs="+", default=["train", "test", "neighbors", "distances"])
    options = parser.parse_args()
    try:
        with hdf5_input.open_hdf5_records(hdf5_input.build_input_args(options)) as records:
            for index, record in enumerate(records, 1):
                print(f"File {index}")
                for key in options.keys:
                    array = hdf5_input.read_matrix(record.hdf5, key)
                    print(f"{key}: shape={array.shape}, dtype={array.dtype}")
                    print(f"First row (first 10 values): {array[0, :10].tolist()}")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
