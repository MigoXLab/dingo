import base64
import json
import re
from typing import List

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log


@Model.llm_register("VLMDocumentParsingOCRTrain")
class VLMDocumentParsingOCRTrain(BaseOpenAI):
    """
    LLM for document parsing quality ocr
    """
    _metric_info = {
        "category": "OCR Eval Metric",
        "metric_name": "MinerURecognizeTrainQuality",
        "description": "Evaluate the quality of mineru recognize",
        "evaluation_results": "error_category and error_label",
    }
    prompt = r"""
    你是一位熟悉文档解析领域的质量专家，你的核心任务是根据带bbox的图"原图"，以及对应OCR工具预测结果"Pred的内容"，获取工具预测结果的错误类型。
    *错误类别和标签*
    以下是你可以使用的错误类别和对应的标签。在输出的JSON中，"error_category"字段应填写问题大类（如:公式识别相关问题），"error_label"字段应填写问题子类(如：公式中字符识别错误)。
    **1.公式识别相关问题**
       - 公式字符识别错误：公式渲染正确，但识别错误
       - 公式内容模型输出重复
    **2.表格识别相关问题**
       - 表格输出格式错误：输出otsl格式有误导致转换失败
       - 表格结构错误：结构造成的内容丢失也算在里面
       - 表格内容错误：结构是对的，仅文本错
       - 表格内容模型输出重复
    **3. 分行分段相关问题**
        - 非跨栏内容段落粘连: 原本不同段落的文本，在OCR结果中被错误地合并成一个段落。
        - 段落异常拆分: 原本完整的一个段落，在OCR结果中被错误地分割成了多个段落的文本。
    **4.列表相关问题**
        -列表项异常合并/粘连: 原图中文档中的独立的列表项（有序列表和无序列表，或者(1)、(2)...样式的列表）、参考文献被合并成一行。可能是多个项合并成一项，或列表项与前后文本合并。
    **5.标题相关问题**
        -标题格式丢失: 原文件中的标题，在OCR结果中被识别为普通文本，丢失了标题应有的Markdown格式（如#）。
        -标题分级错误: 原图中的标题被识别，但其层级（如H1, H2）与原图不符，包括层级识别错误（如一级标题识别为二级）。
    **5.OCR识别问题**
        - 字符识别错误：文本、标题、列表类型等文本内容识别错误。
    **6.其他**
        -其他问题: 此分类用于标记不属于上述任何具体类别的其他OCR质量问题。经过仔细判断后确认无法归入其他既有标签的OCR质量问题。

    *输出格式*
     请严格按照以下JSON结构组织你的发现：
        ```json
        {
        "errors": [
            {
            "bbox_id": "1", //原图中的bbox序号
            "bbox_type": "equation", //图中的bbox类型
            "error_category": "公式识别相关问题", // 错误的大类
            "error_label": "公式中字符识别错误", // 从上面的《错误类别和标签》列表中选取的一个具体的二级标签
            },
            {
            "bbox_id": "2",
            "bbox_type": "table", //图中的bbox类型
            "error_category": "表格识别相关问题",
            "error_label": "表格输出格式错误"
            },
            {
            "bbox_id": "3",
            // ... 更多按 error_label 汇总的错误
            }
        ]
        }
        ```
         *工作流程:*
        1.  接收并理解 **原图** 和 **Pred的内容**。
        2.  仔细比对两者，识别所有内容和格式上的差异。
        3.  根据 **错误类别和标签** 对每个差异进行分类。
        4.  记录每个错误的信息（错误类别、错误标签）。如果同一位置存在多个独立的错误，请在 errors 列表内分别列出，不要再堆叠。
        5.  按照指定的 **输出格式** 生成 JSON 报告
        ```
        *输入:*
        *   **原图：**
        *   **Pred的内容：**
        *输出:*
        ```json
        [请在此处提供你的JSON分析结果, 注意仅输出json,不要输出任何解释]
        ```
        """

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
                    {"type": "text", "text": cls.prompt},
                    {"type": "image_url", "image_url": {"url": base64_image}},
                    {"type": "text", "text": f"Markdown:\n{input_data.content}"}
                ]
            }
        ]
        return messages

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        log.info(response)
        json_match = re.search(r'\{[\s\S]*"errors"[\s\S]*\}', response)
        # types = []
        # names = []
        tmp_types = []

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
                        # types.append(error_category)
                        # names.append(error_label)
                        tmp_types.append(f"{error_category}.{error_label}")
            except json.JSONDecodeError as e:
                log.error(f"JSON解析错误: {e}")
        else:
            log.error("未找到JSON内容")

        result = EvalDetail(metric=cls.__name__)
        result.status = False
        # result.type = types
        # result.name = names
        # result.reason = [json_str] if 'json_str' in locals() else [response]
        result.label = tmp_types
        result.reason = [json_str] if 'json_str' in locals() else [response]

        return result
