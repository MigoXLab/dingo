import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
    OPENAI_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
    common_config = {
        "model": OPENAI_MODEL,
        "key": OPENAI_KEY,
        "api_url": OPENAI_URL,
    }

    input_data = {
        "input_path": str(Path(__file__).parent.joinpath("../../test/data/test_mtbench101_jsonl.jsonl").resolve()),
        "dataset": {
            "source": "local",
            "format": "multi_turn_dialog",
        },
        "executor": {
            "result_save": {
                "bad": True,
                "good": True
            },
            "multi_turn_mode": "all"
        },
        "evaluator": [
            {
                "fields": {"content": "history"},
                "evals": [
                    {"name": "LLMTextQualityV3", "config": common_config}
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
