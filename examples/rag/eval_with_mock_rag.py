"""
参考 ragas/examples/ragas_examples/improve_rag/rag.py 构建的 RAG 系统及评测示例。

本示例展示了如何：
1. 使用 test/data/fiqa.jsonl 构建一个基于 BM25 检索和 OpenAI 生成的简单 RAG 系统。
2. 使用 Dingo 对 RAG 系统的输出进行批量评测（使用 Dingo 框架）。

前置依赖:
    pip install langchain langchain-community langchain-text-splitters openai dingo-python

环境变量:
    OPENAI_API_KEY: OpenAI API 密钥
    OPENAI_BASE_URL: (可选) OpenAI API 基础 URL
    OPENAI_MODEL: (可选) 使用的模型名称，默认为 deepseek-chat
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

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

if not OPENAI_API_KEY:
    logger.warning("未设置 OPENAI_API_KEY 环境变量，可能无法正常运行 RAG 生成和评测。")


class BM25Retriever:
    """基于 BM25 的文档检索器"""

    def __init__(self, jsonl_path="test/data/fiqa.jsonl", default_k=3):
        self.default_k = default_k
        # 从 JSONL 文件加载数据
        logger.info(f"正在从 {jsonl_path} 加载数据...")
        self.knowledge_base = self._load_jsonl(jsonl_path)
        logger.info(f"已加载 {len(self.knowledge_base)} 条数据用于构建索引")

        self.retriever = self._build_retriever()

    def _load_jsonl(self, jsonl_path: str) -> List[Dict]:
        """从 JSONL 文件加载数据"""
        knowledge_base = []
        try:
            with open(jsonl_path, 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line.strip())
                    # 使用 retrieved_contexts 作为知识库
                    if 'retrieved_contexts' in data and data['retrieved_contexts']:
                        for idx, context in enumerate(data['retrieved_contexts']):
                            knowledge_base.append({
                                "text": context,
                                "source": f"fiqa/{data.get('user_input', 'unknown')[:50]}/{idx}"
                            })
            logger.info(f"从 JSONL 文件中提取了 {len(knowledge_base)} 条上下文文档")
        except Exception as e:
            logger.error(f"加载 JSONL 文件失败: {e}")
            raise

        return knowledge_base

    def _build_retriever(self) -> LangchainBM25Retriever:
        """构建 BM25 检索器"""
        # 创建文档对象
        source_documents = []
        for row in self.knowledge_base:
            source = row.get("source", "unknown")
            if "/" in source:
                source = source.split("/")[1]

            source_documents.append(
                Document(
                    page_content=row["text"],
                    metadata={"source": source},
                )
            )

        # 切分文档
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            add_start_index=True,
            strip_whitespace=True,
            separators=["\n\n", "\n", ".", " ", ""],
        )

        all_chunks = []
        for document in source_documents:
            chunks = text_splitter.split_documents([document])
            all_chunks.extend(chunks)

        # 简单去重
        unique_chunks = []
        seen_content = set()
        for chunk in all_chunks:
            if chunk.page_content not in seen_content:
                seen_content.add(chunk.page_content)
                unique_chunks.append(chunk)

        return LangchainBM25Retriever.from_documents(
            documents=unique_chunks,
            k=self.default_k,
        )

    def retrieve(self, query: str, top_k: int = None):
        """检索文档"""
        if top_k is None:
            top_k = self.default_k
        self.retriever.k = top_k
        return self.retriever.invoke(query)


class RAG:
    """简单的 RAG 系统"""

    def __init__(self, llm_client: AsyncOpenAI, retriever: BM25Retriever, system_prompt=None, model="gpt-3.5-turbo"):
        self.llm_client = llm_client
        self.retriever = retriever
        self.model = model
        self.system_prompt = system_prompt or (
            "Answer only based on documents. Be concise.\n\n"
            "Question: {query}\n"
            "Documents:\n{context}\n"
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
        context = "\n\n".join([f"Document {i}:\n{doc.page_content}" for i, doc in enumerate(docs, 1)])
        prompt = self.system_prompt.format(query=question, context=context)

        # 3. 生成回答
        try:
            response = await self.llm_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}]
            )
            answer = response.choices[0].message.content.strip()
        except Exception as e:
            answer = f"Error generating response: {str(e)}"

        return {
            "answer": answer,
            "retrieved_documents": docs,
            "context_list": [doc.page_content for doc in docs]
        }


def print_metrics_summary(summary: SummaryModel):
    """打印指标统计摘要（支持按字段分组）"""
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

        print(f"\n  📈 指标排名（从高到低）:")
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


async def generate_rag_responses(rag: RAG, questions: List[str]) -> List[Dict[str, Any]]:
    """为所有问题生成 RAG 响应"""
    results = []
    for i, question in enumerate(questions, 1):
        logger.info(f"处理问题 {i}/{len(questions)}: {question[:50]}...")
        result = await rag.query(question, top_k=3)
        results.append({
            "user_input": question,
            "response": result["answer"],
            "retrieved_contexts": result["context_list"]
        })
    return results


def save_rag_results_to_jsonl(results: List[Dict], output_path: str):
    """将 RAG 结果保存到 JSONL 文件"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for result in results:
            f.write(json.dumps(result, ensure_ascii=False) + '\n')
    logger.info(f"RAG 结果已保存到: {output_path}")


async def main():
    print("=" * 80)
    print("Dingo RAG 构建与批量评测示例")
    print("=" * 80)

    # 数据路径
    INPUT_JSONL = "test/data/fiqa.jsonl"
    RAG_OUTPUT_JSONL = "test/data/fiqa_rag_output.jsonl"

    # 步骤1: 从 fiqa.jsonl 加载问题
    logger.info(f"从 {INPUT_JSONL} 加载问题...")
    questions = []
    with open(INPUT_JSONL, 'r', encoding='utf-8') as f:
        for line in f:
            data = json.loads(line.strip())
            questions.append(data['user_input'])
    logger.info(f"已加载 {len(questions)} 个问题")

    # 步骤2: 使用 fiqa.jsonl 的 retrieved_contexts 构建 BM25 索引
    logger.info("构建 BM25 检索器...")
    retriever = BM25Retriever(jsonl_path=INPUT_JSONL, default_k=3)

    # 步骤3: 初始化 OpenAI 客户端和 RAG 系统
    client = AsyncOpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL
    )
    rag = RAG(client, retriever, model=OPENAI_MODEL)

    # 步骤4: 为所有问题生成 RAG 响应
    logger.info("开始生成 RAG 响应...")
    rag_results = await generate_rag_responses(rag, questions)

    # 步骤5: 保存 RAG 结果到 JSONL
    save_rag_results_to_jsonl(rag_results, RAG_OUTPUT_JSONL)

    # 步骤6: 使用 Dingo 框架进行批量评测
    print("\n" + "=" * 80)
    print("使用 Dingo 框架进行 RAG 评估")
    print("=" * 80)

    llm_config = {
        "model": OPENAI_MODEL,
        "key": OPENAI_API_KEY,
        "api_url": OPENAI_BASE_URL,
    }
    llm_config_embedding = {
        "model": OPENAI_MODEL,
        "key": OPENAI_API_KEY,
        "api_url": OPENAI_BASE_URL,
        "parameters": {
            "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
            "strictness": 3,
            "threshold": 5
        }
    }

    input_data = {
        "task_name": "rag_evaluation_with_mock_rag",
        "input_path": RAG_OUTPUT_JSONL,
        "output_path": "outputs/",
        # "log_level": "INFO",
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

    # 执行评测
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    summary = executor.execute()

    # 打印评测结果
    print_metrics_summary(summary)

    print("\n✅ 评测完成！")
    print(f"详细结果已保存到: {summary.output_path}")

if __name__ == "__main__":
    asyncio.run(main())
