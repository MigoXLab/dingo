import re

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["xinghe"])
class RuleDoi(BaseRule):
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleDoi",
        "description": "Check whether the string is in the correct format of the doi",
        "paper_title": "",
        "paper_url": "",
        "paper_authors": "",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs(pattern=r'^10\.\d{4,9}/([^A-Z\s]*)$')

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        content = input_data.content
        if re.match(cls.dynamic_config.pattern, content):
            res.label = [QualityLabel.QUALITY_GOOD]
        else:
            res.status = True
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [content]
        return res


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["xinghe"])
class RuleIsbn(BaseRule):
    _metric_info = {
        "category": "Rule-Based TEXT Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleIsbn",
        "description": "Check whether the string is in the correct format of the isbn",
        "paper_title": "",
        "paper_url": "",
        "paper_authors": "",
        "evaluation_results": ""
    }

    dynamic_config = EvaluatorRuleArgs()

    @classmethod
    def _validate_isbn10(cls, isbn: str) -> bool:
        """验证ISBN-10格式"""
        # 前9位必须是数字，第10位可以是数字或X
        if not (isbn[:-1].isdigit() and (isbn[-1].isdigit() or isbn[-1].upper() == 'X')):
            return False

        # 计算校验和
        total = 0
        for i, char in enumerate(isbn):
            if char.upper() == 'X':
                value = 10
            else:
                value = int(char)
            total += value * (10 - i)

        return total % 11 == 0

    @classmethod
    def _validate_isbn13(cls, isbn: str) -> bool:
        """验证ISBN-13格式"""
        # 必须全部是数字
        if not isbn.isdigit():
            return False

        # 前三位必须是978或979
        if not isbn.startswith(('978', '979')):
            return False

        # 计算校验和
        total = 0
        for i, digit in enumerate(isbn):
            value = int(digit)
            # 奇数位乘1，偶数位乘3（索引从0开始）
            total += value * (1 if i % 2 == 0 else 3)

        return total % 10 == 0

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=cls.__name__)
        res.label = [QualityLabel.QUALITY_GOOD]

        content = input_data.content
        content = str(content).replace('-', '')
        if len(content) == 10:
            if cls._validate_isbn10(content):
                pass
            else:
                res.status = True
        elif len(content) == 13:
            if cls._validate_isbn13(content):
                pass
            else:
                res.status = True
        else:
            res.status = True

        # add details
        if res.status:
            res.label = [f"{cls.metric_type}.{cls.__name__}"]
            res.reason = [content]
        return res
