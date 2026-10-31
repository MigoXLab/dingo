"""Repository-specific adapters around Dingo's built-in security evaluators."""

import json

from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.llm.security.llm_security_politics import LLMSecurityPolitics
from dingo.model.llm.security.llm_security_prohibition import LLMSecurityProhibition
from dingo.utils.exception import ConvertJsonError


class LLMRepositorySecurityProhibition(LLMSecurityProhibition):
    prompt = """
You are a precision-first content-safety reviewer for repository source code.
Judge comments, strings, documentation, and other natural-language content in context.

- porn: explicit sexual acts/anatomy intended sexually, or pornographic promotion.
- gamble: promotion, inducement, organization, payment, or traffic diversion for gambling.
- drug: promotion, transaction, production instructions, or actionable misuse of illegal drugs.

Medical, educational, legal, news, warning, test-fixture, identifier-only, and neutral
technical contexts are not positive. Return only JSON:
{"porn":"pos|neg","gamble":"pos|neg","drug":"pos|neg"}

Text to be reviewed:
    """

    @classmethod
    def process_response(cls, response):
        result = super().process_response(response)
        labels = {
            "porn": "Security.Porn",
            "gamble": "Security.Gamble",
            "drug": "Security.Drug",
        }
        result.label = [labels[name] for name in result.reason if name in labels] or ["QUALITY_GOOD"]
        return result


class LLMRepositorySecurityPolitics(LLMSecurityPolitics):
    prompt = """
你是一名代码仓库训练数据的内容安全审查员。判断注释、字符串和文档是否明确支持、
宣传、煽动或组织以下有害政治内容。新闻转述、法律法规、历史学术研究、审核规则、
反对或谴责、引用、测试样例和仅出现关键词均不属于负面立场。

五类内容为：损害社会主义政权制度、损害中国国家利益和形象、损害国家统一和稳定、
宣扬恐怖主义和极端主义、煽动民族仇恨和歧视。

涉及且持有害立场返回 neg；涉及但反对、防范或持正面立场返回 pos；否则返回 none。
仅输出一个 JSON 对象，不要使用 Markdown 代码块，不要添加解释文字：
{"hurt_socialist_regime_system":"neg|pos|none","hurt_china_interests_image":"neg|pos|none",
"hurt_china_unity_stability":"neg|pos|none","terrorism_and_extremism":"neg|pos|none",
"ethnic_hate_and_discrimination":"neg|pos|none"}

需要审查的语料：
    """

    @classmethod
    def process_response(cls, response):
        text = response.strip()
        if text.startswith("```json") and text.endswith("```"):
            text = text[7:-3].strip()
        elif text.startswith("```") and text.endswith("```"):
            text = text[3:-3].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ConvertJsonError("Invalid political review JSON")
        text = text[start:end + 1].strip()
        if text.startswith("{{") and text.endswith("}}"):
            text = text[1:-1].strip()
        try:
            payload = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            raise ConvertJsonError("Invalid political review JSON") from None
        expected = {
            "hurt_socialist_regime_system", "hurt_china_interests_image",
            "hurt_china_unity_stability", "terrorism_and_extremism",
            "ethnic_hate_and_discrimination",
        }
        if set(payload) != expected or any(value not in {"neg", "pos", "none"} for value in payload.values()):
            raise ConvertJsonError("Invalid political review schema")
        negative = [name for name, value in payload.items() if value == "neg"]
        return EvalDetail(
            metric=cls.__name__, status=bool(negative), score=0 if negative else 1,
            label=["Security.Politics"] if negative else ["QUALITY_GOOD"],
            reason=negative or ["No harmful political stance confirmed."],
        )

    @classmethod
    def eval(cls, input_data):
        result = super().eval(input_data)
        parse_failed = (
            not result.applicable
            and f"{QualityLabel.REVIEW_EXECUTION_ERROR_PREFIX}ConvertJsonError" in (result.label or [])
        )
        if not parse_failed:
            return result
        retry = super().eval(input_data)
        retry.usage = cls._merge_token_usage(result.usage, retry.usage)
        return retry
