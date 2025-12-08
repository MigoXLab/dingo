"""
参考 ragas/examples/ragas_examples/improve_rag/rag.py 构建的 RAG 系统及评测示例。

本示例展示了如何：
1. 构建一个基于 BM25 检索和 OpenAI 生成的简单 RAG 系统。
2. 使用 Dingo 对 RAG 系统的输出进行多维度评测（忠实度、上下文相关性、答案相关性等）。

前置依赖:
    pip install langchain langchain-community langchain-text-splitters datasets openai dingo-python

环境变量:
    OPENAI_API_KEY: OpenAI API 密钥
    OPENAI_BASE_URL: (可选) OpenAI API 基础 URL
    OPENAI_MODEL: (可选) 使用的模型名称，默认为 deepseek-chat
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

# RAG 构建相关依赖
import datasets
from langchain_community.retrievers import BM25Retriever as LangchainBM25Retriever
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from openai import AsyncOpenAI

# Dingo 评测相关依赖
from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.rag.llm_rag_answer_relevancy import LLMRAGAnswerRelevancy
from dingo.model.llm.rag.llm_rag_context_precision import LLMRAGContextPrecision
from dingo.model.llm.rag.llm_rag_context_recall import LLMRAGContextRecall
from dingo.model.llm.rag.llm_rag_context_relevancy import LLMRAGContextRelevancy
from dingo.model.llm.rag.llm_rag_faithfulness import LLMRAGFaithfulness

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

    def __init__(self, dataset_name="m-ric/huggingface_doc", default_k=3):
        self.default_k = default_k
        # 为了演示方便，这里只加载数据集的前 100 条数据，避免下载过多数据
        logger.info(f"正在加载数据集 {dataset_name}...")
        try:
            # 尝试加载数据集，如果是流式或者部分加载会更快
            self.dataset = datasets.load_dataset(dataset_name, split="train", streaming=True)
            self.knowledge_base = list(self.dataset.take(100))
            logger.info(f"已加载 100 条数据用于构建索引")
        except Exception as e:
            logger.warning(f"加载 HuggingFace 数据集失败: {e}。将使用内置示例文档。")
            self.knowledge_base = [
                {"text": "Python 由 Guido van Rossum 于 1989 年底发明，第一个公开发行版发行于 1991 年。", "source": "manual/python_history"},
                {"text": "Dingo 是一个用于评估大语言模型(LLM)应用的框架，支持 RAG 评测。", "source": "manual/dingo_intro"},
                {"text": "深度学习是机器学习的一种，通过多层神经网络学习数据的表示。", "source": "manual/deep_learning"},
            ]

        self.retriever = self._build_retriever()

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


def evaluate_rag_result(question: str, rag_result: Dict[str, Any]):
    """使用 Dingo 评测 RAG 结果"""

    answer = rag_result["answer"]
    contexts = rag_result["context_list"]

    logger.info("正在进行评测...")

    # 构造 Dingo 数据对象
    # 注意：某些指标（如 ContextRecall）通常需要 ground_truth (reference)，
    # 这里我们模拟一种无 ground_truth 的场景，或者只评测无参考指标。
    # 如果需要评测 Recall，通常需要人工标注的标准答案。
    # 为了演示，我们只评测：
    # 1. Faithfulness (忠实度): 答案是否忠实于上下文
    # 2. Answer Relevancy (答案相关性): 答案是否回答了问题
    # 3. Context Relevancy (上下文相关性): 检索到的上下文是否与问题相关

    data = Data(
        data_id="rag_eval_demo",
        prompt=question,
        content=answer,
        context=contexts
    )

    # 1. 评测忠实度
    LLMRAGFaithfulness.dynamic_config = EvaluatorLLMArgs(
        key=OPENAI_API_KEY,
        api_url=OPENAI_BASE_URL,
        model=OPENAI_MODEL,
    )
    faith_result = LLMRAGFaithfulness.eval(data)
    print(f"Faithfulness details: {faith_result.eval_details}")

    # 2. 评测答案相关性
    LLMRAGAnswerRelevancy.dynamic_config = EvaluatorLLMArgs(
        key=OPENAI_API_KEY,
        api_url=OPENAI_BASE_URL,
        model=OPENAI_MODEL,
    )
    ans_rel_result = LLMRAGAnswerRelevancy.eval(data)
    print(f"Answer Relevancy details: {ans_rel_result.eval_details}")

    # 3. 评测上下文相关性
    LLMRAGContextRelevancy.dynamic_config = EvaluatorLLMArgs(
        key=OPENAI_API_KEY,
        api_url=OPENAI_BASE_URL,
        model=OPENAI_MODEL,
    )
    ctx_rel_result = LLMRAGContextRelevancy.eval(data)
    print(f"Context Relevancy details: {ctx_rel_result.eval_details}")

    return {
        "faithfulness": faith_result.eval_details,
        "answer_relevancy": ans_rel_result.eval_details,
        "context_relevancy": ctx_rel_result.eval_details
    }


async def main():
    print("=" * 60)
    print("Dingo RAG 构建与评测示例")
    print("=" * 60)

    # 初始化 OpenAI 客户端
    client = AsyncOpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL
    )

    # 初始化检索器
    # 如果没有 HuggingFace 环境，可能会回退到内置的简单文档
    retriever = BM25Retriever()

    # 初始化 RAG
    rag = RAG(client, retriever, model=OPENAI_MODEL)

    # 示例问题
    # 注意：问题的选择取决于加载了什么文档。
    # 如果加载了 huggingface_doc，可以问 transformers 相关的问题。
    # 如果回退到内置文档，可以问 Python 相关的问题。

    # 这里我们检测一下知识库内容来决定问什么
    sample_text = retriever.knowledge_base[0]["text"]
    if "Python" in sample_text or "Dingo" in sample_text:
        query = "Python 是哪一年发布的？"
    else:
        query = "How to load a model using transformers?"

    print(f"\nQuery: {query}")

    # 运行 RAG
    print("正在运行 RAG 查询...")
    result = await rag.query(query)

    print("\nRAG Result:")
    print(f"Answer: {result['answer']}")
    print(f"Retrieved {len(result['context_list'])} documents.")
    print(f"Contexts: {result['context_list']}")

    # 运行评测
    print("\n" + "-" * 40)
    print("开始 Dingo 评测")
    print("-" * 40)

    if result["context_list"]:
        evaluate_rag_result(query, result)
    else:
        print("未检索到文档，跳过评测。")

if __name__ == "__main__":
    asyncio.run(main())
