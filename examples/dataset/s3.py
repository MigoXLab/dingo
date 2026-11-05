import os

from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    # S3 配置信息
    # 可以从环境变量中获取，或者直接设置
    S3_ACCESS_KEY = ""
    S3_SECRET_KEY = ""
    S3_ENDPOINT_URL = ""
    S3_BUCKET = ""

    input_data = {
        # 数据文件路径；S3 数据源传对象 Key，不包含 s3://bucket/
        "input_path": "",
        # 单个文件示例："input_path": "path/to/your/data.jsonl",
        # 目录路径以 / 结尾，会读取目录下所有文件

        # 数据集配置
        "dataset": {
            "source": "s3",  # 使用 S3 数据源
            "format": "jsonl",  # 支持 "jsonl" 或 "plaintext"
            # S3 连接配置
            "s3_config": {
                "s3_ak": S3_ACCESS_KEY,
                "s3_sk": S3_SECRET_KEY,
                "s3_endpoint_url": S3_ENDPOINT_URL,
                "s3_bucket": S3_BUCKET,
                "s3_addressing_style": "path",  # 可选值: "path" 或 "virtual"
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
