import os

from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    # S3 配置信息
    # 可以从环境变量中获取，或者直接设置
    S3_ACCESS_KEY = ""
    S3_SECRET_KEY = ""
    S3_ENDPOINT_URL = ""

    input_data = {
        # 完整 S3 URI，包含 bucket 和对象 Key/前缀
        # 单个文件示例："input_path": "s3://bucket-name/path/to/data.jsonl",
        # 目录路径以 / 结尾，会读取目录下所有文件
        "input_path": "s3://bucket-name/path/to/your/data/",

        # 数据集配置
        "dataset": {
            "source": "s3",  # 使用 S3 数据源
            "format": "jsonl",  # 支持 "jsonl" 或 "plaintext"
            # S3 连接配置
            "s3_config": {
                "s3_ak": S3_ACCESS_KEY,
                "s3_sk": S3_SECRET_KEY,
                "s3_endpoint_url": S3_ENDPOINT_URL,
            }
        },
        "evaluator": [
            {
                "fields": {"content": "content"},
                "evals": [
                    {"name": "RuleColonEnd"}
                ]
            }
        ]
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
