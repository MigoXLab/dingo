from dingo.io.input import RequiredField
from dingo.model import Model
from dingo.model.llm.text_quality.base_text_quality import BaseTextQuality


@Model.llm_register("LLMTextTable")
class LLMTextTable(BaseTextQuality):
    # Metadata for documentation generation
    _metric_info = {
        "category": "Pretrain Text Quality Assessment Metrics",
        "metric_name": "LLMTextQualityV5",
        "description": "Impact-driven text quality evaluation for LLM pretraining, focusing on structural completeness, readability, diversity, and safety with quantitative thresholds",
        "paper_title": "WanJuanSiLu: A High-Quality Open-Source Webtext Dataset for Low-Resource Languages",
        "paper_url": "https://arxiv.org/abs/2501.14506",
        "paper_authors": "Yu et al., 2025",
        "examples": "examples/llm_and_rule/llm_local.py",
        "evaluation_results": "docs/eval/prompt/redpajama_data_evaluated_by_prompt.md"
    }
    _required_fields = [RequiredField.CONTENT]
    prompt = r"""
你是一个专业的表格数据质检员。我会给你一段从文档中提取的 HTML 表格（table_body 字段），请判断该表格是否存在质量问题。

## 检测维度

请从以下维度进行检查：

1. **结构问题**
   - HTML 标签不完整或嵌套错误（<table>、<tr>、<td> 未正确闭合）
   - 行列结构异常（某行 <td> 数量与其他行差异过大）
   - 表格内容全部为空

2. **识别问题**
   - 存在明显乱码或无意义字符
   - 疑似 OCR 识别错误（如字母/数字混淆：0与O、1与l、S与5等）
   - 文字截断或内容残缺

3. **语义问题**
   - 单元格内容语义不连贯，无法理解表格表达的含义
   - 行列关系混乱，内容错位

## 一级错误类型（type）

- `structure`：结构问题
- `recognition`：识别问题
- `semantic`：语义问题

## 二级错误类型（name）

- `tag_error`：标签不完整或嵌套错误
- `row_col_mismatch`：行列数量不一致
- `empty_table`：表格内容为空
- `garbled_text`：乱码或无意义字符
- `ocr_error`：OCR 字符识别错误
- `truncated_content`：文字截断或内容残缺
- `incoherent_semantics`：语义不连贯
- `misaligned_content`：内容错位
- `none`：无问题

## Output Format

Return JSON only: {"score": 0/1, "type": "", "name": "", "reason": ""}

score 类型必须为int；
score 为 1 表示通过，type 填 "Good"，name 填 "None"，reason 说明公式正常的依据；
score 为 0 表示不通过，type 和 name 填对应的错误类型，reason 说明判断依据并指出具体位置或内容。

## Input content to evaluate:

"""
    # process_response method is now inherited from BaseTextQuality
