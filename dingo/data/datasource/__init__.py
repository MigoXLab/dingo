from dingo.data.datasource.base import DataSource  # noqa E402.
from dingo.data.datasource.huggingface import HuggingFaceSource  # noqa E402.
from dingo.data.datasource.local import LocalDataSource  # noqa E402.
from dingo.data.datasource.s3 import S3DataSource  # noqa E402.
from dingo.data.datasource.sql import SqlDataSource  # noqa E402.

datasource_map = DataSource.datasource_map
