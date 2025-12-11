"""
Dataset Factuality Evaluation Example

This example demonstrates how to use Dingo's factuality evaluation capability
for batch evaluation of datasets, particularly useful for:
- LLM response validation
- RAG system evaluation
- SFT data quality assessment
"""
import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor
from dingo.io import Data
# Force import factuality evaluation modules
from dingo.model.llm.llm_factcheck_public import LLMFactCheckPublic
from dingo.model.prompt.prompt_factcheck import PromptFactCheck

OPENAI_MODEL = 'deepseek-chat'
OPENAI_URL = 'https://api.deepseek.com/v1'
OPENAI_KEY = os.getenv("OPENAI_KEY")


def evaluate_factuality_jsonl_dataset():
    """
    Example: Evaluate a JSONL dataset for factuality
    Expected JSONL format:
    {"data_id": "1", "prompt": "question", "content": "response"}
    """
    print("=== Dataset Factuality Evaluation ===")

    input_data = {
        "input_path": str(Path("test/data/factcheck_test.jsonl")),  # Your JSONL file path
        "output_path": "output/factcheck_evaluation/",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "prompt": "question",  # 注意这里使用 question 作为 prompt 字段
                "content": "content"
            }
        },
        "executor": {
            "eval_group": "factuality",  # 使用 factuality 评估组
            "result_save": {
                "bad": True,  # 保存不实信息
                "good": True  # 保存真实信息
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMFactCheckPublic": {
                    "model": OPENAI_MODEL,
                    "key": OPENAI_KEY,
                    "api_url": OPENAI_URL,
                }
            }
        }
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()

    print("\n=== Evaluation Summary ===")
    print(f"Total processed: {result.total}")
    print(f"Factual responses: {result.num_good}")
    print(f"Non-factual responses: {result.num_bad}")
    print(f"Overall factuality score: {result.score:.2%}")
    print(f"\nType distribution: {result.type_ratio}")
    print(f"Name distribution: {result.name_ratio}")


def evaluate_single_data_example():
    """
    Example: Evaluate a single piece of data for factuality
    This is useful for testing or real-time evaluation
    """
    print("=== Single Data Factuality Evaluation ===")

    # 配置评估器
    evaluator = LLMFactCheckPublic()
    evaluator.dynamic_config.model = OPENAI_MODEL
    evaluator.dynamic_config.key = OPENAI_KEY
    evaluator.dynamic_config.api_url = OPENAI_URL
    evaluator.dynamic_config.parameters = {
        "temperature": 0.1,  # 降低随机性以提高一致性
        "max_tokens": 2000
    }

    # 创建测试数据
    test_data = Data(
        data_id="test_1",
        prompt="Tell me about Albert Einstein's Nobel Prize.",
        content="Albert Einstein won the Nobel Prize in Physics in 1921 for his work on the photoelectric effect. However, many people mistakenly think he won it for his theory of relativity, which actually never received a Nobel Prize due to the controversial nature of relativity at the time."
    )
    # 执行评估
    result = evaluator.eval(test_data)

    print("\n=== Evaluation Result ===")
    print(f"Error Status: {result.error_status}")
    print(f"Type: {result.type}")
    print(f"Name: {result.name}")
    print(f"Reason: {result.reason}")


if __name__ == "__main__":
    print("📊 Dingo Factuality Evaluation Examples")
    print("=" * 60)
    print()

    # Run examples
    # print("1. Dataset Evaluation Example")
    # print("-" * 30)
    # evaluate_factuality_jsonl_dataset()

    print("2. Single Data Evaluation Example")
    print("-" * 30)
    evaluate_single_data_example()
