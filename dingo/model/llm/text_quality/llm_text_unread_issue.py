import json

from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMTextUnreadIssue")
class LLMTextUnreadIssue(BaseOpenAI):
    prompt = """
    ### Role
    You are a data quality assessment expert, you can communicate fluently in English, and think from the perspective of Chinese people.
    ### Background
    We use extraction tools to extract PDF files (from academic papers, books, and financial reports) into markdown format, intercept markdown with a fixed length, and need to evaluate the quality of the intercepted content.
    The most desired evaluation is whether the intercepted content meets the quality standards.
    ### Goal
    Your primary Goal is to assess the suitability of this dataset for training a large language model. Unreadable issues can affect the validity of training data for LLMs.
    ### Unreadable issues
    Unreadable issues: It caused by string encoding and decoding methods are inconsistent. Unreadable characters include tow types:
    - Squares (usually placeholders for undefined characters in Unicode): such as "□", "■", "�", etc.
    - Other special symbols: such as "â", "ã", "ä", "å", etc.
    ### Workflow
    1. Calculate the length of the garbled string, denoted as a.
    2. Calculate the total length of the evaluated string, denoted as b.
    3. If the ratio of a/b is greater than 0.01, then it is considered low-quality data.
    ### Quality Standard
    After workflow, you can judge
    1. low-quality：If the ratio of a/b is greater than 0.01, then it is considered low-quality data.
    2. high-quality:If the ratio of a/b is smaller than 0.01，it is considered high-quality data.
    ### Warning
    Please remember to output only JSON data, without additional content.
    Score: 0 (data meets low-quality) or 1 (data meets high-quality).
    Type: If the score is 0, it is the most serious error type; if it is 1, it is "high quality".
    Problem: The problem must be one of the following lists: please be careful not to output anything other than the list type;
    Reason: A brief description of the score. Please print the reason if the type is from the following list: ["Unreadable issue"].
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
