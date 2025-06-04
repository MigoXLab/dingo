from dingo.data.datasource.base import DataSource
from dingo.data.datasource.huggingface import HuggingFaceSource
from dingo.data.datasource.local import LocalDataSource
from dingo.utils import log

try:
    from dingo.data.datasource.s3 import S3DataSource
except Exception as e:
    log.warning('S3 datasource not imported. Open debug log for more details.')
    log.debug(str(e))

datasource_map = DataSource.datasource_map
