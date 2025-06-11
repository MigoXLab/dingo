from dingo.exec import Executor
from dingo.io import InputArgs

input_data = {
    "input_path": "../../test/data/test_dataman_jsonl.jsonl",  # local filesystem dataset
    "save_data": True,
    "save_correct": True,
    "dataset": "local",
    "data_format": "jsonl",
    "column_content": "content",
    "custom_config":
        {
            "prompt_list": ["PromptDataManAssessment"],
            "llm_config": {
                "dataman_assessment": {
                    "key": "enter your key, such as:EMPTY",
                    "api_url": "enter your local llm api url, such as:http://127.0.0.1:8080/v1",
                }
            }
        },
    "log_level": "INFO"
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
