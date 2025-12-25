"""
LLM Resume Optimizer for ATS Optimization

Optimizes resumes for ATS systems with keyword injection and STAR method polishing.
"""

import json
import re
from typing import List, Tuple

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError

# Import EvalDetail for dev branch compatibility, fallback to ModelRes for main branch
try:
    from dingo.io.output.eval_detail import EvalDetail, QualityLabel
    USE_EVAL_DETAIL = True
except ImportError:
    from dingo.model.modelres import ModelRes
    USE_EVAL_DETAIL = False


@Model.llm_register("LLMResumeOptimizer")
class LLMResumeOptimizer(BaseOpenAI):
    """
    ATS-focused resume optimization using LLM.

    输入要求:
    - input_data.content: 简历文本
    - input_data.prompt: 目标岗位 (可选)
    - input_data.context: KeywordMatcher 的匹配报告 (可选, 触发针对性优化模式)

    Two modes:
    1. Targeted Mode: When context (match_report) is provided
    2. General Mode: When context is empty
    """

    _metric_info = {
        "category": "Resume Quality Assessment Metrics",
        "metric_name": "LLMResumeOptimizer",
        "description": "ATS-focused resume optimization with keyword injection and STAR polishing",
        "paper_title": "N/A",
        "paper_url": "",
        "source_frameworks": "Dingo ATS Tools"
    }

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        """
        Build messages for resume optimization.
        """
        resume_text = input_data.content or ""
        target_position = input_data.prompt or "Not specified"
        # Handle both branches: dev branch has context, main branch doesn't
        match_report = getattr(input_data, 'context', None) or ""

        # Detect language (simple heuristic: check for Chinese characters)
        is_chinese = cls._detect_chinese(resume_text)

        # Parse match report to determine mode
        missing_required, missing_nice, negative_keywords, is_targeted = cls._parse_match_report(match_report)

        if is_targeted:
            required_str = ", ".join(missing_required) if missing_required else ("无" if is_chinese else "None")
            nice_str = ", ".join(missing_nice) if missing_nice else ("无" if is_chinese else "None")
            negative_str = ", ".join(negative_keywords) if negative_keywords else ("无" if is_chinese else "None")

            if is_chinese:
                prompt_content = cls._build_targeted_prompt_zh(
                    target_position, required_str, nice_str, negative_str, resume_text
                )
            else:
                prompt_content = cls._build_targeted_prompt_en(
                    target_position, required_str, nice_str, negative_str, resume_text
                )
        else:
            if is_chinese:
                prompt_content = cls._build_general_prompt_zh(target_position, resume_text)
            else:
                prompt_content = cls._build_general_prompt_en(target_position, resume_text)

        messages = [{"role": "user", "content": prompt_content}]
        return messages

    @classmethod
    def _detect_chinese(cls, text: str) -> bool:
        """
        Detect if text contains significant Chinese characters.
        Returns True if more than 10% of characters are Chinese.
        """
        if not text:
            return False

        chinese_count = 0
        total_count = 0

        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                chinese_count += 1
            if char.strip():
                total_count += 1

        if total_count == 0:
            return False

        return (chinese_count / total_count) > 0.1

    @classmethod
    def _parse_match_report(cls, match_report) -> Tuple[List[str], List[str], List[str], bool]:
        """
        Parse match_report from KeywordMatcher.

        Supports multiple input formats:
        1. JSON string: Will be parsed to dict
        2. Dict with Plugin format: {"match_details": {"missing": [...], "negative_warnings": [...]}}
        3. Dict with Dingo format: {"keyword_analysis": [...]}
        4. List[str]: Treated as list of missing required keywords

        Returns:
            tuple: (missing_required, missing_nice, negative_keywords, is_targeted_mode)
        """
        missing_required = []
        missing_nice = []
        negative_keywords = []

        if not match_report:
            return missing_required, missing_nice, negative_keywords, False

        try:
            # Parse JSON string if needed
            if isinstance(match_report, str):
                match_report = json.loads(match_report)

            # Handle List[str] type - treat as list of missing required keywords
            if isinstance(match_report, list):
                missing_required = [kw for kw in match_report if isinstance(kw, str)]
                is_targeted = bool(missing_required)
                return missing_required, missing_nice, negative_keywords, is_targeted

            # Ensure match_report is a dict before calling .get()
            if not isinstance(match_report, dict):
                log.warning(f"Unsupported match_report type: {type(match_report)}")
                return [], [], [], False

            # Try Plugin format first (match_details structure)
            match_details = match_report.get("match_details", {})
            if match_details:
                # Extract missing keywords from Plugin format
                missing_list = match_details.get("missing", [])
                for item in missing_list:
                    skill = item.get("skill", "")
                    importance = item.get("importance", "Nice-to-have")
                    if skill:
                        if importance == "Required":
                            missing_required.append(skill)
                        else:
                            missing_nice.append(skill)

                # Extract negative warnings from Plugin format
                negative_list = match_details.get("negative_warnings", [])
                for item in negative_list:
                    skill = item.get("skill", "")
                    if skill:
                        negative_keywords.append(skill)

            # Try Dingo format (keyword_analysis structure)
            keyword_analysis = match_report.get("keyword_analysis", [])
            if keyword_analysis and not match_details:
                for kw in keyword_analysis:
                    keyword = kw.get("keyword", "")
                    importance = kw.get("importance", "").lower()
                    match_status = kw.get("match_status", "").lower()

                    if importance == "excluded" and match_status == "matched":
                        negative_keywords.append(keyword)
                    elif match_status == "missing":
                        if importance == "required":
                            missing_required.append(keyword)
                        elif importance == "nice-to-have":
                            missing_nice.append(keyword)

            is_targeted = bool(missing_required or missing_nice or negative_keywords)
            return missing_required, missing_nice, negative_keywords, is_targeted

        except (json.JSONDecodeError, TypeError, AttributeError) as e:
            log.warning(f"Failed to parse match_report: {e}")
            return [], [], [], False

    @classmethod
    def process_response(cls, response: str):
        """Process LLM response. Returns EvalDetail (dev) or ModelRes (main)."""
        log.info(f"Raw LLM response length: {len(response)} chars")

        # Clean response
        response = cls._clean_response(response)

        try:
            response_json = json.loads(response)
        except json.JSONDecodeError:
            raise ConvertJsonError(f"Convert to JSON format failed: {response[:500]}")

        # Extract optimization results
        optimization_summary = response_json.get("optimization_summary", {})
        section_changes = response_json.get("section_changes", [])
        overall_improvement = response_json.get("overall_improvement", "")

        # Generate reason text
        reason = cls._generate_reason(optimization_summary, section_changes, overall_improvement)

        # Return appropriate result type based on branch
        if USE_EVAL_DETAIL:
            result = EvalDetail(metric=cls.__name__)
            result.status = False
            result.label = [QualityLabel.QUALITY_GOOD]
            result.reason = [reason]
            # Store full response for downstream use (using extra field)
            result.optimized_content = response_json
        else:
            result = ModelRes()
            result.error_status = False
            result.type = "RESUME_OPTIMIZED"
            result.name = "OPTIMIZATION_COMPLETE"
            result.reason = [reason]
            # Store full response for downstream use
            result.optimized_content = response_json

        return result

    @staticmethod
    def _clean_response(response: str) -> str:
        """Clean response format."""
        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()

        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]

        if response.endswith("```"):
            response = response[:-3]

        return response.strip()

    @classmethod
    def _generate_reason(cls, summary: dict, changes: List[dict], overall: str) -> str:
        """Generate human-readable reason for the optimization."""
        reason_parts = []

        # Overall improvement
        if overall:
            reason_parts.append(f"Overall: {overall}")

        # Keywords added
        keywords_added = summary.get("keywords_added", [])
        if keywords_added:
            reason_parts.append(f"Keywords Added: {', '.join(keywords_added)}")

        # Associative keywords
        keywords_assoc = summary.get("keywords_associative", [])
        if keywords_assoc:
            reason_parts.append(f"Associative: {', '.join(keywords_assoc)}")

        # De-emphasized keywords
        keywords_de = summary.get("keywords_deemphasized", [])
        if keywords_de:
            reason_parts.append(f"De-emphasized: {', '.join(keywords_de)}")

        # Unused keywords
        keywords_unused = summary.get("keywords_unused", [])
        if keywords_unused:
            reason_parts.append(f"Could not integrate: {', '.join(keywords_unused)}")

        # General improvements (for General Mode)
        improvements = summary.get("improvements", [])
        if improvements:
            reason_parts.append(f"Improvements: {', '.join(improvements)}")

        # Section changes summary
        if changes:
            changed_sections = [c.get("section_name", "Unknown") for c in changes]
            reason_parts.append(f"Sections Modified: {', '.join(changed_sections)}")

        return "\n".join(reason_parts) if reason_parts else "Optimization complete"

    @classmethod
    def eval(cls, input_data: Data):
        """Override eval to validate inputs. Returns EvalDetail (dev) or ModelRes (main)."""
        # Validate that content (resume) is provided
        if not input_data.content:
            if USE_EVAL_DETAIL:
                result = EvalDetail(metric=cls.__name__)
                result.status = True
                result.label = [f"QUALITY_BAD.{cls.__name__}"]
                result.reason = ["Resume text (content) is required but was not provided"]
                return result
            else:
                return ModelRes(
                    error_status=True,
                    type="RESUME_OPTIMIZER_ERROR",
                    name="MISSING_RESUME",
                    reason=["Resume text (content) is required but was not provided"]
                )

        # Call parent eval method
        return super().eval(input_data)

    # ========== Prompt Templates ==========

    @staticmethod
    def _build_targeted_prompt_en(
        target_position: str, required_str: str, nice_str: str, negative_str: str, resume_text: str
    ) -> str:
        """Build English targeted optimization prompt."""
        return f"""You are a professional ATS (Applicant Tracking System) optimization expert.

## Critical Rules
- **DO NOT use any Emoji symbols**. Output must be plain text Markdown only.
- Keep resume content in its original language, do not translate.
- Only output sections that have been modified.
- Both "Before" and "After" must contain the **FULL TEXT** of that section.

## Format Standardization (Silent Fixes)
1. **Date Format**: Standardize to `YYYY.MM–YYYY.MM` (using Em dash, no spaces).
2. **Separators**: Convert HTML `<hr>` to Markdown `---`.

## Polish Method
Use **Implicit STAR Method** to improve weak sentences:
- Do NOT use explicit labels like [Situation], [Task]
- Use natural, professional language following "Context → Task → Action → Result"

## Mode: Targeted Optimization

Target Position: {target_position}

### Keyword Injection Strategy

**P1 - Force Inject (Required)**: {required_str}
- These keywords MUST appear in the resume
- Add to "Skills" section or naturally integrate into "Work Experience"

**P2 - Associative Injection (Nice-to-have)**: {nice_str}
- Use associative mention for similar tools
- Example: User has MySQL → Add "MySQL (familiar with PostgreSQL)"

**P3 - Implied Skills**:
- If user has LoRA/SFT experience → Can infer PyTorch
- If user has RAG project → Can infer "vector database"

**P4 - De-emphasize**: {negative_str}
- Do NOT delete historical facts
- Move these skills to the end of skill lists

### Anti-Fabrication Rules
- **ABSOLUTELY FORBIDDEN** to invent non-existent companies, projects, or experience
- If a keyword cannot be integrated, add to "Unused Suggestions" list

## Output Format (JSON)

Return a JSON object with this structure:
{{{{
    "target_position": "String",
    "optimization_summary": {{{{
        "keywords_added": ["keyword1", "keyword2"],
        "keywords_associative": ["keyword (context)"],
        "keywords_deemphasized": ["keyword"],
        "keywords_unused": ["keyword"]
    }}}},
    "section_changes": [
        {{{{
            "section_name": "String",
            "before": "Full original text",
            "after": "Full optimized text",
            "changes": ["Change 1", "Change 2"]
        }}}}
    ],
    "overall_improvement": "Brief summary of improvements"
}}}}

**Input Data:**
Resume:
{resume_text}

Please optimize and return the JSON result:
"""

    @staticmethod
    def _build_general_prompt_en(target_position: str, resume_text: str) -> str:
        """Build English general optimization prompt."""
        return f"""You are a professional ATS (Applicant Tracking System) optimization expert.

## Critical Rules
- **DO NOT use any Emoji symbols**. Output must be plain text Markdown only.
- Keep resume content in its original language, do not translate.
- Only output sections that have been modified.

## Format Standardization (Silent Fixes)
1. **Date Format**: Standardize to `YYYY.MM–YYYY.MM` (using Em dash, no spaces).
2. **Separators**: Convert HTML `<hr>` to Markdown `---`.

## Polish Method
Use **Implicit STAR Method** to improve weak sentences:
- Do NOT use explicit labels like [Situation], [Task]
- Use natural, professional language following "Context → Task → Action → Result"

## Mode: General Polish

Target Position: {target_position}

Focus on:
1. Using STAR method to improve sentence expression
2. Standardizing date format and separators
3. Improving overall professionalism and readability

## Output Format (JSON)

Return a JSON object with this structure:
{{{{
    "target_position": "String",
    "optimization_summary": {{{{
        "improvements": ["Improvement 1", "Improvement 2"]
    }}}},
    "section_changes": [
        {{{{
            "section_name": "String",
            "before": "Full original text",
            "after": "Full optimized text",
            "changes": ["Change 1", "Change 2"]
        }}}}
    ],
    "overall_improvement": "Brief summary of improvements"
}}}}

**Input Data:**
Resume:
{resume_text}

Please optimize and return the JSON result:
"""

    @staticmethod
    def _build_targeted_prompt_zh(
        target_position: str, required_str: str, nice_str: str, negative_str: str, resume_text: str
    ) -> str:
        """Build Chinese targeted optimization prompt."""
        return f"""你是一位专业的 ATS（求职跟踪系统）优化专家。

## 重要规则
- **禁止使用任何 Emoji 符号**。输出必须是纯文本 Markdown。
- 简历内容保持原语言，不要翻译。
- 只输出有修改的板块，未修改的板块不需要输出。
- "修改前"和"修改后"都必须输出该板块的**完整文本**，方便用户直接复制替换。

## 格式统一（静默修复）
1. **日期格式**：统一为 `YYYY.MM–YYYY.MM`（使用 Em dash，无空格）。
2. **分隔符**：将 HTML `<hr>` 转换为 Markdown `---`。

## 润色方法
使用**隐式 STAR 法则**改善弱句：
- 不要使用 [Situation]、[Task] 等显式标签
- 用自然、专业的语言，让句子遵循"背景 → 任务 → 行动 → 结果"的逻辑流

## 优化模式：针对性优化

目标岗位：{target_position}

### 关键词注入策略

**P1 - 强制注入（Required）**: {required_str}
- 这些关键词必须出现在简历中
- 可以添加到"专业技能"板块
- 可以在"工作经历"中自然融入

**P2 - 关联注入（Nice-to-have）**: {nice_str}
- 如果用户有类似工具经验，使用关联提及
- 例如：用户有 MySQL 经验 → 添加 "MySQL（熟悉 PostgreSQL 概念）"

**P3 - 隐含推断**:
- 如果用户做过 LoRA/SFT → 可以推断并添加 PyTorch
- 如果用户做过 RAG 项目 → 可以推断并添加"向量数据库"

**P4 - 弱化处理**: {negative_str}
- 不要删除历史事实
- 将这些技能移到技能列表末尾

### 禁止造假规则
- **绝对禁止**发明不存在的公司、项目或工作经历
- 如果某个关键词完全无法自然融入，将其放入"未能融入的建议"列表

## 输出格式 (JSON)

返回以下结构的 JSON 对象：
{{{{
    "target_position": "目标岗位",
    "optimization_summary": {{{{
        "keywords_added": ["关键词1", "关键词2"],
        "keywords_associative": ["关键词 (关联说明)"],
        "keywords_deemphasized": ["被弱化的关键词"],
        "keywords_unused": ["未能融入的关键词"]
    }}}},
    "section_changes": [
        {{{{
            "section_name": "板块名称",
            "before": "完整原文",
            "after": "完整优化后文本",
            "changes": ["变更1", "变更2"]
        }}}}
    ],
    "overall_improvement": "优化总结"
}}}}

**输入数据：**
简历：
{resume_text}

请优化并返回 JSON 结果：
"""

    @staticmethod
    def _build_general_prompt_zh(target_position: str, resume_text: str) -> str:
        """Build Chinese general optimization prompt."""
        return f"""你是一位专业的 ATS（求职跟踪系统）优化专家。

## 重要规则
- **禁止使用任何 Emoji 符号**。输出必须是纯文本 Markdown。
- 简历内容保持原语言，不要翻译。
- 只输出有修改的板块。

## 格式统一（静默修复）
1. **日期格式**：统一为 `YYYY.MM–YYYY.MM`（使用 Em dash，无空格）。
2. **分隔符**：将 HTML `<hr>` 转换为 Markdown `---`。

## 润色方法
使用**隐式 STAR 法则**改善弱句：
- 不要使用 [Situation]、[Task] 等显式标签
- 用自然、专业的语言，让句子遵循"背景 → 任务 → 行动 → 结果"的逻辑流

## 优化模式：通用润色

目标岗位：{target_position}

专注于：
1. 使用 STAR 法则改善句子表达
2. 统一日期格式和分隔符
3. 提升整体专业性和可读性

## 输出格式 (JSON)

返回以下结构的 JSON 对象：
{{{{
    "target_position": "目标岗位",
    "optimization_summary": {{{{
        "improvements": ["改进1", "改进2"]
    }}}},
    "section_changes": [
        {{{{
            "section_name": "板块名称",
            "before": "完整原文",
            "after": "完整优化后文本",
            "changes": ["变更1", "变更2"]
        }}}}
    ],
    "overall_improvement": "优化总结"
}}}}

**输入数据：**
简历：
{resume_text}

请优化并返回 JSON 结果：
"""
