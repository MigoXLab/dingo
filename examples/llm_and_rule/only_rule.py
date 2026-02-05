from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

if __name__ == '__main__':
    input_data = {
        "input_path": str(PROJECT_ROOT / "test/data/test_local_jsonl.jsonl"),
        "dataset": {
            "source": "local",
            "format": "jsonl",
        },
        "executor": {
            "result_save": {
                "merge": True,
            }
        },
        "evaluator": [
            {
                "fields": {"content": "content"},
                "evals": [
                    {"name": "RuleColonEnd"},
                    {"name": "RuleSpecialCharacter"}
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
