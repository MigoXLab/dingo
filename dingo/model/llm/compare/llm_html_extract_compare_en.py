import json
import re
from typing import List

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMHtmlExtractCompareEn")
class LLMHtmlExtractCompareEn(BaseOpenAI):
    prompt = r"""
    You are a professional HTML content extraction evaluator, skilled in analyzing the conversion quality between HTML code and Markdown text. I will provide three pieces of content:

    1. **Original HTML Code**: The complete HTML structure of the webpage.
    2. **Tool A's Extracted Markdown**: Markdown text extracted from HTML, suitable for LLM training.
    3. **Tool B's Extracted Markdown**: Markdown text extracted from HTML, suitable for LLM training.

    Note: The order of Tool A and Tool B is not fixed. Do not favor either tool based on order; evaluate objectively based on actual conversion quality.

    Your Task:
    1. Compare both Markdown extractions against the HTML code. Strictly check extraction effectiveness for the following 8 module types:

    **HTML Element Identification:**
    - `code`: Code blocks (<pre>, <code> tags)
    - `math`: Mathematical formulas (MathJax, MathML, LaTeX)
    - `table`: Tables (<table> tags)
    - `image`: Images (<img> tags)
    - `list`: Ordered/unordered lists (<ul>, <ol> tags)
    - `title`: Headings (<h1> - <h6> tags)
    - `paragraph`: Paragraph text (<p>, <div> containers)
    - `other`: Other visible content not covered above

    **Markdown Element Statistics:**
    - Code blocks: ```...``` or indented code
    - Formulas: $...$ $$...$$ \(...\) \[...\]
    - Tables: |...| format
    - Images: ![](...) format
    - Lists: -, *, 1. markers
    - Headings: #, ## markers
    - Paragraphs: Plain text blocks

    2. **Scoring Rules**: Evaluate which tool has better extraction quality.
    - **Extraction Completeness**: Check if key content (code, tables, images, lists) is fully extracted.
    - **Format Accuracy**: Verify correct Markdown formatting (code indentation, table alignment, image links).
    - **Semantic Coherence**: Ensure logical flow and heading hierarchy are preserved.

    3. **Issue Feedback**: Strictly identify problems by the 8 module types above; return empty list if no issues.

    4. **Return Result**: JSON format with 3 fields: score, name, reason.
    - `score`: 1 if Tool A is better, 2 if Tool B is better.
    - `name`: Must be one of the 8 module types, selecting the module with greatest difference.
    - `reason`: Objective description of performance differences in that module.

    Example Output:
    {
    "score": [1|2],
    "name": "[module_type]",
    "reason": "[objective description of differences]"
    }
    """

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        messages = [
            {
                "role": "user",
                "content": cls.prompt.format(
                    input_data.content,
                    input_data.raw_data["magic_md"],
                    input_data.raw_data["content"],
                ),
            }
        ]
        return messages

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        log.info(response)

        response_think = ""
        if response.startswith("<think>"):
            think_content = re.search(
                r"<think>(.*?)</think>", response, flags=re.DOTALL
            )
            response_think = think_content.group(1).strip()
            response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
            response = response.strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        try:
            response_json = json.loads(response)
            response_json["reason"] += "\n"
            response_json["reason"] += response_think
        except json.JSONDecodeError:
            raise ConvertJsonError(f"Convert to JSON format failed: {response}")

        response_model = ResponseScoreTypeNameReason(**response_json)

        result = EvalDetail(metric=cls.__name__)
        # status
        if response_model.score != 1:
            result.status = True

        # type
        # if response_model.score == 1:
        #     result.type = "TOOL_ONE_BETTER"
        # if response_model.score == 2:
        #     result.type = "TOOL_TWO_BETTER"
        # if response_model.score == 0:
        #     result.type = "TOOL_EQUAL"
        #
        # # name
        # result.name = response_model.name
        #
        # # reason
        # result.reason = [json.dumps(response_json, ensure_ascii=False)]

        tmp_type = ''
        if response_model.score == 1:
            tmp_type = "TOOL_ONE_BETTER"
        if response_model.score == 2:
            tmp_type = "TOOL_TWO_BETTER"
        if response_model.score == 0:
            tmp_type = "TOOL_EQUAL"
        result.label = [f"{tmp_type}.{response_model.name}"]
        result.reason = [json.dumps(response_json, ensure_ascii=False)]

        return result
