from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": str(Path(__file__).parent.joinpath("../../test/data/test_img_md.jsonl").resolve()),
        "dataset": {
            "source": "local",
            "format": "image",
        },
        "executor": {
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": [
            {
                "fields": {"id": "id", "content": "content", "image": "img"},
                "evals": [
                    {"name": "VLMDocumentParsingQuality", "config": {"key": "", "api_url": ""}},
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
