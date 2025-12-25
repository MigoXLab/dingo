"""
RAG Context Relevancy (上下文相关性) LLM评估器

基于LLM评估检索上下文与问题的相关性。
"""

import json
from typing import List

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMRAGContextRelevancy")
class LLMRAGContextRelevancy(BaseOpenAI):
    """
    RAG上下文相关性评估LLM

    输入要求:
    - input_data.prompt 或 raw_data['question']: 用户问题
    - input_data.context 或 raw_data['contexts']: 检索到的上下文列表

    注意: Context Relevancy 只需要问题和上下文，不需要答案

    RAG上下文相关性评估Prompt

    输入参数:
    - {0}: 问题 (question)
    - {1}: 上下文 (contexts，已拼接)

    基于 Ragas、DeepEval 和 TruLens 的设计
    """

    _metric_info = {
        "category": "RAG Evaluation Metrics",
        "metric_name": "PromptRAGContextRelevancy",
        "description": "评估检索上下文与问题的相关性，检测噪声信息",
        "paper_title": "RAGAS: Automated Evaluation of Retrieval Augmented Generation",
        "paper_url": "https://arxiv.org/abs/2309.15217",
        "examples": "examples/rag/dataset_rag_eval_baseline.py",
        "source_frameworks": "Ragas + DeepEval + TruLens"
    }

    @staticmethod
    def context_relevance_judge1_prompt(query: str, context: str) -> str:
        """
        First judge template for context relevance evaluation (Chinese version).

        Args:
            query: The user's question
            context: The retrieved context to evaluate

        Returns:
            Prompt string for rating (0, 1, or 2)
        """
        safe_query = json.dumps(query)
        safe_context = json.dumps(context)

        return f"""### 指令

你是一位世界级专家，专门评估上下文对回答问题的相关性分数。
你的任务是确定上下文是否包含回答问题所需的适当信息。
请不要依赖你对该问题的先前知识。
仅使用上下文和问题中提供的信息。
请遵循以下指示：
0. 如果上下文不包含任何与回答问题相关的信息，请给出0分。
1. 如果上下文部分包含与回答问题相关的信息，请给出1分。
2. 如果上下文包含与回答问题相关的信息，请给出2分。
你必须提供0、1或2的相关性分数，不要提供其他内容。
请不要解释。
请以JSON格式返回你的响应，格式如下：{{"rating": X}}，其中X是0、1或2。

### 问题：{safe_query}

### 上下文：{safe_context}

请不要尝试解释。
分析上下文和问题后，相关性分数为 """

    @staticmethod
    def context_relevance_judge2_prompt(query: str, context: str) -> str:
        """
        Second judge template for context relevance evaluation (Chinese version).

        Args:
            query: The user's question
            context: The retrieved context to evaluate

        Returns:
            Prompt string for rating (0, 1, or 2)
        """
        safe_query = json.dumps(query)
        safe_context = json.dumps(context)

        return f"""

作为一名专门评估给定上下文与问题相关性分数的专家，我的任务是确定上下文在多大程度上提供了回答问题所需的信息。
我将仅依赖上下文和问题中提供的信息，而不依赖任何先前的知识。

我将遵循以下指示：
* 如果上下文不包含任何与回答问题相关的信息，我将给出0分的相关性分数。
* 如果上下文部分包含与回答问题相关的信息，我将给出1分的相关性分数。
* 如果上下文包含与回答问题相关的信息，我将给出2分的相关性分数。
请以JSON格式返回你的响应，格式如下：{{"rating": X}}，其中X是0、1或2。

### 问题：{safe_query}

### 上下文：{safe_context}

请不要尝试解释。
根据提供的问题和上下文，相关性分数为 ["""

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        """
        构建LLM输入消息

        Args:
            input_data: 输入数据

        Returns:
            消息列表
        """
        # 提取字段
        raw_data = getattr(input_data, 'raw_data', {})
        question = input_data.prompt or raw_data.get("question", "")

        # 处理contexts
        contexts = None
        if input_data.context:
            if isinstance(input_data.context, list):
                contexts = input_data.context
            else:
                contexts = [input_data.context]
        elif "contexts" in raw_data:
            raw_contexts = raw_data["contexts"]
            if isinstance(raw_contexts, list):
                contexts = raw_contexts
            else:
                contexts = [raw_contexts]

        if not question:
            raise ValueError("Context Relevancy评估需要question字段")
        if not contexts:
            raise ValueError("Context Relevancy评估需要contexts字段")

        # 对于每个上下文，使用第一个judge prompt
        # 这里我们使用第一个judge prompt作为主要评估
        combined_contexts = "\n\n".join([f"上下文{i + 1}:\n{ctx}" for i, ctx in enumerate(contexts)])

        # 构建prompt内容
        prompt_content = cls.context_relevance_judge1_prompt(question, combined_contexts)

        messages = [{"role": "user", "content": prompt_content}]

        return messages

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        """
        处理LLM响应

        Args:
            response: LLM原始响应

        Returns:
            EvalDetail对象
        """
        log.info(f"RAG Context Relevancy response: {response}")

        # 清理响应
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]

        try:
            response_json = json.loads(response.strip())
        except json.JSONDecodeError:
            raise ConvertJsonError(f"Convert to JSON format failed: {response}")

        # 解析响应 - 现在是0-2的评分
        rating = response_json.get("rating", 0)

        # 将0-2的评分转换为0-10的评分
        score = (rating / 2) * 10

        # 生成评估理由
        if rating == 0:
            reason = "上下文不包含任何与问题相关的信息"
        elif rating == 1:
            reason = "上下文部分包含与问题相关的信息"
        else:  # rating == 2
            reason = "上下文包含与问题相关的信息"

        result = EvalDetail(metric=cls.__name__)
        result.score = score

        # 根据分数判断是否通过，默认阈值为5
        threshold = 5
        if hasattr(cls, 'dynamic_config') and cls.dynamic_config.parameters:
            threshold = cls.dynamic_config.parameters.get('threshold', 5)

        if score >= threshold:
            result.status = False
            result.label = ["QUALITY_GOOD.CONTEXT_RELEVANCY_PASS"]
            result.reason = [f"上下文相关性评估通过 (分数: {score:.2f}/10)\n{reason}"]
        else:
            result.status = True
            result.label = ["QUALITY_BAD.CONTEXT_RELEVANCY_FAIL"]
            result.reason = [f"上下文相关性评估未通过 (分数: {score:.2f}/10)\n{reason}"]

        return result
