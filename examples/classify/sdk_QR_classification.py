from dingo.exec import Executor
from dingo.io import InputArgs


def classify_QR():
    input_data = {
        "eval_group": "test",
        "input_path": "../../test/data/test_imgQR_jsonl.jsonl",  # local filesystem dataset
        "dataset": "local",
        "data_format": "jsonl",
        "save_data": True,
        "save_correct": True,
        "column_id": "id",
        "column_content": "content",
        "custom_config": {
            "prompt_list": ["PromptClassifyQR"],
            "llm_config": {
                "LLMClassifyQR": {
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


if __name__ == '__main__':
    classify_QR()
