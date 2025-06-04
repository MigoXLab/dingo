from typing import List

from dingo.io.input import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.prompt.prompt_image_relevant import PromptImageRelevant


@Model.llm_register('VLMImageRelevant')
class VLMImageRelevant(BaseOpenAI):
    prompt = PromptImageRelevant

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        messages = [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': cls.prompt.content},
                    {'type': 'image_url', 'image_url': {'url': input_data.prompt}},
                    {'type': 'image_url', 'image_url': {'url': input_data.content}},
                ],
            }
        ]
        return messages
