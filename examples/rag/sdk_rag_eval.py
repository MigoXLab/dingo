"""
简单的RAG指标测试脚本

用于快速验证RAG评估指标的实现是否正确（基于LLM评估器）

使用方法：
python simple_rag_test.py
"""

import os

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.rag.llm_rag_answer_relevancy import LLMRAGAnswerRelevancy
from dingo.model.llm.rag.llm_rag_context_precision import LLMRAGContextPrecision
from dingo.model.llm.rag.llm_rag_context_recall import LLMRAGContextRecall
from dingo.model.llm.rag.llm_rag_context_relevancy import LLMRAGContextRelevancy
from dingo.model.llm.rag.llm_rag_faithfulness import LLMRAGFaithfulness

# 配置（从环境变量读取，或直接设置）
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
OPENAI_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "YOUR_API_KEY")


def test_faithfulness():
    """测试忠实度指标"""
    print("\n" + "=" * 80)
    print("测试 Faithfulness (忠实度)")
    print("=" * 80)

    # 配置 LLM
    LLMRAGFaithfulness.dynamic_config = EvaluatorLLMArgs(
        key=OPENAI_KEY,
        api_url=OPENAI_URL,
        model=OPENAI_MODEL,
    )

    # 测试用例1: 忠实的答案
    data1 = Data(
        data_id="test_faithful",
        prompt="Python是什么时候发布的？",
        content="Python由Guido van Rossum创建，于1991年首次发布。",
        context=[
            "Python由Guido van Rossum设计，1991年首次发布。"
        ]
    )

    print("\n用例1 - 忠实的答案:")
    result1 = LLMRAGFaithfulness.eval(data1)
    print(f"  状态: {'✅ 通过' if not result1.status else '❌ 未通过'}")
    print(f"  详情: {result1}")

    # 测试用例2: 包含幻觉
    data2 = Data(
        data_id="test_hallucination",
        prompt="Python是什么时候发布的？",
        content="Python由Guido van Rossum创建，于1991年首次发布。它是第一种人工智能编程语言。",
        context=[
            "Python由Guido van Rossum设计，1991年首次发布。"
        ]
    )

    print("\n用例2 - 包含幻觉:")
    result2 = LLMRAGFaithfulness.eval(data2)
    print(f"  状态: {'✅ 通过' if not result2.status else '❌ 未通过'}")
    print(f"  详情: {result2}")
    print("\n预期: 用例2分数 < 用例1分数")

    return result1, result2


def test_context_precision():
    """测试上下文精度指标"""
    print("\n" + "=" * 80)
    print("测试 Context Precision (上下文精度)")
    print("=" * 80)

    # 配置 LLM
    LLMRAGContextPrecision.dynamic_config = EvaluatorLLMArgs(
        key=OPENAI_KEY,
        api_url=OPENAI_URL,
        model=OPENAI_MODEL,
    )

    data = Data(
        data_id="test_context_precision",
        prompt="深度学习的主要应用有哪些？",
        content="深度学习主要应用于计算机视觉、自然语言处理和语音识别领域。",
        context=[
            "深度学习在计算机视觉领域取得了突破性进展。",
            "自然语言处理是深度学习的重要应用领域。",
            "语音识别技术通过深度学习得到了显著改善。",
            "区块链是一种分布式账本技术。"  # 不相关
        ]
    )

    result = LLMRAGContextPrecision.eval(data)
    print(f"  状态: {'✅ 通过' if not result.status else '❌ 未通过'}")
    print(f"  详情: {result}")
    print("\n预期: 前3个上下文相关，最后1个不相关")

    return result


def test_answer_relevancy():
    """测试答案相关性指标"""
    print("\n" + "=" * 80)
    print("测试 Answer Relevancy (答案相关性)")
    print("=" * 80)

    # 配置 LLM
    LLMRAGAnswerRelevancy.dynamic_config = EvaluatorLLMArgs(
        key=OPENAI_KEY,
        api_url=OPENAI_URL,
        model=OPENAI_MODEL,
    )

    # 测试用例1: 相关的答案
    data1 = Data(
        data_id="test_relevant",
        prompt="什么是机器学习？",
        content="机器学习是人工智能的一个分支，它使计算机能够从数据中学习而无需明确编程。"
    )

    print("\n用例1 - 直接回答:")
    result1 = LLMRAGAnswerRelevancy.eval(data1)
    print(f"  状态: {'✅ 通过' if not result1.status else '❌ 未通过'}")
    print(f"  详情: {result1}")

    # 测试用例2: 包含无关信息
    data2 = Data(
        data_id="test_irrelevant",
        prompt="什么是机器学习？",
        content="机器学习是人工智能的一个分支。今天天气很好。神经网络很复杂。我喜欢编程。"
    )

    print("\n用例2 - 包含无关信息:")
    result2 = LLMRAGAnswerRelevancy.eval(data2)
    print(f"  状态: {'✅ 通过' if not result2.status else '❌ 未通过'}")
    print(f"  详情: {result2}")
    print("\n预期: 用例2分数 < 用例1分数")

    return result1, result2


def test_context_recall():
    """测试上下文召回指标"""
    print("\n" + "=" * 80)
    print("测试 Context Recall (上下文召回)")
    print("=" * 80)

    # 配置 LLM
    LLMRAGContextRecall.dynamic_config = EvaluatorLLMArgs(
        key=OPENAI_KEY,
        api_url=OPENAI_URL,
        model=OPENAI_MODEL,
    )

    # 测试用例1: 上下文完全支持答案
    data1 = Data(
        data_id="test_complete_recall",
        prompt="Python的主要特点是什么？",
        content="Python具有简洁的语法和丰富的库支持。",
        context=[
            "Python以其简洁易读的语法著称。",
            "Python拥有庞大的第三方库生态系统。"
        ]
    )

    print("\n用例1 - 上下文完全支持:")
    result1 = LLMRAGContextRecall.eval(data1)
    print(f"  状态: {'✅ 通过' if not result1.status else '❌ 未通过'}")
    print(f"  详情: {result1}")

    # 测试用例2: 上下文部分支持答案
    data2 = Data(
        data_id="test_partial_recall",
        prompt="Python的主要特点是什么？",
        content="Python具有简洁的语法、丰富的库支持和跨平台兼容性。",
        context=[
            "Python以其简洁易读的语法著称。"
            # 缺少关于库支持和跨平台的上下文
        ]
    )

    print("\n用例2 - 上下文部分支持:")
    result2 = LLMRAGContextRecall.eval(data2)
    print(f"  状态: {'✅ 通过' if not result2.status else '❌ 未通过'}")
    print(f"  详情: {result2}")
    print("\n预期: 用例2分数 < 用例1分数")

    return result1, result2


def test_context_relevancy():
    """测试上下文相关性指标"""
    print("\n" + "=" * 80)
    print("测试 Context Relevancy (上下文相关性)")
    print("=" * 80)

    # 配置 LLM
    LLMRAGContextRelevancy.dynamic_config = EvaluatorLLMArgs(
        key=OPENAI_KEY,
        api_url=OPENAI_URL,
        model=OPENAI_MODEL,
    )

    # 测试用例1: 所有上下文都相关
    data1 = Data(
        data_id="test_all_relevant",
        prompt="深度学习有哪些应用？",
        context=[
            "深度学习在图像识别领域应用广泛。",
            "自然语言处理是深度学习的重要应用。",
            "语音识别也使用深度学习技术。"
        ]
    )

    print("\n用例1 - 所有上下文相关:")
    result1 = LLMRAGContextRelevancy.eval(data1)
    print(f"  状态: {'✅ 通过' if not result1.status else '❌ 未通过'}")
    print(f"  详情: {result1}")

    # 测试用例2: 包含不相关上下文
    data2 = Data(
        data_id="test_mixed_relevancy",
        prompt="深度学习有哪些应用？",
        context=[
            "深度学习在图像识别领域应用广泛。",
            "区块链是一种分布式账本技术。",  # 不相关
            "天气预报需要气象数据。"  # 不相关
        ]
    )

    print("\n用例2 - 包含不相关上下文:")
    result2 = LLMRAGContextRelevancy.eval(data2)
    print(f"  状态: {'✅ 通过' if not result2.status else '❌ 未通过'}")
    print(f"  详情: {result2}")
    print("\n预期: 用例2分数 < 用例1分数")

    return result1, result2


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("RAG 指标简单测试")
    print("=" * 80)
    print(f"模型: {OPENAI_MODEL}")
    print(f"API: {OPENAI_URL}")

    # 运行所有测试
    test_faithfulness()
    test_context_precision()
    test_answer_relevancy()
    test_context_recall()
    test_context_relevancy()

    print("\n" + "=" * 80)
    print("✅ 测试完成！")
    print("=" * 80)
