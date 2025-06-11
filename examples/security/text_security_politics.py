from dingo.exec import Executor
from dingo.io import InputArgs

input_data = {
    "input_path": "../../test/data/test_local_jsonl.jsonl",
    "save_data": True,
    "save_correct": True,
    "dataset": "local",
    "data_format": "jsonl",
    "column_content": "content",
    "custom_config": {
        "prompt_list": ["PromptPolitics"],
        "llm_config": {
            "LLMSecurityPolitics": {
                "key": "",
                "api_url": "",
            }
        }
    },
    "log_level": "INFO"
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
