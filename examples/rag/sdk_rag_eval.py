"""
简单的RAG指标测试脚本

用于快速验证RAG评估指标的实现是否正确（基于LLM评估器）

使用方法：
python simple_rag_test.py
"""

import csv
import json
import logging
import os
import time

# 配置日志文件路径
LOG_FILE_PATH = "rag_eval_log.txt"

# 配置Python标准日志：同时输出到控制台和文件
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, encoding='utf-8'),  # 保存到文件
        logging.StreamHandler()  # 输出到控制台
    ]
)

# 创建logger对象用于记录日志
logger = logging.getLogger(__name__)

# 配置Dingo项目的日志模块为INFO级别
from dingo.utils import log

log.setLevel('INFO')

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.rag.llm_rag_answer_relevancy import LLMRAGAnswerRelevancy
from dingo.model.llm.rag.llm_rag_context_precision import LLMRAGContextPrecision
from dingo.model.llm.rag.llm_rag_context_recall import LLMRAGContextRecall
from dingo.model.llm.rag.llm_rag_context_relevancy import LLMRAGContextRelevancy
from dingo.model.llm.rag.llm_rag_faithfulness import LLMRAGFaithfulness

# 配置（从环境变量读取，或直接设置）
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_URL = os.getenv("OPENAI_BASE_URL", "")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

# Embedding模型配置（从环境变量读取，或直接设置）
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

# 输入文件路径配置
CSV_FILE_PATH = "D:\\lld\\PycharmProjects\\dingo\\examples\\rag\\ragflow_eval_data_50.jsonl"  # 支持CSV和JSONL格式



def test_faithfulness():
    """测试忠实度指标"""
    logger.info("\n" + "=" * 80)
    logger.info("测试 Faithfulness (忠实度)")
    logger.info("=" * 80)
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

    logger.info("\n用例1 - 忠实的答案:")
    print("\n用例1 - 忠实的答案:")
    result1 = LLMRAGFaithfulness.eval(data1)
    logger.info(f"  状态: {'✅ 通过' if not result1.eval_status else '❌ 未通过'}")
    logger.info(f"  分数: {result1.score}/10")
    print(f"  状态: {'✅ 通过' if not result1.eval_status else '❌ 未通过'}")
    print(f"  分数: {result1.score}/10")

    # 测试用例2: 包含幻觉
    data2 = Data(
        data_id="test_hallucination",
        prompt="Python是什么时候发布的？",
        content="Python由Guido van Rossum创建，于1991年首次发布。它是第一种人工智能编程语言。",
        context=[
            "Python由Guido van Rossum设计，1991年首次发布。"
        ]
    )

    logger.info("\n用例2 - 包含幻觉:")
    print("\n用例2 - 包含幻觉:")
    result2 = LLMRAGFaithfulness.eval(data2)
    logger.info(f"  状态: {'✅ 通过' if not result2.eval_status else '❌ 未通过'}")
    logger.info(f"  分数: {result2.score}/10")
    logger.info("\n预期: 用例2分数 < 用例1分数")
    print(f"  状态: {'✅ 通过' if not result2.eval_status else '❌ 未通过'}")
    print(f"  分数: {result2.score}/10")
    print("\n预期: 用例2分数 < 用例1分数")

    return result1, result2


def test_context_precision():
    """测试上下文精度指标"""
    logger.info("\n" + "=" * 80)
    logger.info("测试 Context Precision (上下文精度)")
    logger.info("=" * 80)
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
    logger.info(f"  状态: {'✅ 通过' if not result.eval_status else '❌ 未通过'}")
    logger.info(f"  分数: {result.score}/10")
    logger.info("\n预期: 前3个上下文相关，最后1个不相关")
    print(f"  状态: {'✅ 通过' if not result.eval_status else '❌ 未通过'}")
    print(f"  分数: {result.score}/10")
    print("\n预期: 前3个上下文相关，最后1个不相关")

    return result


def test_answer_relevancy():
    """测试答案相关性指标"""
    logger.info("\n" + "=" * 80)
    logger.info("测试 Answer Relevancy (答案相关性)")
    logger.info("=" * 80)
    print("\n" + "=" * 80)
    print("测试 Answer Relevancy (答案相关性)")
    print("=" * 80)

    # 配置 LLM 和 Embedding 模型
    LLMRAGAnswerRelevancy.dynamic_config = EvaluatorLLMArgs(
        key=OPENAI_KEY,
        api_url=OPENAI_URL,
        model=OPENAI_MODEL,
        parameters={
            "embedding_model": EMBEDDING_MODEL,
            "strictness": 3,  # 生成的问题数量
            "threshold": 5     # 评分阈值
        }
    )

    # 初始化 Embedding 模型
    LLMRAGAnswerRelevancy.init_embedding_model(EMBEDDING_MODEL)

    # 测试用例1: 相关的答案
    data1 = Data(
        data_id="test_relevant",
        prompt="什么是机器学习？",
        content="机器学习是人工智能的一个分支，它使计算机能够从数据中学习而无需明确编程。"
    )

    logger.info("\n用例1 - 直接回答:")
    print("\n用例1 - 直接回答:")
    result1 = LLMRAGAnswerRelevancy.eval(data1)
    logger.info(f"  状态: {'✅ 通过' if not result1.eval_status else '❌ 未通过'}")
    logger.info(f"  分数: {result1.score}/10")
    print(f"  状态: {'✅ 通过' if not result1.eval_status else '❌ 未通过'}")
    print(f"  分数: {result1.score}/10")

    # 测试用例2: 包含无关信息
    data2 = Data(
        data_id="test_irrelevant",
        prompt="什么是机器学习？",
        content="机器学习是人工智能的一个分支。今天天气很好。神经网络很复杂。我喜欢编程。"
    )

    logger.info("\n用例2 - 包含无关信息:")
    print("\n用例2 - 包含无关信息:")
    result2 = LLMRAGAnswerRelevancy.eval(data2)
    logger.info(f"  状态: {'✅ 通过' if not result2.eval_status else '❌ 未通过'}")
    logger.info(f"  分数: {result2.score}/10")
    logger.info("\n预期: 用例2分数 < 用例1分数")
    print(f"  状态: {'✅ 通过' if not result2.eval_status else '❌ 未通过'}")
    print(f"  分数: {result2.score}/10")
    print("\n预期: 用例2分数 < 用例1分数")

#     return result1, result2


def test_context_recall():
    """测试上下文召回指标"""
    logger.info("\n" + "=" * 80)
    logger.info("测试 Context Recall (上下文召回)")
    logger.info("=" * 80)
    logger.info(f"LLM配置: {OPENAI_MODEL} at {OPENAI_URL}")
    print("\n" + "=" * 80)
    print("测试 Context Recall (上下文召回)")
    print("=" * 80)
    print(f"LLM配置: {OPENAI_MODEL} at {OPENAI_URL}")

    # 配置 LLM
    LLMRAGContextRecall.dynamic_config = EvaluatorLLMArgs(
        key=OPENAI_KEY,
        api_url=OPENAI_URL,
        model=OPENAI_MODEL,
    )
    logger.info("LLM配置完成")
    print("LLM配置完成")

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

    logger.info("\n用例1 - 上下文完全支持:")
    print("\n用例1 - 上下文完全支持:")
    result1 = LLMRAGContextRecall.eval(data1)
    logger.info(f"  状态: {'✅ 通过' if not result1.eval_status else '❌ 未通过'}")
    logger.info(f"  分数: {result1.score}/10")
    print(f"  状态: {'✅ 通过' if not result1.eval_status else '❌ 未通过'}")
    print(f"  分数: {result1.score}/10")

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

    logger.info("\n用例2 - 上下文部分支持:")
    print("\n用例2 - 上下文部分支持:")
    result2 = LLMRAGContextRecall.eval(data2)
    logger.info(f"  状态: {'✅ 通过' if not result2.eval_status else '❌ 未通过'}")
    logger.info(f"  分数: {result2.score}/10")
    logger.info("\n预期: 用例2分数 < 用例1分数")
    print(f"  状态: {'✅ 通过' if not result2.eval_status else '❌ 未通过'}")
    print(f"  分数: {result2.score}/10")
    print("\n预期: 用例2分数 < 用例1分数")

    return result1, result2


def test_context_relevancy():
    """测试上下文相关性指标"""
    logger.info("\n" + "=" * 80)
    logger.info("测试 Context Relevancy (上下文相关性)")
    logger.info("=" * 80)
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

    logger.info("\n用例1 - 所有上下文相关:")
    print("\n用例1 - 所有上下文相关:")
    result1 = LLMRAGContextRelevancy.eval(data1)
    logger.info(f"  状态: {'✅ 通过' if not result1.eval_status else '❌ 未通过'}")
    logger.info(f"  分数: {result1.score}/10")
    print(f"  状态: {'✅ 通过' if not result1.eval_status else '❌ 未通过'}")
    print(f"  分数: {result1.score}/10")

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

    logger.info("\n用例2 - 包含不相关上下文:")
    print("\n用例2 - 包含不相关上下文:")
    result2 = LLMRAGContextRelevancy.eval(data2)
    logger.info(f"  状态: {'✅ 通过' if not result2.eval_status else '❌ 未通过'}")
    logger.info(f"  分数: {result2.score}/10")
    logger.info("\n预期: 用例2分数 < 用例1分数")
    print(f"  状态: {'✅ 通过' if not result2.eval_status else '❌ 未通过'}")
    print(f"  分数: {result2.score}/10")
    print("\n预期: 用例2分数 < 用例1分数")

    return result1, result2


def evaluate_from_jsonl(jsonl_path):
    """从JSONL文件读取数据并进行RAG指标评测"""
    logger.info(f"\n从JSONL文件 {jsonl_path} 读取数据进行评测...")
    print(f"\n从JSONL文件 {jsonl_path} 读取数据进行评测...")

    # 配置所有LLM评估器
    llm_args = EvaluatorLLMArgs(
        key=OPENAI_KEY,
        api_url=OPENAI_URL,
        model=OPENAI_MODEL,
    )

    # 设置所有评估器的LLM配置
    # LLMRAGFaithfulness.dynamic_config = llm_args
    # LLMRAGContextPrecision.dynamic_config = llm_args
    # LLMRAGContextRecall.dynamic_config = llm_args
    # LLMRAGContextRelevancy.dynamic_config = llm_args
    #
    # 为AnswerRelevancy配置额外的参数（包括embedding模型）
    LLMRAGAnswerRelevancy.dynamic_config = EvaluatorLLMArgs(
        key=OPENAI_KEY,
        api_url=OPENAI_URL,
        model=OPENAI_MODEL,
        parameters={
            "embedding_model": EMBEDDING_MODEL,
            "strictness": 3,
            "threshold": 5
        }
    )

    # 初始化Embedding模型
    LLMRAGAnswerRelevancy.init_embedding_model(EMBEDDING_MODEL)

    # 读取JSONL文件
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        total_rows = 0

        # 初始化累计总分
        total_faithfulness = 0
        total_precision = 0
        total_recall = 0
        total_relevancy = 0
        total_answer_relevancy = 0

        # 遍历每一行数据
        for line in f:
            total_rows += 1

            # 解析JSON行
            row = json.loads(line.strip())

            logger.info(f"\n处理第 {total_rows} 条数据:")
            logger.info(f"问题: {row['question']}")
            print(f"\n处理第 {total_rows} 条数据:")
            print(f"问题: {row['question']}")

            # 获取retrieved_contexts（支持字符串列表或单个字符串）
            retrieved_contexts = row.get('retrieved_contexts', [])
            if isinstance(retrieved_contexts, str):
                retrieved_contexts = [retrieved_contexts]

            # 创建Data对象
            data = Data(
                data_id=f"jsonl_row_{total_rows}",
                prompt=row['question'],
                content=row['response'],
                context=retrieved_contexts,
                reference=row.get('reference', '')  # 标准答案是可选的
            )

            # # # 进行各项指标评测
            # print("\n1. 忠实度 (Faithfulness):")
            # faithfulness_result = LLMRAGFaithfulness.eval(data)
            # print(f"   状态: {'✅ 通过' if not faithfulness_result.eval_status else '❌ 未通过'}")
            # print(f"   分数: {faithfulness_result.score}/10")
            # total_faithfulness += faithfulness_result.score

            # logger.info("\n2. 上下文精度 (Context Precision):")
            # print("\n2. 上下文精度 (Context Precision):")
            # precision_result = LLMRAGContextPrecision.eval(data)
            # logger.info(f"   状态: {'✅ 通过' if not precision_result.eval_status else '❌ 未通过'}")
            # logger.info(f"   分数: {precision_result.score}/10")
            # print(f"   状态: {'✅ 通过' if not precision_result.eval_status else '❌ 未通过'}")
            # print(f"   分数: {precision_result.score}/10")
            # total_precision += precision_result.score

            # print("\n3. 上下文召回 (Context Recall):")
            # recall_result = LLMRAGContextRecall.eval(data)
            # print(f"   状态: {'✅ 通过' if not recall_result.eval_status else '❌ 未通过'}")
            # print(f"   分数: {recall_result.score}/10")
            # total_recall += recall_result.score

            # print("\n4. 上下文相关性 (Context Relevancy):")
            # relevancy_result = LLMRAGContextRelevancy.eval(data)
            # print(f"   状态: {'✅ 通过' if not relevancy_result.eval_status else '❌ 未通过'}")
            # print(f"   分数: {relevancy_result.score}/10")
            # total_relevancy += relevancy_result.score
            #
            print("\n5. 答案相关性 (Answer Relevancy):")
            answer_relevancy_result = LLMRAGAnswerRelevancy.eval(data)
            print(f"   状态: {'✅ 通过' if not answer_relevancy_result.eval_status else '❌ 未通过'}")
            print(f"   分数: {answer_relevancy_result.score}/10")
            total_answer_relevancy += answer_relevancy_result.score

    logger.info(f"\n所有 {total_rows} 条数据评测完成！")
    print(f"\n所有 {total_rows} 条数据评测完成！")

    # 计算并打印平均得分
    if total_rows > 0:
        avg_faithfulness = total_faithfulness / total_rows
        avg_precision = total_precision / total_rows
        avg_recall = total_recall / total_rows
        avg_relevancy = total_relevancy / total_rows
        avg_answer_relevancy = total_answer_relevancy / total_rows

        logger.info("\n" + "=" * 60)
        logger.info("🚀 RAG 指标平均得分")
        logger.info("=" * 60)
        logger.info(f"忠实度 (Faithfulness) 平均值: {avg_faithfulness:.2f}/10")
        logger.info(f"上下文精度 (Context Precision) 平均值: {avg_precision:.2f}/10")
        logger.info(f"上下文召回 (Context Recall) 平均值: {avg_recall:.2f}/10")
        logger.info(f"上下文相关性 (Context Relevancy) 平均值: {avg_relevancy:.2f}/10")
        logger.info(f"答案相关性 (Answer Relevancy) 平均值: {avg_answer_relevancy:.2f}/10")

        # 计算所有指标的总平均值
        overall_avg = (avg_faithfulness + avg_precision + avg_recall + avg_relevancy + avg_answer_relevancy) / 5
        logger.info(f"\n📊 综合平均得分: {overall_avg:.2f}/10")
        logger.info("=" * 60)

        print("\n" + "=" * 60)
        print("🚀 RAG 指标平均得分")
        print("=" * 60)
        print(f"忠实度 (Faithfulness) 平均值: {avg_faithfulness:.2f}/10")
        print(f"上下文精度 (Context Precision) 平均值: {avg_precision:.2f}/10")
        print(f"上下文召回 (Context Recall) 平均值: {avg_recall:.2f}/10")
        print(f"上下文相关性 (Context Relevancy) 平均值: {avg_relevancy:.2f}/10")
        print(f"答案相关性 (Answer Relevancy) 平均值: {avg_answer_relevancy:.2f}/10")

        # 计算所有指标的总平均值
        overall_avg = (avg_faithfulness + avg_precision + avg_recall + avg_relevancy + avg_answer_relevancy) / 5
        print(f"\n📊 综合平均得分: {overall_avg:.2f}/10")
        print("=" * 60)


def evaluate_from_csv(csv_path):
    """从CSV文件读取数据并进行RAG指标评测"""
    logger.info(f"\n从CSV文件 {csv_path} 读取数据进行评测...")
    print(f"\n从CSV文件 {csv_path} 读取数据进行评测...")

    # 配置所有LLM评估器
    llm_args = EvaluatorLLMArgs(
        key=OPENAI_KEY,
        api_url=OPENAI_URL,
        model=OPENAI_MODEL,
    )

    # 设置所有评估器的LLM配置
    LLMRAGFaithfulness.dynamic_config = llm_args
    LLMRAGContextPrecision.dynamic_config = llm_args
    LLMRAGContextRecall.dynamic_config = llm_args
    LLMRAGContextRelevancy.dynamic_config = llm_args

    # 为AnswerRelevancy配置额外的参数（包括embedding模型）
    LLMRAGAnswerRelevancy.dynamic_config = EvaluatorLLMArgs(
        key=OPENAI_KEY,
        api_url=OPENAI_URL,
        model=OPENAI_MODEL,
        parameters={
            "embedding_model": EMBEDDING_MODEL,
            "strictness": 3,
            "threshold": 5
        }
    )

    # 初始化Embedding模型
    LLMRAGAnswerRelevancy.init_embedding_model(EMBEDDING_MODEL)

    # 读取CSV文件，尝试使用GBK编码（处理中文编码数据）
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        total_rows = 0

        # 初始化累计总分
        total_faithfulness = 0
        total_precision = 0
        total_recall = 0
        total_relevancy = 0
        total_answer_relevancy = 0

        # 遍历每一行数据
        for row in reader:
            total_rows += 1
            logger.info(f"\n处理第 {total_rows} 条数据:")
            logger.info(f"问题: {row['question']}")
            print(f"\n处理第 {total_rows} 条数据:")
            print(f"问题: {row['question']}")

            # 解析retrieved_contexts（假设是JSON字符串）
            try:
                retrieved_contexts = json.loads(row['retrieved_contexts'])
            except json.JSONDecodeError:
                # 如果不是JSON字符串，尝试按列表格式解析
                retrieved_contexts = [context.strip() for context in row['retrieved_contexts'].strip('[]').split(',')]

            # 创建Data对象
            data = Data(
                data_id=f"csv_row_{total_rows}",
                prompt=row['question'],
                content=row['response'],
                context=retrieved_contexts,
                reference=row.get('reference', '')  # 标准答案是可选的
            )

            # # # # 进行各项指标评测
            print("\n1. 忠实度 (Faithfulness):")
            faithfulness_result = LLMRAGFaithfulness.eval(data)
            print(f"   状态: {'✅ 通过' if not faithfulness_result.eval_status else '❌ 未通过'}")
            print(f"   分数: {faithfulness_result.score}/10")
            total_faithfulness += faithfulness_result.score

            # logger.info("\n2. 上下文精度 (Context Precision):")
            # print("\n2. 上下文精度 (Context Precision):")
            # precision_result = LLMRAGContextPrecision.eval(data)
            # logger.info(f"   状态: {'✅ 通过' if not precision_result.eval_status else '❌ 未通过'}")
            # logger.info(f"   分数: {precision_result.score}/10")
            # print(f"   状态: {'✅ 通过' if not precision_result.eval_status else '❌ 未通过'}")
            # print(f"   分数: {precision_result.score}/10")
            # total_precision += precision_result.score
            #
            # print("\n3. 上下文召回 (Context Recall):")
            # recall_result = LLMRAGContextRecall.eval(data)
            # print(f"   状态: {'✅ 通过' if not recall_result.eval_status else '❌ 未通过'}")
            # print(f"   分数: {recall_result.score}/10")
            # total_recall += recall_result.score
            #
            # print("\n4. 上下文相关性 (Context Relevancy):")
            # relevancy_result = LLMRAGContextRelevancy.eval(data)
            # print(f"   状态: {'✅ 通过' if not relevancy_result.eval_status else '❌ 未通过'}")
            # print(f"   分数: {relevancy_result.score}/10")
            # total_relevancy += relevancy_result.score
            #
            # print("\n5. 答案相关性 (Answer Relevancy):")
            # answer_relevancy_result = LLMRAGAnswerRelevancy.eval(data)
            # print(f"   状态: {'✅ 通过' if not answer_relevancy_result.eval_status else '❌ 未通过'}")
            # print(f"   分数: {answer_relevancy_result.score}/10")
            # total_answer_relevancy += answer_relevancy_result.score

    logger.info(f"\n所有 {total_rows} 条数据评测完成！")
    print(f"\n所有 {total_rows} 条数据评测完成！")

    # 计算并打印平均得分
    if total_rows > 0:
        avg_faithfulness = total_faithfulness / total_rows
        avg_precision = total_precision / total_rows
        avg_recall = total_recall / total_rows
        avg_relevancy = total_relevancy / total_rows
        avg_answer_relevancy = total_answer_relevancy / total_rows

        logger.info("\n" + "=" * 60)
        logger.info("🚀 RAG 指标平均得分")
        logger.info("=" * 60)
        logger.info(f"忠实度 (Faithfulness) 平均值: {avg_faithfulness:.2f}/10")
        logger.info(f"上下文精度 (Context Precision) 平均值: {avg_precision:.2f}/10")
        logger.info(f"上下文召回 (Context Recall) 平均值: {avg_recall:.2f}/10")
        logger.info(f"上下文相关性 (Context Relevancy) 平均值: {avg_relevancy:.2f}/10")
        logger.info(f"答案相关性 (Answer Relevancy) 平均值: {avg_answer_relevancy:.2f}/10")

        # 计算所有指标的总平均值
        overall_avg = (avg_faithfulness + avg_precision + avg_recall + avg_relevancy + avg_answer_relevancy) / 5
        logger.info(f"\n📊 综合平均得分: {overall_avg:.2f}/10")
        logger.info("=" * 60)

        print("\n" + "=" * 60)
        print("🚀 RAG 指标平均得分")
        print("=" * 60)
        print(f"忠实度 (Faithfulness) 平均值: {avg_faithfulness:.2f}/10")
        print(f"上下文精度 (Context Precision) 平均值: {avg_precision:.2f}/10")
        print(f"上下文召回 (Context Recall) 平均值: {avg_recall:.2f}/10")
        print(f"上下文相关性 (Context Relevancy) 平均值: {avg_relevancy:.2f}/10")
        print(f"答案相关性 (Answer Relevancy) 平均值: {avg_answer_relevancy:.2f}/10")

        # 计算所有指标的总平均值
        overall_avg = (avg_faithfulness + avg_precision + avg_recall + avg_relevancy + avg_answer_relevancy) / 5
        print(f"\n📊 综合平均得分: {overall_avg:.2f}/10")
        print("=" * 60)


def main():
    # 记录测试开始时间
    start_time = time.time()
    logger.info("\n" + "=" * 80)
    logger.info("RAG 指标测试")
    logger.info("=" * 80)
    logger.info(f"模型: {OPENAI_MODEL}")
    logger.info(f"API: {OPENAI_URL}")
    logger.info(f"输入文件路径: {CSV_FILE_PATH}")
    logger.info(f"日志文件路径: {LOG_FILE_PATH}")
    print("\n" + "=" * 80)
    print("RAG 指标测试")
    print("=" * 80)
    print(f"模型: {OPENAI_MODEL}")
    print(f"API: {OPENAI_URL}")
    print(f"输入文件路径: {CSV_FILE_PATH}")
    print(f"日志文件路径: {LOG_FILE_PATH}")

    # 使用脚本中配置的文件路径进行评测
    if os.path.exists(CSV_FILE_PATH):
        # 根据文件扩展名选择解析器
        file_extension = os.path.splitext(CSV_FILE_PATH)[1].lower()
        if file_extension == '.csv':
            evaluate_from_csv(CSV_FILE_PATH)
        elif file_extension == '.jsonl':
            evaluate_from_jsonl(CSV_FILE_PATH)
        else:
            logger.error(f"错误: 不支持的文件格式 {file_extension}！仅支持 .csv 和 .jsonl")
            print(f"错误: 不支持的文件格式 {file_extension}！仅支持 .csv 和 .jsonl")
    else:
        logger.error(f"错误: 文件 {CSV_FILE_PATH} 不存在！")
        logger.info("\n运行默认测试用例...")
        print(f"错误: 文件 {CSV_FILE_PATH} 不存在！")
        print("\n运行默认测试用例...")
        # test_faithfulness()
        # test_context_precision()
        # test_answer_relevancy()
        # test_context_recall()
        # test_context_relevancy()

    # 记录测试结束时间和总耗时
    end_time = time.time()
    total_time = end_time - start_time
    logger.info("\n" + "=" * 80)
    logger.info("✅ 测试完成！")
    logger.info(f"总耗时: {total_time:.2f} 秒")
    logger.info("=" * 80)
    print("\n" + "=" * 80)
    print("✅ 测试完成！")
    print(f"总耗时: {total_time:.2f} 秒")
    print("=" * 80)


if __name__ == "__main__":
    main()
