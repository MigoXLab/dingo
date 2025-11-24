from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "lmsys/mt_bench_human_judgments",
        "dataset": {
            "source": "hugging_face",
            "format": "multi_turn_dialog",
            "hf_config": {
                "huggingface_split": "human"
            }
        },
        "executor": {
            "result_save": {
                "bad": True,
                "good": True
            },
            "end_index": 5,
            "multi_turn_mode": "all"
        },
        "evaluator": [
            {
                "fields": {"id": "question_id", "content": "conversation_a"},
                "evals": [
                    {"name": "LLMTextQualityV3", "config": {"key": "", "api_url": ""}}
                ],
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
