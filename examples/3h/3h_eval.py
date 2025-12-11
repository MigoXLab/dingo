import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    OPENAI_MODEL = 'deepseek-chat'
    OPENAI_URL = 'https://api.deepseek.com/v1'
    OPENAI_KEY = os.getenv("OPENAI_KEY")

    input_data = {
        "input_path": str(Path("test/data/test_3h_jsonl.jsonl")),
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "prompt": "input",
                "content": "response",
                "context": "response"
            }
        },
        "executor": {
            "prompt_list": ["PromptTextHarmless", "PromptTextHelpful", "PromptTextHonest"],
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMText3HHarmless": {
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
