from dingo.exec import Executor
from dingo.io import InputArgs

input_data = {
    "input_path": "../../test/data/test_mtbench101_jsonl.jsonl",  # local filesystem dataset
    "save_data": True,
    "save_correct": True,
    "dataset": "local",
    "data_format": "multi_turn_dialog",
    "column_id": "id",
    "column_content": "history",  # the column name of multi-turn dialogues, e.g.: history, dialogues
    "custom_config":
        {
            "prompt_list": ["PromptTextQualityV3"],
            "llm_config": {
                "detect_text_quality_detail": {
                    "key": "",
                    "api_url": "",
                }
            },
            "multi_turn_mode": "all"
        }
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
