from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

SCRIPT_DIR = Path(__file__).parent


def exec_first():
    input_data = {
        "input_path": str(SCRIPT_DIR.joinpath("../../test/data/test_local_jsonl.jsonl").resolve()),
        "dataset": {
            "source": "local",
            "format": "jsonl"
        },
        "executor": {
            "end_index": 1,
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": [
            {
                "fields": {"id": "id", "content": "content"},
                "evals": [
                    {"name": "RuleColonEnd"},
                    {"name": "RuleContentNull"}
                ]
            }
        ]
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


def exec_second():
    input_data = {
        "input_path": str(SCRIPT_DIR.joinpath("../../test/data/test_local_jsonl.jsonl").resolve()),
        "dataset": {
            "source": "local",
            "format": "jsonl",
        },
        "executor": {
            "start_index": 1,
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": [
            {
                "fields": {"id": "id", "content": "content"},
                "evals": [
                    {"name": "RuleColonEnd"},
                    {"name": "RuleContentNull"}
                ]
            }
        ]
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    exec_first()
    exec_second()
