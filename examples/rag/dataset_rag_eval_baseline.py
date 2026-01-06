"""
使用扩展的 SummaryModel 进行 RAG 批量评估
展示如何自动收集和计算指标平均分数

特点：
    1. 使用标准 Dingo 框架（InputArgs + Executor）
    2. 自动收集每个评估的分数
    3. 自动计算平均值、最小值、最大值、标准差
    4. 结果自动保存到 summary.json 中

评测数据集:
    fiqa.jsonl 的字段: user_input, reference, response, retrieved_contexts
        - user_input: 问题
        - reference: 标准答案
        - response: RAG生成的答案
        - retrieved_contexts: 检索的上下文

    ragflow_eval_data_50.jsonl 的字段: question, response, retrieved_contexts, reference
        - question: 问题
        - response: RAG生成的答案
        - retrieved_contexts: 检索的上下文
        - reference: 标准答案

使用方法：
    python dataset_rag_eval_with_metrics.py
"""

import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor
from dingo.io.output.summary_model import SummaryModel

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 配置（从环境变量读取）
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "doubao-embedding-large-text-250515")

# 数据文件路径
INPUT_DATA_PATH = str(PROJECT_ROOT / "test/data/fiqa.jsonl")  # 或 "test/data/ragflow_eval_data_50.jsonl"


def print_metrics_summary(summary: SummaryModel):
    """打印指标统计摘要（支持按字段分组）"""
    # print(summary.to_dict())  # 如果需要看完整输出，取消注释

    if not summary.metrics_score_stats:
        print("⚠️  没有指标统计数据")
        return

    print("\n" + "=" * 80)
    print("📊 RAG 评估指标统计")
    print("=" * 80)

    # 遍历每个字段组
    for field_key, metrics in summary.metrics_score_stats.items():
        print(f"\n📁 字段组: {field_key}")
        print("-" * 80)

        # 打印该字段组的每个指标详细统计
        for metric_name, stats in metrics.items():
            # 简化指标名称显示
            display_name = metric_name.replace("LLMRAG", "")
            print(f"\n  {display_name}:")
            print(f"    平均分: {stats.get('score_average', 0):.2f}")
            print(f"    最小分: {stats.get('score_min', 0):.2f}")
            print(f"    最大分: {stats.get('score_max', 0):.2f}")
            print(f"    样本数: {stats.get('score_count', 0)}")
            if 'score_std_dev' in stats:
                print(f"    标准差: {stats.get('score_std_dev', 0):.2f}")

        # 打印该字段组的总平均分
        overall_avg = summary.get_metrics_score_overall_average(field_key)
        print(f"\n  🎯 该字段组总平均分: {overall_avg:.2f}")

        # 打印该字段组的指标排名（从高到低）
        metrics_summary = summary.get_metrics_score_summary(field_key)
        sorted_metrics = sorted(metrics_summary.items(), key=lambda x: x[1], reverse=True)

        print("\n  📈 指标排名（从高到低）:")
        for i, (metric_name, avg_score) in enumerate(sorted_metrics, 1):
            display_name = metric_name.replace("LLMRAG", "")
            print(f"    {i}. {display_name}: {avg_score:.2f}")

    # 如果有多个字段组，打印总体统计
    if len(summary.metrics_score_stats) > 1:
        print("\n" + "=" * 80)
        print("🌍 所有字段组总体统计")
        print("=" * 80)
        for field_key in summary.metrics_score_stats.keys():
            overall_avg = summary.get_metrics_score_overall_average(field_key)
            print(f"  {field_key}: {overall_avg:.2f}")

    print("\n" + "=" * 80)


def run_rag_evaluation():
    """
    运行 RAG 评估并自动收集指标统计
    """
    print("=" * 80)
    print("使用 Dingo 框架进行 RAG 评估（自动收集指标统计）")
    print("=" * 80)
    print(f"数据文件: {INPUT_DATA_PATH}")
    print(f"模型: {OPENAI_MODEL}")
    print(f"API: {OPENAI_URL}")
    print("=" * 80)

    llm_config = {
        "model": OPENAI_MODEL,
        "key": OPENAI_KEY,
        "api_url": OPENAI_URL,
    }

    llm_config_embedding = {
        "model": OPENAI_MODEL,
        "key": OPENAI_KEY,
        "api_url": OPENAI_URL,
        "parameters": {
            "embedding_model": EMBEDDING_MODEL,
            "strictness": 3,
            "threshold": 5
        }
    }

    # 构建配置
    input_data = {
        "task_name": "rag_evaluation_with_metrics",
        "input_path": INPUT_DATA_PATH,
        "output_path": "outputs/",
        # "log_level": "INFO",
        "dataset": {
            "source": "local",
            "format": "jsonl",
        },
        "executor": {
            "max_workers": 10,  # RAG 评估建议串行执行
            "batch_size": 10,
            "result_save": {
                "good": True,
                "bad": True,
                "all_labels": True
            }
        },
        "evaluator": [
            {
                # fiqa.jsonl 的字段: user_input, reference, response, retrieved_contexts
                "fields": {
                    "prompt": "user_input",           # 问题
                    "content": "response",            # RAG生成的答案
                    "context": "retrieved_contexts",  # 检索的上下文
                    "reference": "reference"          # 标准答案（可选）
                },
                # # ragflow_eval_data_50.jsonl 的字段: question, response, retrieved_contexts, reference
                # "fields": {
                #     "prompt": "question",           # 问题
                #     "content": "response",            # RAG生成的答案
                #     "context": "retrieved_contexts",  # 检索的上下文
                #     "reference": "reference"          # 标准答案（可选）
                # },
                "evals": [
                    {
                        "name": "LLMRAGFaithfulness",
                        "config": llm_config
                    },
                    {
                        "name": "LLMRAGContextPrecision",
                        "config": llm_config
                    },
                    {
                        "name": "LLMRAGContextRecall",
                        "config": llm_config
                    },
                    {
                        "name": "LLMRAGContextRelevancy",
                        "config": llm_config
                    },
                    # Answer Relevancy 需要 Embedding API
                    # 如果您的 API 支持 embeddings 端点，可以启用此项
                    {
                        "name": "LLMRAGAnswerRelevancy",
                        "config": llm_config_embedding
                    }
                ]
            }
        ]
    }

    # 创建 InputArgs 并执行
    print("\n开始评估...")
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    summary = executor.execute()

    # 打印基本统计信息
    print("\n" + "=" * 80)
    print("✅ 评估完成！")
    print("=" * 80)
    print(f"输出目录: {summary.output_path}")
    print(f"总数据量: {summary.total}")
    print(f"通过: {summary.num_good}")
    print(f"未通过: {summary.num_bad}")
    print(f"通过率: {summary.score}%")

    # 打印指标统计摘要（使用新功能）
    print_metrics_summary(summary)

    print(f"\n💾 详细结果已保存到: {summary.output_path}/summary.json")
    print("    metrics_score (层级结构):")
    print("      - stats: 每个指标的详细统计")
    print("      - summary: 各指标平均分汇总")
    print("      - overall_average: 总平均分")

    return summary


if __name__ == "__main__":
    summary = run_rag_evaluation()
