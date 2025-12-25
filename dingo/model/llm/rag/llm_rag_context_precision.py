"""
RAG Context Precision (上下文精度) LLM评估器

基于LLM评估检索上下文的精确度和排序质量。
"""
import json
import time
from typing import List

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
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
        "examples": "examples/rag/dataset_rag_eval_baseline.py",
        "source_frameworks": "Ragas"
    }

    @classmethod
    def context_precision_prompt(cls, question: str, context: str, answer: str) -> str:
        """上下文精度评估Prompt (Chinese version)

        输入参数:
        - question: 用户问题
        - context: 单个检索上下文
        - answer: 生成的答案

        输出格式:
        ```json
        {{
            "verdict": true/false,
            "reason": "简要说明判断理由"
        }}
        ```
        true表示上下文相关，false表示不相关
        """
        return f"""
你是一个信息检索专家。你的任务是评估检索到的上下文是否对回答问题有帮助。

**问题**:
{question}

**答案**:
{answer}

**上下文**:
{context}

**任务要求**:
1. 仔细分析上下文内容，判断它是否包含有助于回答问题的相关信息
2. 为你的判断提供简洁的理由
3. 严格按照指定格式输出结果

**判断标准**:
- 相关 (true): 上下文包含与问题直接相关的信息，这些信息对于生成答案是有帮助的
- 不相关 (false): 上下文与问题无关，或者不包含任何有用的信息

**输出格式要求**:
仅以JSON格式返回结果，包含以下字段：
- verdict: true表示相关，false表示不相关
- reason: 简要说明判断理由

**示例输出**:
```json
{{
    "verdict": true,
    "reason": "上下文明确提到北京是中国的首都，与问题直接相关"
}}
```

或者：
```json
{{
    "verdict": false,
    "reason": "上下文讨论的是天气，与问题无关"
}}
```
        """

    @classmethod
    def _calculate_average_precision(cls, verdicts: List[bool]) -> float:
        """计算平均精度(Average Precision)

        Args:
            verdicts: 相关性判断列表，true表示相关，false表示不相关

        Returns:
            float: 平均精度分数
        """

        # 转换为0/1列表
        verdict_list = [1 if v else 0 for v in verdicts]
        denominator = sum(verdict_list) + 1e-10
        numerator = sum(
            [
                (sum(verdict_list[: i + 1]) / (i + 1)) * verdict_list[i]
                for i in range(len(verdict_list))
            ]
        )
        score = numerator / denominator
        return float(score)

    @classmethod
    def _ensemble_verdicts(cls, verdicts_list: List[dict]) -> dict:
        """集成多个评估结果

        Args:
            verdicts_list: 多个评估结果列表

        Returns:
            dict: 集成后的评估结果
        """
        if not verdicts_list:
            return {"verdict": False, "reason": "没有评估结果"}

        # 统计真实结果数量
        true_count = sum(1 for v in verdicts_list if v.get("verdict", False))
        total_count = len(verdicts_list)

        # 简单多数投票
        final_verdict = true_count > total_count / 2

        # 收集所有理由
        reasons = [v.get("reason", "无理由") for v in verdicts_list]
        final_reason = "; ".join(reasons[:3])  # 最多显示3个理由

        return {
            "verdict": final_verdict,
            "reason": final_reason
        }

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        """构建LLM输入消息"""
        # 提取字段
        raw_data = getattr(input_data, 'raw_data', {})
        question = input_data.prompt or raw_data.get("question", "")
        answer = input_data.content or raw_data.get("answer", "")

        if not answer:
            raise ValueError("Context Precision评估需要answer字段")

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
            raise ValueError("Context Precision评估需要contexts字段")

        # 为每个上下文构建单独的消息
        messages_list = []
        for i, context in enumerate(contexts):
            prompt_content = cls.context_precision_prompt(question, context, answer)
            messages_list.append({
                "context_index": i,
                "messages": [{"role": "user", "content": prompt_content}]
            })

        return messages_list

    @classmethod
    def process_response(cls, responses: List[str]) -> EvalDetail:
        """处理LLM响应

        Args:
            responses: 每个上下文的评估响应列表

        Returns:
            EvalDetail: 评估结果
        """
        log.info(f"RAG Context Precision responses: {responses}")

        # 解析每个响应
        all_verdicts = []
        all_reasons = []
        context_verdicts = []

        for i, response in enumerate(responses):
            # 清理响应
            cleaned_response = response
            if cleaned_response.startswith("```json"):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.startswith("```"):
                cleaned_response = cleaned_response[3:]
            if cleaned_response.endswith("```"):
                cleaned_response = cleaned_response[:-3]

            try:
                response_json = json.loads(cleaned_response.strip())
                # 如果是包含多个评估结果的列表
                if isinstance(response_json, list):
                    # 集成多个评估结果
                    ensemble_result = cls._ensemble_verdicts(response_json)
                    verdict = ensemble_result["verdict"]
                    reason = ensemble_result["reason"]
                else:
                    # 单个评估结果
                    verdict = response_json.get("verdict", False)
                    reason = response_json.get("reason", "无理由")

                context_verdicts.append(verdict)
                all_verdicts.append(verdict)
                all_reasons.append(f"上下文{i + 1}: {'相关' if verdict else '不相关'}\n理由: {reason}")
            except json.JSONDecodeError:
                raise ConvertJsonError(f"Convert to JSON format failed for response {i + 1}: {response}")

        # 计算平均精度
        avg_precision = cls._calculate_average_precision(context_verdicts)
        # 转换为0-10分
        score = round(avg_precision * 10, 2)

        # 构建评估理由
        reason_text = "\n\n".join(all_reasons)
        reason_text += f"\n\n平均精度: {avg_precision:.4f}，转换为0-10分: {score}/10"

        result = EvalDetail(metric=cls.__name__)
        result.score = score

        # 根据分数判断是否通过，默认阈值为5
        threshold = 5
        if hasattr(cls, 'dynamic_config') and cls.dynamic_config.parameters:
            threshold = cls.dynamic_config.parameters.get('threshold', 5)

        if score >= threshold:
            result.status = False
            result.label = ["QUALITY_GOOD.CONTEXT_PRECISION_PASS"]
            result.reason = [f"上下文精度评估通过 (分数: {score}/10)\n{reason_text}"]
        else:
            result.status = True
            result.label = ["QUALITY_BAD.CONTEXT_PRECISION_FAIL"]
            result.reason = [f"上下文精度评估未通过 (分数: {score}/10)\n{reason_text}"]

        return result

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """重写父类的eval方法，支持为每个上下文发送单独的请求"""
        if cls.client is None:
            cls.create_client()

        # 获取所有上下文的消息
        messages_list = cls.build_messages(input_data)
        responses = []

        # 为每个上下文发送单独的请求
        for item in messages_list:
            messages = item["messages"]
            attempts = 0
            response = None

            while attempts < 3:
                try:
                    response = cls.send_messages(messages)
                    break
                except Exception as e:
                    attempts += 1
                    log.error(f"发送消息失败 (尝试 {attempts}/3): {e}")
                    time.sleep(1)

            if response is None:
                # 如果所有尝试都失败，返回错误结果
                res = EvalDetail(metric=cls.__name__)
                # res.eval_status = True
                # res.eval_details = {
                #     "label": ["QUALITY_BAD.REQUEST_FAILED"],
                #     "metric": [cls.__name__],
                #     "reason": [f"为上下文{item['context_index']+1}发送请求失败"]
                # }
                res.status = True
                res.label = ["QUALITY_BAD.REQUEST_FAILED"]
                res.reason = [f"为上下文{item['context_index'] + 1}发送请求失败"]
                return res

            responses.append(response)

        # 处理所有响应
        return cls.process_response(responses)
