import json

from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMResumeQuality")
class LLMResumeQuality(BaseOpenAI):
    """LLM-based resume quality evaluation."""
    _metric_info = {
        "category": "Resume Quality Assessment Metrics",
        "metric_name": "PromptResumeQualityZh",
        "description": "Comprehensive resume quality evaluation covering privacy, contact, format, structure, professionalism, date, and completeness issues",
        "paper_title": "N/A",
        "paper_url": "",
        "paper_authors": "Dingo Team",
        "evaluation_results": ""
    }

    prompt = """
    # Role
    You are an expert in resume quality evaluation.

    # Background
    The resume is submitted by job seekers for employment opportunities. Your task is to evaluate the quality of the resume based on professional standards.

    # Goals
    Your primary objective is to assess the quality of this resume. If the resume meets any of the following negative criteria, it will be considered as having quality issues.

    # Criteria
    1. Privacy
        1.1 Error_ID_Card: The resume contains Chinese ID card numbers (18 digits), which is a serious privacy leak.
        1.2 Error_Detailed_Address: The resume contains detailed address information (province, city, district, street, building number), which may leak privacy.

    2. Contact
        2.1 Error_Email_Missing: The resume does not contain a valid email address.
        2.2 Error_Phone_Missing: The resume does not contain a valid phone number.
        2.3 Error_Phone_Format_Error: The phone number format is incorrect or invalid.

    3. Format
        3.1 Error_Excessive_Whitespace: The resume contains excessive consecutive spaces (3 or more spaces).
        3.2 Error_Markdown_Syntax_Error: The resume has Markdown syntax errors (e.g., too many # symbols, excessive * or _).

    4. Structure
        4.1 Error_Name_Missing: The resume does not have a clear name or heading in the first section.
        4.2 Error_Section_Missing: The resume is missing required sections such as education or work experience.
        4.3 Error_Heading_Level_Error: The resume has inconsistent or incorrect heading hierarchy.

    5. Professionalism
        5.1 Error_Emoji_Usage: The resume contains emoji characters, which reduces professionalism.
        5.2 Error_Informal_Language: The resume uses informal or colloquial expressions (e.g., "搞定", "牛逼", "厉害").
        5.3 Error_Typo: The resume contains obvious typos or grammatical errors.

    6. Date
        6.1 Error_Date_Format_Inconsistent: The resume uses inconsistent date formats (e.g., mixing "2020.01" and "2021-03").
        6.2 Error_Date_Logic_Error: The resume has date logic errors (e.g., graduation date earlier than enrollment date, end date earlier than start date).

    7. Completeness
        7.1 Error_Education_Missing: The resume does not contain education background information.
        7.2 Error_Experience_Missing: The resume does not contain work experience or project experience information.

    # Workflow
    1. Carefully read and understand the provided resume content, evaluate the quality based on the negative criteria above.
    2. Assign a type to the resume.
       - If the resume does not hit any negative criteria above, type must only be 'Good'.
       - Otherwise, type must only be one of the list ['Privacy', 'Contact', 'Format', 'Structure', 'Professionalism', 'Date', 'Completeness'].
    3. Assign a name to the resume.
       - If type is 'Good', name must only be 'None'.
       - If type is 'Privacy', name must only be one of ['Error_ID_Card', 'Error_Detailed_Address'].
       - If type is 'Contact', name must only be one of ['Error_Email_Missing', 'Error_Phone_Missing', 'Error_Phone_Format_Error'].
       - If type is 'Format', name must only be one of ['Error_Excessive_Whitespace', 'Error_Markdown_Syntax_Error'].
       - If type is 'Structure', name must only be one of ['Error_Name_Missing', 'Error_Section_Missing', 'Error_Heading_Level_Error'].
       - If type is 'Professionalism', name must only be one of ['Error_Emoji_Usage', 'Error_Informal_Language', 'Error_Typo'].
       - If type is 'Date', name must only be one of ['Error_Date_Format_Inconsistent', 'Error_Date_Logic_Error'].
       - If type is 'Completeness', name must only be one of ['Error_Education_Missing', 'Error_Experience_Missing'].
    4. Assign a score to the resume according to the type. If the type is 'Good', score is 1, otherwise the score is 0.
    5. Provide a clear reason for the evaluation.
    6. Return the results in JSON format: {"score": 0/1, "type": "", "name": "", "reason": ""}.

    # Warning
    Please remember to output only a JSON format data, without any additional content.

    # Input content
    """

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        log.info(response)

        # Clean response format
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

        # Validate response using Pydantic model
        response_model = ResponseScoreTypeNameReason(**response_json)

        result = EvalDetail(metric=cls.__name__)

        # Check if resume is good quality
        if response_model.type == "Good" and response_model.score == 1:
            result.status = False
            result.label = [f"{QualityLabel.QUALITY_GOOD}.ResumeQualityGood"]
            result.reason = [response_model.reason]
        else:
            # Resume has quality issues
            result.status = True

            # Map issue type to metric type
            type_mapping = {
                "Privacy": "RESUME_QUALITY_BAD_PRIVACY",
                "Contact": "RESUME_QUALITY_BAD_CONTACT",
                "Format": "RESUME_QUALITY_BAD_FORMAT",
                "Structure": "RESUME_QUALITY_BAD_STRUCTURE",
                "Professionalism": "RESUME_QUALITY_BAD_PROFESSIONALISM",
                "Date": "RESUME_QUALITY_BAD_DATE",
                "Completeness": "RESUME_QUALITY_BAD_COMPLETENESS"
            }

            tmp_type = type_mapping.get(response_model.type, "RESUME_QUALITY_BAD")
            tmp_name = response_model.name
            result.label = [f"{tmp_type}.{tmp_name}"]
            result.reason = [response_model.reason]

        return result
