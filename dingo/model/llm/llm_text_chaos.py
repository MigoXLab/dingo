import json

from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMTextChaos")
class LLMTextChaos(BaseOpenAI):
    prompt = """
    请判断一下文本是否存在乱码与反扒文本。
    返回一个json，如{"score": 0, "reason": "xxx"}.
    如果存在问题，score是0，否则是1。reason是判断的依据。
    除了json不要有其他内容。
    以下是需要判断的文本：
    """

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

        response_model = ResponseScoreTypeNameReason(**response_json)

        result = EvalDetail(metric=cls.__name__)
        # eval_status
        if response_model.score == 1:
            result.label = [f"{QualityLabel.QUALITY_GOOD}.{cls.__name__}"]
            result.reason = [response_model.reason]
        else:
            result.status = True
            result.label = [f"{response_model.type}.{response_model.name}"]
            result.reason = [response_model.reason]

        return result
