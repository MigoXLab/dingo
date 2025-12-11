import os

from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    # S3 配置信息
    # 可以从环境变量中获取，或者直接设置
    S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "your_access_key")
    S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "your_secret_key")
    S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "https://s3.amazonaws.com")
    S3_BUCKET = os.getenv("S3_BUCKET", "your_bucket_name")  # qa-huawei

    # LLM 配置信息
    OPENAI_MODEL = 'deepseek-chat'
    OPENAI_URL = 'https://api.deepseek.com/v1'
    OPENAI_KEY = os.getenv("OPENAI_KEY")

    input_data = {
        # 数据文件路径
        "input_path": "dingo/test_local_jsonl.jsonl",  # 单个文件路径
        # 或者 "input_path": "path/to/your/data/",  # 目录路径（以 / 结尾会读取目录下所有文件）

        # 数据集配置
        "dataset": {
            "source": "s3",  # 使用 S3 数据源
            "format": "jsonl",  # 支持 "jsonl" 或 "plaintext"
            "field": {
                "content": "content"  # 从 JSON 中提取的字段名
            },
            # S3 连接配置
            "s3_config": {
                "s3_ak": S3_ACCESS_KEY,
                "s3_sk": S3_SECRET_KEY,
                "s3_endpoint_url": S3_ENDPOINT_URL,
                "s3_bucket": S3_BUCKET,
                "s3_addressing_style": "path",  # 可选值: "path" 或 "virtual"
            }
        },

        # 执行器配置
        "executor": {
            "rule_list": ["RuleColonEnd"],
            "result_save": {
                "bad": True,
                "good": True
            }
        }

        # # 评估器配置
        # "evaluator": {
        #     "llm_config": {
        #         "LLMTextQualityPromptBase": {
        #             "model": OPENAI_MODEL,
        #             "key": OPENAI_KEY,
        #             "api_url": OPENAI_URL,
        #         }
        #     }
        # }
    }

    # 创建 InputArgs 实例
    input_args = InputArgs(**input_data)

    # 创建执行器
    executor = Executor.exec_map["local"](input_args)

    # 执行评估
    result = executor.execute()

    # 打印结果
    print(result)
