import json

from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.prompt.prompt_classify_topic import PromptClassifyTopic
from dingo.model.modelres import ModelRes
from dingo.model.response.response_class import ResponseNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register('LlmClassifyTopic')
class LlmClassifyTopic(BaseOpenAI):
    prompt = PromptClassifyTopic

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

        response_model = ResponseNameReason(**response_json)

        result = ModelRes()
        result.error_status = False

        # type
        result.type = cls.prompt.metric_type

        # name
        result.name = response_model.name

        # reason
        result.reason = [response_model.reason]

        return result
