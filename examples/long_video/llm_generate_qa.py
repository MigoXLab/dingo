from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "../../test/data/test_long_video_qa.jsonl",
        "dataset": {
            "source": "local",
            "format": "jsonl",
        },
        "executor": {
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": [
            {
                "fields": {"id": "video_id", "content": "summary"},
                "evals": [
                    {"name": "LLMLongVideoQa", "config": {"key": "sk-5b3e85f25d214c3b9c79ea62eab41e35", "api_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"}}
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
