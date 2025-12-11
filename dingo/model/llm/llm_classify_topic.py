import json

from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.response.response_class import ResponseNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMClassifyTopic")
class LLMClassifyTopic(BaseOpenAI):
    # Metadata for documentation generation
    _metric_info = {
        "category": "Classification Metrics",
        "metric_name": "PromptClassifyTopic",
        "description": "Classifies text into categories like language processing, writing, code, mathematics, role-play, or knowledge Q&A. Based on BERTopic and INSTAG methodologies",
        "paper_title": "BERTopic & INSTAG",
        "paper_url": "https://maartengr.github.io/BERTopic/index.html#quick-start, https://arxiv.org/pdf/2308.07074",
        "paper_authors": "Grootendorst, 2022; Wei et al., 2023",
        "evaluation_results": "docs/eval/prompt/text_data_classified_by_topic.md",
        "validation_dataset": "AlignBench (https://github.com/THUDM/AlignBench)"
    }

    prompt = """
    Assume you are a topic classifier, and your task is to categorize user-provided instructions.
    There are six options in the list provided. You are required to select one category from the following list: ["Language Understanding and Processing", "Writing Ability", "Code", "Mathematics & Reasoning", "Task-oriented Role Play", "Knowledge-based Question and Answering"].
    Make sure your answer is within the list provided and do not create any additional answers.

    Here are some explanations of the categories you can choose from in the list:
    1. Language Understanding and Processing: Tasks that require linguistic understanding or processing of questions, such as word comprehension, proverbs and poetry, Chinese culture, grammatical and syntactic analysis, translation, information extraction, text classification, semantic understanding, grammar checking, sentence restructuring, text summarization, opinion expression, sentiment analysis, and providing suggestions and recommendations.
    2. Writing Ability: Some questions that require text writing, such as practical writing (adjusting format, checking grammar, etc.), cultural understanding, creative writing, and professional writing(giving a professional plan, evaluation, report, case, etc.).
    3. Code: Tasks focused on code generation or solving programming problems (e.g., code generation, code review, code debugging).
    4. Mathematics & Reasoning: Mathematical questions require numerical computations, proving mathematical formulas, solving mathematical problems in application contexts. Reasoning questions often require you to assess the validity of logic, determine which statement is true based on the given assertions and derive conclusions, arrange information according to specific rules, or analyze the logical relationships between sentences.
    5. Task-oriented Role Play: Such questions provide a simulated dialogue scenario and explicitly assign you a role to perform specific tasks (e.g., delivering a speech or evaluation, engaging in situational dialogue, providing an explanation).
    6. Knowledge-based Question and Answering: Some purely question-and-answer tasks that require specialized subject knowledge or common knowledge, usually involving brief factual answers (e.g., physics, music theory, sports knowledge inquiries, foundational computer science concepts, history, geography, biomedical sciences, factual recall or common sense knowledge).

    Guidelines:
    1. Any question that begins with phrases such as "Assume you are a xxx," or "You are playing the role of a xxx," must be classified as 'Task-oriented Role Play', regardless of the category to which the latter part of the sentence belongs.

    Task requirements:
    1. According to the explanations of the categories, select one category from the following list: ["Language Understanding and Processing", "Writing Ability", "Code", "Mathematics & Reasoning", "Task-oriented Role Play", "Knowledge-based Question and Answering"].
    2. Return answer in JSON format: {"name":"xxx"}. Please remember to output only the JSON FORMAT, without any additional content.

    Below is an instruction:
    """

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        log.info(response)

        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        try:
            response_json = json.loads(response)
        except json.JSONDecodeError:
            raise ConvertJsonError(f"Convert to JSON format failed: {response}")

        response_model = ResponseNameReason(**response_json)

        result = EvalDetail(metric=cls.__name__)
        result.status = False
        result.label = [f"{cls.__name__}.{response_model.name}"]
        result.reason = [response_model.reason]

        return result
