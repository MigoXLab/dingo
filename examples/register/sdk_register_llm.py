import json

from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.prompt_text_quality import PromptTextQualityV2
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


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
    from dingo.exec import Executor
    from dingo.io import InputArgs

    input_data = {
        "eval_group": "test",
        "input_path": "../../test/data/test_local_jsonl.jsonl",  # local filesystem dataset
        "save_data": True,
        "save_correct": True,
        "dataset": "local",
        "data_format": "jsonl",
        "column_content": "content",
        "custom_config": {
            "prompt_list": ["PromptTextQualityV2"],
            "llm_config": {
                "LlmTextQualityRegister": {
                    "key": "",
                    "api_url": "",
                }
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
