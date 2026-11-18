"""Share HDF5 input and field mapping across the benchmark examples"""

from __future__ import annotations
import os
from argparse import ArgumentParser, Namespace
from collections.abc import Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from h5py import Dataset, File

    from dingo.config import InputArgs
    from dingo.io import Data


def add_hdf5_arguments(parser: ArgumentParser, *, required: bool = True) -> None:
    parser.add_argument("--source", choices=("local", "s3"), default="local")
    parser.add_argument("--input-path", required=required, help="Existing local HDF5 file or s3://bucket/key")


def build_input_args(options: Namespace) -> InputArgs:
    from dingo.config import InputArgs

    input_path = options.input_path
    if not input_path:
        raise ValueError("--input-path is required for HDF5 input")
    config: dict[str, str | dict[str, str]] = {"source": options.source, "format": "hdf5"}
    if options.source == "local":
        input_path = str(Path(input_path).expanduser())
    else:
        s3_config = {
            "s3_ak": os.environ.get("S3_ACCESS_KEY", ""),
            "s3_sk": os.environ.get("S3_SECRET_KEY", ""),
            "s3_endpoint_url": os.environ.get("S3_ENDPOINT_URL", ""),
        }
        if not all(s3_config.values()):
            raise ValueError("S3 input requires S3_ACCESS_KEY, S3_SECRET_KEY, and S3_ENDPOINT_URL")
        config["s3_config"] = s3_config
    return InputArgs(input_path=input_path, dataset=config)


@contextmanager
def open_hdf5(input_args: InputArgs) -> Iterator[File]:
    from dingo.data import dataset_map, datasource_map

    source_name = input_args.dataset.source
    if source_name not in ("local", "s3") or input_args.dataset.format != "hdf5":
        raise ValueError("HDF5 input requires format=hdf5 and a local or S3 source")
    if source_name == "local" and not Path(input_args.input_path).is_file():
        raise ValueError(f"HDF5 input is not a file: {input_args.input_path}")
    source = datasource_map[source_name](input_args=input_args)
    dataset = dataset_map[source_name](source=source)
    with closing(dataset.get_data()) as records:
        try:
            data = next(records)
        except OSError as exc:
            raise ValueError(f"Could not open HDF5 input: {input_args.input_path}") from exc
        yield data.hdf5


def read_matrix(hdf5: File, key: str) -> Dataset:
    array = hdf5.get(key)
    if getattr(array, "ndim", None) != 2 or not all(array.shape) or array.dtype.kind not in "fiu":
        raise ValueError(f"Expected a nonempty two-dimensional numeric array at {key!r}")
    return array


def dataset_name(input_args: InputArgs, dataset_id: str | None) -> str:
    name = Path(input_args.input_path).stem if dataset_id is None else dataset_id.strip()
    if not name:
        raise ValueError("Dataset ID must be nonempty")
    return name


@contextmanager
def open_vector_data(
    input_args: InputArgs, *, key: str, field: str, dataset_id: str | None = None,
) -> Iterator[Data]:
    from dingo.io import Data

    with open_hdf5(input_args) as hdf5:
        vectors = read_matrix(hdf5, key)
        yield Data(
            **{field: vectors},
            metadata={"name": dataset_name(input_args, dataset_id), "dimension": vectors.shape[1]},
        )


@contextmanager
def open_evaluation_data(
    input_args: InputArgs, *, base_key: str, ground_truth_key: str | None, dataset_id: str | None = None,
) -> Iterator[Data]:
    from dingo.io import Data

    with open_hdf5(input_args) as hdf5:
        base = read_matrix(hdf5, base_key)
        truth = read_matrix(hdf5, ground_truth_key) if ground_truth_key is not None else None
        if truth is not None and truth.dtype.kind not in "iu":
            raise ValueError("Ground truth requires integer IDs")
        yield Data(base=base, ground_truth=truth, metadata={"name": dataset_name(input_args, dataset_id)})
