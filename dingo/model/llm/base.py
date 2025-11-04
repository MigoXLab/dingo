from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io import Data
from dingo.model.modelres import ModelRes


class BaseLLM:
    client = None

    prompt = None
    dynamic_config: EvaluatorLLMArgs


    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        raise NotImplementedError()
