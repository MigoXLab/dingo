from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "../../test/data/test_dataman_jsonl.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "content": "content"
            }
        },
        "executor": {
            "prompt_list": ["PromptDataManAssessment"],
            "batch_size": 10,
            "max_workers": 10,
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMDatamanAssessment": {
                    "key": "enter your key, such as:EMPTY",
                    "api_url": "enter your local llm api url, such as:http://127.0.0.1:8080/v1",
                }
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
