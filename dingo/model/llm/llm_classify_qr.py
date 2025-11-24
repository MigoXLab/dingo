import json
from typing import List

from dingo.io.input import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.response.response_class import ResponseNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMClassifyQR")
class LLMClassifyQR(BaseOpenAI):
    # Metadata for documentation generation
    _metric_info = {
        "category": "Multimodality Assessment Metrics",
        "metric_name": "PromptClassifyQR",
        "description": "Identifies images as CAPTCHA, QR code, or normal images",
        "evaluation_results": ""
    }

    prompt = """
    'Classify the image into one of the following categories: "CAPTCHA", "QR code", or "Normal image". '
    'Return the type as the image category (CAPTCHA or QR code or Normal image) and the reason as the specific type of CAPTCHA or QR code. '
    'Possible CAPTCHA types include: "Text CAPTCHA", "Image CAPTCHA", "Math CAPTCHA", "Slider CAPTCHA", "SMS CAPTCHA", "Voice CAPTCHA". '
    'Return the answer in JSON format: {"name": "xxx", "reason": "xxx" (if applicable)}.'
    'Please remember to output only the JSON format, without any additional content.'

    Here is the image you need to evaluate:
    """

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": cls.prompt},
                    {"type": "image_url", "image_url": {"url": input_data.content}},
                ],
            }
        ]
        return messages

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
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

        result = ModelRes()
        result.eval_status = False
        # result.type = cls.prompt.metric_type
        # result.name = response_model.name
        # result.reason = [response_model.reason]

        result.eval_details = {
            "label": [f"{cls.__name__}.{response_model.name}"],
            "metric": [cls.__name__],
            "reason": [response_model.reason]
        }

        return result
