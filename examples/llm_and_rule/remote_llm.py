from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "../../test/data/test_local_jsonl.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "content": "content"
            }
        },
        "executor": {
            "prompt_list": ["PromptRepeat"],
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMTextQualityPromptBase": {
                    "model": "enter your llm, such as:deepseek-chat",
                    "key": "enter your key, such as:sk-123456789012345678901234567890xx",
                    "api_url": "enter remote llm api url, such as:https://api.deepseek.com/v1",
                }
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
