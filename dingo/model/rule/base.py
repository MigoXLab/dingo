from typing import List

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail


class BaseRule:
    metric_type: str = ''  # This will be set by the decorator
    group: List[str] = []  # This will be set by the decorator
    dynamic_config: EvaluatorRuleArgs = EvaluatorRuleArgs()  # Default config, can be overridden by subclasses

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        raise NotImplementedError()
