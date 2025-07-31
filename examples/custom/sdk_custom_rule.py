from dingo.config import InputArgs
from dingo.exec import Executor

input_data = {
    "input_path": "test/data/test_local_json.json",
    "dataset": {
        "source": "local",
        "format": "json",
        "field": {
            "content": "prediction"
        }
    },
    "executor": {
        "rule_list": ["RuleSpecialCharacter"],
        "result_save": {
            "bad": True,
            "good": True
        }
    },
    "evaluator": {
        "rule_config": {
            "RuleSpecialCharacter": {
                "pattern": "sky"
            }
        }
    }
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
