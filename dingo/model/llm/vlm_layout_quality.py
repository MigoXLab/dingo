import base64
import json
import os
from typing import List

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.prompt_layout_quality import PromptLayoutQuality
from dingo.utils import log


@Model.llm_register("VLMLayoutQuality")
class VLMLayoutQuality(BaseOpenAI):
    prompt = PromptLayoutQuality

    @classmethod
    def _encode_image(cls, image_path: str) -> str:
        """
        Encode a local image file to base64 data URL format.
        If the input is already a URL, return it as is.

        This method follows Python's standard path resolution:
        - Relative paths are resolved relative to the current working directory
        - Absolute paths are used as-is
        - URLs (http://, https://, data:) are passed through unchanged

        Args:
            image_path: Local file path (absolute or relative) or URL

        Returns:
            Base64 data URL for local files, or original URL for web resources

        Raises:
            FileNotFoundError: If a local file path does not exist
            RuntimeError: If the file cannot be read
        """
        # Pass through URLs unchanged
        if image_path.startswith('data:'):
            return image_path

        if image_path.startswith(("http://", "https://", 'data:')):
            return image_path

        # Standard file path handling (relative or absolute)
        if not os.path.isfile(image_path):
            raise FileNotFoundError(
                f"Image file not found: '{image_path}'\n"
                f"Current working directory: {os.getcwd()}\n"
                f"Absolute path would be: {os.path.abspath(image_path)}\n"
                f"Ensure the path is correct relative to your current working directory."
            )

        try:
            with open(image_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                # Determine MIME type from file extension
                ext = os.path.splitext(image_path)[1].lower()
                mime_type = 'image/jpeg' if ext in ['.jpg', '.jpeg'] else f'image/{ext[1:]}'
                return f"data:{mime_type};base64,{base64_image}"
        except Exception as e:
            raise RuntimeError(
                f"Failed to read image file '{image_path}': {e}"
            )

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        if isinstance(input_data.image[0], str):
            image_base64 = cls._encode_image(input_data.image[0])

        bboxs = eval(input_data.content)

        bbox_line = [
            f"Bbox{bbox['bbox_id']} Type: {bbox['type']}"
            for bbox in bboxs
        ]
        bbox_info = "\n".join(bbox_line)

        layout_prompt = cls.prompt.content.replace("{{ bbox_typr_list }}", bbox_info)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": layout_prompt},
                    {"type": "image_url", "image_url": {"url": image_base64}},
                ]
            }
        ]
        return messages

    @classmethod
    def send_messages(cls, messages: List):
        if cls.dynamic_config.model:
            model_name = cls.dynamic_config.model
        else:
            model_name = cls.client.models.list().data[0].id

        params = cls.dynamic_config.parameters
        cls.validate_config(params)

        completions = cls.client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=0.1
        )

        return str(completions.choices[0].message.content)

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
                    error_type = error.get("error_type", "")

                    if error_type:
                        types.append(error_type)
                        names.append(error_type)
            except json.JSONDecodeError as e:
                log.error(f"JSON解析错误: {e}")

        result = ModelRes()
        result.error_status = False
        result.type = types
        result.name = names
        result.reason = [response]

        return result
