import json
import re
from typing import List

from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.response.response_class import ResponseScoreTypeNameReason
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMHtmlExtractCompareV3")
class LLMHtmlExtractCompareV3(BaseOpenAI):
    """
    HTML提取工具对比评估 V3 版本

    基于 LLMTextQualityV5 的质量维度（Completeness / Effectiveness / Similarity / Security）
    对两个 HTML 提取工具的完整输出做对比评估，判断哪个工具的提取质量更高。

    与 V2 的区别：V2 侧重"谁保留了更多信息内容"，V3 侧重"谁引入了更少质量缺陷"。
    V3 直接发送全文（不做 diff 预处理），保留完整上下文，确保质量缺陷（尤其是
    Error_Formula 等需要上下文才能正确归因的问题）能被准确识别。

    输入数据要求：
    - input_data.prompt: 工具A提取的文本（对应 Data.prompt 字段）
    - input_data.content: 工具B提取的文本（对应 Data.content 字段）
    - language: 可选，来自 input_data.language 或 raw_data["language"]，缺省为 "en"

    EvalDetail.label 前缀与 Data 字段对齐（避免 TOOL_ONE/TOOL_TWO 歧义）：
    - PROMPT_BETTER：score=1，Data.prompt 侧提取质量更好
    - CONTENT_BETTER：score=2，Data.content 侧更好
    - EXTRACTION_EQUAL：score=0，两者相当
    """

    _metric_info = {
        "category": "Pretrain Text Quality Assessment Metrics",
        "metric_name": "LLMHtmlExtractCompareV3",
        "description": "Compares two HTML extraction tools using LLM pretraining quality dimensions (completeness, effectiveness, similarity, security) with full-text evaluation for accurate defect attribution",
    }

    _required_fields = [RequiredField.PROMPT, RequiredField.CONTENT]

    prompt = {
        "content_en": r"""You are an expert in assessing pretraining data quality for large language models. You will compare two texts extracted from the same HTML page by different tools, and determine which extraction is of higher quality for LLM pretraining.

# Quality Dimensions

Evaluate BOTH texts against these dimensions and compare:

## 1. Completeness
- **Error_Content_Coverage**: One extraction tool failed to capture the full main-body content of the page — at least one complete paragraph or named section present in the other extraction is entirely absent (e.g., an "Applications" or "Common Algorithms" section is missing). This is about **extraction-level omission** (the tool did not locate or include that block), NOT about individual missing words, broken formatting, or formula stripping (use the specific error types below for those).
- **Error_Formula**: Mathematical content with broken LaTeX syntax (unmatched delimiters, unclosed environments) OR systematically stripped symbols/formulas (orphan hyphens from stripped Greek letters like "-solutions" instead of "κ-solutions", empty positions after connective words like "thus ;" where a formula was removed)
- **Error_Table**: Malformed or unreadable table structures (misaligned columns, missing headers, garbled HTML tags)
- **Error_Code**: Code blocks with formatting corruption (missing code fences, lost indentation, broken identifiers like "sys .argv", line numbers mixed with code)

## 2. Effectiveness
- **Error_Garbled_Characters**: Encoding issues or anti-crawler artifacts ("â€™", "□□□", "ï»¿"); threshold: >1% of characters garbled
- **Error_Words_Stuck**: Missing spaces breaking tokenization ("Thequickbrownfox"); threshold: >1% of text affected
- **Error_Lack_Punctuation**: Unclear sentence boundaries ("I like apples they are red also I like oranges")

## 3. Similarity
- **Error_Duplicate**: Excessive repetition dominating the text; threshold: same phrase repeats >5 times OR duplicate ratio >30%

## 4. Security
- **Error_Politics**: Content promoting extremism, terrorism, ethnic hatred
- **Error_Prohibition**: Violence, pornography, gambling, drugs

# Input

**Text A** (Data.prompt — first extraction tool):
{text_tool_a}

**Text B** (Data.content — second extraction tool):
{text_tool_b}

# Evaluation Rules

1. Evaluate each text independently against the quality dimensions above, then compare.
2. Identify the dimension with the **largest quality difference** between the two texts.
3. Minor formatting or whitespace differences that do not affect training quality should be ignored.

⚠️ The order of Text A and Text B reflects the fixed field mapping: A = `Data.prompt`, B = `Data.content`. Do NOT favor either text based on its position.

# Output Format

Return JSON only:
{{
  "score": [0|1|2],
  "name": "[error_type from the dimension with greatest difference]",
  "reason": "[objective description of quality differences]"
}}

Where:
- `score`: 1 if Text A (`Data.prompt`) is better, 2 if Text B (`Data.content`) is better, 0 if equal
- `name`: The specific error type with the biggest quality difference (e.g., "Error_Content_Coverage", "Error_Formula", "Error_Table", "Error_Code", "Error_Garbled_Characters", "Error_Words_Stuck", "Error_Lack_Punctuation", "Error_Duplicate", "Error_Politics", "Error_Prohibition"). Use "None" if both are equal.
- `reason`: Brief objective description (1-3 sentences)
""",
        "content_cn": r"""你是一位大语言模型预训练数据质量评估专家。你将对比两个不同 HTML 提取工具从同一网页中提取的文本，判断哪个提取结果的质量更高，更适合用于 LLM 预训练。

# 质量维度

请基于以下维度分别评估两段文本并进行对比：

## 1. 完整性 (Completeness)
- **Error_Content_Coverage**：一个提取工具未能覆盖网页的完整主体内容——另一方存在的至少一个完整段落或命名小节在这方完全缺失（例如"应用场景"或"常用算法"整节不见）。这针对的是**提取层面的遗漏**（工具未识别或未包含该区块），而非个别词语缺失、格式损坏或公式剥离（这些请用下方对应的专用错误类型）。
- **Error_Formula**：数学内容存在 LaTeX 语法错误（未匹配的定界符、未关闭的环境）或符号/公式被系统性剥离（如 "κ-solutions" 被剥离为 "-solutions"，连接词后公式缺失如 "thus ;" ）
- **Error_Table**：表格结构畸形或不可读（列未对齐、缺少表头、HTML标签残留）
- **Error_Code**：代码块格式损坏（缺少代码围栏、缩进丢失、标识符断裂如 "sys .argv"、行号混入代码）

## 2. 有效性 (Effectiveness)
- **Error_Garbled_Characters**：编码问题或反爬虫伪影（"â€™"、"□□□"、"ï»¿"）；阈值：>1% 的字符为乱码
- **Error_Words_Stuck**：缺失空格导致分词错误（"Thequickbrownfox"）；阈值：>1% 的文本受影响
- **Error_Lack_Punctuation**：句子边界不清（"I like apples they are red also I like oranges"）

## 3. 相似性 (Similarity)
- **Error_Duplicate**：过度重复内容；阈值：同一短语重复>5次 或 重复率>30%

## 4. 安全性 (Security)
- **Error_Politics**：宣扬极端主义、恐怖主义、民族仇恨的内容
- **Error_Prohibition**：暴力、色情、赌博、毒品相关内容

# 输入

**文本A**（Data.prompt — 第一个提取工具的结果）：
{text_tool_a}

**文本B**（Data.content — 第二个提取工具的结果）：
{text_tool_b}

# 评估规则

1. 独立按上述质量维度评估每段文本，再进行对比。
2. 找出两段文本之间**质量差异最大**的维度。
3. 不影响训练质量的细微格式差异或空白差异应忽略。

⚠️ 文本A和文本B的顺序反映固定字段映射：A = `Data.prompt`，B = `Data.content`。请勿因位置先后偏好任何一方。

# 输出格式

仅返回 JSON：
{{
  "score": [0|1|2],
  "name": "[差异最大维度中的具体错误类型]",
  "reason": "[客观描述两段文本的质量差异]"
}}

其中：
- `score`：文本A（`Data.prompt`）更好为 1，文本B（`Data.content`）更好为 2，质量相当为 0
- `name`：差异最大的具体错误类型（如 "Error_Content_Coverage"、"Error_Formula"、"Error_Table"、"Error_Code"、"Error_Garbled_Characters"、"Error_Words_Stuck"、"Error_Lack_Punctuation"、"Error_Duplicate"、"Error_Politics"、"Error_Prohibition"）。如果两者相当则为 "None"。
- `reason`：简要客观描述（1-3句话）
""",
    }

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        text_tool_a = input_data.prompt
        text_tool_b = input_data.content

        raw_data = getattr(input_data, "raw_data", {}) or {}
        language = raw_data.get("language", getattr(input_data, "language", "en"))

        if language == "zh":
            prompt_template = cls.prompt["content_cn"]
        else:
            prompt_template = cls.prompt["content_en"]

        prompt_content = prompt_template.format(
            text_tool_a=text_tool_a,
            text_tool_b=text_tool_b,
        )

        return [{"role": "user", "content": prompt_content}]

    @classmethod
    def process_response(cls, response: str) -> EvalDetail:
        log.info(response)

        response_think = ""
        if response.startswith("<think>"):
            think_content = re.search(
                r"<think>(.*?)</think>", response, flags=re.DOTALL
            )
            if think_content:
                response_think = think_content.group(1).strip()
            response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL)
            response = response.strip()

        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        response = response.strip()

        try:
            response_json = json.loads(response)
            if response_think:
                response_json["reason"] = response_json.get("reason", "") + "\n" + response_think
        except json.JSONDecodeError:
            raise ConvertJsonError(f"Convert to JSON format failed: {response}")

        response_model = ResponseScoreTypeNameReason(**response_json)

        result = EvalDetail(metric=cls.__name__)

        # Label prefixes match Data fields: prompt=first extraction, content=second.
        if response_model.score == 1:
            tmp_type = "PROMPT_BETTER"
        elif response_model.score == 2:
            tmp_type = "CONTENT_BETTER"
        else:
            tmp_type = "EXTRACTION_EQUAL"

        result.status = response_model.score != 1
        result.label = [f"{tmp_type}"]
        result.reason = [json.dumps(response_json, ensure_ascii=False)]

        return result
