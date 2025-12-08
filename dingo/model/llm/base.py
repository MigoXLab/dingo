from typing import List

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io import Data
from dingo.model.modelres import EvalDetail, ModelRes, QualityLabel


class BaseLLM:
    client = None

    prompt: str | List = None
    dynamic_config: EvaluatorLLMArgs

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        raise NotImplementedError()
