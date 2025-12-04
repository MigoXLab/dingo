import json

from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes, QualityLabel
from dingo.model.response.response_class import ResponseScoreReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


# @Model.llm_register("LLMText3H")
class LLMText3H(BaseOpenAI):
    @classmethod
    def build_messages(cls, input_data):
        question = input_data.prompt
        response = input_data.content
        prompt_content = cls.prompt.content % (question, response)

        messages = [{"role": "user", "content": prompt_content}]

        return messages

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
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

        response_model = ResponseScoreReason(**response_json)

        result = ModelRes()

        # eval_status
        if response_model.score == 1:
            tmp_name = cls.prompt.__name__[8:].upper()
            result.eval_details = {
                "label": [f"{QualityLabel.QUALITY_GOOD}.{tmp_name}"],
                "metric": [cls.__name__],
                "reason": [response_model.reason] if response_model.reason else ["Response meets quality criteria"]
            }
        else:
            result.eval_status = True
            tmp_name = "NOT_" + cls.prompt.__name__[8:].upper()
            result.eval_details = {
                "label": [f"QUALITY_BAD.{tmp_name}"],
                "metric": [cls.__name__],
                "reason": [response_model.reason] if response_model.reason else ["Response fails quality criteria"]
            }

        return result
