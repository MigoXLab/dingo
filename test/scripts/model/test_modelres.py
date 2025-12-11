from typing import List

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule


@Model.rule_register('QUALITY_BAD_RELEVANCE', ['test'])
class RegisterRuleColon(BaseRule):
    """let user input pattern to search"""
    dynamic_config = EvaluatorRuleArgs(pattern = "blue")

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        if len(content) <= 0:
            return res
        if content[-1] == ":":
            # res.eval_status = True
            # res.type = [cls.metric_type, 'TestType']
            # res.name = [cls.__name__, 'TestName']
            # res.reason = [content[-100:]]
            # res.eval_details = {
            #     "label": [cls.metric_type, 'TestType'],
            #     "metric": [cls.__name__],
            #     "reason": [content[-100:]]
            # }
            res.status = True
            res.label = [cls.metric_type, 'TestType']
            res.reason = [content[-100:]]
        return res


class TestModelRes:
    def test_type_name_list(self):

        data = Data(
            data_id='0',
            prompt="",
            content="Hello! The world is a vast and diverse place, full of wonders, cultures, and incredible natural beauty:"
        )

        res = RegisterRuleColon().eval(data)
        # print(res)
        assert isinstance(res.label, List)
        assert isinstance(res.reason, List)
        assert len(res.label) == 2
        assert 'TestType' in res.label
