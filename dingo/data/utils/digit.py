# This file is modified from:
# https://github.com/mlflow/mlflow/blob/master/mlflow/data/digest_utils.py
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

import logging
from typing import Any, List

from packaging.version import Version

from dingo.data.utils import insecure_hash

logger = logging.getLogger(__name__)
logger.setLevel("ERROR")
MAX_ROWS = 10000


def compute_pandas_digest(df) -> str:
    """Computes a digest for the given Pandas DataFrame.

    Args:
        df: A Pandas DataFrame.

    Returns:
        A string digest.
    """
    import numpy as np
    import pandas as pd

    # trim to max rows
    trimmed_df = df.head(MAX_ROWS)

    # keep string and number columns, drop other column types
    if Version(pd.__version__) >= Version("2.1.0"):
        string_columns = trimmed_df.columns[(df.map(type) == str).all(0)]
    else:
        string_columns = trimmed_df.columns[(df.applymap(type) == str).all(0)]
    numeric_columns = trimmed_df.select_dtypes(include=[np.number]).columns

    desired_columns = string_columns.union(numeric_columns)
    trimmed_df = trimmed_df[desired_columns]

    return get_normalized_md5_digest(
        [
            pd.util.hash_pandas_object(trimmed_df).values,
            np.int64(len(df)),
        ]
        + [str(x).encode() for x in df.columns]
    )


def get_normalized_md5_digest(elements: List[Any]) -> str:
    """Computes a normalized digest for a list of hashable elements.

    Args:
        elements: A list of hashable elements for inclusion in the md5 digest.

    Returns:
        An 8-character, truncated md5 digest.
    """

    if not elements:
        raise RuntimeError(
            "No hashable elements were provided for md5 digest creation",
        )

    md5 = insecure_hash.md5()
    for element in elements:
        md5.update(element)

    return md5.hexdigest()[:8]
