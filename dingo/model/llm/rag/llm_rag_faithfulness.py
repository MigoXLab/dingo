"""
RAG Faithfulness (忠实度) LLM评估器

基于LLM评估答案是否忠实于上下文，检测幻觉。
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


@Model.llm_register("LLMRAGFaithfulness")
class LLMRAGFaithfulness(BaseOpenAI):
    """
    RAG忠实度评估LLM

    输入要求:
    - input_data.prompt 或 raw_data['question']: 用户问题
    - input_data.content 或 raw_data['answer']: 生成的答案
    - input_data.context 或 raw_data['contexts']: 检索到的上下文列表

    RAG忠实度评估Prompt

    输入参数:
    - %s[0]: 问题 (question)
    - %s[1]: 答案 (answer)
    - %s[2]: 上下文 (contexts，已拼接)
    """

    _metric_info = {
        "category": "RAG Evaluation Metrics",
        "metric_name": "PromptRAGFaithfulness",
        "description": "评估生成答案是否忠实于给定上下文，检测幻觉和编造信息",
        "paper_title": "RAGAS: Automated Evaluation of Retrieval Augmented Generation",
        "paper_url": "https://arxiv.org/abs/2309.15217",
        "source_frameworks": "Ragas + DeepEval"
    }

    prompt = """你是一个严格的事实验证专家。你的任务是评估一个答案是否忠实于给定的上下文。

    **评估流程**:
    1. 从答案中提取独立的事实陈述
    2. 对每个陈述验证是否能从上下文推导
    3. 计算忠实陈述的比例

    **判断标准**:
    - faithful (忠实): 陈述可以从上下文中直接推导或明确支持
    - unfaithful (不忠实): 陈述无法从上下文推导，或与上下文矛盾，或包含上下文中没有的信息

    **问题**:
    {0}

    **答案**:
    {1}

    **上下文**:
    {2}

    **任务要求**:
    1. 提取答案中的独立陈述（每个陈述应该是完整的、可独立验证的事实）
    2. 对每个陈述判断是否忠实于上下文
    3. 计算忠实度分数 = 忠实陈述数量 / 总陈述数量
    4. 以JSON格式返回结果，不要输出其他内容

    **输出格式**:
    ```json
    {{
        "score": 0-10,
        "reason": "评估理由说明"
    }}
    ```

    其中score为0-10之间的整数，10表示完全忠实，0表示完全不忠实。
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
        raw_data = getattr(input_data, 'raw_data', {})
        question = input_data.prompt or raw_data.get("question", "")
        answer = input_data.content or raw_data.get("answer", "")

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

        if not contexts:
            raise ValueError("Faithfulness评估需要contexts字段")

        # 拼接上下文
        combined_contexts = "\n\n".join([f"上下文{i + 1}:\n{ctx}" for i, ctx in enumerate(contexts)])

        # 构建prompt内容
        prompt_content = cls.prompt.format(question, answer, combined_contexts)

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
        log.info(f"RAG Faithfulness response: {response}")

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

        # 根据分数判断是否通过（默认阈值5，满分10分）
        threshold = 5
        if hasattr(cls, 'dynamic_config') and cls.dynamic_config.parameters:
            threshold = cls.dynamic_config.parameters.get('threshold', 5)

        if response_model.score >= threshold:
            result.eval_status = False
            # result.type = "QUALITY_GOOD"
            # result.name = "FAITHFULNESS_PASS"
            # result.reason = [f"忠实度评估通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            result.eval_details = {
                "label": [f"{QualityLabel.QUALITY_GOOD}.FAITHFULNESS_PASS"],
                "metric": [cls.__name__],
                "reason": [f"忠实度评估通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            }
        else:
            result.eval_status = True
            # result.type = cls.prompt.metric_type
            # result.name = cls.prompt.__name__
            # result.reason = [f"忠实度评估未通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            result.eval_details = {
                "label": ["QUALITY_BAD.FAITHFULNESS_FAIL"],
                "metric": [cls.__name__],
                "reason": [f"忠实度评估未通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            }

        return result
