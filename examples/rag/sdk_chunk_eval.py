import argparse
import os
from typing import Dict

from dingo.config import InputArgs
from dingo.exec import Executor

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
OPENAI_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
EVALUATOR_NAME = "LLMChunkQuality"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="使用 evaluator 配置方式执行 Chunk 评测。")
    parser.add_argument("--input-jsonl", default="test/data/test_chunk.jsonl", help="输入 JSONL 路径")
    parser.add_argument("--content-field", default="text", help="输入中映射到 content 的字段名")
    parser.add_argument("--output-path", default="output/chunk_test_run", help="输出目录")
    parser.add_argument("--model", default=OPENAI_MODEL, help="LLM 模型名")
    parser.add_argument("--api-url", default=OPENAI_URL, help="LLM API 地址")
    parser.add_argument("--api-key", default=OPENAI_KEY, help="LLM API Key")
    parser.add_argument("--request-timeout", type=int, default=60, help="请求超时（秒）")
    parser.add_argument("--max-workers", type=int, default=10, help="并发 worker 数")
    parser.add_argument("--batch-size", type=int, default=10, help="批大小")
    return parser.parse_args()


def build_llm_config(args: argparse.Namespace) -> Dict:
    return {
        "model": args.model,
        "key": args.api_key,
        "api_url": args.api_url,
        "timeout": args.request_timeout,
    }


def build_input_data(args: argparse.Namespace, llm_config: Dict) -> Dict:
    return {
        "input_path": args.input_jsonl,
        "output_path": args.output_path,
        "dataset": {"source": "local", "format": "jsonl"},
        "executor": {
            "max_workers": args.max_workers,
            "batch_size": args.batch_size,
            "result_save": {"bad": True, "good": True},
        },
        "evaluator": [
            {
                "fields": {"content": args.content_field},
                "evals": [{"name": EVALUATOR_NAME, "config": llm_config}],
            }
        ],
    }


def run_evaluation(input_data: Dict):
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    return executor.execute()


def main():
    args = parse_args()
    if not args.api_key:
        raise ValueError("OPENAI_API_KEY 为空，请设置环境变量或通过 --api-key 传入。")

    llm_config = build_llm_config(args)
    input_data = build_input_data(args, llm_config)
    result = run_evaluation(input_data)

    print(result)
    print(f"[Done] output_path={args.output_path}")


if __name__ == "__main__":
    main()
