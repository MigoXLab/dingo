import json

from dingo.config.config import DynamicLLMConfig
from dingo.io.input.MetaData import MetaData
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.base import BasePrompt
from dingo.model.prompt.prompt_common import PromptRepeat
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register('detect_text_quality_detail')
class DetectTextQualityDetail(BaseOpenAI):
    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        log.info(response)

        if response.startswith('```json'):
            response = response[7:]
        if response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        try:
            response_json = json.loads(response)
        except json.JSONDecodeError:
            raise ConvertJsonError(f'Convert to JSON format failed: {response}')

        response_model = ResponseScoreTypeNameReason(**response_json)

        result = ModelRes()
        # error_status
        if response_model.score == 1:
            result.reason = [response_model.reason]
        else:
            result.error_status = True
            result.type = response_model.type
            result.name = response_model.name
            result.reason = [response_model.reason]

        return result

if __name__ == "__main__":
    DetectTextQualityDetail.prompt = PromptRepeat()
    DetectTextQualityDetail.dynamic_config = DynamicLLMConfig(
        key='',
        api_url='',
        # model='',
    )
    res = DetectTextQualityDetail.call_api(MetaData(data_id='123', content="hello, introduce the world"))
    print(res)
