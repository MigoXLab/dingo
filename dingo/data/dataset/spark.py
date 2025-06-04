import json
from typing import Any, Dict, Generator, Optional, Union

from dingo.data.dataset.base import Dataset
from dingo.data.datasource import DataSource
from dingo.data.utils.digit import compute_pandas_digest
from dingo.io import Data
from dingo.utils import log


@Dataset.register()
class SparkDataset(Dataset):
    """Represents a HuggingFace dataset for use with Dingo Tracking."""

    @property
    def profile(self) -> Optional[Any]:
        return None

    def __init__(
        self,
        source: DataSource,
        name: Optional[str] = None,
        digest: Optional[str] = None,
    ):
        """
        Args:
            source: The source of the local file data source
            name: The name of the dataset. E.g. "wiki_train". If unspecified, a name is
                automatically generated.
            digest: The digest (hash, fingerprint) of the dataset. If unspecified, a digest
                is automatically computed.
        """
        self._ds = source.load()
        self._targets = 'text'
        if source.get_source_type() == 'hugging_face' and source.input_args.data_format == 'plaintext':
            if source.input_args.column_content != '':
                self._targets = source.input_args.column_content
            if self._targets is not None and self._targets not in self._ds.column_names:
                raise RuntimeError(
                    f"The specified Hugging Face dataset does not contain the specified targets column"
                    f" '{self._targets}'.",
                )
        super().__init__(source=source, name=name, digest=digest)

    @staticmethod
    def get_dataset_type() -> str:
        return 'spark'

    def _compute_digest(self) -> str:
        """Computes a digest for the dataset.

        Called if the user doesn't supply a digest when constructing the
        dataset.
        """
        if self.source.get_source_type() == 'local' or self.source.get_source_type() == 's3':
            return str(hash(json.dumps(self.source.to_dict())))[:8]
        elif self.source.get_source_type() == 'hugging_face':
            df = next(self._ds.to_pandas(batch_size=10000, batched=True))  # noqa
            return compute_pandas_digest(df)
        elif self.source.get_source_type() == 'spark':
            raise NotImplementedError('Spark dataset is not yet implemented.')
        raise RuntimeError("Spark Datasource must in ['local', 'hugging_face', 'spark', 's3]")

    def to_dict(self) -> Dict[str, str]:
        """Create config dictionary for the dataset.

        Returns a string dictionary containing the following fields: name, digest, source, source
        type, schema, and profile.
        """
        config = super().to_dict()
        config.update(
            {
                'profile': json.dumps(self.profile),
            }
        )
        return config

    def get_data(self) -> Generator[Data, None, None]:
        """Returns the input model for the dataset.

        But convert data in executor.
        """
        for data_raw in self._ds:
            if self.source.get_source_type() == 'hugging_face' and self.input_args.data_format == 'plaintext':
                data_raw = data_raw[self.input_args.column_content]
            data: Union[Generator[Data, None, None], Data] = self.converter(data_raw)
            if not isinstance(data, Data):
                for d in data:
                    try:
                        yield d
                    except TypeError as e:
                        log.error('')
                        raise e
            else:
                yield data

    @property
    def ds(self):
        """Spark dataset from anywhere.

        Returns:
            Spark dataset from anywhere. Iterable yielding Spark datasets.
        """
        return self._ds

    @property
    def source(self) -> DataSource:
        """Hugging Face dataset source information.

        Returns:
            A :py:class:`mlflow.data.huggingface_dataset_source.HuggingFaceSource`
        """
        return self._source
