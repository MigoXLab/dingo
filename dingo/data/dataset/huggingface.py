import json
from typing import Any, Dict, Generator, Mapping, Optional, Sequence, Union

import datasets

from dingo.data.dataset.base import Dataset
from dingo.data.datasource import DataSource
from dingo.data.datasource.huggingface import HuggingFaceSource
from dingo.data.utils.digit import compute_pandas_digest
from dingo.io import Data

_MAX_ROWS_FOR_DIGEST_COMPUTATION_AND_SCHEMA_INFERENCE = 10000


@Dataset.register()
class HuggingFaceDataset(Dataset):
    """
    Represents a HuggingFace dataset for use with Dingo Tracking.
    """

    def __init__(
        self,
        source: HuggingFaceSource,
        name: Optional[str] = None,
        digest: Optional[str] = None,
    ):
        """
        Args:
            source: The source of the Hugging Face dataset.
            name: The name of the dataset. E.g. "wiki_train". If unspecified, a name is
                automatically generated.
            digest: The digest (hash, fingerprint) of the dataset. If unspecified, a digest
                is automatically computed.
        """
        self._ds: datasets.Dataset = source.load()
        self._targets = "text"
        if source.input_args.dataset.format == "plaintext":
            # if source.input_args.dataset.fields != []:
            #     self._targets = source.input_args.dataset.fields[0]
            if self._targets is not None and self._targets not in self._ds.column_names:
                raise RuntimeError(
                    f"The specified Hugging Face dataset does not contain the specified targets column"
                    f" '{self._targets}'.",
                )

        super().__init__(source=source, name=name, digest=digest)

    @staticmethod
    def get_dataset_type() -> str:
        return "hugging_face"

    def _compute_digest(self) -> str:
        """
        Computes a digest for the dataset. Called if the user doesn't supply
        a digest when constructing the dataset.
        """
        df = next(
            self._ds.to_pandas(
                batch_size=_MAX_ROWS_FOR_DIGEST_COMPUTATION_AND_SCHEMA_INFERENCE,
                batched=True,
            )
        )
        return compute_pandas_digest(df)

    def to_dict(self) -> Dict[str, str]:
        """Create config dictionary for the dataset.
        Returns a string dictionary containing the following fields: name, digest, source, source
        type, schema, and profile.
        """
        config = super().to_dict()
        config.update(
            {
                "profile": json.dumps(self.profile),
            }
        )
        return config

    def get_data(self) -> Generator[Data, None, None]:
        """
        Returns the input model for the dataset.
        Convert data here.
        """
        for data_raw in self._ds:
            if self._converter == "plaintext":
                data_raw = data_raw[self._targets]
            data: Union[Generator[Data], Data] = self.converter(data_raw)
            if isinstance(data, Generator):
                for d in data:
                    yield d
            else:
                yield data

    @property
    def ds(self) -> datasets.Dataset:
        """The Hugging Face ``datasets.Dataset`` instance.
        Returns:
            The Hugging Face ``datasets.Dataset`` instance.
        """
        return self._ds

    @property
    def targets(self) -> Optional[str]:
        """
        The name of the Hugging Face dataset column containing targets (labels) for supervised
        learning.
        Returns:
            The string name of the Hugging Face dataset column containing targets.
        """
        return self._targets

    @property
    def source(self) -> DataSource:
        """Hugging Face dataset source information.
        Returns:
            A :py:class:`mlflow.data.huggingface_dataset_source.HuggingFaceSource`
        """
        return self._source

    @property
    def profile(self) -> Optional[Any]:
        """
        Summary statistics for the Hugging Face dataset, including the number of rows,
        size, and size in bytes.
        """
        return {
            "num_rows": self._ds.num_rows,
            "dataset_size": self._ds.dataset_size,
            "size_in_bytes": self._ds.size_in_bytes,
        }


def from_huggingface(
    path: Optional[str] = None,
    split: str = "train",
    targets: Optional[str] = None,
    data_dir: Optional[str] = None,
    data_files: Optional[
        Union[str, Sequence[str], Mapping[str, Union[str, Sequence[str]]]]
    ] = None,
    revision=None,
    name: Optional[str] = None,
    digest: Optional[str] = None,
    trust_remote_code: Optional[bool] = None,
) -> HuggingFaceDataset:
    """
    Create a `dingo.data.dataset.huggingface.HuggingFaceDataset` from a Hugging Face dataset.
    Args:

        path: The path of the Hugging Face dataset used to construct the source. This is the same
            argument as `path` in `datasets.load_dataset()` function. To be able to reload the
            dataset via Dingo, `path` must match the path of the dataset on the hub, e.g.,
            "databricks/databricks-dolly-15k". If no path is specified, a `CodeDatasetSource` is,
            used which will source information from the run context.
        split: The name of the dataset split.
        targets: The name of the Hugging Face `dataset.Dataset` column containing targets (labels)
            for supervised learning.
        data_dir: The `data_dir` of the Hugging Face dataset configuration. This is used by the
            `datasets.load_dataset()` function to reload the dataset upon request via
            :py:func:`HuggingFaceDataset.source.load()
            <mlflow.data.huggingface_dataset_source.HuggingFaceSource.load>`.
        data_files: Paths to source data file(s) for the Hugging Face dataset configuration.
            This is used by the `datasets.load_dataset()` function to reload the
            dataset upon request via :py:func:`HuggingFaceDataset.source.load()
            <mlflow.data.huggingface_dataset_source.HuggingFaceSource.load>`.
        revision: Version of the dataset script to load. This is used by the
            `datasets.load_dataset()` function to reload the dataset upon request via
            :py:func:`HuggingFaceDataset.source.load()
            <mlflow.data.huggingface_dataset_source.HuggingFaceSource.load>`.
        name: The name of the dataset. E.g. "wiki_train". If unspecified, a name is automatically
            generated.
        digest: The digest (hash, fingerprint) of the dataset. If unspecified, a digest is
            automatically computed.
        trust_remote_code: Whether to trust remote code from the dataset repo.
    """
    if path is not None:
        source = HuggingFaceSource(
            path=path,
            data_dir=data_dir,
            data_files=data_files,
            split=split,
            revision=revision,
            trust_remote_code=trust_remote_code,
        )
    else:
        raise RuntimeError("You must specify a path to Hugging Face dataset.")
    return HuggingFaceDataset(targets=targets, source=source, name=name, digest=digest)
