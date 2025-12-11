import base64
import json
import re
from typing import List

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.prompt_mineru_recognize import PromptMinerURecognizeQuality
from dingo.model.response.response_class import ResponseScoreReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMMinerURecognizeQuality")
class LLMMinerURecognizeQuality(BaseOpenAI):
    """
    LLM for document parsing quality ocr
    """
    prompt = PromptMinerURecognizeQuality

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        gt_markdown = input_data.prompt
        pred_content = input_data.content
        messages = [
            {
                "role": "user",
                "content": cls.prompt.content + f"ground_truth:{gt_markdown}\n\nPred_content:{pred_content}"
            }]
        return messages

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        log.info(response)
        json_match = re.search(r'\{[\s\S]*"errors"[\s\S]*\}', response)
        types = []
        names = []

        if json_match:
            try:
                json_str = json_match.group()
                result_data = json.loads(json_str)
                errors = result_data.get("errors", [])

                for error in errors:
                    error_category = error.get("error_category", "")
                    error_label = error.get("error_label", "")
                    # 只提取 error_category 和 error_label
                    if error_category and error_label:
                        types.append(error_category)
                        names.append(error_label)
            except json.JSONDecodeError as e:
                log.error(f"JSON解析错误: {e}")
        else:
            log.error("未找到JSON内容")

        result = ModelRes()
        result.error_status = False
        result.type = types
        result.name = names
        result.reason = [json_str] if 'json_str' in locals() else [response]

        return result
