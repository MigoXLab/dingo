import json

from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.response.response_class import ResponseScoreReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register('detect_multi_turn_dialogues')
class DetectMultiTurnDialogues(BaseOpenAI):
    @classmethod
    def build_messages(cls, input_data):
        # Get conversation history and response to evaluate
        history = input_data.prompt
        response = input_data.content
        
        # Format the prompt with history and response
        prompt_content = cls.prompt.content % (history, response)

        messages = [{"role": "user", "content": prompt_content}]
        return messages

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

        response_model = ResponseScoreReason(**response_json)


        result = ModelRes()

        # Set result based on score with more granular evaluation
        if float(response_model.score) >= 7:
            result.reason = [response_model.reason]
        else:
            result.error_status = True
            result.type = cls.prompt.metric_type
            result.name = cls.prompt.__name__
            result.reason = [response_model.reason]

        return result
