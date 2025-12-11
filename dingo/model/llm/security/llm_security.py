import json

from dingo.io.output.eval_detail import EvalDetail
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


# @Model.llm_register("LLMSecurity")
class LLMSecurity(BaseOpenAI):
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
        for k, v in response_json.items():
            if v == "pos":
                result.status = True
                tmp_reason.append(k)

        result.label = [f"Security.{cls.__name__}"]
        result.reason = tmp_reason
        return result
