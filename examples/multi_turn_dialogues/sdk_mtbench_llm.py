from dingo.exec import Executor
from dingo.io import InputArgs

input_data = {
    "input_path": "lmsys/mt_bench_human_judgments",  # huggingface dataset
    "save_data": True,
    "save_correct": True,
    "end_index": 5,
    "data_format": "multi_turn_dialog",
    "huggingface_split": "human",
    "column_id": "question_id",
    "column_content": "conversation_a",  # the column name of multi-turn dialogues, e.g.: history, dialogues
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
