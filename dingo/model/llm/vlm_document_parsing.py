import base64
import json
from typing import List

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.prompt_document_parsing import PromptDocumentParsingQuality
from dingo.utils import log


@Model.llm_register("VLMDocumentParsingQuality")
class VLMDocumentParsingQuality(BaseOpenAI):
    prompt = PromptDocumentParsingQuality

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        if isinstance(input_data.image[0], str):
            with open(input_data.image[0], "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
        else:
            base64_image = input_data.image[0]

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": cls.prompt.content},
                    {"type": "image_url", "image_url": {"url": base64_image}},
                    {"type": "text", "text": f"Markdown:\n{input_data.content}"}
                ]
            }
        ]
        return messages

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        log.info(response)

        response = response.replace("```json", "")
        response = response.replace("```", "")

        types = []
        names = []

        if response:
            try:
                result_data = json.loads(response)
                errors = result_data.get("errors", [])

                for error in errors:
                    error_category = error.get("error_category", "")
                    error_label = error.get("error_label", "")

                    if error_category and error_label:
                        types.append(error_category)
                        names.append(error_label)
            except json.JSONDecodeError as e:
                log.error(f"JSON解析错误: {e}")

        result = ModelRes()
        result.error_status = False
        result.type = types
        result.name = names
        result.reason = [response]

        return result
