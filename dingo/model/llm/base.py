from typing import List

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail


class BaseLLM:
    client = None

    prompt: str | List = None
    dynamic_config: EvaluatorLLMArgs = EvaluatorLLMArgs()

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        raise NotImplementedError()
