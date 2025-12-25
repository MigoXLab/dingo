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


@Model.llm_register("LLMHtmlExtractCompare")
class LLMHtmlExtractCompare(BaseOpenAI):
    prompt = r"""
    你是一位专业的 HTML 内容提取评估专家，擅长分析 HTML 代码和 Markdown 文本的转换质量。现在我会提供三段内容：

    1. **原始网页的 HTML 代码**：这是网页的完整 HTML 结构。
    2. **工具A提取的 Markdown 文本**：这是从 HTML 中提取的、适合大语言模型训练的 Markdown 格式文本。
    3. **工具B提取的 Markdown 文本**：这是从 HTML 中提取的、适合大语言模型训练的 Markdown 格式文本。

    ⚠️ 注意：工具A与工具B的顺序不是固定的，请不要因为顺序而偏好某一工具，必须客观公正地评估两个工具的实际转换质量。

    你的任务：
    1. 将两个工具提取出来的 Markdown 文本分别与 HTML 代码做对比。严格按以下模块类型检查提取效果：

    **原始HTML元素识别：**
    - `code`：代码块（`<pre>` `<code>` 标签）
    - `math`：数学公式（MathJax、MathML、LaTeX 格式）
    - `table`：表格（`<table>` 标签）
    - `image`：图片（`<img>` 标签）
    - `list`：有序/无序列表（`<ul>` `<ol>` 标签）
    - `title`：标题（`<h1>`-`<h6>` 标签）
    - `paragraph`：段落文本（`<p>` `<div>` 等文本容器）
    - `other`：其他（非以上标签的可见内容）

    **Markdown元素统计：**
    - 代码块：\`\`\`...\`\`\` 或缩进代码
    - 公式：`$...$` `$$...$$` `\\(...\\)` `\\[...\\]`
    - 表格：`|...|` 格式
    - 图片：`![](...)` 格式
    - 列表：`-` `*` `1.` 等标记
    - 标题：`#` `##` 等标记
    - 段落：普通文本块

    2. **评分规则**：评价两个抽取工具的抽取质量，判断哪个工具抽取效果更好。
       - **抽取完整性**：检查 Markdown 文本是否完整抽取了 HTML 中的关键内容（如代码块、表格、图片、列表等）。
       - **格式准确性**：检查 Markdown 文本的格式是否正确（如代码块缩进、表格对齐、图片链接等）。
       - **语义连贯性**：检查 Markdown 文本是否保持了 HTML 内容的语义连贯性（如段落逻辑、标题层次等）。

    3. **问题反馈**：严格按上述 8 类模块定位问题，若无问题则返回空列表。

    4. **返回结果**：以 JSON 格式返回，包含3个字段：score、name、reason。
       - `score`：如果工具A抽取效果更好，score取值为1。如果工具B抽取效果更好，score取值为2。如果工具A和工具B抽取效果基本相同，score取值为0。
       - `name`：必须从 8 类模块中选择，且选择差异最大的问题模块。
       - `reason`：客观描述两个工具在该模块的表现差异。

    示例输出：
    ```json
    {{
      "score": [0|1|2],
      "name": "[模块类型]",
      "reason": "[客观描述两个工具在该模块的具体表现差异]"
    }}
    ```

    **注意事项**：
    1. 禁止使用预定义模块以外的分类。
    2. 重点关注结构化内容（代码、表格、公式、图片等）的转换质量。
    3. 段落分析需检查文本连贯性和语义完整性。

    ### 原始网页的 HTML 代码如下：

    ```html
    {}
    ```

    ### 工具A提取的 Markdown 文本如下：

    ```md
    {}
    ```

    ### 工具B提取的 Markdown 文本如下：

    ```md
    {}
    ```


    返回结果只有一个 JSON，不要有其他任何解释说明以及分析的信息！
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
