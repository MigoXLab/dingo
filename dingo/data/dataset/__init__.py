from dingo.data.dataset.base import Dataset
from dingo.data.dataset.huggingface import HuggingFaceDataset
from dingo.data.dataset.local import LocalDataset
from dingo.utils import log

try:
    from dingo.data.dataset.spark import SparkDataset
except Exception as e:
    log.warning('Spark Dataset not imported. Open debug log for more details.')
    log.debug(str(e))

dataset_map = Dataset.dataset_map
