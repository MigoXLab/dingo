from dingo.io.input import RequiredField
from dingo.model import Model
from dingo.model.llm.text_quality.base_text_quality import BaseTextQuality


@Model.llm_register("LLMTextEquation")
class LLMTextEquation(BaseTextQuality):
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
你是一个专业的数学、化学等学科的公式质检员。我会给你一个从文档中提取的 equation 类型元素（JSON 格式），请对其 text 字段进行质量检测。

## 检测维度

1. **语法问题**
   - LaTeX 命令拼写错误（如 \frace 代替 \frac）
   - 括号未正确配对闭合（{}、[]、()）
   - 环境标签不匹配（如 \begin{} 与 \end{} 不对应）

2. **识别问题**
   - 疑似 OCR 识别错误（如字母与符号混淆：x 与 ×、- 与 −、l 与 1、O 与 0 等）
   - 公式内容明显残缺或截断
   - 出现乱码或无意义字符

3. **语义问题**
   - 公式结构不完整，无法表达完整的数学含义
   - 运算符或符号使用明显不合数学规范

## 一级错误类型（type）

- `syntax`：语法问题
- `recognition`：识别问题
- `semantic`：语义问题

## 二级错误类型（name）

- `command_error`：LaTeX 命令拼写错误
- `bracket_mismatch`：括号未正确配对
- `env_mismatch`：环境标签不匹配
- `ocr_error`：OCR 字符识别错误
- `truncated_content`：公式残缺或截断
- `garbled_text`：乱码或无意义字符
- `incomplete_expression`：公式结构不完整
- `invalid_notation`：数学符号使用不规范
- `none`：无问题

## Output Format

Return JSON only: {"score": 0/1, "type": "", "name": "", "reason": ""}

score 类型必须为int；
score 为 1 表示通过，type 填 "Good"，name 填 "None"，reason 说明公式正常的依据；
score 为 0 表示不通过，type 和 name 填对应的错误类型，reason 说明判断依据并指出具体的问题位置或内容。

## Input content to evaluate:

"""
    # process_response method is now inherited from BaseTextQuality
