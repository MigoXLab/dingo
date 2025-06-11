from dingo.exec import Executor
from dingo.io import InputArgs

input_data = {
    "input_path": "../../test/data/compare/test_compare_content.jsonl",
    "save_data": True,
    "save_correct": True,
    "save_raw": True,
    "batch_size": 10,
    "max_workers": 10,
    "dataset": "local",
    "data_format": "jsonl",
    "column_id": "track_id",
    "column_content": "clean_html",
    "custom_config":
        {
            "prompt_list": ["PromptHtmlAbstract"],
            "llm_config": {
                "LLMHtmlAbstract": {
                    "key": "",
                    "api_url": ""
                }
            }
        },
    "log_level": "INFO"
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
