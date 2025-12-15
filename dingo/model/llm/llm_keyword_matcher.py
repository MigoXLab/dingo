"""
LLM Keyword Matcher for ATS Resume Optimization

Evaluates how well a resume matches a job description using semantic matching.
"""

import json
import re
from typing import List

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

# Complete synonym mapping for keyword normalization
SYNONYM_MAP = {
    "k8s": "Kubernetes",
    "js": "JavaScript",
    "ts": "TypeScript",
    "py": "Python",
    "tf": "TensorFlow",
    "react.js": "React",
    "reactjs": "React",
    "vue.js": "Vue.js",
    "vuejs": "Vue.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "express.js": "Express.js",
    "expressjs": "Express.js",
    "nest.js": "NestJS",
    "nestjs": "NestJS",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "aws": "Amazon Web Services",
    "gcp": "Google Cloud Platform",
    "azure": "Microsoft Azure",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "ml": "Machine Learning",
    "dl": "Deep Learning",
    "ai": "Artificial Intelligence",
    "nlp": "Natural Language Processing",
    "cv": "Computer Vision",
    "golang": "Go",
    "cpp": "C++",
    "csharp": "C#",
    "dotnet": ".NET",
    "pt": "PyTorch",
    "pytorch": "PyTorch",
    "sklearn": "scikit-learn",
    "scikit-learn": "scikit-learn",
}


def _get_synonym_map_str() -> str:
    """Format SYNONYM_MAP for prompt injection."""
    return "\n".join([f"  - {k} → {v}" for k, v in SYNONYM_MAP.items()])


@Model.llm_register("LLMKeywordMatcher")
class LLMKeywordMatcher(BaseOpenAI):
    """
    Resume-JD keyword matching using LLM.

    输入要求:
    - input_data.content: 简历文本
    - input_data.prompt: 职位描述文本

    Features:
    - Semantic matching (not just string matching)
    - Negative constraint recognition (Excluded skills)
    - Evidence-based matching (quotes from resume)
    - Weighted scoring (Required × 2, Nice-to-have × 1)
    """

    _metric_info = {
        "category": "Resume Quality Assessment Metrics",
        "metric_name": "LLMKeywordMatcher",
        "description": "Semantic keyword matching between resume and job description",
        "paper_title": "N/A",
        "paper_url": "",
        "source_frameworks": "Dingo ATS Tools"
    }

    threshold = 0.6  # Default threshold for good match (60%)

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        """
        Build messages for keyword matching.
        """
        resume_text = input_data.content or ""
        jd_text = input_data.prompt or ""

        prompt_content = cls._build_prompt(jd_text, resume_text)

        messages = [{"role": "user", "content": prompt_content}]
        return messages

    @staticmethod
    def _build_prompt(jd_text: str, resume_text: str) -> str:
        """Build the keyword matching prompt."""
        synonym_str = _get_synonym_map_str()

        return f"""You are an expert ATS (Applicant Tracking System) Analyzer. Your goal is to assess how well a candidate's resume matches a specific Job Description (JD).

### 1. KNOWN ALIASES (Synonyms)
Use these strict mappings for matching. If the resume uses an alias, count it as a match.
{synonym_str}

### 2. ANALYSIS LOGIC (Step-by-Step)

**Step 1: JD Extraction & Classification**
Extract technical skills/keywords from the JD and classify their importance:
- **Required**: Core skills, "must have", "proficient in", "X years of experience in"
- **Nice-to-have**: "Plus", "preferred", "bonus", "familiarity with"
- **Excluded**: Negative constraints like "No need for X", "Not X", "Unlike X", "We don't use X"

**Step 2: Evidence Verification**
For each skill found in JD, search the Resume for evidence:
- **Exact**: String appears exactly (case-insensitive)
- **Substring**: Keyword exists inside a phrase. Example: JD "SQL" → Resume "MySQL"
- **Semantic**: Different words but same meaning. Example: JD "GPU Optimization" → Resume "TensorRT"
- **Alias**: Known synonym from the alias list. Example: JD "Kubernetes" → Resume "k8s"

**Step 3: Frequency Count**
Count how many times the keyword appears in both JD and Resume.

### 3. OUTPUT SCHEMA (Strict JSON)
Return ONLY a valid JSON object. No markdown, no code blocks, no commentary.

{{{{
  "jd_analysis": {{{{
    "job_title": "String (extracted job title, or null if not found)",
    "skills_total": Integer
  }}}},
  "keyword_analysis": [
    {{{{
      "keyword": "String (normalized form, e.g., 'Kubernetes' not 'k8s')",
      "importance": "Required" | "Nice-to-have" | "Excluded",
      "match_status": "Matched" | "Missing",
      "match_type": "Exact" | "Substring" | "Semantic" | "Alias" | "None",
      "evidence": "String (max 50 chars quote from resume, or null if missing)",
      "reasoning": "String (ONLY for Semantic match, explain why, else null)",
      "frequency": {{{{
        "jd": Integer,
        "resume": Integer
      }}}}
    }}}}
  ]
}}}}

### 4. IMPORTANT RULES
1. **Excluded + Matched**: If a skill is Excluded in JD but present in Resume, set match_status to "Matched".
2. **Excluded + Missing**: If a skill is Excluded in JD and NOT in Resume, set match_status to "Missing".
3. **Focus on HARD SKILLS**: Do not extract generic terms like "Communication", "Teamwork".
4. **Alias Priority**: Normalize to standard form, set match_type to "Alias".
5. **Evidence Length**: Keep evidence under 50 characters.
6. **Reasoning**: ONLY provide reasoning for Semantic matches.

**Input Data:**
Job Description:
{jd_text}

Resume:
{resume_text}

Please analyze and return the JSON result:
"""

    @classmethod
    def process_response(cls, response: str):
        """Process LLM response. Returns EvalDetail (dev) or ModelRes (main)."""
        log.info(f"Raw LLM response: {response}")

        # Extract think content and clean response
        response_think = cls._extract_think_content(response)
        response = cls._clean_response(response)

        try:
            response_json = json.loads(response)
        except json.JSONDecodeError:
            raise ConvertJsonError(f"Convert to JSON format failed: {response}")

        # Extract data from dict
        jd_analysis = response_json.get("jd_analysis", {})
        keyword_analysis = response_json.get("keyword_analysis", [])

        # Calculate weighted score
        score = cls._calculate_match_score(keyword_analysis)

        # Generate detailed reason
        reason = cls._generate_reason(jd_analysis, keyword_analysis, score)

        # Add think content to reason if exists
        if response_think:
            reason += "\n\n[LLM Thinking]\n" + response_think

        log.info(f"Keyword match score: {score:.1%}, threshold: {cls.threshold:.0%}")

        # Return appropriate result type based on branch
        if USE_EVAL_DETAIL:
            result = EvalDetail(metric=cls.__name__)
            result.score = score
            result.reason = [reason]
            if score >= cls.threshold:
                result.status = False
                result.label = [QualityLabel.QUALITY_GOOD]
            else:
                result.status = True
                result.label = [f"QUALITY_BAD.{cls.__name__}"]
        else:
            result = ModelRes()
            result.score = score
            result.reason = [reason]
            if score >= cls.threshold:
                result.error_status = False
                result.type = "KEYWORD_MATCH_GOOD"
                result.name = "MATCH_GOOD"
            else:
                result.error_status = True
                result.type = "KEYWORD_MATCH_LOW"
                result.name = "MATCH_LOW"

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
            reason_parts.append(f"Required (Matched): {', '.join(matched_required)}")
        if missing_required:
            reason_parts.append(f"Required (Missing): {', '.join(missing_required)}")
        if matched_nice:
            reason_parts.append(f"Nice-to-have (Matched): {', '.join(matched_nice)}")
        if missing_nice:
            reason_parts.append(f"Nice-to-have (Missing): {', '.join(missing_nice)}")
        if excluded_warning:
            reason_parts.append(f"Warning - Excluded skills in resume: {', '.join(excluded_warning)}")

        return "\n".join(reason_parts)

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
                    type="KEYWORD_MATCH_ERROR",
                    name="MISSING_RESUME",
                    reason=["Resume text (content) is required but was not provided"]
                )

        # Validate that prompt (JD) is provided
        if not input_data.prompt:
            if USE_EVAL_DETAIL:
                result = EvalDetail(metric=cls.__name__)
                result.status = True
                result.label = [f"QUALITY_BAD.{cls.__name__}"]
                result.reason = ["Job description (prompt) is required but was not provided"]
                return result
            else:
                return ModelRes(
                    error_status=True,
                    type="KEYWORD_MATCH_ERROR",
                    name="MISSING_JD",
                    reason=["Job description (prompt) is required but was not provided"]
                )

        # Call parent eval method
        return super().eval(input_data)
