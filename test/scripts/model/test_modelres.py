import os
import re
from typing import List

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.model.model import Model
from dingo.model.modelres import ModelRes
from dingo.model.rule.base import BaseRule


@Model.rule_register('QUALITY_BAD_RELEVANCE', ['test'])
class RegisterRuleColon(BaseRule):
    """let user input pattern to search"""
    dynamic_config = EvaluatorRuleArgs(pattern = "blue")

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        content = input_data.content
        if len(content) <= 0:
            return res
        if content[-1] == ":":
            res.error_status = True
            res.type = [cls.metric_type, 'TestType']
            res.name = [cls.__name__, 'TestName']
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
        assert isinstance(res.type, List)
        assert isinstance(res.name, List)
        assert len(res.type) == 2
        assert len(res.name) == 2
        assert 'TestType' in res.type
        assert 'TestName' in res.name
