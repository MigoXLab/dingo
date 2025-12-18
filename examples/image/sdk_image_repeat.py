from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

SCRIPT_DIR = Path(__file__).parent


def image_repeat():
    input_data = {
        "input_path": str(SCRIPT_DIR.joinpath("../../test/data/test_img_repeat.jsonl").resolve()),
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
                    {"name": "RuleImageRepeat"}
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    image_repeat()
