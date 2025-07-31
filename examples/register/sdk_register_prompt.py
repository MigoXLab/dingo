import os

from dingo.model import Model
from dingo.model.prompt.base import BasePrompt

OPENAI_MODEL = 'deepseek-chat'
OPENAI_URL = 'https://api.deepseek.com/v1'
OPENAI_KEY = os.getenv("OPENAI_KEY")


@Model.prompt_register("QUALITY_BAD_SIMILARITY", [])
class PromptRepeatDemo(BasePrompt):
    content = """
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
        "input_path": "test/data/test_local_jsonl.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "content": "content"
            }
        },
        "executor": {
            "prompt_list": ["PromptRepeatDemo"],
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMTextQualityPromptBase": {
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
