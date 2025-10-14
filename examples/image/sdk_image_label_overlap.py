from dingo.config import InputArgs
from dingo.exec import Executor


def image_label_overlap():
    input_data = {
        "input_path": "../../test/data/img_label/test_img_label_overlap.jsonl",
        "dataset": {
            "source": "local",
            "format": "image",
            "field": {
                "id": "id",
                "content": "content",
                "image": "img"
            }
        },
        "executor": {
            "rule_list": ["RuleImageLabelOverlap"],
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


if __name__ == '__main__':
    image_label_overlap()
