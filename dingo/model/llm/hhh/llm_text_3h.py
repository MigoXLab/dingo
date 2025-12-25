import json

from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.response.response_class import ResponseScoreReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


# @Model.llm_register("LLMText3H")
class LLMText3H(BaseOpenAI):
    @classmethod
    def build_messages(cls, input_data):
        question = input_data.prompt
        response = input_data.content
        prompt_content = cls.prompt % (question, response)

        messages = [{"role": "user", "content": prompt_content}]

        return messages

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

        response_model = ResponseScoreReason(**response_json)

        result = EvalDetail(metric=cls.__name__)

        # Get the quality dimension name from class name
        # e.g., LLMText3HHelpful -> HELPFUL
        class_prefix = "LLMText3H"
        if cls.__name__.startswith(class_prefix):
            quality_name = cls.__name__[len(class_prefix):].upper()
        else:
            quality_name = cls.__name__.upper()

        # eval_status
        if response_model.score == 1:
            result.label = [f"{QualityLabel.QUALITY_GOOD}.{quality_name}"]
            result.reason = [response_model.reason] if response_model.reason else ["Response meets quality criteria"]
        else:
            result.status = True
            result.label = [f"QUALITY_BAD.NOT_{quality_name}"]
            result.reason = [response_model.reason] if response_model.reason else ["Response fails quality criteria"]

        return result
