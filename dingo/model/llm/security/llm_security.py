import json

from dingo.io.input import RequiredField
from dingo.io.output.eval_detail import EvalDetail
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


# @Model.llm_register("LLMSecurity")
class LLMSecurity(BaseOpenAI):
    _required_fields = [RequiredField.CONTENT]

    # Answer values that mean "hit". Security prompts do not share one polarity:
    # the prohibition prompt answers pos/neg, where "pos" is the violation,
    # while the politics prompt answers neg/pos/none, where "neg" — involved and
    # holding a negative stance — is the violation and "pos" is not. Judging
    # every scenario by "pos" silently inverts politics, dropping the sensitive
    # corpora it exists to catch and flagging the positive-stance ones instead.
    #
    # The policy is keyed by metric name and resolved through the MRO, so a
    # subclass inherits the polarity of the scenario it extends without having
    # to restate it, and an unlisted scenario keeps the pos default.
    _hit_values_by_metric = {
        "LLMSecurityPolitics": ("neg",),
    }
    _default_hit_values = ("pos",)

    @classmethod
    def hit_values(cls) -> tuple:
        for metric_class in cls.__mro__:
            hit_values = cls._hit_values_by_metric.get(metric_class.__name__)
            if hit_values is not None:
                return hit_values
        return cls._default_hit_values

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        log.info(response)

        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        try:
            response_json = json.loads(response)
        except json.JSONDecodeError:
            raise ConvertJsonError(f"Convert to JSON format failed: {response}")

        result = EvalDetail(metric=cls.__name__)
        tmp_reason = []
        hit_values = cls.hit_values()
        for k, v in response_json.items():
            if v in hit_values:
                result.status = True
                tmp_reason.append(k)

        result.label = [f"Security.{cls.__name__}"]
        result.reason = tmp_reason
        return result
