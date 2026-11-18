"""Share HDF5 input and field mapping across the benchmark examples"""

from __future__ import annotations
import os
from argparse import ArgumentParser, Namespace
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from h5py import File

    from dingo.io import Data


def add_hdf5_arguments(parser: ArgumentParser) -> None:
    parser.add_argument("--source", choices=("local", "s3"), default="local")
    parser.add_argument("--input-path", required=True, help="Existing local HDF5 file or s3://bucket/key")


@contextmanager
def open_hdf5(options: Namespace) -> Iterator[File]:
    from dingo.config import InputArgs
    from dingo.data import dataset_map, datasource_map

    input_path = options.input_path
    config: dict[str, str | dict[str, str]] = {"source": options.source, "format": "hdf5"}
    if options.source == "local":
        path = Path(input_path).expanduser()
        if not path.is_file():
            raise ValueError(f"HDF5 input is not a file: {path}")
        input_path = str(path)
    else:
        s3_config = {
            "s3_ak": os.environ.get("S3_ACCESS_KEY", ""),
            "s3_sk": os.environ.get("S3_SECRET_KEY", ""),
            "s3_endpoint_url": os.environ.get("S3_ENDPOINT_URL", ""),
        }
        if not all(s3_config.values()):
            raise ValueError("S3 input requires S3_ACCESS_KEY, S3_SECRET_KEY, and S3_ENDPOINT_URL")
        config["s3_config"] = s3_config
    args = InputArgs(input_path=input_path, dataset=config)
    source = datasource_map[options.source](input_args=args)
    dataset = dataset_map[options.source](source=source)
    with closing(dataset.get_data()) as records:
        try:
            data = next(records)
        except OSError as exc:
            raise ValueError(f"Could not open HDF5 input: {input_path}") from exc
        yield data.hdf5


@contextmanager
def open_import_data(options: Namespace) -> Iterator[Data]:
    from dingo.io import Data

    with open_hdf5(options) as hdf5:
        vectors = hdf5.get(options.vector_key)
        if getattr(vectors, "ndim", None) != 2 or not all(vectors.shape) or vectors.dtype.kind not in "fiu":
            raise ValueError(f"Expected a nonempty two-dimensional numeric array at {options.vector_key!r}")
        yield Data(
            base=vectors,
            metadata={
                "name": Path(options.input_path).stem,
                "dimension": vectors.shape[1],
            },
        )


@contextmanager
def open_ann_data(options: Namespace, name: str = "sift-128-euclidean") -> Iterator[Data]:
    with open_hdf5(options) as hdf5:
        yield read_ann_fields(hdf5, name, options.input_path)


def read_ann_fields(raw: File, name: str, path: str) -> Data:
    from dingo.io import Data

    fields = ("train", "test", "neighbors", "distances")
    missing = [key for key in fields if key not in raw]
    if missing:
        raise ValueError(f"Missing ANN-Benchmarks fields: {missing}")
    base, queries, neighbors, distances = (raw[key] for key in fields)
    if any(getattr(array, "ndim", None) != 2 for array in (base, queries, neighbors, distances)):
        raise ValueError("ANN-Benchmarks fields must be two-dimensional arrays")
    if not all(base.shape) or not all(queries.shape) or not all(neighbors.shape):
        raise ValueError("ANN-Benchmarks arrays must be nonempty")
    if base.shape[1] != queries.shape[1]:
        raise ValueError("Base and query dimensions differ")
    if neighbors.shape[0] != queries.shape[0] or distances.shape != neighbors.shape:
        raise ValueError("Query and ground-truth shapes differ")
    if base.dtype.kind not in "fiu" or queries.dtype.kind not in "fiu":
        raise ValueError("Vectors must have numeric dtypes")
    if neighbors.dtype.kind not in "iu" or distances.dtype.kind not in "fiu":
        raise ValueError("Ground truth requires integer IDs and numeric distances")
    dimension = int(raw.attrs.get("dimension", base.shape[1]))
    metric = raw.attrs.get("distance", "")
    if isinstance(metric, bytes):
        metric = metric.decode("utf-8")
    if dimension != base.shape[1] or metric != "euclidean":
        raise ValueError("Expected matching dimension and euclidean distance")
    # 分批检查近邻 ID，行号对应 base 中的向量
    for start in range(0, len(neighbors), 1024):
        batch = neighbors[start:start + 1024]
        if batch.min() < 0 or batch.max() >= len(base):
            raise ValueError("Neighbor IDs are outside the base array")
    return Data(
        base=base, queries=queries, ground_truth=neighbors, distances=distances,
        metadata={"name": name, "dimension": dimension, "distance": metric, "path": path},
    )
