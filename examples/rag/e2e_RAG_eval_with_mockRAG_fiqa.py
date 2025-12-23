"""
真正的端到端 FiQA RAG 系统评测

本示例展示如何：
1. 使用完整的 FiQA corpus (57,638 文档) 构建检索系统
2. 对 FiQA test 集 (648 问题) 进行端到端 RAG 评测
3. 将结果与 baseline 对比

数据来源：
    - 自动从 HuggingFace 下载 FiQA 数据集
    - Dataset: explodinggradients/fiqa
      - Corpus: 57,638 文档
      - Test: 648 问题
      - Baseline: 30 样本

前置依赖:
    pip install langchain langchain-community langchain-text-splitters openai dingo-python datasets

环境变量:
    OPENAI_API_KEY: OpenAI API 密钥
    OPENAI_BASE_URL: (可选) OpenAI API 基础 URL
    OPENAI_MODEL: (可选) 使用的模型名称，默认为 deepseek-chat

本地 Embedding 模型配置:
    如需使用本地 Embedding 模型（如 BAAI/bge-m3），请修改 run_dingo_evaluation() 函数中的
    llm_config_embedding 配置，使用 embedding_config 指定独立的 Embedding 服务地址。
    详见代码中的"方式2"注释示例。

使用方法:
    # 评测所有 648 个问题（可能需要较长时间）
    python examples/rag/e2e_RAG_eval_with_mockRAG_fiqa.py

    # 只评测前 N 个问题（快速测试）
    python examples/rag/e2e_RAG_eval_with_mockRAG_fiqa.py --limit 10

    # 与 baseline 对比（只评测 baseline 中的 30 个问题）
    python examples/rag/e2e_RAG_eval_with_mockRAG_fiqa.py --compare-baseline
"""

import argparse
import asyncio
import json
import logging
import os
from typing import Any, Dict, List

# HuggingFace datasets
from datasets import load_dataset
# RAG 构建相关依赖
from langchain_community.retrievers import BM25Retriever as LangchainBM25Retriever
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI

# Dingo 框架评测相关依赖
from dingo.config import InputArgs
from dingo.exec import Executor
from dingo.io.output.summary_model import SummaryModel

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置 OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "deepseek-chat")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

# FiQA 数据集配置
FIQA_DATASET = "explodinggradients/fiqa"

if not OPENAI_API_KEY:
    logger.warning("未设置 OPENAI_API_KEY 环境变量，可能无法正常运行。")


class FiQACorpusRetriever:
    """基于 FiQA 完整语料库的 BM25 检索器"""

    def __init__(self, corpus_dataset=None, default_k: int = 3, chunk_size: int = 500):
        self.default_k = default_k
        self.chunk_size = chunk_size

        if corpus_dataset is None:
            logger.info("正在从 HuggingFace 下载 FiQA corpus...")
            corpus_dataset = load_dataset(FIQA_DATASET, "corpus", split="corpus")

        logger.info(f"已加载 {len(corpus_dataset)} 条文档")
        self.corpus = self._prepare_corpus(corpus_dataset)

        logger.info("正在构建 BM25 检索器...")
        self.retriever = self._build_retriever()
        logger.info("BM25 检索器构建完成")

    def _prepare_corpus(self, corpus_dataset) -> List[Dict[str, str]]:
        """准备语料库数据"""
        corpus = []
        for idx, item in enumerate(corpus_dataset):
            corpus.append({
                "text": item["doc"],
                "source": f"corpus_doc_{idx}"
            })
        return corpus

    def _build_retriever(self) -> LangchainBM25Retriever:
        """构建 BM25 检索器"""
        # 创建文档对象
        documents = [
            Document(
                page_content=doc["text"],
                metadata={"source": doc["source"]}
            )
            for doc in self.corpus
        ]

        # 切分文档（如果文档过长）
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=50,
            add_start_index=True,
            strip_whitespace=True,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        all_chunks = []
        for document in documents:
            # 只有当文档超过 chunk_size 时才切分
            if len(document.page_content) > self.chunk_size:
                chunks = text_splitter.split_documents([document])
                all_chunks.extend(chunks)
            else:
                all_chunks.append(document)

        logger.info(f"文档切分后共 {len(all_chunks)} 个 chunks")

        return LangchainBM25Retriever.from_documents(
            documents=all_chunks,
            k=self.default_k,
        )

    def retrieve(self, query: str, top_k: int = None) -> List[Document]:
        """检索相关文档"""
        if top_k is None:
            top_k = self.default_k
        self.retriever.k = top_k
        return self.retriever.invoke(query)


class SimpleRAG:
    """简单的 RAG 系统"""

    def __init__(self, llm_client: AsyncOpenAI, retriever: FiQACorpusRetriever,
                 system_prompt: str = None, model: str = "gpt-3.5-turbo"):
        self.llm_client = llm_client
        self.retriever = retriever
        self.model = model
        self.system_prompt = system_prompt or (
            "You are a financial advisor assistant. Answer the question based ONLY on the provided documents. "
            "Be concise and accurate.\n\n"
            "Question: {query}\n\n"
            "Documents:\n{context}\n\n"
            "Answer:"
        )

    async def query(self, question: str, top_k: int = 3) -> Dict[str, Any]:
        """执行 RAG 查询"""
        # 1. 检索
        docs = self.retriever.retrieve(question, top_k)

        if not docs:
            return {
                "answer": "No relevant documents found.",
                "retrieved_documents": [],
                "context_list": []
            }

        # 2. 构建上下文
        context = "\n\n".join([
            f"Document {i}:\n{doc.page_content}"
            for i, doc in enumerate(docs, 1)
        ])
        prompt = self.system_prompt.format(query=question, context=context)

        # 3. 生成回答
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1  # 降低温度以提高一致性
            )
            answer = response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"LLM 生成失败: {e}")
            answer = f"Error generating response: {str(e)}"

        return {
            "answer": answer,
            "retrieved_documents": docs,
            "context_list": [doc.page_content for doc in docs]
        }


def load_test_questions(limit: int = None) -> List[Dict[str, Any]]:
    """从 HuggingFace 加载测试问题"""
    logger.info("正在从 HuggingFace 下载 FiQA test 数据...")
    test_dataset = load_dataset(FIQA_DATASET, "main", split="test")

    questions = []
    for item in test_dataset:
        questions.append({
            "question": item["question"],
            "ground_truths": item["ground_truths"]
        })
        if limit and len(questions) >= limit:
            break

    return questions


def load_baseline_data() -> List[Dict[str, Any]]:
    """从 HuggingFace 加载 baseline 数据（用于对比）"""
    logger.info("正在从 HuggingFace 下载 FiQA baseline 数据...")
    baseline_dataset = load_dataset(FIQA_DATASET, "ragas_eval_v3", split="baseline")

    baseline_data = []
    for item in baseline_dataset:
        baseline_data.append({
            "question": item["user_input"],
            "ground_truths": item["reference"]  # baseline 已经包含 reference
        })

    return baseline_data


async def generate_rag_responses(rag: SimpleRAG, questions: List[Dict[str, Any]],
                                 top_k: int = 3) -> List[Dict[str, Any]]:
    """为所有问题生成 RAG 响应"""
    results = []
    total = len(questions)

    for idx, q in enumerate(questions, 1):
        question_text = q["question"]
        logger.info(f"[{idx}/{total}] 处理问题: {question_text[:80]}...")

        try:
            result = await rag.query(question_text, top_k=top_k)
            results.append({
                "user_input": question_text,
                "reference": q["ground_truths"],  # 保持原始列表格式
                "response": result["answer"],
                "retrieved_contexts": result["context_list"]
            })
        except Exception as e:
            logger.error(f"处理问题失败: {e}")
            results.append({
                "user_input": question_text,
                "reference": q["ground_truths"],
                "response": f"Error: {str(e)}",
                "retrieved_contexts": []
            })

    return results


def save_rag_results(results: List[Dict], output_path: str):
    """保存 RAG 结果到 JSONL"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    logger.info(f"结果已保存到: {output_path}")


def print_metrics_summary(summary: SummaryModel):
    """打印指标统计摘要"""
    if not summary.metrics_score_stats:
        print("⚠️  没有指标统计数据")
        return

    print("\n" + "=" * 80)
    print("📊 RAG 评估指标统计")
    print("=" * 80)

    for field_key, metrics in summary.metrics_score_stats.items():
        print(f"\n📁 字段组: {field_key}")
        print("-" * 80)

        for metric_name, stats in metrics.items():
            display_name = metric_name.replace("LLMRAG", "")
            print(f"\n  {display_name}:")
            print(f"    平均分: {stats.get('score_average', 0):.2f}")
            print(f"    最小分: {stats.get('score_min', 0):.2f}")
            print(f"    最大分: {stats.get('score_max', 0):.2f}")
            print(f"    样本数: {stats.get('score_count', 0)}")
            if 'score_std_dev' in stats:
                print(f"    标准差: {stats.get('score_std_dev', 0):.2f}")

        overall_avg = summary.get_metrics_score_overall_average(field_key)
        print(f"\n  🎯 该字段组总平均分: {overall_avg:.2f}")

        metrics_summary = summary.get_metrics_score_summary(field_key)
        sorted_metrics = sorted(metrics_summary.items(), key=lambda x: x[1], reverse=True)

        print("\n  📈 指标排名（从高到低）:")
        for i, (metric_name, avg_score) in enumerate(sorted_metrics, 1):
            display_name = metric_name.replace("LLMRAG", "")
            print(f"    {i}. {display_name}: {avg_score:.2f}")

    print("\n" + "=" * 80)


def run_dingo_evaluation(rag_output_path: str) -> SummaryModel:
    """使用 Dingo 框架评测 RAG 输出"""
    llm_config = {
        "model": OPENAI_MODEL,
        "key": OPENAI_API_KEY,
        "api_url": OPENAI_BASE_URL,
    }

    # ⚠️ 注意：LLMRAGAnswerRelevancy 必须配置 embedding_config
    llm_config_embedding = {
        "model": OPENAI_MODEL,
        "key": OPENAI_API_KEY,
        "api_url": OPENAI_BASE_URL,  # LLM 服务地址
        "embedding_config": {  # ⭐ 必需：Embedding 配置
            "model": EMBEDDING_MODEL,
            "api_url": OPENAI_BASE_URL,  # 如果同一服务提供 embedding
            "key": OPENAI_API_KEY
        },
        "parameters": {
            "strictness": 3,
            "threshold": 5
        }
    }

    input_data = {
        "task_name": "fiqa_end_to_end_rag_evaluation",
        "input_path": rag_output_path,
        "output_path": "outputs/",
        "dataset": {
            "source": "local",
            "format": "jsonl",
        },
        "executor": {
            "max_workers": 10,
            "batch_size": 10,
            "result_save": {
                "good": True,
                "bad": True,
                "all_labels": True
            }
        },
        "evaluator": [
            {
                "fields": {
                    "prompt": "user_input",
                    "content": "response",
                    "reference": "reference",
                    "context": "retrieved_contexts"
                },
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
                    {
                        "name": "LLMRAGAnswerRelevancy",
                        "config": llm_config_embedding
                    }
                ]
            }
        ]
    }

    logger.info("开始使用 Dingo 评测...")
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    summary = executor.execute()

    return summary


async def main():
    parser = argparse.ArgumentParser(description='FiQA 端到端 RAG 评测')
    parser.add_argument('--limit', type=int, default=None,
                        help='限制评测问题数量（用于快速测试）')
    parser.add_argument('--compare-baseline', action='store_true',
                        help='只评测 baseline 中的问题以便对比')
    parser.add_argument('--top-k', type=int, default=3,
                        help='检索文档数量（默认: 3）')
    args = parser.parse_args()

    print("=" * 80)
    print("FiQA 端到端 RAG 系统评测")
    print("=" * 80)
    print(f"数据集: {FIQA_DATASET} (从 HuggingFace 自动下载)")
    print(f"API Key: {('sk-...' + OPENAI_API_KEY[-4:]) if OPENAI_API_KEY else 'Not set'}")
    print(f"API Base URL: {OPENAI_BASE_URL}")
    print(f"模型: {OPENAI_MODEL}")
    print(f"Top-K: {args.top_k}")
    print("=" * 80)

    # 步骤1: 构建检索器（使用完整语料库）
    retriever = FiQACorpusRetriever(
        corpus_dataset=None,  # 自动从 HuggingFace 下载
        default_k=args.top_k,
        chunk_size=500
    )

    # 步骤2: 初始化 RAG 系统
    client = AsyncOpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL
    )
    rag = SimpleRAG(client, retriever, model=OPENAI_MODEL)

    # 步骤3: 加载测试问题
    if args.compare_baseline:
        logger.info("对比模式：只评测 baseline 中的 30 个问题")
        # 直接从 HuggingFace 加载 baseline 问题和 reference
        test_questions = load_baseline_data()
        logger.info(f"已加载 {len(test_questions)} 个 baseline 问题")
    else:
        test_questions = load_test_questions(limit=args.limit)
        logger.info(f"已加载 {len(test_questions)} 个测试问题")

    # 步骤4: 生成 RAG 响应
    logger.info("开始生成 RAG 响应...")
    rag_results = await generate_rag_responses(rag, test_questions, top_k=args.top_k)

    # 步骤5: 保存结果
    output_filename = "fiqa_end_to_end_rag_output.jsonl"  # noqa: F541
    if args.compare_baseline:
        output_filename = "fiqa_end_to_end_rag_output_baseline_subset.jsonl"
    elif args.limit:
        output_filename = f"fiqa_end_to_end_rag_output_limit_{args.limit}.jsonl"

    output_path = "test/data/" + output_filename
    save_rag_results(rag_results, output_path)

    # 步骤6: 使用 Dingo 评测
    print("\n" + "=" * 80)
    print("使用 Dingo 框架进行评测")
    print("=" * 80)

    summary = run_dingo_evaluation(output_path)

    # 步骤7: 打印结果
    print("\n" + "=" * 80)
    print("✅ 评测完成！")
    print("=" * 80)
    print(f"总数据量: {summary.total}")
    print(f"通过: {summary.num_good}")
    print(f"未通过: {summary.num_bad}")
    print(f"通过率: {summary.score}%")

    print_metrics_summary(summary)

    print(f"\n💾 详细结果已保存到: {summary.output_path}")
    print(f"💾 RAG 输出已保存到: {output_path}")

    # 如果是对比模式，提供对比建议
    if args.compare_baseline:
        print("\n📊 对比建议:")
        print(f"  Baseline: {FIQA_DATASET} (ragas_eval_v3)")
        print(f"  Your RAG: {output_path}")
        print("  可以使用 dataset_rag_eval_baseline.py 评测 baseline")
        print("  然后对比两者的 metrics_score")


if __name__ == "__main__":
    asyncio.run(main())
