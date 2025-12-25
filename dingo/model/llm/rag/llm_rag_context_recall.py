"""
RAG Context Recall (上下文召回) LLM评估器

基于LLM评估检索上下文的完整性。
"""

import json
from typing import List

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
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
        "examples": "examples/rag/dataset_rag_eval_baseline.py",
        "source_frameworks": "Ragas + DeepEval"
    }

    prompt = """上下文召回评估提示词，用于分类陈述归因"""

    @staticmethod
    def context_recall_prompt(question: str, context: str, answer: str) -> str:
        """
        生成上下文召回评估的提示词

        参数:
            question: 原始问题
            context: 用于评估的检索上下文
            answer: 包含要分类陈述的参考答案

        返回:
            为LLM格式化的提示字符串
        """
        # 使用json.dumps()安全转义字符串
        safe_question = json.dumps(question)
        safe_context = json.dumps(context)
        safe_answer = json.dumps(answer)

        return f"""给定一个上下文和一个答案，请分析答案中的每个句子，并分类该句子是否可以归因于给定的上下文。仅使用'是'(1)或'否'(0)作为二元分类。输出包含理由的JSON格式。

 --------示例-----------
 示例1
 输入: {{
     "question": "关于中国的长城，你能告诉我什么？",
     "context": "长城是中国古代的军事防御工程，是世界上最伟大的建筑之一。长城的修建始于春秋战国时期，秦始皇统一中国后将各诸侯国的长城连接起来，形成了万里长城的雏形。明朝是长城修建的鼎盛时期，今天我们看到的大部分长城都是明朝修建的。长城的主要作用是防御北方游牧民族的入侵，它不仅是一道军事防线，也是中国古代文明的象征。1987年，长城被联合国教科文组织列入世界文化遗产名录。",
     "answer": "长城是中国古代的军事防御工程，是世界上最伟大的建筑之一。长城始建于春秋战国时期，秦始皇统一中国后将各诸侯国的长城连接起来。长城在唐朝达到了修建的鼎盛时期，今天我们看到的大部分长城都是唐朝修建的。长城的主要作用是抵御南方诸侯国的进攻。"
 }}
 输出: {{
     "classifications": [
         {{
             "statement": "长城是中国古代的军事防御工程，是世界上最伟大的建筑之一。",
             "reason": "上下文中明确提到了长城的性质和地位。",
             "attributed": 1
         }},
         {{
             "statement": "长城始建于春秋战国时期，秦始皇统一中国后将各诸侯国的长城连接起来。",
             "reason": "给定上下文中存在完全相同的信息。",
             "attributed": 1
         }},
         {{
             "statement": "长城在唐朝达到了修建的鼎盛时期，今天我们看到的大部分长城都是唐朝修建的。",
             "reason": "上下文中提到鼎盛时期是明朝而非唐朝。",
             "attributed": 0
         }},
         {{
             "statement": "长城的主要作用是抵御南方诸侯国的进攻。",
             "reason": "上下文中提到长城的作用是防御北方游牧民族而非南方诸侯国。",
             "attributed": 0
         }}
     ]
 }}
 -----------------------------

 现在对以下输入执行相同操作
 输入: {{
     "question": {safe_question},
     "context": {safe_context},
     "answer": {safe_answer}
 }}
 输出: """

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
        # Context Recall 需要 expected_output 而不是实际的 answer
        expected_output = raw_data.get("expected_output", "")
        if not expected_output:
            # 如果没有 expected_output，尝试使用 content 或 answer
            expected_output = input_data.content or raw_data.get("answer", "")

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

        if not expected_output:
            raise ValueError("Context Recall评估需要expected_output或answer字段")
        if not contexts:
            raise ValueError("Context Recall评估需要contexts字段")

        # 拼接上下文
        combined_contexts = "\n\n".join([f"上下文{i + 1}:\n{ctx}" for i, ctx in enumerate(contexts)])

        # 构建prompt内容
        prompt_content = cls.context_recall_prompt(question, combined_contexts, expected_output)

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

        # 计算分数：(可归因陈述数 / 总陈述数) × 10
        classifications = response_json.get("classifications", [])
        total_statements = len(classifications)
        attributed_statements = sum(1 for item in classifications if item.get("attributed", 0) == 1)

        if total_statements == 0:
            score = 0
        else:
            score = (attributed_statements / total_statements) * 10

        # 生成详细的reason文本，包含每个陈述的信息
        all_reasons = []
        for i, item in enumerate(classifications):
            statement = item.get("statement", "")
            is_attributed = item.get("attributed", 0) == 1
            reason = item.get("reason", "")

            status_text = "可归因于上下文" if is_attributed else "不可归因于上下文"
            all_reasons.append(f"陈述{i + 1}: {statement}\n状态: {status_text}\n理由: {reason}")

        # 构建完整的reason文本
        reason_text = "\n\n".join(all_reasons)
        reason_text += f"\n\n总共有 {total_statements} 个陈述，其中 {attributed_statements} 个可归因于上下文，{total_statements - attributed_statements} 个不可归因于上下文"

        result = EvalDetail(metric=cls.__name__)
        result.score = score

        # 根据分数判断是否通过，默认阈值为5
        threshold = 5
        if hasattr(cls, 'dynamic_config') and cls.dynamic_config.parameters:
            threshold = cls.dynamic_config.parameters.get('threshold', 5)

        if score >= threshold:
            result.status = False
            result.label = ["QUALITY_GOOD.CONTEXT_RECALL_PASS"]
            result.reason = [f"上下文召回评估通过 (分数: {score:.2f}/10)\n{reason_text}"]
        else:
            result.status = True
            result.label = ["QUALITY_BAD.CONTEXT_RECALL_FAIL"]
            result.reason = [f"上下文召回评估未通过 (分数: {score:.2f}/10)\n{reason_text}"]

        return result
