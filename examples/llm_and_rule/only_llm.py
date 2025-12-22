import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

if __name__ == '__main__':
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
    OPENAI_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

    input_data = {
        "input_path": str(PROJECT_ROOT / "test/data/test_local_jsonl.jsonl"),
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
                    {"name": "LLMTextRepeat", "config": {"key": OPENAI_KEY, "api_url": OPENAI_URL}}
                ],
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
