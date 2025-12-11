"""
HTML 提取工具对比评估 - Dataset 批量执行示例

这个示例展示了如何使用 Executor 批量评估 JSONL 数据集中的 HTML 提取工具对比任务。

特点：
1. 支持从 JSONL 文件批量读取数据
2. 使用 LLMHtmlExtractCompareV2 进行评估
3. 自动生成评估报告
4. 支持保存好样本和坏样本

数据格式要求：
{
    "data_id": "唯一标识",
    "content": "工具A提取的文本",
    "magic_md": "工具B提取的文本",
    "language": "zh" 或 "en"
}

使用方法：
python examples/compare/dataset_html_extract_compare_evaluation.py
"""

import os
from pathlib import Path

from dingo.config.input_args import InputArgs
from dingo.exec.base import Executor

# API 配置
OPENAI_MODEL = 'deepseek-chat'
OPENAI_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")


def evaluate_html_extract_compare_dataset():
    """
    批量评估 HTML 提取工具对比数据集

    数据集格式：
    {"data_id": "001", "content": "工具A文本", "magic_md": "工具B文本", "language": "zh"}
    """
    print("=== HTML Extract Compare Dataset Evaluation ===")
    print(f"使用模型: {OPENAI_MODEL}")
    print(f"API URL: {OPENAI_URL}")
    print()

    # 配置参数
    input_data = {
        "task_name": "html_extract_compare_v2_evaluation",
        "input_path": str(Path("test/data/html_extract_compare_test.jsonl")),
        "output_path": "output/html_extract_compare_evaluation/",
        # "log_level": "INFO",

        # 数据集配置
        "dataset": {
            "source": "local",  # 本地数据源
            "format": "jsonl",  # JSONL 格式
            "field": {
                "id": "data_id",  # data_id 字段映射
                "prompt": "content",  # prompt 字段映射
                "content": "magic_md",  # content 字段映射
                # language 会自动放入 raw_data
            }
        },

        # 执行器配置
        "executor": {
            "eval_group": "html_extract_compare",  # 使用 html_extract_compare 评估组
            "max_workers": 4,  # 并发数
            "batch_size": 1,  # 批次大小
            "result_save": {
                "bad": True,  # 保存工具B更好的样本（error_status=True）
                "good": True  # 保存工具A更好或相同的样本
            }
        },

        # 评估器配置
        "evaluator": {
            "llm_config": {
                "LLMHtmlExtractCompareV2": {
                    "model": OPENAI_MODEL,
                    "key": OPENAI_KEY,
                    "api_url": OPENAI_URL,
                }
            }
        }
    }

    # 创建 InputArgs 并执行
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)

    print("开始执行评估...")
    result = executor.execute()

    # 打印结果
    print("\n" + "=" * 60)
    print("评估完成！")
    print("=" * 60)
    print(f"任务名称: {result.task_name}")
    print(f"评估组: {result.eval_group}")
    print(f"总样本数: {result.total}")
    print(f"工具B更好的样本数: {result.num_bad} ")
    print(f"工具A更好或相同: {result.num_good} ")
    print(f"\n输出路径: {result.output_path}")

    # 打印详细统计
    if hasattr(result, 'type_count') and result.type_count:
        print("\n详细统计:")
        for eval_type, count in result.type_count.items():
            print(f"  - {eval_type}: {count}")

    print("=" * 60)

    return result


if __name__ == "__main__":
    evaluate_html_extract_compare_dataset()
