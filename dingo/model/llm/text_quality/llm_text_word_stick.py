import json

from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMTextWordStick")
class LLMTextWordStick(BaseOpenAI):
    prompt = """
    ### Role
    You are a data quality assessment expert, you can communicate fluently in English, and think from the perspective of Chinese people.
    ### Background
    We use extraction tools to extract PDF files (from academic papers, books, and financial reports) into markdown format, intercept markdown with a fixed length, and need to evaluate the quality of the intercepted content.
    The most desired evaluation is whether the intercepted content meets the quality standards.
    ### Goals
    Your primary goal is to evaluate whether there are any word stuck issues in the text.Word stuck issues can affect the fluency of the corpus used for running LLMs.
    ### workdflow
    1 Problem Definition：Word Stuck Issue is defined as independent words are missing spaces or punctuation between them, causing them to stick together. For example, "aboutafootwideandtwofeetlong" combines the sentence "about a foot wide and two feet long" without a space, which is considered a Word Stuck Issue.
    2 Calculate the total length of the data in characters and denote it as len(b).
    3 Calculate the length of the stuck words(satisfy Word Stuck Issue definition) and denote it as len(a).
    4 Sum up the lengths of all instances of stuck words to get sum(len(a)).
    5 Calculate the ratio as ratio = sum(len(a)) / len(b).
    6 If the ratio is greater than 0.01, then it is considered low-quality data, and output a score of 0; otherwise, it is considered high-quality data, and output a score of 1.
    ### Warning
    Please remember to output only JSON data, without additional content.
    Score: 0 (data meets low-quality standard) or 1 (data  meets high-quality standard).
    Type: If the score is 0, it is the most serious error type; if it is 1, it is "high quality".
    Reason: Return workflow-based reason. Please print the reason if the type is from the following list: ["Word Stuck Issue"].
    Return your answer in JSON format: {"score": 0, "type": "xxx", "reason": "xxx"}.
    Here are the data you need to evaluate:
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

        response_model = ResponseScoreTypeNameReason(**response_json)

        result = EvalDetail(metric=cls.__name__)
        # eval_status
        if response_model.score == 1:
            result.label = [QualityLabel.QUALITY_GOOD]
            result.reason = [response_model.reason]
        else:
            result.status = True
            result.label = [f"{response_model.type}.{response_model.name}"]
            result.reason = [response_model.reason]

        return result
