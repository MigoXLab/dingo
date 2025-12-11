import base64
import os
from typing import List

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.prompt.prompt_image_relevant import PromptImageRelevant


@Model.llm_register("VLMImageRelevant")
class VLMImageRelevant(BaseOpenAI):
    prompt = PromptImageRelevant

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
        if image_path.startswith(('http://', 'https://', 'data:')):
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
        # Encode images if they are local file paths
        image_url_1 = cls._encode_image(input_data.prompt)
        image_url_2 = cls._encode_image(input_data.content)

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": cls.prompt.content},
                    {"type": "image_url", "image_url": {"url": image_url_1}},
                    {"type": "image_url", "image_url": {"url": image_url_2}},
                ],
            }
        ]
        return messages
