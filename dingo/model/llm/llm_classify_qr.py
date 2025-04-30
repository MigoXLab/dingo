import json
from typing import List

from dingo.io.input import MetaData
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.prompt_classify_qr import PromptClassifyQR
from dingo.model.response.response_class import ResponseNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register('LLMClassifyQR')
class LLMClassifyQR(BaseOpenAI):
    prompt = PromptClassifyQR

    @classmethod
    def build_messages(cls, input_data: MetaData) -> List:
        messages = [
            {"role": "user",
             "content": [{'type': 'text', 'text': cls.prompt.content},
                         {'type': 'image_url', 'image_url': {'url': input_data.content}}]
             }
        ]
        return messages

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
