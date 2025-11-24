from dingo.data.datasource.base import DataSource  # noqa E402.
from dingo.data.datasource.huggingface import HuggingFaceSource  # noqa E402.
from dingo.data.datasource.local import LocalDataSource  # noqa E402.
from dingo.utils import log

try:
    from dingo.data.datasource.s3 import S3DataSource  # noqa E402.
except Exception as e:
    log.warning("S3 datasource not imported. Open debug log for more details.")
    log.debug(str(e))

try:
    from dingo.data.datasource.sql import SqlDataSource  # noqa E402.
except Exception as e:
    log.warning("SQL datasource not imported. Open debug log for more details.")
    log.debug(str(e))

datasource_map = DataSource.datasource_map
