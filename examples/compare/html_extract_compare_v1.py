from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "../../test/data/compare/old_new_compare_10000.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
        },
        "executor": {
            "batch_size": 10,
            "max_workers": 10,
            "result_save": {
                "bad": True,
                "good": True,
                "raw": True
            }
        },
        "evaluator": [
            {
                "fields": {"id": "track_id", "content": "clean_html"},
                "evals": [
                    {"name": "LLMHtmlExtractCompare", "config": {"key": "", "api_url": ""}}
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
