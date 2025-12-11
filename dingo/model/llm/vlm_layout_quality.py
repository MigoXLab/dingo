import base64
import json
import os
from typing import List

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log


@Model.llm_register("VLMLayoutQuality")
class VLMLayoutQuality(BaseOpenAI):
    prompt = r"""
     # 角色
    你是一名严谨细致的布局检测模型专家，你的任务是审查一个布局检测模型输出的蒙版图片，。由于没有标准的正确答案，你需要运用你对通用文档结构、排版惯例和逻辑关系的深刻理解，来识别并标记模型预测中的所有错误。

    # 布局类别定义
    模型能够识别并输出的类别是固定的。在判断“类别错误”时，请以此处定义的类别为准。合法的类别包括：
    *   **title (标题)**: 独立成行，在视觉上（如字体、字号、加粗）与正文有明显区别的各级标题。
    *   **text (文本)**: 普通段落文本。每个自然段应对应一个边界框，每一个列表项也对应一个边界框。
    *   **table (表格)**: 具有清晰行/列结构的数据或文本。结构简单的（如仅有几行几列且无标题）可被视为多个独立的`text`元素。
    *   **image (统计图表或图片)**: 柱状图、折线图、饼图等具有数学统计属性的图表。或者页面中的照片、插图、示意图等。
        *   **分割原则**: 如果图片内部有明显的空白分界线，应将其拆分为多个子图。
        *   **文本密集型图片**: 若图片主要由文本构成（如无复杂流程的截图），应将其中的文本块标注为`text`。
    *   **equation (公式)**: 单个独立成行的数学或化学公式，可以包含公式编号。
    *   **caption (图/表/代码标题)**: 位于图片、图表、表格或代码块上方或下方的标题或说明文字。
    *   **footnote (图/表/代码注释)**: 位于图片、图表、表格或代码块下方的补充性注释文字。
    *   **header (页眉)**: 页面顶部区域固定的、重复出现的内容，如章节名。
    *   **footer (页脚)**: 页面底部区域固定的、重复出现的内容，通常不包含页码。
    *   **page_number (页码)**: 仅包含页码的元素，通常位于页眉或页脚。
    *   **page_footnote (页面注释)**: 位于页面底部，对正文某处内容进行补充说明的注释（如脚注¹）。
    *   **reference (参考文献)**: 参考文献区域的单个条目。
    *   **code (代码)**: 多行代码块。
    *   **algorithm (算法块)**: 格式化的算法描述区域。
    *   **pinyin (拼音)**: 位于汉字上方的拼音标注，按行标注。
    *   **aside (边栏)**: 页面主内容区域之外的侧边栏文本或图像。
    *   **other (其他)**: 无法归入以上任何类别的元素。


    # 任务
    请你仔细审查图片上的每一个边界框，并结合其对应的类别信息，根据下方定义的错误类型，找出所有存在的错误。最终，你需要生成一份详细的、结构化的JSON格式错误报告。如果没有任何错误，请返回一个空的错误列表。

    # 错误类型定义
    在审核时，请重点关注以下几种基于视觉的错误：
    1.  **检测遗漏错误**:页面上肉眼可见的、有明确意义的独立内容（如文本块、图片、表格等），但模型未能为其生成任何边界框。
    2.  **检测不准错误**：检测不准确包括检测冗余、检测不完整、检测框重叠。检测冗余表示模型在**没有任何实际内容**的空白区域，或在不应被视为独立元素的装饰性图案/线条上，错误地生成了一个边界框。检测不完整表示元素的边界框过小，未能完整地包裹其全部视觉内容，导致部分内容（如文字笔画、图像边缘）或者边界框过大，包含了过多的无效内容。**请注意：只要内容被完整包裹，边界框包含少量额外的空白区域是可以接受的，如果过多的空白则是错误的。**检测框重叠表示原本互不重叠的检测框重叠在了一起，具体表现为蒙版的颜色相对其他蒙版更深。
    3.  **类别错误**: 元素的类别（label）与其在图片上呈现的视觉功能不符。结合框内**文本内容、字体大小、粗细、颜色、排版位置（如居中、缩进）、以及它在整个页面布局中的作用**来综合判断。
    *   **示例**:
        *   一个框内的文字是“第一章 绪论”，且字体显著大于正文、位置居中，但其`label`被标为`text`（文本），这应是`title`（标题）。
        *   一个明显是数据图表或照片的区域被错误地标记为`table`（表格）。
    4.  **阅读顺序错误**:模型输出的元素ID顺序与文档内容的**自然阅读流**不一致。注意只考虑检测出的元素的阅读顺序，未检测到的元素不考虑阅读顺序问题。

    # 工作流程
    1.  **全局审阅**: 首先快速浏览整张图片，对页面的整体布局、内容分区（如页眉、页脚、正文区、边栏）有一个大致的了解。
    2.  **逐项核对**: 按照ID顺序（或按视觉从上到下的顺序），仔细检查图片上的每一个边界框及其标注。
    3.  **综合判断**: 对于每个框，结合其**框内的视觉内容、标注的类别以及它与周围框体的空间关系**，判断是否存在错误。
    4.  **记录错误**: 一旦发现错误，根据上述【错误类型定义】，记录下来。
    5.  **生成报告**: 将所有发现的错误整理成指定格式的JSON报告。

    # 输出格式要求
    请严格按照以下JSON格式输出你的审核报告。报告的主体是一个名为`error_analysis`的列表，其中每个对象代表一个已识别的错误。

    **请特别注意以下两条规则：**
    *   **聚合相似错误**: 如果页面上有多个元素犯了**完全相同性质的错误**，请将它们**合并到同一个错误条目**中,并在`description`中进行概括性描述。
    *   **允许单个元素的多重错误**: 如果**同一个元素**（例如 `id=1`）同时存在多种类型的错误（例如，既有`Boundary Error`，又有`Classification Error`），你需要为它**创建多个独立的错误条目**，每个条目对应一种错误类型。
    *   对于“检测遗漏错误”，也应遵循此原则。例如，如果页面同时遗漏了页眉和页脚，你应该只创建一个检测遗漏错误条目，并在description中同时描述这两个被遗漏的元素，而不是创建两个独立的错误条目。

    **输出格式示例**
    请严格按照以下JSON结构输出完整报告：
    ```json
    {
        "errors": [
            {
                "error_id": 1,
                "error_type": "边界框不准错误",
                "error_location": "元素1的边界框过小，未能完整包含其文本内容'第一章：系统概述'的全部，文字的下半部分被截断。",
                "suggestion": "应调整边界框，确保其紧密包裹整个文本区域。"
            },
            {
                "error_id": 2,
                "error_type": "检测遗漏错误",
                "error_location": "页面上有两处明显的检测遗漏：1. 页面右上角的页眉 '财务报表' 未被检测。 2. 页面右下角的页脚 '2021年度报告 307' 未被检测。",
                "suggestion": "应为页眉和页脚分别添加新的边界框，并将其类别分别标记为 'header' 和 'footer'。"
            },
            {
                "error_id": 3,
                "error_type": "检测不准错误",
                "error_location": "页面上存在多处边界框检测不准确的问题：1. 元素8的边界框明显向左偏移，未能完整包裹其文本内容，导致文字右侧笔画被截断。 2. 元素24和元素28的边界框底部包含了过多的空白区域，属于冗余检测。",
                "suggestion": "应调整元素8的边界框位置，确保其紧密且完整地包裹该列文本。同时，应缩减元素24和28的边界框高度，以消除底部的多余空白区域。"
            }
        ]
    }
    ```

    *   `error_id`: (Int)错误问题的编号，从1开始计数，以此类推。
    *   `error_type`: (String) 从上述【错误类型定义】中选择一个。
    *   `error_location`: (String) 对错误位置的详细、客观的文字描述，**请结合图片上的视觉特征进行说明**。
    *   `suggestion`: (String) 针对该错误提出的具体、可操作的修改建议。

     *如果未发现任何错误，请返回：*
    ```json
    {
        "errors": []
    }
    ```
    ---------
    # 任务开始

    ## 输入信息
    1.  **布局检测图**: [待提供的原始图像] 这是一张模型布局检测结果的可视化图片。图中的标注样式遵循以下规则：
        边界框 (Bounding Box): 每个被检测出的布局元素，都被一个红色的矩形边框所包围。
        内容蒙版 (Content Mask): 位于红色边界框内部的区域，都被灰色的半透明蒙版覆盖，用于将注意力集中在元素的边界和位置上。
        元素ID序号: 每个边界框的外部附近，都有一个数字序号，代表模型为该元素预测的ID，此ID通常也对应了其认定的阅读顺序。
        请特别注意：某些元素在原始文档中可能本身就带有背景色块或边框。这些同样是独立的布局元素。如果它们没有红色的边界框和ID序号，就意味着模型未能检测到它们，这同样构成检测遗漏。
    2.  **元素属性列表**: 以下是模型为当前图片中每个ID预测的类别。请基于此列表和图片进行分析。
    {{ bbox_typr_list }}
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

        layout_prompt = cls.prompt.replace("{{ bbox_typr_list }}", bbox_info)

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
    def process_response(cls, response: str) -> EvalDetail:
        log.info(response)

        response = response.replace("```json", "")
        response = response.replace("```", "")

        types = []

        if response:
            try:
                result_data = json.loads(response)
                errors = result_data.get("errors", [])

                for error in errors:
                    eval_details = error.get("eval_details", "")

                    if eval_details:
                        types.append(eval_details)
            except json.JSONDecodeError as e:
                log.error(f"JSON解析错误: {e}")

        result = EvalDetail(metric=cls.__name__)
        result.label = types
        result.reason = [response]

        return result
