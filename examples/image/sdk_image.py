from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


def image():
    input_data = {
        "input_path": str(PROJECT_ROOT / "test/data/test_local_img.jsonl"),
        "dataset": {
            "source": "local",
            "format": "image",
            "field": {
                "id": "id",
                "image": "img"
            }
        },
        "executor": {
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": [
            {
                "fields": {"id": "id", "image": "img"},
                "evals": [
                    {"name": "RuleImageValid"},
                    {"name": "RuleImageSizeValid"},
                    {"name": "RuleImageQuality"},
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    image()
