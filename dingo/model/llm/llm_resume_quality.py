import json

from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.prompt_resume_quality import PromptResumeQualityZh
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMResumeQuality")
class LLMResumeQuality(BaseOpenAI):
    """LLM-based resume quality evaluation."""

    prompt = PromptResumeQualityZh

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
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

        result = ModelRes()

        # Check if resume is good quality
        if response_model.type == "Good" and response_model.score == 1:
            result.error_status = False
            result.type = "QUALITY_GOOD"
            result.name = "ResumeQualityGood"
            result.reason = [response_model.reason]
        else:
            # Resume has quality issues
            result.error_status = True

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

            result.type = type_mapping.get(response_model.type, "RESUME_QUALITY_BAD")
            result.name = response_model.name
            result.reason = [response_model.reason]

        return result
