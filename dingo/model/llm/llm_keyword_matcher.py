import json
import re
from typing import List

from dingo.io import Data
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.modelres import ModelRes
from dingo.model.prompt.prompt_keyword_matcher import PromptKeywordMatcher
from dingo.utils import log
from dingo.utils.exception import ConvertJsonError


@Model.llm_register("LLMKeywordMatcher")
class LLMKeywordMatcher(BaseOpenAI):
    """
    Resume-JD keyword matching using LLM.
    Evaluates how well a resume matches a job description for ATS optimization.

    Input fields (multi-field support):
    - content: Resume text
    - prompt: Job description text

    Features:
    - Semantic matching (not just string matching)
    - Negative constraint recognition (Excluded skills)
    - Evidence-based matching (quotes from resume)
    - Weighted scoring (Required × 2, Nice-to-have × 1)
    """

    prompt = PromptKeywordMatcher
    threshold = 0.6  # Default threshold for good match (60%)

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        """
        Build messages for keyword matching.
        Expects input_data to have:
        - content: Resume text
        - prompt: Job description text
        """
        resume_text = input_data.content or ""
        jd_text = input_data.prompt or ""

        prompt_content = cls.prompt.content.format(jd_text, resume_text)

        messages = [{"role": "user", "content": prompt_content}]
        return messages

    @classmethod
    def process_response(cls, response: str) -> ModelRes:
        log.info(f"Raw LLM response: {response}")

        # Extract think content and clean response (like llm_code_compare.py)
        response_think = cls._extract_think_content(response)
        response = cls._clean_response(response)

        try:
            response_json = json.loads(response)
        except json.JSONDecodeError:
            raise ConvertJsonError(f"Convert to JSON format failed: {response}")

        # Extract data from dict (no Pydantic, like llm_code_compare.py)
        jd_analysis = response_json.get("jd_analysis", {})
        keyword_analysis = response_json.get("keyword_analysis", [])

        # Calculate weighted score
        score = cls._calculate_match_score(keyword_analysis)

        # Generate detailed reason
        reason = cls._generate_reason(jd_analysis, keyword_analysis, score)

        # Add think content to reason if exists
        if response_think:
            reason += "\n\n[LLM Thinking]\n" + response_think

        result = ModelRes()

        # Set error_status based on threshold
        if score >= cls.threshold:
            result.error_status = False
            result.type = "KEYWORD_MATCH_GOOD"
            result.name = "MATCH_GOOD"
        else:
            result.error_status = True
            result.type = "KEYWORD_MATCH_LOW"
            result.name = "MATCH_LOW"

        result.reason = [reason]
        result.score = score

        log.info(f"Keyword match score: {score:.1%}, threshold: {cls.threshold:.0%}")

        return result

    @staticmethod
    def _extract_think_content(response: str) -> str:
        """Extract <think> content from response (for reasoning models)."""
        if response.startswith("<think>"):
            think_content = re.search(r"<think>(.*?)</think>", response, flags=re.DOTALL)
            return think_content.group(1).strip() if think_content else ""
        return ""

    @staticmethod
    def _clean_response(response: str) -> str:
        """Clean response format, remove think tags and markdown code blocks."""
        response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()

        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]

        if response.endswith("```"):
            response = response[:-3]

        return response.strip()

    @classmethod
    def _calculate_match_score(cls, keyword_analysis: List[dict]) -> float:
        """
        Calculate weighted match score.
        Formula: (Required_Matched × 2 + Nice_Matched × 1) / (Required_Total × 2 + Nice_Total × 1)
        Note: Excluded keywords do NOT affect the score.
        """
        required_total = 0
        required_matched = 0
        nice_total = 0
        nice_matched = 0

        for kw in keyword_analysis:
            importance = kw.get("importance", "").lower()
            match_status = kw.get("match_status", "").lower()

            if importance == "required":
                required_total += 1
                if match_status == "matched":
                    required_matched += 1
            elif importance == "nice-to-have":
                nice_total += 1
                if match_status == "matched":
                    nice_matched += 1
            # Excluded keywords are ignored in score calculation

        total_weight = required_total * 2 + nice_total * 1
        earned_weight = required_matched * 2 + nice_matched * 1

        if total_weight == 0:
            return 0.0

        return earned_weight / total_weight

    @classmethod
    def _generate_reason(cls, jd_analysis: dict, keyword_analysis: List[dict], score: float) -> str:
        """Generate human-readable reason for the match assessment."""
        matched_required = []
        matched_nice = []
        missing_required = []
        missing_nice = []
        excluded_warning = []

        for kw in keyword_analysis:
            keyword = kw.get("keyword", "")
            importance = kw.get("importance", "").lower()
            match_status = kw.get("match_status", "").lower()

            if importance == "excluded":
                if match_status == "matched":
                    excluded_warning.append(keyword)
            elif importance == "required":
                if match_status == "matched":
                    matched_required.append(keyword)
                else:
                    missing_required.append(keyword)
            elif importance == "nice-to-have":
                if match_status == "matched":
                    matched_nice.append(keyword)
                else:
                    missing_nice.append(keyword)

        # Build reason text
        reason_parts = [f"Match Score: {score:.1%} (threshold: {cls.threshold:.0%})"]

        job_title = jd_analysis.get("job_title")
        if job_title:
            reason_parts.append(f"Position: {job_title}")

        if matched_required:
            reason_parts.append(f"✅ Required (Matched): {', '.join(matched_required)}")
        if missing_required:
            reason_parts.append(f"❌ Required (Missing): {', '.join(missing_required)}")
        if matched_nice:
            reason_parts.append(f"✅ Nice-to-have (Matched): {', '.join(matched_nice)}")
        if missing_nice:
            reason_parts.append(f"⚪ Nice-to-have (Missing): {', '.join(missing_nice)}")
        if excluded_warning:
            reason_parts.append(f"⚠️ Warning - Excluded skills in resume: {', '.join(excluded_warning)}")

        return "\n".join(reason_parts)

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        """Override eval to validate inputs."""
        # Validate that content (resume) is provided
        if not input_data.content:
            return ModelRes(
                error_status=True,
                type="KEYWORD_MATCH_ERROR",
                name="MISSING_RESUME",
                reason=["Resume text (content) is required but was not provided"]
            )

        # Validate that prompt (JD) is provided
        if not input_data.prompt:
            return ModelRes(
                error_status=True,
                type="KEYWORD_MATCH_ERROR",
                name="MISSING_JD",
                reason=["Job description (prompt) is required but was not provided"]
            )

        # Call parent eval method
        return super().eval(input_data)
