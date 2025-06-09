# This file is modified from:
# https://github.com/mlflow/mlflow/blob/master/mlflow/data/dataset.py
#
# Copyright 2018 Databricks, Inc.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from abc import abstractmethod
from functools import wraps
from typing import Any, Callable, Dict, Generator, Optional

from dingo.data.converter import BaseConverter, converters
from dingo.data.datasource.base import DataSource
from dingo.io import Data, InputArgs
from dingo.utils import log


class Dataset:
    """Represents a dataset for use with Dingo Tracking, including the name,
    digest (hash), schema, and profile of the dataset as well as source
    information (e.g. the S3 bucket or managed Delta table from which the
    dataset was derived).

    Most datasets expose features and targets for training and evaluation as
    well.
    """

    dataset_map = {}

    def __init__(
        self,
        source: DataSource,
        name: Optional[str] = None,
        digest: Optional[str] = None,
    ):
        """Base constructor for a dataset.

        All subclasses must call this constructor.
        """
        self.input_args = None
        self.converter = None
        self._name = name
        self._source = source
        self.input_args = source.input_args
        self._converter = self.input_args.data_format

        if source.get_source_type() == "hugging_face" and self._converter == "listjson":
            self._converter = "jsonl"
        try:
            converter_cls: BaseConverter = converters[self._converter]
        except KeyError as e:
            log.error(f'Convertor "{self._converter}" not exist in {str(converters.keys())}')
            raise e

        self.converter: Callable = converter_cls.convertor(self.input_args)
        self._digest = digest or self._compute_digest()

    @staticmethod
    @abstractmethod
    def get_dataset_type() -> str:
        """Obtains a string representing the type of the dataset.

        Returns:
            A string representing the type of the dataset, e.g. "hugging_face", "spark", "local", ...
        """

    @abstractmethod
    def _compute_digest(self) -> str:
        """Computes a digest for the dataset. Called if the user doesn't supply
        a digest when constructing the dataset.

        Returns:
            A string digest for the dataset. We recommend a maximum digest length
            of 10 characters with an ideal length of 8 characters.
        """

    @abstractmethod
    def to_dict(self) -> Dict[str, str]:
        """Create config dictionary for the dataset.

        Subclasses should override this method to provide additional fields in the config dict,
        e.g., schema, profile, etc.

        Returns a string dictionary containing the following fields: name, digest, source, source
        type.
        """
        return {
            "name": self.name,
            "digest": self.digest,
            "source": self.source.to_json(),
            "source_type": self.source.get_source_type(),
        }

    @abstractmethod
    def get_data(self, **kwargs) -> Generator[Data, None, None]:
        """Eval Data Generator."""

    def to_json(self) -> str:
        """Obtains a JSON string representation of the :py:class:`Dataset
        <dingo.data.dataset.Dataset>`.

        Returns:
            A JSON string representation of the :py:class:`Dataset <dingo.data.dataset.Dataset>`.
        """

        return json.dumps(self.to_dict())

    @property
    def name(self) -> str:
        """The name of the dataset, e.g. ``"iris_data"``,
        ``"myschema.mycatalog.mytable@v1"``, etc."""
        if self._name is not None:
            return self._name
        else:
            return "dataset"

    @property
    def digest(self) -> str:
        """A unique hash or fingerprint of the dataset, e.g. ``"498c7496"``."""
        return self._digest

    @property
    def source(self) -> DataSource:
        """Information about the dataset's source, represented as an instance
        of :py:class:`DataSource <dingo.data.dataset_source.DataSource>`.

        For example, this may be the S3 location or the name of the managed
        Delta Table from which the dataset was derived.
        """
        return self._source

    @property
    @abstractmethod
    def profile(self) -> Optional[Any]:
        """Optional summary statistics for the dataset, such as the number of
        rows in a table, the mean / median / std of each table column, etc."""

    @classmethod
    def register(cls):
        """Register a dataset.

        (register)
        """

        def decorator(root_class):
            cls.dataset_map[root_class.get_dataset_type()] = root_class

            @wraps(root_class)
            def wrapped_function(*args, **kwargs):
                return root_class(*args, **kwargs)

            return wrapped_function

        return decorator
