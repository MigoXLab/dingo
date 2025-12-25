import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Configure LLM (set your API key via environment variable OPENAI_KEY)
LLM_CONFIG = {
    "key": os.getenv("OPENAI_KEY", "YOUR_API_KEY"),
    "api_url": os.getenv("OPENAI_URL", "https://api.openai.com/v1"),
    "model": os.getenv("OPENAI_MODEL", "gpt-4o")
}


def classify_topic():
    input_data = {
        "input_path": str(PROJECT_ROOT / "test/data/test_sft_jsonl.jsonl"),
        "dataset": {
            "source": "local",
            "format": "jsonl"
        },
        "executor": {
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": [
            {
                "fields": {"content": "question"},
                "evals": [
                    {"name": "LLMClassifyTopic", "config": LLM_CONFIG}
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    classify_topic()
