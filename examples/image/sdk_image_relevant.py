from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

SCRIPT_DIR = Path(__file__).parent


def image_relevant():
    input_data = {
        "input_path": str(SCRIPT_DIR.joinpath("../../test/data/test_img_jsonl.jsonl").resolve()),
        "output_path": "output/hallucination_evaluation/",
        "dataset": {
            "source": "local",
            "format": "jsonl",
        },
        "executor": {
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": [
            {
                "fields": {"id": "id", "prompt": "url_1", "content": "url_2"},
                "evals": [
                    {"name": "VLMImageRelevant", "config": {"model": "", "key": "", "api_url": ""}},
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == '__main__':
    image_relevant()
