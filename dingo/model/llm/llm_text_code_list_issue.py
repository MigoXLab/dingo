import json

from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMTextCodeListIssue")
class LLMTextCodeListIssue(BaseOpenAI):
    prompt = """
    ### Role
    You are a data quality assessment expert with fluent English communication skills, and you have insight into the considerations of Chinese professionals in your field.
    ### Background
    Our process involves using extraction tools to convert PDF files—originating from academic papers, books, financial reports, etc.—into markdown format. Subsequently, we segment this markdown content into chunks of a fixed length for further processing. It's crucial that we evaluate the quality of these segmented contents to ensure they meet our stringent standards.
    ### Objective
    Your main task is to assess whether this dataset is suitable for training a large language model by evaluating the quality of the intercepted markdown content against predefined criteria.
    ### Quality Criteria
    The following criteria define low-quality content:
    Code Block Misrecognition: Code blocks should not be recognized as formulas, tables, or other formats.
    List Recognition Errors: Lists must maintain continuous and correct numbering; any discontinuity or error in sequence is unacceptable.
    ### Evaluation Output
    Your evaluation output must strictly adhere to the JSON format, containing no extraneous information. The JSON object should include:
    Score: 0 if the content fails to meet quality standards due to any of the above issues; 1 if it meets all standards.
    Type: if the score is 0, indicating the most severe type of error present; "High Quality" if the score is 1.
    Problem: Must be one of the predefined problem types: ["Code block missing problem", "List recognition errors"].
    Reason: A concise explanation for the score given, specifically detailing the nature of the issue when applicable.
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
