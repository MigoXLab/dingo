"""
RAG Answer Relevancy (答案相关性) LLM评估器

基于LLM评估答案是否直接回答了问题。
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


@Model.llm_register("LLMRAGAnswerRelevancy")
class LLMRAGAnswerRelevancy(BaseOpenAI):
    """
    RAG答案相关性评估LLM

    输入要求:
    - input_data.prompt 或 raw_data['question']: 用户问题
    - input_data.content 或 raw_data['answer']: 生成的答案

    RAG答案相关性评估Prompt

    输入参数:
    - %s[0]: 问题 (question)
    - %s[1]: 答案 (answer)
    """
    _metric_info = {
        "category": "RAG Evaluation Metrics",
        "metric_name": "PromptRAGAnswerRelevancy",
        "description": "评估答案是否直接回答问题，检测无关和冗余信息",
        "paper_title": "RAGAS: Automated Evaluation of Retrieval Augmented Generation",
        "paper_url": "https://arxiv.org/abs/2309.15217",
        "source_frameworks": "Ragas + DeepEval + TruLens"
    }
    prompt = """你是一个问答质量评估专家。你的任务是评估答案是否直接、完整地回答了用户的问题。

    **评估目标**:
    - 答案是否回答了问题
    - 答案是否包含无关或冗余信息
    - 答案的针对性和完整性

    **判断标准**:
    - 高分(8-10): 答案直接回答问题，信息准确且简洁
    - 中分(4-7): 答案回答了问题但包含一些无关信息
    - 低分(0-3): 答案大部分内容与问题无关或答非所问

    **问题**:
    {0}

    **答案**:
    {1}

    **任务要求**:
    1. 分析答案中的每个陈述是否与问题相关
    2. 识别无关、冗余或偏题的内容
    3. 评估答案的针对性和完整性
    4. 计算相关性分数
    5. 以JSON格式返回结果，不要输出其他内容

    **输出格式**:
    ```json
    {{
        "score": 0-10,
        "reason": "评估理由，指出相关和不相关的部分"
    }}
    ```

    其中score为0-10之间的整数，10表示答案完全相关，0表示答案完全不相关。
    """

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        """构建LLM输入消息"""
        # 提取字段
        raw_data = getattr(input_data, 'raw_data', {})
        question = input_data.prompt or raw_data.get("question", "")
        answer = input_data.content or raw_data.get("answer", "")

        if not question:
            raise ValueError("Answer Relevancy评估需要question字段")
        if not answer:
            raise ValueError("Answer Relevancy评估需要answer字段")

        # 构建prompt内容
        prompt_content = cls.prompt.format(question, answer)

        messages = [{"role": "user", "content": prompt_content}]

        return messages

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        """处理LLM响应"""
        log.info(f"RAG Answer Relevancy response: {response}")

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
            # result.name = "ANSWER_RELEVANCY_PASS"
            # result.reason = [f"答案相关性评估通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            result.eval_details = {
                "label": [f"{QualityLabel.QUALITY_GOOD}.ANSWER_RELEVANCY_PASS"],
                "metric": [cls.__name__],
                "reason": [f"答案相关性评估通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            }
        else:
            result.eval_status = True
            # result.type = cls.prompt.metric_type
            # result.name = cls.prompt.__name__
            # result.reason = [f"答案相关性评估未通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            result.eval_details = {
                "label": ["QUALITY_BAD.ANSWER_RELEVANCY_FAIL"],
                "metric": [cls.__name__],
                "reason": [f"答案相关性评估未通过 (分数: {response_model.score}/10)\n{response_model.reason}"]
            }

        return result
