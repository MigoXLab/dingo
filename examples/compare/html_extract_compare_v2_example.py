"""
HTML 提取工具对比评估 V2 示例

这个示例展示了如何使用 LLMHtmlExtractCompareV2 来对比两种 HTML 提取工具的效果。

V2 版本的主要优势：
1. 使用 diff-match-patch 算法预先计算文本差异
2. 只向 LLM 提供独有内容和共同内容，大幅减少 token 消耗
3. 支持中英文双语评估
4. 使用 A/B/C 判断格式，评估结果更清晰

使用方法：
python examples/compare/html_extract_compare_v2_example.py
"""

import os

from dingo.io import Data
from dingo.model.llm.llm_html_extract_compare_v2 import LLMHtmlExtractCompareV2

OPENAI_MODEL = 'deepseek-chat'
OPENAI_URL = 'https://api.deepseek.com/v1'
OPENAI_KEY = os.getenv("OPENAI_KEY")

# 初始化模型
evaluator = LLMHtmlExtractCompareV2()
evaluator.dynamic_config.model = OPENAI_MODEL
evaluator.dynamic_config.key = OPENAI_KEY
evaluator.dynamic_config.api_url = OPENAI_URL

# 示例数据 - 中文网页
example_data_cn = Data(
    data_id="example_cn_001",  # 必需字段
    prompt="""# 机器学习简介

机器学习是人工智能的一个分支，它使计算机能够从数据中学习并做出决策。

## 主要类型

1. 监督学习
2. 无监督学习
3. 强化学习

机器学习在图像识别、自然语言处理等领域有广泛应用。

---
相关文章：
- 深度学习入门
- 神经网络基础
作者：张三
""",
    content="""# 机器学习简介

    机器学习是人工智能的一个分支，它使计算机能够从数据中学习并做出决策。

    ## 主要类型

    1. 监督学习
    2. 无监督学习
    3. 强化学习

    ## 应用场景

    机器学习在图像识别、自然语言处理、推荐系统等领域有广泛应用。

    ## 常用算法

    - 决策树
    - 支持向量机
    - 神经网络

    参考文献：
    [1] Mitchell, T. 1997. Machine Learning.
    """,
    raw_data={
        "language": "zh",  # 指定语言为中文
    }
)

# 示例数据 - 英文网页
example_data_en = Data(
    data_id="example_en_001",  # 必需字段
    prompt="""# Introduction to Machine Learning

Machine learning is a branch of artificial intelligence that enables computers to learn from data and make decisions.

## Main Types

1. Supervised Learning
2. Unsupervised Learning
3. Reinforcement Learning

Machine learning has wide applications in image recognition and natural language processing.

---
Related articles:
- Deep Learning Basics
- Neural Networks Introduction
Author: John Doe
""",
    content="""# Introduction to Machine Learning

    Machine learning is a branch of artificial intelligence that enables computers to learn from data and make decisions.

    ## Main Types

    1. Supervised Learning
    2. Unsupervised Learning
    3. Reinforcement Learning

    ## Application Scenarios

    Machine learning has wide applications in image recognition, natural language processing, and recommendation systems.

    ## Common Algorithms

    - Decision Trees
    - Support Vector Machines
    - Neural Networks

    References:
    [1] Mitchell, T. 1997. Machine Learning.
    """,
    raw_data={
        "language": "en",  # 指定语言为英文
    }
)


def run_comparison(data: Data, description: str):
    """运行对比评估"""
    print(f"\n{'=' * 60}")
    print(f"测试场景: {description}")
    print(f"{'=' * 60}\n")

    # 执行评估
    result = evaluator.eval(data)

    # 打印结果
    print(f"评估结果类型: {result.type}")
    print(f"判断名称: {result.name}")
    print(f"是否存在问题: {result.error_status}")
    print(f"\n推理过程:\n{result.reason[0]}")
    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    # 测试中文场景
    run_comparison(example_data_cn, "中文网页 - 对比两种HTML提取工具")

    # 测试英文场景
    # run_comparison(example_data_en, "英文网页 - 对比两种HTML提取工具")

    print("\n说明:")
    print("- 判断结果 A: Tool A 包含更多核心信息 (TOOL_ONE_BETTER)")
    print("- 判断结果 B: 两个工具提取的信息量相同 (TOOL_EQUAL)")
    print("- 判断结果 C: Tool B 包含更多核心信息 (TOOL_TWO_BETTER)")
