from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "../../test/data/test_imgae_artimuse.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "data_id": "id",
                "content": "content"
            }
        },
        "executor": {
            "rule_list": ["RuleImageArtimuse"],
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
