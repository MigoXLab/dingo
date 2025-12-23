"""
RAG Answer Relevancy (答案相关性) LLM评估器

基于LLM和Embedding模型评估答案与问题的相关性。
参考RAGAS的实现，通过生成相关问题并计算相似度来评估答案相关性。
"""

import json
from typing import Any, Dict, List

import numpy as np

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMRAGAnswerRelevancy")
class LLMRAGAnswerRelevancy(BaseOpenAI):
    """
    RAG答案相关性评估LLM

    输入要求:
    - input_data.prompt 或 raw_data['question']: 用户问题
    - input_data.content 或 raw_data['answer']: 生成的答案

    RAG答案相关性评估基于RAGAS的实现：
    1. 从答案生成相关问题
    2. 计算生成的问题与原始问题的相似度
    3. 评估答案是否是不置可否的
    4. 综合计算相关性分数
    """
    _metric_info = {
        "category": "RAG Evaluation Metrics",
        "metric_name": "PromptRAGAnswerRelevancy",
        "description": "评估答案是否直接回答问题，检测无关和冗余信息",
        "paper_title": "RAGAS: Automated Evaluation of Retrieval Augmented Generation",
        "paper_url": "https://arxiv.org/abs/2309.15217",
        "examples": "examples/rag/dataset_rag_eval_baseline.py",
        "source_frameworks": "Ragas"
    }

    question_generation_prompt = """Task: Generate a question for the given answer and identify if the answer is noncommittal.

    Instructions:
    1. Generate a single question that directly corresponds to the provided answer content.
    2. Determine if the answer is noncommittal:
       - Set "noncommittal" to 1 if the answer is evasive, vague, or ambiguous (e.g., "I don't know", "I'm not sure")
       - Set "noncommittal" to 0 if the answer provides a clear, direct response
    3. Ensure the generated question maintains a consistent language style throughout.

    --------EXAMPLES-----------
    Example 1:
    Input: {{
        "response": "Albert Einstein was born in Germany."
    }}
    Output: {{
        "question": "Where was Albert Einstein born?",
        "noncommittal": 0
    }}

    Example 2:
    Input: {{
        "response": "I don't know about the groundbreaking feature of the smartphone invented in 2023 as I'm unaware of information beyond 2022."
    }}
    Output: {{
        "question": "What was the groundbreaking feature of the smartphone invented in 2023?",
        "noncommittal": 1
    }}
    -----------------------------

    Now perform the same with the following input:
    Input: {{
        "response": {0}
    }}
    Output: """

    # 配置参数
    strictness = 3  # 生成的问题数量

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        """构建LLM输入消息"""
        # 提取字段
        raw_data = getattr(input_data, 'raw_data', {})
        answer = input_data.content or raw_data.get("answer", "")

        if not answer:
            raise ValueError("Answer Relevancy评估需要answer字段")

        # 使用json.dumps()来安全转义响应字符串
        import json
        safe_response = json.dumps(answer)

        # 构建prompt内容
        prompt_content = cls.question_generation_prompt.format(safe_response)

        messages = [{"role": "user", "content": prompt_content}]

        return messages

    @classmethod
    def generate_multiple_questions(cls, input_data: Data, n: int = 3) -> List[Dict[str, Any]]:
        """生成多个相关问题"""
        questions = []

        # 确保客户端已经创建
        if not hasattr(cls, 'client') or cls.client is None:
            cls.create_client()

        for i in range(n):
            # 构建消息
            messages = cls.build_messages(input_data)

            # 调用LLM生成问题
            response = cls.send_messages(messages)

            # 处理响应
            processed_response = cls.process_question_response(response)
            questions.append(processed_response)

        return questions

    @classmethod
    def process_question_response(cls, response: str) -> Dict[str, Any]:
        """处理问题生成的响应"""
        log.info(f"Question generation response: {response}")

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

        return response_json

    @classmethod
    def calculate_similarity(cls, question: str, generated_questions: List[str]) -> np.ndarray:
        """计算原始问题与生成问题的相似度"""
        # 检查 Embedding 模型是否已初始化
        if cls.embedding_model is None:
            raise ValueError(
                "Embedding model not initialized. Please configure 'embedding_config' in your LLM config with:\n"
                "  - model: embedding model name (e.g., 'BAAI/bge-m3')\n"
                "  - api_url: embedding service URL\n"
                "  - key: API key (optional for local services)"
            )

        # 检查生成的问题是否为空列表或全为空字符串
        if not generated_questions or all(q == "" for q in generated_questions):
            return np.array([])

        # 生成embedding
        # 单个查询的embedding
        question_response = cls.embedding_model['client'].embeddings.create(
            model=cls.embedding_model['model_name'],
            input=question
        )
        question_vec = np.asarray(question_response.data[0].embedding).reshape(1, -1)

        # 多个文档的embedding
        gen_questions_response = cls.embedding_model['client'].embeddings.create(
            model=cls.embedding_model['model_name'],
            input=generated_questions
        )
        gen_question_vec = np.asarray([data.embedding for data in gen_questions_response.data]).reshape(len(generated_questions), -1)

        # 计算余弦相似度
        norm = np.linalg.norm(gen_question_vec, axis=1) * np.linalg.norm(question_vec, axis=1)
        return np.dot(gen_question_vec, question_vec.T).reshape(-1) / norm

    @classmethod
    def calculate_score(cls, answers: List[Dict[str, Any]], original_question: str) -> tuple[float, List[Dict[str, Any]]]:
        """计算答案相关性分数并收集详细信息"""
        # 提取生成的问题
        gen_questions = [answer.get("question", "") for answer in answers]

        # 检查是否所有生成的问题都为空
        if all(q == "" for q in gen_questions):
            log.warning("Invalid response. Expected dictionary with key 'question'")
            return 0.0, []

        # 检查是否所有答案都是不置可否的
        all_noncommittal = np.all([answer.get("noncommittal", 0) for answer in answers])

        # 计算相似度
        cosine_sim = cls.calculate_similarity(original_question, gen_questions)

        # 计算最终分数
        if len(cosine_sim) == 0:
            score = 0.0
        else:
            score = cosine_sim.mean() * int(not all_noncommittal)
            # 转换为0-10的分数范围
            score = float(score * 10)

        # 收集详细信息
        details = []
        for i, (answer, question, sim) in enumerate(zip(answers, gen_questions, cosine_sim)):
            is_noncommittal = answer.get("noncommittal", 0) == 1
            details.append({
                "question_index": i + 1,
                "generated_question": question,
                "similarity_score": sim,
                "is_noncommittal": is_noncommittal
            })

        return score, details

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """评估答案相关性"""
        raw_data = getattr(input_data, 'raw_data', {})
        # 提取原始问题
        original_question = input_data.prompt or raw_data.get("question", "")
        if not original_question:
            raise ValueError("Answer Relevancy评估需要question字段")

        try:
            # 增加温度参数以提高问题生成的随机性
            if hasattr(cls, 'dynamic_config') and cls.dynamic_config.parameters:
                if 'temperature' not in cls.dynamic_config.parameters:
                    cls.dynamic_config.parameters['temperature'] = 0.7
            else:
                # 如果没有parameters，创建一个包含temperature的parameters
                current_params = cls.dynamic_config.parameters or {}
                current_params['temperature'] = 0.7
                cls.dynamic_config.parameters = current_params

            # 生成多个相关问题
            generated_questions = cls.generate_multiple_questions(input_data, cls.strictness)

            # 计算相关性分数和详细信息
            score, details = cls.calculate_score(generated_questions, original_question)

            # 构建结果
            result = EvalDetail(metric=cls.__name__)
            result.score = score

            # 根据分数判断是否通过，默认阈值为5
            threshold = 5
            if hasattr(cls, 'dynamic_config') and cls.dynamic_config.parameters:
                threshold = cls.dynamic_config.parameters.get('threshold', 5)
                # 检查是否有自定义的strictness参数
                cls.strictness = cls.dynamic_config.parameters.get('strictness', 3)

            # 构建详细的reason文本
            all_reasons = []
            for detail in details:
                noncommittal_text = "(不置可否的回答)" if detail["is_noncommittal"] else ""
                all_reasons.append(f"生成的问题{detail['question_index']}: {detail['generated_question']}{noncommittal_text}\n与原始问题的相似度: {detail['similarity_score']:.4f}")

            reason_text = "\n\n".join(all_reasons)
            if details:
                reason_text += f"\n\n平均相似度: {np.mean([d['similarity_score'] for d in details]):.4f}\n是否所有回答都不置可否: {'是' if np.all([d['is_noncommittal'] for d in details]) else '否'}"

            if score >= threshold:
                result.status = False
                result.label = ["QUALITY_GOOD.ANSWER_RELEVANCY_PASS"]
                result.reason = [f"答案相关性评估通过 (分数: {score:.2f}/10)\n{reason_text}"]
            else:
                result.status = True
                result.label = ["QUALITY_BAD.ANSWER_RELEVANCY_FAIL"]
                result.reason = [f"答案相关性评估未通过 (分数: {score:.2f}/10)\n{reason_text}"]

            return result

        except Exception as e:
            log.error(f"Answer Relevancy评估出错: {str(e)}")
            result = EvalDetail(metric=cls.__name__)
            result.status = True
            result.label = ["QUALITY_BAD.ANSWER_RELEVANCY_ERROR"]
            result.reason = [f"答案相关性评估出错: {str(e)}"]
            return result
