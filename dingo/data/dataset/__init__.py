from dingo.data.dataset.base import Dataset  # noqa E402.
from dingo.data.dataset.huggingface import HuggingFaceDataset  # noqa E402.
from dingo.data.dataset.local import LocalDataset  # noqa E402.
from dingo.utils import log

try:
    from dingo.data.dataset.s3 import S3Dataset  # noqa E402.
except Exception as e:
    log.warning("S3 Dataset not imported. Open debug log for more details.")
    log.debug(str(e))

try:
    from dingo.data.dataset.spark import SparkDataset  # noqa E402.
except Exception as e:
    log.warning("Spark Dataset not imported. Open debug log for more details.")
    log.debug(str(e))

try:
    from dingo.data.dataset.sql import SqlDataset  # noqa E402.
except Exception as e:
    log.warning("SQL Dataset not imported. Open debug log for more details.")
    log.debug(str(e))

dataset_map = Dataset.dataset_map
