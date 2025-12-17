import os

from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI

OPENAI_MODEL = 'deepseek-chat'
OPENAI_URL = 'https://api.deepseek.com/v1'
OPENAI_KEY = os.getenv("OPENAI_KEY", "sk-5b3e85f25d214c3b9c79ea62eab41e35")

common_config = {
    "model": OPENAI_MODEL,
    "key": OPENAI_KEY,
    "api_url": OPENAI_URL,
}


@Model.llm_register('LlmTextQualityRegister')
class LlmTextQualityRegister(BaseOpenAI):
    prompt = """
    请判断一下文本是否存在重复问题。
    返回一个json，如{"score": 0, reason": "xxx"}.
    如果存在重复，score是0，否则是1。当score是0时，type是REPEAT。reason是判断的依据。
    除了json不要有其他内容。
    以下是需要判断的文本：
    """


if __name__ == '__main__':
    from dingo.config import InputArgs
    from dingo.exec import Executor

    input_data = {
        "input_path": "../../test/data/test_local_jsonl.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
        },
        "executor": {
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": [
            {
                "fields": {"content": "content"},
                "evals": [
                    {"name": "LlmTextQualityRegister", "config": common_config}
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
