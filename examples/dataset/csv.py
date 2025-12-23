import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    # 获取项目根目录
    root_dir = Path(__file__).parent.parent.parent
    input_data = {
        "input_path": str(root_dir / "test/data/test_local_csv.csv"),
        "dataset": {
            "source": "local",
            "format": "csv",
            "csv_config": {
                "has_header": True,  # 第一行是否为列名
                "encoding": "utf-8",  # 文件编码
                "dialect": "excel",  # CSV 格式
                # "delimiter": ",",  # 可选：自定义分隔符
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
