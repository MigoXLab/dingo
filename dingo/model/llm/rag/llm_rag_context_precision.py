"""
RAG Context Precision (上下文精度) LLM评估器

基于LLM评估检索上下文的精确度和排序质量。
"""

import json
from typing import List

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.response.response_class import ResponseScoreReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMRAGContextPrecision")
class LLMRAGContextPrecision(BaseOpenAI):
    """
    RAG上下文精度评估LLM

    输入要求:
    - input_data.prompt 或 raw_data['question']: 用户问题
    - input_data.content 或 raw_data['answer']: 生成的答案
    - input_data.context 或 raw_data['contexts']: 检索到的上下文列表

    RAG上下文精度评估Prompt

    输入参数:
    - %s[0]: 问题 (question)
    - %s[1]: 答案 (answer)
    - %s[2]: 上下文列表 (contexts，每行一个)
    """

    _metric_info = {
        "category": "RAG Evaluation Metrics",
        "metric_name": "PromptRAGContextPrecision",
        "description": "评估检索上下文的精确度，包括相关性和排序质量",
        "paper_title": "RAGAS: Automated Evaluation of Retrieval Augmented Generation",
        "paper_url": "https://arxiv.org/abs/2309.15217",
        "source_frameworks": "Ragas"
    }

    prompt = """你是一个信息检索专家。你的任务是评估检索到的上下文是否对回答问题有帮助。

    **评估目标**:
    - 判断每个上下文是否与问题和答案相关
    - 评估上下文的排序质量（相关的应该排在前面）

    **判断标准**:
    - relevant (相关): 上下文包含有助于回答问题的信息
    - not_relevant (不相关): 上下文与问题无关或不包含有用信息

    **问题**:
    {0}

    **答案**:
    {1}

    **检索到的上下文**:
    {2}

    **任务要求**:
    1. 按顺序评估每个上下文的相关性
    2. 计算平均精度（Average Precision），考虑排序质量
    3. 相关上下文排在前面会得到更高分数
    4. 以JSON格式返回结果，不要输出其他内容

    **输出格式**:
    ```json
    {{
        "score": 0-10,
        "reason": "评估理由，说明各上下文的相关性"
    }}
    ```

    其中score为0-10之间的整数，10表示所有上下文相关且排序完美，0表示所有上下文都不相关。
    """

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        """构建LLM输入消息"""
        # 提取字段
        question = input_data.prompt or input_data.raw_data.get("question", "")
        answer = input_data.content or input_data.raw_data.get("answer", "")

        if not answer:
            raise ValueError("Context Precision评估需要answer字段")

        # 处理contexts
        contexts = None
        if input_data.context:
            if isinstance(input_data.context, list):
                contexts = input_data.context
            else:
                contexts = [input_data.context]
        elif "contexts" in input_data.raw_data:
            raw_contexts = input_data.raw_data["contexts"]
            if isinstance(raw_contexts, list):
                contexts = raw_contexts
            else:
                contexts = [raw_contexts]

        if not contexts:
            raise ValueError("Context Precision评估需要contexts字段")

        # 格式化上下文列表
        contexts_formatted = "\n".join([f"{i + 1}. {ctx}" for i, ctx in enumerate(contexts)])

        # 构建prompt内容
        prompt_content = cls.prompt.format(question, answer, contexts_formatted)

        messages = [{"role": "user", "content": prompt_content}]

        return messages

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        """处理LLM响应"""
        log.info(f"RAG Context Precision response: {response}")

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

        # 解析响应
        response_model = ResponseScoreReason(**response_json)

        result = ModelRes()
        result.score = response_model.score

        # 根据分数判断是否通过（默认阈值5，满分10分）
        threshold = 5
        if hasattr(cls, 'dynamic_config') and cls.dynamic_config.parameters:
            threshold = cls.dynamic_config.parameters.get('threshold', 5)

        if response_model.score >= threshold:
            result.eval_status = False
            # result.type = "QUALITY_GOOD"
            # result.name = "CONTEXT_PRECISION_PASS"
            # result.reason = [f"上下文精度评估通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            result.eval_details = {
                "label": ["QUALITY_GOOD.CONTEXT_PRECISION_PASS"],
                "metric": [cls.__name__],
                "reason": [f"上下文精度评估通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            }
        else:
            result.eval_status = True
            # result.type = cls.prompt.metric_type
            # result.name = cls.prompt.__name__
            # result.reason = [f"上下文精度评估未通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            result.eval_details = {
                "label": ["QUALITY_BAD.CONTEXT_PRECISION_FAIL"],
                "metric": [cls.__name__],
                "reason": [f"上下文精度评估未通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            }

        return result
