import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    # Configure LLM (set your API key via environment variable OPENAI_KEY)
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_URL = os.getenv("OPENAI_URL", "https://api.openai.com/v1")
    OPENAI_KEY = os.getenv("OPENAI_KEY", "YOUR_API_KEY")  # Set OPENAI_KEY env var
    common_config = {
        "model": OPENAI_MODEL,
        "key": OPENAI_KEY,
        "api_url": OPENAI_URL,
    }

    # Get the path relative to this script
    script_dir = Path(__file__).parent
    data_path = script_dir / "../../test/data/test_3h_jsonl.jsonl"

    input_data = {
        "input_path": str(data_path.resolve()),
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
                "fields": {"prompt": "input", "content": "response", "context": "response"},
                "evals": [
                    {"name": "LLMText3HHarmless", "config": common_config},
                    # {"name": "LLMText3HHelpful", "config": common_config},
                    # {"name": "LLMText3HHonest", "config": common_config},
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
