import json
import re
from typing import List

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.prompt_table_compare import PromptTableCompare
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register('LLMTableCompare')
class LLMTableCompare(BaseOpenAI):
    """
    专注于表格抽取效果的对比
    """
    prompt = PromptTableCompare

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        messages = [
            {
                'role': 'user',
                'content': cls.prompt.content.format(
                    input_data.content,
                    input_data.raw_data.get('llm-webkit_content', ''),
                    input_data.raw_data.get('trafilatura_content', ''),
                ),
            }
        ]
        return messages

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        log.info(response)

        # 提取思考内容和清理响应
        response_think = cls._extract_think_content(response)
        response = cls._clean_response(response)

        try:
            response_json = json.loads(response)
            if response_think and 'reason' in response_json:
                response_json['reason'] += '\n' + response_think
            elif response_think:
                response_json['reason'] = response_think
        except json.JSONDecodeError:
            raise ConvertJsonError(f'Convert to JSON format failed: {response}')

        # 处理特殊情况：没有表格
        if response_json.get('no_table'):
            return cls._create_no_table_result(response_json)

        # 处理正常情况
        return cls._create_normal_result(response_json)

    @staticmethod
    def _extract_think_content(response: str) -> str:
        if response.startswith('<think>'):
            think_content = re.search(r'<think>(.*?)</think>', response, flags=re.DOTALL)
            return think_content.group(1).strip() if think_content else ''
        return ''

    @staticmethod
    def _clean_response(response: str) -> str:
        response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL).strip()

        if response.startswith('```json'):
            response = response[7:]
        elif response.startswith('```'):
            response = response[3:]

        if response.endswith('```'):
            response = response[:-3]

        return response

    @staticmethod
    def _create_no_table_result(response_json: dict) -> ModelRes:
        result = ModelRes()
        result.error_status = False
        result.type = 'NO_TABLE'
        result.name = 'table'
        result.reason = [json.dumps(response_json, ensure_ascii=False)]
        return result

    @staticmethod
    def _create_normal_result(response_json: dict) -> ModelRes:
        result = ModelRes()
        score = response_json.get('score', 0)

        result.error_status = score != 1
        result.type = {1: 'TOOL_ONE_BETTER', 2: 'TOOL_TWO_BETTER'}.get(score, 'TOOL_EQUAL')
        result.name = 'table'
        result.reason = [json.dumps(response_json, ensure_ascii=False)]

        return result
