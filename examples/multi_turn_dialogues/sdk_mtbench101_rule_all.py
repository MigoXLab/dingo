from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "../../test/data/test_mtbench101_jsonl.jsonl",
        "dataset": {
            "source": "local",
            "format": "multi_turn_dialog",
            "field": {
                "id": "id",
                "content": "history"  # the column name of multi-turn dialogues, e.g.: history, dialogues
            }
        },
        "executor": {
            "eval_group": "qa_standard_v1",
            "result_save": {
                "bad": True,
                "good": True
            },
            "multi_turn_mode": "all"
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
