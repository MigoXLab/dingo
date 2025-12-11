from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "../../test/data/test_layout_quality.jsonl",
        "dataset": {
            "source": "local",
            "format": "image",
            "field": {
                "id": "id",
                "content": "pred",
                "image": "image_path"
            }
        },
        "executor": {
            "prompt_list": ["PromptLayoutQuality"],
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "llm_config": {
                "VLMLayoutQuality": {
                    "model": "",
                    "key": "",
                    "api_url": "",
                }
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
