from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": str(Path(__file__).parent.joinpath("../../test/data/test_local_json.json").resolve()),
        "dataset": {
            "source": "local",
            "format": "json",
        },
        "executor": {
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": [
            {
                "fields": {"content": "prediction"},
                "evals": [
                    {"name": "RuleSpecialCharacter", "config": {"key_list": ["sky", "apple"]}}
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
