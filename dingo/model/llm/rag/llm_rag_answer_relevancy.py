"""
RAG Answer Relevancy (答案相关性) LLM评估器

基于LLM和Embedding模型评估答案与问题的相关性。
参考RAGAS的实现，通过生成相关问题并计算相似度来评估答案相关性。
"""

import json
from typing import Any, Dict, List

import numpy as np

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.response.response_class import ResponseScoreReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


# 用于embedding的模型，支持OpenAI和HuggingFace
class EmbeddingModel:
    """Embedding模型接口，支持OpenAI和HuggingFace模型"""
    def __init__(self, model_name: str = "text-embedding-3-large", is_openai: bool = True, api_key: str = None, base_url: str = None):
        self.is_openai = is_openai
        self.model_name = model_name

        if is_openai:
            # 使用OpenAI Embeddings
            import os

            from openai import OpenAI
            self.client = OpenAI(
                api_key=api_key,
                base_url=base_url
            )
        else:
            # 使用HuggingFace Embeddings
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)

    def embed_query(self, text: str) -> List[float]:
        """生成查询的embedding"""
        if self.is_openai:
            response = self.client.embeddings.create(
                model=self.model_name,
                input=text
            )
            return response.data[0].embedding
        else:
            return self.model.encode(text).tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """生成多个文档的embedding"""
        if self.is_openai:
            response = self.client.embeddings.create(
                model=self.model_name,
                input=texts
            )
            return [data.embedding for data in response.data]
        else:
            return self.model.encode(texts).tolist()


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
        "source_frameworks": "Ragas"
    }

    # 问题生成的prompt模板
    question_generation_prompt = """为给定的答案生成一个问题，并判断该答案是否是非承诺性的。如果答案是非承诺性的，将noncommittal设为1；如果答案是承诺性的，将noncommittal设为0。非承诺性答案是指回避、模糊或模棱两可的回答。例如，"我不知道"或"我不确定"就是非承诺性答案。

 --------EXAMPLES-----------
 示例1
 输入: {{
     "response": "爱因斯坦出生于德国。"
 }}
 输出: {{
     "question": "爱因斯坦出生于哪里？",
     "noncommittal": 0
 }}

 示例2
 输入: {{
     "response": "我不知道2023年发明的智能手机的突破性功能，因为我对2022年以后的信息不了解。"
 }}
 输出: {{
     "question": "2023年发明的智能手机的突破性功能是什么？",
     "noncommittal": 1
 }}
 -----------------------------

 现在对以下输入执行相同的操作。请尝试从不同角度生成问题，使用不同的表述方式，但保持与原答案的相关性。
 输入: {{
     "response": {0}
 }}
 输出: """

    # 默认的embedding模型
    embedding_model = None

    # 配置参数
    strictness = 3  # 生成的问题数量

    @classmethod
    def init_embedding_model(cls, model_name: str = "text-embedding-3-large"):
        """初始化embedding模型"""
        # 检查是否是OpenAI模型
        is_openai = model_name.startswith("text-embedding-")
        api_key = None
        base_url = None
        if is_openai:
            # 从配置中获取API密钥和base_url
            if not cls.dynamic_config.key:
                raise ValueError("key cannot be empty in llm config.")
            elif not cls.dynamic_config.api_url:
                raise ValueError("api_url cannot be empty in llm config.")
            else:
                api_key = cls.dynamic_config.key
                base_url = cls.dynamic_config.api_url
        cls.embedding_model = EmbeddingModel(model_name, is_openai, api_key, base_url)

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
        if cls.embedding_model is None:
            cls.init_embedding_model()

        # 生成embedding
        question_vec = np.asarray(cls.embedding_model.embed_query(question)).reshape(1, -1)
        gen_question_vec = np.asarray(cls.embedding_model.embed_documents(generated_questions)).reshape(len(generated_questions), -1)

        # 计算余弦相似度
        norm = np.linalg.norm(gen_question_vec, axis=1) * np.linalg.norm(question_vec, axis=1)
        return np.dot(gen_question_vec, question_vec.T).reshape(-1) / norm

    @classmethod
    def calculate_score(cls, answers: List[Dict[str, Any]], original_question: str) -> float:
        """计算答案相关性分数"""
        # 提取生成的问题
        gen_questions = [answer.get("question", "") for answer in answers]

        # 检查是否所有生成的问题都为空
        if all(q == "" for q in gen_questions):
            log.warning("Invalid response. Expected dictionary with key 'question'")
            return 0.0

        # 检查是否所有答案都是不置可否的
        all_noncommittal = np.all([answer.get("noncommittal", 0) for answer in answers])

        # 计算相似度
        cosine_sim = cls.calculate_similarity(original_question, gen_questions)

        # 计算最终分数
        score = cosine_sim.mean() * int(not all_noncommittal)

        # 转换为0-10的分数范围
        score = float(score * 10)

        return score

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        """评估答案相关性"""
        # 初始化embedding模型（如果尚未初始化）
        if cls.embedding_model is None:
            cls.init_embedding_model()
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
                from dingo.config.input_args import EvaluatorLLMArgs
                current_params = cls.dynamic_config.parameters or {}
                current_params['temperature'] = 0.7
                cls.dynamic_config.parameters = current_params

            # 生成多个相关问题
            generated_questions = cls.generate_multiple_questions(input_data, cls.strictness)

            # 计算相关性分数
            score = cls.calculate_score(generated_questions, original_question)

            # 构建结果
            result = ModelRes()
            result.score = score

            # 根据分数判断是否通过，默认阈值为5
            threshold = 5
            if hasattr(cls, 'dynamic_config') and cls.dynamic_config.parameters:
                threshold = cls.dynamic_config.parameters.get('threshold', 5)
                # 检查是否有自定义的strictness参数
                cls.strictness = cls.dynamic_config.parameters.get('strictness', 3)

                # 检查是否有自定义的embedding模型
                embedding_model_name = cls.dynamic_config.parameters.get('embedding_model', None)
                if embedding_model_name:
                    cls.init_embedding_model(embedding_model_name)

            if score >= threshold:
                result.eval_status = False
                result.eval_details = {
                    "label": ["QUALITY_GOOD.ANSWER_RELEVANCY_PASS"],
                    "metric": [cls.__name__],
                    "reason": [f"答案相关性评估通过 (分数: {score:.2f}/10)"]
                }
            else:
                result.eval_status = True
                result.eval_details = {
                    "label": ["QUALITY_BAD.ANSWER_RELEVANCY_FAIL"],
                    "metric": [cls.__name__],
                    "reason": [f"答案相关性评估未通过 (分数: {score:.2f}/10)"]
                }

            return result

        except Exception as e:
            log.error(f"Answer Relevancy评估出错: {str(e)}")
            result = ModelRes()
            result.eval_status = True
            result.eval_details = {
                "label": ["QUALITY_BAD.ANSWER_RELEVANCY_ERROR"],
                "metric": [cls.__name__],
                "reason": [f"答案相关性评估出错: {str(e)}"]
            }
            return result
