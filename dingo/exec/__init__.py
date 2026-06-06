from dingo.exec.base import ExecProto, Executor  # noqa E402.
from dingo.exec.local import LocalExecutor  # noqa E402.
from dingo.utils import log

try:
    from dingo.exec.spark import SparkExecutor  # noqa E402.
except Exception as e:
    log.warning("Spark Executor not imported. Open debug log for more details.")
    log.debug(str(e))

try:
    from dingo.exec.retrieval import RetrievalExecutor  # noqa E402.
except Exception as e:
    log.debug("Retrieval Executor not imported (install extras 'retrieval'): %s", e)
