from dingo.exec import Executor
from dingo.io import InputArgs


def image_repeat():
    input_data = {
        "eval_group": "test",
        "input_path": "../../test/data/test_img_repeat.jsonl",  # local filesystem dataset
        "dataset": "local",
        "data_format": "jsonl",
        "save_data": True,
        "save_correct": True,
        "column_content": "content",
        "custom_config": {
            "rule_list": ["RuleImageRepeat"]
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    image_repeat()
