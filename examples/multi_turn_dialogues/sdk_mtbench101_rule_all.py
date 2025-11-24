from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "../../test/data/test_mtbench101_jsonl.jsonl",
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
                "fields": {"id": "id", "content": "history"},
                "evals": [
                    {"name": "RuleEnterAndSpace"},
                    {"name": "RuleAbnormalChar"}
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
