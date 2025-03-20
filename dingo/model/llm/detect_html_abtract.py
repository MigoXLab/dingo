import json
import re
from typing import Dict, List

from dingo.io import MetaData
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register('detect_html_abstract')
class DetectHtmlAbstract(BaseOpenAI):
    @classmethod
    def build_messages(cls, input_data: MetaData) -> List:
        messages = [{"role": "user",
                     "content": cls.prompt.content.format(input_data.content, input_data.raw_data['markdown_ours'], input_data.raw_data['markdown_m10'])}]
        return messages

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        log.info(response)

        response_think = ''
        if response.startswith('<think>'):
            think_content = re.search(r'<think>(.*?)</think>', response, flags=re.DOTALL)
            response_think = think_content.group(1).strip()
            response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
            response = response.strip()
        if response.startswith('```json'):
            response = response[7:]
        if response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]
        try:
            response_json = json.loads(response)
            response_json['reason'] += '\n'
            response_json['reason'] += response_think
        except json.JSONDecodeError:
            raise ConvertJsonError(f'Convert to JSON format failed: {response}')

        response_model = ResponseScoreTypeNameReason(**response_json)

        result = ModelRes()
        # status
        if response_model.score != 1:
            result.error_status = True

        # type
        if response_model.score == 1:
            result.type = 'TOOL_ONE_BETTER'
        if response_model.score == 2:
            result.type = 'TOOL_TWO_BETTER'
        if response_model.score == 0:
            result.type = 'TOOL_EQUAL'

        # name
        result.name = response_model.name

        # reason
        result.reason = [json.dumps(response_json, ensure_ascii=False)]

        return result
