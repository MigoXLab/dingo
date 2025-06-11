from dingo.exec import Executor
from dingo.io import InputArgs


def image_text_similar():
    input_data = {
        "eval_group": "test",
        "input_path": "../../test/data/test_img_text.jsonl",  # local filesystem dataset
        "dataset": "local",
        "data_format": "image",
        "save_data": True,
        "save_correct": True,
        "column_id": "id",
        "column_content": "content",
        "column_image": "img",
        "custom_config": {
            "rule_list": ["RuleImageTextSimilarity"]
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    image_text_similar()
