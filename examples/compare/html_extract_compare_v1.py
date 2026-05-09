import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

if __name__ == '__main__':
    input_data = {
        "input_path": str(PROJECT_ROOT / "test/data/compare/test_compare_content.jsonl"),
        "dataset": {
            "source": "local",
            "format": "jsonl",
        },
        "executor": {
            "batch_size": 10,
            "max_workers": 10,
            "result_save": {
                "bad": True,
                "good": True,
                "raw": True
            }
        },
        "evaluator": [
            {
                "fields": {
                    "data_id": "track_id",
                    "prompt": "markdown_m10",
                    "reference": "markdown_ours",
                    "content": "clean_html",
                },
                "evals": [
                    {
                        "name": "LLMHtmlExtractCompare",
                        "config": {
                            "key": OPENAI_KEY,
                            "api_url": OPENAI_URL,
                            "model": OPENAI_MODEL,
                        },
                    }
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
