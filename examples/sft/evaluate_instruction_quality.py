"""
SFT Instruction Quality Evaluation - 指令质量评估

评估 SFT 数据中 query/instruction 的质量，包括：
1. 指令清晰度 (Instruction Clarity)
2. 任务难度 (Task Difficulty)

基于最新研究:
- IFEval: Instruction Following Evaluation (Google, 2023)
- Self-Instruct (University of Washington, 2023)
- Task Complexity in Instruction Following (Google DeepMind, 2023)
"""
import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

# 配置
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")


def evaluate_instruction_clarity():
    """评估指令清晰度"""
    print("=" * 80)
    print("  评估指令清晰度 (Instruction Clarity)")
    print("=" * 80 + "\n")

    input_data = {
        "task_name": "instruction_clarity_evaluation",
        "input_path": str(Path("test/data/instructions.jsonl")),  # 格式: {"instruction": "你的指令"}
        "output_path": "outputs/instruction_clarity/",
        "dataset": {
            "source": "local",
            "format": "jsonl"
        },
        "executor": {
            "max_workers": 5,  # LLM 评估建议较低并发
            "result_save": {
                "bad": True,   # 保存不清晰的指令
                "good": True,  # 也保存清晰的指令用于分析
                "all_labels": True
            }
        },
        "evaluator": [
            {
                "fields": {
                    "content": "instruction"  # 将 instruction 字段映射到 content
                },
                "evals": [
                    {
                        "name": "LLMInstructionClarity",
                        "config": {
                            "model": OPENAI_MODEL,
                            "key": OPENAI_API_KEY,
                            "api_url": OPENAI_BASE_URL,
                            "parameters": {
                                "threshold": 6.0  # 清晰度阈值 (0-10)
                            }
                        }
                    }
                ]
            }
        ]
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    summary = executor.execute()

    print("\n" + "=" * 80)
    print("  评估结果")
    print("=" * 80)
    print(f"总数: {summary.total}")
    print(f"清晰指令: {summary.num_good} ({summary.score:.1f}%)")
    print(f"不清晰指令: {summary.num_bad}")
    print(f"输出路径: {summary.output_path}")

    # 显示清晰度问题分布
    if summary.type_ratio:
        print("\n问题类型分布:")
        # type_ratio 是嵌套字典: {"instruction": {"TYPE": ratio}}
        for field, ratios in summary.type_ratio.items():
            if isinstance(ratios, dict):
                for issue_type, ratio in sorted(ratios.items(), key=lambda x: x[1], reverse=True):
                    if "CLARITY" in issue_type:
                        print(f"  {issue_type}: {ratio * 100:.1f}%")
            else:
                print(f"  {field}: {ratios * 100:.1f}%")

    return summary


def evaluate_task_difficulty():
    """评估任务难度"""
    print("=" * 80)
    print("  评估任务难度 (Task Difficulty)")
    print("=" * 80 + "\n")

    input_data = {
        "task_name": "task_difficulty_evaluation",
        "input_path": str(Path("test/data/instructions.jsonl")),
        "output_path": "outputs/task_difficulty/",
        "dataset": {
            "source": "local",
            "format": "jsonl"
        },
        "executor": {
            "max_workers": 5,
            "result_save": {
                "bad": False,  # 难度评估通常不需要保存"bad"
                "good": True,  # 保存所有评估结果
                "all_labels": True
            }
        },
        "evaluator": [
            {
                "fields": {
                    "content": "instruction"
                },
                "evals": [
                    {
                        "name": "LLMTaskDifficulty",
                        "config": {
                            "model": OPENAI_MODEL,
                            "key": OPENAI_API_KEY,
                            "api_url": OPENAI_BASE_URL,
                            "parameters": {
                                # 可选：设置期望的难度范围
                                # "min_difficulty": 4.0,  # 最低难度（太简单的会被标记）
                                # "max_difficulty": 8.0,  # 最高难度（太难的会被标记）
                            }
                        }
                    }
                ]
            }
        ]
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    summary = executor.execute()

    print("\n" + "=" * 80)
    print("  评估结果")
    print("=" * 80)
    print(f"总数: {summary.total}")
    print(f"输出路径: {summary.output_path}")

    # 显示难度级别分布
    if summary.type_ratio:
        print("\n难度级别分布:")
        # type_ratio 是嵌套字典: {"instruction": {"LEVEL": ratio}}
        for field, ratios in summary.type_ratio.items():
            if isinstance(ratios, dict):
                for level, ratio in sorted(ratios.items(), key=lambda x: x[1], reverse=True):
                    if "TASK_DIFFICULTY" in level:
                        print(f"  {level}: {ratio * 100:.1f}%")
            else:
                print(f"  {field}: {ratios * 100:.1f}%")

    return summary


def evaluate_both():
    """同时评估指令清晰度和任务难度"""
    print("=" * 80)
    print("  综合指令质量评估 (Clarity + Difficulty)")
    print("=" * 80 + "\n")

    input_data = {
        "task_name": "comprehensive_instruction_evaluation",
        "input_path": "test/data/instructions.jsonl",
        "output_path": "outputs/instruction_comprehensive/",
        "dataset": {
            "source": "local",
            "format": "jsonl"
        },
        "executor": {
            "max_workers": 5,
            "result_save": {
                "bad": True,
                "good": True,
                "all_labels": True
            }
        },
        "evaluator": [
            {
                "fields": {
                    "content": "instruction"
                },
                "evals": [
                    {
                        "name": "LLMInstructionClarity",
                        "config": {
                            "model": OPENAI_MODEL,
                            "key": OPENAI_API_KEY,
                            "api_url": OPENAI_BASE_URL,
                            "parameters": {"threshold": 6.0}
                        }
                    },
                    {
                        "name": "LLMTaskDifficulty",
                        "config": {
                            "model": OPENAI_MODEL,
                            "key": OPENAI_API_KEY,
                            "api_url": OPENAI_BASE_URL,
                            "parameters": {
                                "min_difficulty": 3.0,  # 过滤太简单的任务
                                "max_difficulty": 9.0,  # 过滤过于困难的任务
                            }
                        }
                    }
                ]
            }
        ]
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    summary = executor.execute()

    print("\n" + "=" * 80)
    print("  综合评估结果")
    print("=" * 80)
    print(f"总数: {summary.total}")
    print(f"通过所有检查: {summary.num_good} ({summary.score:.1f}%)")
    print(f"存在问题: {summary.num_bad}")
    print(f"输出路径: {summary.output_path}")

    # 获取详细结果进行分析
    bad_list = executor.get_bad_info_list()
    if bad_list:
        print("\n问题分析:")
        clarity_issues = sum(1 for item in bad_list
                           if any('CLARITY' in label for label in item.get('labels', [])))
        difficulty_issues = sum(1 for item in bad_list
                              if any('DIFFICULTY' in label or 'TOO_EASY' in label or 'TOO_HARD' in label
                                   for label in item.get('labels', [])))

        print(f"  清晰度问题: {clarity_issues}")
        print(f"  难度问题: {difficulty_issues}")

    return summary


def analyze_difficulty_distribution():
    """分析任务难度分布（用于数据集平衡）"""
    print("=" * 80)
    print("  任务难度分布分析")
    print("=" * 80 + "\n")

    input_data = {
        "task_name": "difficulty_distribution_analysis",
        "input_path": "test/data/instructions.jsonl",
        "output_path": "outputs/difficulty_distribution/",
        "dataset": {
            "source": "local",
            "format": "jsonl"
        },
        "executor": {
            "max_workers": 10,
            "result_save": {
                "bad": False,
                "good": True,
                "all_labels": True
            }
        },
        "evaluator": [
            {
                "fields": {"content": "instruction"},
                "evals": [
                    {
                        "name": "LLMTaskDifficulty",
                        "config": {
                            "model": OPENAI_MODEL,
                            "key": OPENAI_API_KEY,
                            "api_url": OPENAI_BASE_URL
                        }
                    }
                ]
            }
        ]
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    summary = executor.execute()

    # 分析结果
    good_list = executor.get_good_info_list()

    # 统计难度分布
    difficulty_counts = {
        "Easy (0-3)": 0,
        "Moderate (4-6)": 0,
        "Hard (7-8)": 0,
        "Expert (9-10)": 0
    }

    total_score = 0
    for item in good_list:
        eval_details = item.get('eval_details', {})
        for field, details in eval_details.items():
            for detail in details:
                if detail.get('metric') == 'LLMTaskDifficulty':
                    score = detail.get('score', 0)
                    total_score += score

                    if score <= 3:
                        difficulty_counts["Easy (0-3)"] += 1
                    elif score <= 6:
                        difficulty_counts["Moderate (4-6)"] += 1
                    elif score <= 8:
                        difficulty_counts["Hard (7-8)"] += 1
                    else:
                        difficulty_counts["Expert (9-10)"] += 1

    print("\n" + "=" * 80)
    print("  难度分布分析")
    print("=" * 80)
    print(f"总数: {len(good_list)}")
    if good_list:
        print(f"平均难度: {total_score / len(good_list):.2f}/10")
    print("\n难度级别分布:")
    for level, count in difficulty_counts.items():
        percentage = (count / len(good_list) * 100) if good_list else 0
        print(f"  {level}: {count} ({percentage:.1f}%)")

    print("\n💡 数据集平衡建议:")
    # 理想分布: Easy 20%, Moderate 50%, Hard 25%, Expert 5%
    if difficulty_counts["Easy (0-3)"] / len(good_list) > 0.3:
        print("  ⚠️  简单任务过多，考虑增加难度或过滤部分简单任务")
    if difficulty_counts["Moderate (4-6)"] / len(good_list) < 0.3:
        print("  ⚠️  中等难度任务不足，这是 SFT 的核心部分")
    if difficulty_counts["Hard (7-8)"] / len(good_list) > 0.4:
        print("  ⚠️  困难任务过多，可能影响训练效率")

    return summary


if __name__ == "__main__":
    import sys

    if not OPENAI_API_KEY:
        print("❌ 错误: 请设置 OPENAI_API_KEY 环境变量")
        print("   export OPENAI_API_KEY='your-api-key'")
        sys.exit(1)

    # 选择评估模式
    mode = sys.argv[1] if len(sys.argv) > 1 else "both"

    print(f"\n{'=' * 80}")
    print("  SFT 指令质量评估系统")
    print(f"  模式: {mode}")
    print(f"{'=' * 80}\n")

    if mode == "clarity":
        evaluate_instruction_clarity()
    elif mode == "difficulty":
        evaluate_task_difficulty()
    elif mode == "distribution":
        analyze_difficulty_distribution()
    else:
        evaluate_both()

    print("\n✅ 评估完成！\n")
    print("💡 提示:")
    print("  - 使用 'clarity' 模式只评估清晰度")
    print("  - 使用 'difficulty' 模式只评估难度")
    print("  - 使用 'distribution' 模式分析难度分布")
    print("  - 使用 'both' 模式（默认）进行综合评估")
