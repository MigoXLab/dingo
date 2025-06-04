from typing import List

from dingo.config.config import DynamicRuleConfig
from dingo.io import Data
from dingo.model.modelres import ModelRes


class BaseRule:
    metric_type: str  # This will be set by the decorator
    group: List[str]  # This will be set by the decorator
    dynamic_config: DynamicRuleConfig

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        raise NotImplementedError()
