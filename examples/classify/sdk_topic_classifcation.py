from dingo.exec import Executor
from dingo.io import InputArgs


def classify_topic():
    input_data = {
        "eval_group": "test",
        "input_path": "../../test/data/test_sft_jsonl.jsonl",  # local filesystem dataset
        "save_data": True,
        "save_correct": True,
        "dataset": "local",
        "data_format": "jsonl",
        "column_content": "question",
        "custom_config": {
            "prompt_list": ["PromptClassifyTopic"],
            "llm_config": {
                "LLMClassifyTopic": {
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
    classify_topic()
