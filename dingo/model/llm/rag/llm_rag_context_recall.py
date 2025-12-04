"""
RAG Context Recall (上下文召回) LLM评估器

基于LLM评估检索上下文的完整性。
"""

import json
from typing import List

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes, QualityLabel
from dingo.model.response.response_class import ResponseScoreReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMRAGContextRecall")
class LLMRAGContextRecall(BaseOpenAI):
    """
    RAG上下文召回评估LLM

    输入要求:
    - input_data.prompt 或 raw_data['question']: 用户问题
    - input_data.raw_data['expected_output']: 标准答案/ground truth
    - input_data.context 或 raw_data['contexts']: 检索到的上下文列表

    注意: Context Recall 需要 expected_output 作为参考答案

    RAG上下文召回评估Prompt

    输入参数:
    - {0}: 问题 (question)
    - {1}: 答案/期望输出 (expected_output)
    - {2}: 上下文 (contexts，已拼接)

    基于 Ragas 和 DeepEval 的设计
    """

    _metric_info = {
        "category": "RAG Evaluation Metrics",
        "metric_name": "PromptRAGContextRecall",
        "description": "评估检索上下文的完整性，判断上下文是否能支持答案中的所有陈述",
        "paper_title": "RAGAS: Automated Evaluation of Retrieval Augmented Generation",
        "paper_url": "https://arxiv.org/abs/2309.15217",
        "source_frameworks": "Ragas + DeepEval"
    }

    prompt = """你是一个严格的事实核查专家。你的任务是评估检索到的上下文是否完整地支持了给定答案中的所有信息。

    **评估目标**:
    判断答案中的每个陈述是否能从上下文中找到支持证据

    **评估流程**:
    1. 从答案中提取独立的事实陈述
    2. 对每个陈述，判断是否能从上下文中归因（找到支持证据）
    3. 计算上下文召回率 = 可归因陈述数 / 总陈述数

    **判断标准**:
    - attributed (可归因): 陈述可以从上下文中直接找到或合理推导出
    - not attributed (不可归因): 陈述在上下文中没有支持证据

    **问题**:
    {0}

    **答案**:
    {1}

    **检索到的上下文**:
    {2}

    **任务要求**:
    1. 提取答案中的所有独立陈述（每个陈述应该是完整的、可独立验证的事实）
    2. 对每个陈述判断是否可以从上下文归因
    3. 计算召回率分数 = (可归因陈述数 / 总陈述数) × 10
    4. 以JSON格式返回结果，不要输出其他内容

    **输出格式**:
    ```json
    {{
        "score": 0-10,
        "reason": "评估理由，说明有多少陈述可以归因，有多少不能归因"
    }}
    ```

    其中score为0-10之间的整数，10表示所有陈述都能归因（完美召回），0表示所有陈述都不能归因。
    """

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
        question = input_data.prompt or input_data.raw_data.get("question", "")
        # Context Recall 需要 expected_output 而不是实际的 answer
        expected_output = input_data.raw_data.get("expected_output", "")
        if not expected_output:
            # 如果没有 expected_output，尝试使用 content 或 answer
            expected_output = input_data.content or input_data.raw_data.get("answer", "")

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

        if not expected_output:
            raise ValueError("Context Recall评估需要expected_output或answer字段")
        if not contexts:
            raise ValueError("Context Recall评估需要contexts字段")

        # 拼接上下文
        combined_contexts = "\n\n".join([f"上下文{i + 1}:\n{ctx}" for i, ctx in enumerate(contexts)])

        # 构建prompt内容
        prompt_content = cls.prompt.format(question, expected_output, combined_contexts)

        messages = [{"role": "user", "content": prompt_content}]

        return messages

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        """
        处理LLM响应

        Args:
            response: LLM原始响应

        Returns:
            ModelRes对象
        """
        log.info(f"RAG Context Recall response: {response}")

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
            # result.name = "CONTEXT_RECALL_PASS"
            # result.reason = [f"上下文召回评估通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            result.eval_details = {
                "label": [f"{QualityLabel.QUALITY_GOOD}.CONTEXT_RECALL_PASS"],
                "metric": [cls.__name__],
                "reason": [f"上下文召回评估通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            }
        else:
            result.eval_status = True
            # result.type = cls.prompt.metric_type
            # result.name = cls.prompt.__name__
            # result.reason = [f"上下文召回评估未通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            result.eval_details = {
                "label": ["QUALITY_BAD.CONTEXT_RECALL_FAIL"],
                "metric": [cls.__name__],
                "reason": [f"上下文召回评估未通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            }

        return result
