"""
RAG Faithfulness (忠实度) LLM评估器

基于LLM评估答案是否忠实于上下文，检测幻觉。
"""

import json
from typing import List

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
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
        "examples": "examples/rag/dataset_rag_eval_baseline.py",
        "source_frameworks": "Ragas + DeepEval"
    }

    @staticmethod
    def statement_generator_prompt(question: str, answer: str) -> str:
        """
        Prompt to generate statements from answer (Chinese version).

        Args:
            question: The user's question
            answer: The generated answer

        Returns:
            Prompt string for statement generation
        """
        safe_question = json.dumps(question)
        safe_answer = json.dumps(answer)

        return f"""### 指令

给定一个问题和一个答案，请分析答案中每个句子的复杂性。将每个句子分解为一个或多个完全可理解的陈述。确保在任何陈述中都不使用代词。

### 问题：{safe_question}

### 答案：{safe_answer}

请以JSON格式返回结果，格式如下：
```json
{{
    "statements": [
        "陈述1",
        "陈述2",
        "陈述3"
    ]
}}
```

请不要输出其他内容，只返回JSON格式的结果。
"""

    @staticmethod
    def faithfulness_judge_prompt(context: str, statements: List[str]) -> str:
        """
        Prompt to judge faithfulness of statements (Chinese version).

        Args:
            context: The retrieved context
            statements: List of statements to evaluate

        Returns:
            Prompt string for faithfulness judgment
        """
        safe_context = json.dumps(context)
        safe_statements = json.dumps(statements)

        return f"""### 指令

你的任务是根据给定的上下文判断一系列陈述的忠实度。对于每个陈述，如果可以从上下文中直接推导出该陈述，请返回verdict为1；如果无法从上下文中直接推导出该陈述，请返回verdict为0。

### 上下文：{safe_context}

### 陈述列表：{safe_statements}

请以JSON格式返回结果，格式如下：
```json
{{
    "statements": [
        {{
            "statement": "原始陈述，一字不差",
            "reason": "判断理由",
            "verdict": 0或1
        }}
    ]
}}
```

请不要输出其他内容，只返回JSON格式的结果。
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
        elif hasattr(input_data, "contexts"):
            raw_contexts = input_data.contexts
            if isinstance(raw_contexts, list):
                contexts = raw_contexts
            else:
                contexts = [raw_contexts]

        if not contexts:
            raise ValueError("Faithfulness评估需要contexts字段")

        # 拼接上下文
        combined_contexts = "\n\n".join([f"上下文{i + 1}:\n{ctx}" for i, ctx in enumerate(contexts)])

        # 构建prompt内容
        # 根据ragas的设计，我们需要先生成陈述，然后判断忠实度
        # 这里我们将两个步骤合并到一个prompt中
        prompt_content = f"""你是一个严格的事实验证专家。你的任务是评估一个答案是否忠实于给定的上下文。

**评估流程**:
1. 从答案中提取独立的事实陈述
2. 对每个陈述验证是否能从上下文推导
3. 计算忠实陈述的比例

**问题**:
{question}

**答案**:
{answer}

**上下文**:
{combined_contexts}

**任务要求**:
1. 提取答案中的独立陈述（每个陈述应该是完整的、可独立验证的事实，不使用代词）
2. 对每个陈述判断是否忠实于上下文：
   - 忠实：陈述可以从上下文中直接推导或明确支持
   - 不忠实：陈述无法从上下文推导，或与上下文矛盾，或包含上下文中没有的信息
3. 计算忠实度分数 = (忠实陈述数量 / 总陈述数量) × 10
4. 以JSON格式返回结果，包含：
   - statements：提取的陈述列表，每个陈述包含原始内容、判断理由和 verdict（0或1）
   - score：忠实度分数（0-10之间的数值）

**示例**:

**问题**:
中国的首都是哪里？

**答案**:
中国的首都是北京，北京是中国的政治中心，也是中国最大的城市之一。

**上下文**:
中国的首都是北京，北京是中国的政治中心。

**示例输出**:
```json
{{
    "statements": [
        {{
            "statement": "中国的首都是北京",
            "reason": "上下文明确提到中国的首都是北京",
            "verdict": 1
        }},
        {{
            "statement": "北京是中国的政治中心",
            "reason": "上下文明确提到北京是中国的政治中心",
            "verdict": 1
        }},
        {{
            "statement": "北京是中国最大的城市之一",
            "reason": "上下文没有提到北京是中国最大的城市之一",
            "verdict": 0
        }}
    ],
    "score": 6.67
}}
```

**输出格式**:
```json
{{
    "statements": [
        {{
            "statement": "原始陈述",
            "reason": "判断理由",
            "verdict": 0或1
        }}
    ],
    "score": 0-10
}}
```

请不要输出其他内容，只返回JSON格式的结果。
"""

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
        score = response_json.get("score", 0)
        statements = response_json.get("statements", [])

        # 生成评估理由
        faithful_count = sum(1 for stmt in statements if stmt.get("verdict", 0) == 1)
        total_count = len(statements)

        if total_count > 0:
            reason = f"共提取{total_count}个陈述，其中{faithful_count}个忠实于上下文，{total_count - faithful_count}个不忠实于上下文。"
            # 添加每个陈述的详细信息
            for i, stmt in enumerate(statements, 1):
                status = "忠实" if stmt.get("verdict", 0) == 1 else "不忠实"
                reason += f"\n{i}. [{status}] {stmt.get('statement', '')}\n   理由: {stmt.get('reason', '')}"
        else:
            reason = "未提取到任何陈述"

        result = EvalDetail(metric=cls.__name__)
        result.score = score

        # 根据分数判断是否通过，默认阈值为5
        threshold = 5
        if hasattr(cls, 'dynamic_config') and cls.dynamic_config.parameters:
            threshold = cls.dynamic_config.parameters.get('threshold', 5)

        if score >= threshold:
            result.status = False
            result.label = ["QUALITY_GOOD.FAITHFULNESS_PASS"]
            result.reason = [f"忠实度评估通过 (分数: {score:.2f}/10)\n{reason}"]
        else:
            result.status = True
            result.label = ["QUALITY_BAD.FAITHFULNESS_FAIL"]
            result.reason = [f"忠实度评估未通过 (分数: {score:.2f}/10)\n{reason}"]

        return result
