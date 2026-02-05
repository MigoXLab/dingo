import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    # 获取项目根目录
    root_dir = Path(__file__).parent.parent.parent
    input_data = {
        "input_path": str(root_dir / "test/data/test_local_parquet.parquet"),
        "dataset": {
            "source": "local",
            "format": "parquet",
            "parquet_config": {
                "batch_size": 10000,  # 每次读取的行数
                # "columns": ["id", "content"],  # 可选：指定读取的列
            }
        },
        "executor": {
            "result_save": {
                "bad": True,
                "good": True,
                "raw": True,
            }
        },
        "evaluator": [
            {
                "fields": {"id":"id", "content": "content"},
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
