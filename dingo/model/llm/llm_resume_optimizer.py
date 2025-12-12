import json
import re
from typing import List, Tuple

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.prompt_resume_optimizer import PromptResumeOptimizer
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMResumeOptimizer")
class LLMResumeOptimizer(BaseOpenAI):
    """
    ATS-focused resume optimization using LLM.

    Two modes:
    1. Targeted Mode: When context (match_report) is provided
    2. General Mode: When context is empty

    Input fields (multi-field support):
    - content: Resume text
    - prompt: Target position (optional)
    - context: Match report from KeywordMatcher (optional, triggers Targeted Mode)
    """

    prompt = PromptResumeOptimizer

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        """
        Build messages for resume optimization.
        Expects input_data to have:
        - content: Resume text
        - prompt: Target position (optional)
        - context: Match report JSON (optional, enables Targeted Mode)

        Language detection:
        - Auto-detects Chinese content and uses Chinese prompts
        - Falls back to English prompts for other languages
        """
        resume_text = input_data.content or ""
        target_position = input_data.prompt or "Not specified"
        match_report = input_data.context or ""

        # Detect language (simple heuristic: check for Chinese characters)
        is_chinese = cls._detect_chinese(resume_text)

        # Parse match report to determine mode
        missing_required, missing_nice, negative_keywords, is_targeted = cls._parse_match_report(match_report)

        if is_targeted:
            # Targeted Mode: Use content_targeted prompt
            required_str = ", ".join(missing_required) if missing_required else ("无" if is_chinese else "None")
            nice_str = ", ".join(missing_nice) if missing_nice else ("无" if is_chinese else "None")
            negative_str = ", ".join(negative_keywords) if negative_keywords else ("无" if is_chinese else "None")

            # Select prompt based on language
            if is_chinese:
                prompt_template = cls.prompt.content_targeted_zh
            else:
                prompt_template = cls.prompt.content_targeted

            prompt_content = prompt_template.format(
                target_position,  # {0}
                required_str,     # {1}
                nice_str,         # {2}
                negative_str,     # {3}
                resume_text       # {4}
            )
        else:
            # General Mode: Use content_general prompt
            if is_chinese:
                prompt_template = cls.prompt.content_general_zh
            else:
                prompt_template = cls.prompt.content_general

            prompt_content = prompt_template.format(
                target_position,  # {0}
                resume_text       # {1}
            )

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
            if char.strip():  # Count non-whitespace characters
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
    def process_response(cls, response: str) -> ModelRes:
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
    def eval(cls, input_data: Data) -> ModelRes:
        """Override eval to validate inputs."""
        # Validate that content (resume) is provided
        if not input_data.content:
            return ModelRes(
                error_status=True,
                type="RESUME_OPTIMIZER_ERROR",
                name="MISSING_RESUME",
                reason=["Resume text (content) is required but was not provided"]
            )

        # Call parent eval method
        return super().eval(input_data)
