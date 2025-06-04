import os
from typing import Optional

import toml
from dingo.utils.log_util.logger import Logger
from pydantic import BaseModel


class LogConfig(BaseModel):
    """Logging configuration model."""

    filename: Optional[str] = None
    level: Optional[str] = 'warning'
    fmt: Optional[str] = '[%(asctime)s][%(levelname)s] %(pathname)s[line:%(lineno)d] -: %(message)s'


# with open(
#         os.path.join(
#             os.path.split(os.path.realpath(__file__))[0], 'config.ini'),
#         'r') as f:
#     config = LogConfig(**(toml.loads(f.read())['log']))

config = LogConfig()

# Use this rather than `Logger`
log = Logger(
    filename=config.filename,
    level=config.level,
    fmt=config.fmt,
).log
