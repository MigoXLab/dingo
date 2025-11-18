from typing import List, Optional

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io import Data
from dingo.model.llm.base import BaseLLM
from dingo.model.modelres import ModelRes


class BasePrompt:
    metric_type: str  # This will be set by the decorator
    group: List[str]  # This will be set by the decorator
    dynamic_config: EvaluatorLLMArgs

    content: str
    senario: Optional[BaseLLM]

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        raise NotImplementedError()
