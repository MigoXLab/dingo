import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
OPENAI_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

llm_config = {
    "model": OPENAI_MODEL,
    "key": OPENAI_KEY,
    "api_url": OPENAI_URL,
}

if __name__ == '__main__':
    input_data = {
        "input_path": str(Path("test/data/test_local_jsonl.jsonl")),
        "dataset": {
            "source": "local",
            "format": "jsonl",
        },
        "executor": {
            "max_workers": 10,
            "batch_size": 10,
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": [
            {
                "fields": {"content": "content"},
                "evals": [
                    {"name": "LLMTextQualityV5", "config": llm_config}
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
