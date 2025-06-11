import re

from dingo.config.config import DynamicRuleConfig
from dingo.io import Data
from dingo.model.model import Model
from dingo.model.modelres import ModelRes
from dingo.model.rule.base import BaseRule


@Model.rule_register('QUALITY_BAD_RELEVANCE', ['test'])
class CommonPatternDemo(BaseRule):
    """let user input pattern to search"""
    dynamic_config = DynamicRuleConfig(pattern = "blue")

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        matches = re.findall(cls.dynamic_config.pattern, input_data.content)
        if matches:
            res.error_status = True
            res.type = cls.metric_type
            res.name = cls.__name__
            res.reason = matches
        return res


if __name__ == '__main__':
    from dingo.exec import Executor
    from dingo.io import InputArgs

    input_data = {
        "eval_group": "test",
        "input_path": "../../test/data/test_local_json.json",  # local filesystem dataset
        "dataset": "local",
        "data_format": "json",
        "column_content": "prediction"
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
