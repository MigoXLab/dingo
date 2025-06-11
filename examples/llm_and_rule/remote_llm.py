from dingo.exec import Executor
from dingo.io import InputArgs

input_data = {
    "input_path": "../../test/data/test_local_jsonl.jsonl",  # local filesystem dataset
    "save_data": True,
    "save_correct": True,
    "dataset": "local",
    "data_format": "jsonl",
    "column_content": "content",
    "custom_config":
        {
            "prompt_list": ["PromptRepeat"],
            "llm_config": {
                "LLMTextQualityPromptBase": {
                    "model": "enter your llm, such as:deepseek-chat",
                    "key": "enter your key, such as:sk-123456789012345678901234567890xx",
                    "api_url": "enter remote llm api url, such as:https://api.deepseek.com/v1",
                }
            }
        },
    "log_level": "INFO"
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
