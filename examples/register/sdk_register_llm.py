import json
import os

from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.prompt_text_quality import PromptTextQualityV2
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError

OPENAI_MODEL = 'deepseek-chat'
OPENAI_URL = 'https://api.deepseek.com/v1'
OPENAI_KEY = os.getenv("OPENAI_KEY")
if not OPENAI_KEY:
    raise ValueError('OPENAI_KEY is not set correctly.')


@Model.llm_register('LlmTextQualityRegister')
class LlmTextQualityRegister(BaseOpenAI):
    prompt = PromptTextQualityV2

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        log.debug(response)

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
            result.name = "Flawless"
        else:
            result.error_status = True
            result.type = response_model.type
            result.name = response_model.name
            result.reason = [response_model.reason]

        return result


if __name__ == '__main__':
    from dingo.config import InputArgs
    from dingo.exec import Executor

    input_data = {
        "input_path": "test/data/test_local_jsonl.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "content": "content",
            }
        },
        "executor": {
            "prompt_list": ["PromptTextQualityV2"],
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LlmTextQualityRegister": {
                    "model": OPENAI_MODEL,
                    "key": OPENAI_KEY,
                    "api_url": OPENAI_URL,
                }
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
