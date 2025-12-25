import base64
import os
from typing import List

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI


@Model.llm_register("VLMImageRelevant")
class VLMImageRelevant(BaseOpenAI):
    prompt = """
    你是一个专业的图像对比分析系统。请对比分析两张图片的一致性和相关性。

    【分析步骤】
    1. 第一张图片分析
       仔细观察并记录第一张图片的核心内容：
       - 主要对象（人物、物体、场景）
       - 视觉元素（颜色、构图、风格）
       - 关键细节（文字、标识、特征）
       - 语义信息（主题、意图、情境）

    2. 第二张图片评估
       基于第一张图片，从以下维度评估第二张图片：
       - 内容一致性：主要对象和场景元素是否保持一致
       - 语义相关性：主题意图和信息传达是否相符
       - 视觉质量：图像清晰度、完整性、是否存在明显缺陷
       - 细节保真度：重要特征、比例、空间关系是否准确

    3. 综合评分
       评分标准：
       - 分数1：图片整体一致且相关，无明显问题
       - 分数0：存在以下任一情况
         * 主要内容不一致或缺失
         * 语义偏离或不相关
         * 存在明显的质量缺陷
         * 关键细节错误或失真

    【输出要求】
    请进行逐步分析后，输出最终评分和简要原因。
    输出格式必须为JSON：{"score": 评分, "reason": "原因说明"}
    """

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
                    {"type": "text", "text": cls.prompt},
                    {"type": "image_url", "image_url": {"url": image_url_1}},
                    {"type": "image_url", "image_url": {"url": image_url_2}},
                ],
            }
        ]
        return messages
