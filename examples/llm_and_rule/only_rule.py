import os

from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "../../test/data/test_local_jsonl.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "content": "content"
            }
        },
        "executor": {
            "rule_list": ["RuleColonEnd"],
            "result_save": {
                "bad": True,
                "good": True
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
