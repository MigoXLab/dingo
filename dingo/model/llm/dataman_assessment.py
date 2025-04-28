import json

from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register('dataman_assessment')
class DatamanAssessment(BaseOpenAI):
    """
    Implementation of DataMan assessment using OpenAI API.
    Evaluates text based on 14 quality standards and assigns a domain type.
    """
    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        log.info(response)

        if response.startswith('```json'):
            response = response[7:]
        if response.startswith('```'):
            response = response[3:]
        if response.endswith('```'):
            response = response[:-3]

        try:
            response_json = json.loads(response)
        except json.JSONDecodeError:
            raise ConvertJsonError(f'Convert to JSON format failed: {response}')

        # Parse the response using the ResponseScoreTypeNameReason model
        response_model = ResponseScoreTypeNameReason(**response_json)

        result = ModelRes()
        # Set error_status based on score (1 = good quality, 0 = low quality)
        if response_model.score == 1:
            result.error_status = False
        else:
            result.error_status = True

        # Set type to the domain classification
        result.type = response_model.type

        # Set name to the quality category
        result.name = response_model.name

        # Set reason to the detailed assessment
        result.reason = [response_model.reason]

        return result
