"""
Exa-style pointwise search result relevance grader.

Grades each (query, result) pair independently, outputting structured scores
for query_relevance, result_quality, content_issues, confidence, and an
overall score on a 0.0-1.0 scale.

Two prompt modes are available (from Exa's "How we do evals" blog post):
- ``standard``: minimal 10-line prompt, high correlation with detailed
- ``detailed``: full 46-line prompt with scoring rubric and examples

This registered evaluator supports Data rows through LocalExecutor and direct
grading of search traces during RetrievalExecutor's open evaluation phase.
"""

from __future__ import annotations
import json
import logging
import re
import statistics
import time
from dataclasses import dataclass
from typing import Any

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.io.output.eval_detail import EvalDetail, TokenUsage
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI

logger = logging.getLogger(__name__)

HTML_TAG_PATTERN = r"<[^>]+>"
MOJIBAKE_EVIDENCE_PATTERN = r"[閿熻В鏋撮柨鐔恍掗弸纰凤拷�]|\{\/U\}|u[0-9a-fA-F]{4}|�{2,}"
INVISIBLE_CHAR_PATTERN = r"[\u2000-\u200F\u202F\u205F\u3000\uFEFF\u00A0\u2060-\u206F\uFEFF\xa0]"
DOI_PATTERN = re.compile(r"(?i)(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/[^\s]+)")

STANDARD_SYSTEM_PROMPT = """\
Grade how useful a search result is for a query and assign a relevance score
from 0.0 to 1.0.
Read the query, title, and available content, then return these fields:
- Brief reasoning in 20 words or fewer.
- Assign a query_relevance score between 0.0 and 1.0.
- Assign a result_quality score between 0.0 and 1.0.
- Set content_issues to true or false.
- Assign a confidence score between 0.0 and 1.0.
- Assign an overall score between 0.0 and 1.0.

Set content_issues=true only when mojibake, raw HTML/XML, parser residue, invisible/control
characters, or similar corruption makes visible content materially unreadable. Missing or short
abstracts and truncated previews are not issues when the visible title/snippet remains readable.

Return one valid JSON object only. Do not use double quotes inside reasoning."""

DETAILED_SYSTEM_PROMPT = """\
You are a helpful assistant that grades the relevance of search results for given queries.
Your task is to assign a relevance score between 0.0 and 1.0 to each result, where:

1.0: Perfect match - The result provides exactly what was asked for with high quality and authority
0.8-0.9: Excellent match - Very relevant and high quality, with minor imperfections
0.6-0.7: Good match - Clearly relevant but may be missing some aspects or quality issues
0.4-0.5: Fair match - Partially relevant but significant gaps or quality concerns
0.2-0.3: Poor match - Only tangentially related or major quality issues
0.0-0.1: Irrelevant - Does not meaningfully address the query

Key scoring principles:
- We want exact matches to the user's query - if they ask for a specific entity or type of information, that's what we need
- Lists or general articles about a topic are not good matches when the user wants a specific entity
- Consider both relevance to the query AND the quality/authority of the source
- Use decimal points for fine-grained differentiation (e.g. 0.85 vs 0.82)
- Be consistent in your scoring across different queries

KEEP in mind -- you are seeing a (sometimes truncated) snippet of the result, and results \
may not necessarily have all the information necessary to determine whether they match the \
query. For example, if the query is "companies founded after 2020", a company homepage is \
a good result, even if the homepage doesn't mention the year. Use your judgement and \
knowledge of the query and the result to make the best determination.

Above all else, your job is to use your judgement to determine what would be a good search \
result for a user interested in direct links to their, sometimes complex queries. USE YOUR JUDGEMENT.

Criteria Descriptions:

1. query_relevance: How well the search result matches the user's query. A high score means \
the result directly and fully answers the query, while a low score means the result is only \
tangentially related or irrelevant.

2. result_quality: The authority, accuracy, and trustworthiness of the result. High-quality \
results come from reputable sources, are well-written, and are not spammy or misleading.

3. content_issues: A boolean indicating severe content corruption only. Set this to true \
when the visible title/content has garbled or mojibake text, raw HTML/XML or parser residue \
that materially hurts readability, invisible/control characters, or unreadable text. Do NOT \
set this to true merely because the abstract is missing, the snippet is short, or the preview \
is truncated, if the visible title/snippet is still readable enough to judge relevance.

4. confidence: How certain you are about your grading. If the result snippet is clear and \
directly answers the query, confidence should be high. If you need external information to \
validate whether the result is a good match for the query, your confidence should be lower.

5. score: Your overall assessment of the result, on a scale from 0.0 (irrelevant) to 1.0 \
(perfect match), taking into account both relevance and quality.

For each search result, carefully read the query and the result. Assign a value for \
each criterion as follows:
- Provide a brief explanation of your reasoning in 20 words or fewer.
- Assign a query_relevance score between 0.0 and 1.0.
- Assign a result_quality score between 0.0 and 1.0.
- Indicate if there are severe content_issues (true/false).
- Assign a confidence score between 0.0 and 1.0.
- Assign an overall score between 0.0 and 1.0.

Be consistent and use decimal points for fine-grained differentiation. If you are unsure \
due to missing or unclear information, lower your confidence and make a best guess as to the score.

Return only one valid JSON object. Keep reasoning short and do not use double quotes inside \
the reasoning string. If you need quotation marks in reasoning, use single quotes."""


@dataclass
class RelevanceGrade:
    """Structured grade for a single (query, result) pair."""
    score: float = 0.0
    query_relevance: float = 0.0
    result_quality: float = 0.0
    content_issues: bool = False
    confidence: float = 0.0
    reasoning: str = ""
    error: str = ""
    usage: TokenUsage | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "score": self.score,
            "query_relevance": self.query_relevance,
            "result_quality": self.result_quality,
            "content_issues": self.content_issues,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }
        if self.error:
            d["error"] = self.error
        return d


@dataclass
class OpenEvalSummary:
    """Aggregated open eval metrics for a task."""
    mean_score: float = 0.0
    median_score: float = 0.0
    mean_query_relevance: float = 0.0
    mean_result_quality: float = 0.0
    content_issues_rate: float = 0.0
    mean_confidence: float = 0.0
    graded_pairs: int = 0
    error_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "open_eval_mean_score": round(self.mean_score, 5),
            "open_eval_median_score": round(self.median_score, 5),
            "open_eval_mean_query_relevance": round(self.mean_query_relevance, 5),
            "open_eval_mean_result_quality": round(self.mean_result_quality, 5),
            "open_eval_content_issues_rate": round(self.content_issues_rate, 5),
            "open_eval_mean_confidence": round(self.mean_confidence, 5),
            "open_eval_graded_pairs": self.graded_pairs,
            "open_eval_error_count": self.error_count,
        }


def _get_system_prompt(prompt_mode: str) -> str:
    if prompt_mode == "detailed":
        return DETAILED_SYSTEM_PROMPT
    return STANDARD_SYSTEM_PROMPT


def _build_user_message(
    query: str,
    title: str,
    abstract: str,
    expected_criteria: str | None = None,
) -> str:
    parts = [f"Query: {query}", ""]
    parts.append(f"Result Title: {title}")
    if abstract:
        snippet = abstract[:3000]
        if len(abstract) > 3000:
            snippet += "\n[content truncated]"
        parts.append(f"Result Content:\n{snippet}")
    else:
        parts.append("Result Content: [no content available]")

    if expected_criteria:
        parts.append("")
        parts.append(f"Expected criteria for a good result: {expected_criteria}")

    parts.append("")
    parts.append(
        'Respond in JSON format: {"reasoning": "...", "query_relevance": 0.0-1.0, '
        '"result_quality": 0.0-1.0, "content_issues": true/false, '
        '"confidence": 0.0-1.0, "score": 0.0-1.0}'
    )
    parts.append(
        "Return JSON only. Keep reasoning under 20 words and do not use double quotes inside reasoning."
    )
    return "\n".join(parts)


def _strip_json_fence(response_text: str) -> str:
    text = response_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _extract_json_object(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start:end + 1].strip()


def _repair_unescaped_quotes_in_reasoning(text: str) -> str:
    """Escape stray double quotes inside the reasoning JSON string.

    Some models emit otherwise valid JSON such as:
    {"reasoning": "The query "PBPK" matches", "score": 0.9, ...}
    The inner quotes break json.loads. This repair scopes the change to the
    reasoning value and leaves the following JSON keys untouched.
    """
    start_match = re.search(r'("reasoning"\s*:\s*")', text)
    if not start_match:
        return text

    value_start = start_match.end()
    next_key = re.search(
        r'"\s*(?:,\s*"(?:query_relevance|result_quality|content_issues|confidence|score)"\s*:|})',
        text[value_start:],
        flags=re.DOTALL,
    )
    if not next_key:
        return text

    value_end = value_start + next_key.start()
    value = text[value_start:value_end]
    repaired_value = re.sub(r'(?<!\\)"', r'\\"', value)
    return text[:value_start] + repaired_value + text[value_end:]


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _clamp_score(value: Any) -> float:
    return max(0.0, min(1.0, _coerce_float(value)))


def _grade_from_dict(data: dict[str, Any]) -> RelevanceGrade:
    return RelevanceGrade(
        score=_clamp_score(data.get("score", 0.0)),
        query_relevance=_clamp_score(data.get("query_relevance", 0.0)),
        result_quality=_clamp_score(data.get("result_quality", 0.0)),
        content_issues=bool(data.get("content_issues", False)),
        confidence=_clamp_score(data.get("confidence", 0.0)),
        reasoning=str(data.get("reasoning", "")),
    )


def _parse_grade_fields_lenient(text: str) -> RelevanceGrade | None:
    number_fields = {}
    for field in ("query_relevance", "result_quality", "confidence", "score"):
        match = re.search(
            rf'"{field}"\s*:\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))',
            text,
            flags=re.IGNORECASE,
        )
        if match:
            number_fields[field] = _clamp_score(match.group(1))

    if "score" not in number_fields and "query_relevance" not in number_fields:
        return None

    issue_match = re.search(r'"content_issues"\s*:\s*(true|false)', text, flags=re.IGNORECASE)
    reasoning = ""
    reasoning_match = re.search(
        r'"reasoning"\s*:\s*"(.*?)"\s*(?:,\s*"(?:query_relevance|result_quality|content_issues|confidence|score)"|})',
        text,
        flags=re.DOTALL,
    )
    if reasoning_match:
        reasoning = " ".join(reasoning_match.group(1).split())

    return RelevanceGrade(
        score=number_fields.get("score", number_fields.get("query_relevance", 0.0)),
        query_relevance=number_fields.get("query_relevance", 0.0),
        result_quality=number_fields.get("result_quality", 0.0),
        content_issues=issue_match.group(1).lower() == "true" if issue_match else False,
        confidence=number_fields.get("confidence", 0.0),
        reasoning=reasoning,
    )


def _parse_grade_response(response_text: str) -> RelevanceGrade:
    """Parse LLM JSON response into a RelevanceGrade."""
    text = _strip_json_fence(response_text)
    candidates = [text]
    extracted = _extract_json_object(text)
    if extracted and extracted != text:
        candidates.append(extracted)

    repaired_candidates = []
    for candidate in candidates:
        repaired = _repair_unescaped_quotes_in_reasoning(candidate)
        if repaired != candidate:
            repaired_candidates.append(repaired)
    candidates.extend(repaired_candidates)

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue

        try:
            if not isinstance(data, dict):
                return RelevanceGrade(error=f"JSON is not a dictionary: {candidate[:200]}")
            return _grade_from_dict(data)
        except (ValueError, TypeError) as e:
            return RelevanceGrade(error=f"Failed to parse grade response: {e}. Text: {candidate[:200]}")

    lenient = _parse_grade_fields_lenient(extracted or text)
    if lenient:
        return lenient
    return RelevanceGrade(error=f"JSON parse failed: {text[:200]}")


def _content_issue_evidence(title: str, abstract: str) -> list[str]:
    text = "\n".join([str(title or ""), str(abstract or "")])
    issues: list[str] = []
    if re.search(MOJIBAKE_EVIDENCE_PATTERN, text):
        issues.append("mojibake_or_garbled_text")
    if re.search(INVISIBLE_CHAR_PATTERN, text):
        issues.append("invisible_or_control_char")
    html_matches = re.findall(HTML_TAG_PATTERN, text)
    if html_matches:
        issues.append("html_or_xml_tag_residue")
    if re.search(r"(/docserver/|<\?xml|<!DOCTYPE|&lt;/?[a-zA-Z][^&]*&gt;)", text, flags=re.IGNORECASE):
        issues.append("parser_residue")
    return issues


def _has_severe_content_issue(title: str, abstract: str) -> bool:
    return bool(_content_issue_evidence(title, abstract))


def _normalize_doi(value: Any) -> str:
    """Extract and normalize a DOI from a query or result field."""
    text = str(value or "").strip()
    match = DOI_PATTERN.search(text)
    if not match:
        return ""
    return match.group(1).rstrip(".,;:)]}").lower()


def is_doi_query(query: str) -> bool:
    return bool(_normalize_doi(query))


def _extract_result_dois(result: dict[str, Any]) -> list[str]:
    candidates: list[Any] = [result.get("doi"), result.get("unique_id")]
    locations = result.get("locations")
    if isinstance(locations, list):
        for location in locations:
            if isinstance(location, dict):
                candidates.extend([location.get("doi"), location.get("url"), location.get("landing_page_url")])

    dois: list[str] = []
    for candidate in candidates:
        values = candidate if isinstance(candidate, list) else [candidate]
        for value in values:
            doi = _normalize_doi(value)
            if doi and doi not in dois:
                dois.append(doi)
    return dois


def _grade_doi_result(query: str, result: dict[str, Any]) -> RelevanceGrade | None:
    """Use deterministic identifier matching when the query is a DOI."""
    query_doi = _normalize_doi(query)
    if not query_doi:
        return None

    result_dois = _extract_result_dois(result)
    exact_match = query_doi in result_dois
    score = 1.0 if exact_match else 0.0
    result_text = ", ".join(result_dois) if result_dois else "missing"
    return RelevanceGrade(
        score=score,
        query_relevance=score,
        result_quality=1.0 if exact_match else 0.0,
        content_issues=False,
        confidence=1.0,
        reasoning=(
            f"Exact DOI match: {query_doi}."
            if exact_match
            else f"DOI mismatch: expected {query_doi}; result {result_text}."
        ),
    )


@Model.llm_register("LLMSearchResultRelevance")
class LLMSearchResultRelevance:
    """Exa-style pointwise search result relevance grader.

    Manages its own OpenAI client instance, independent of Dingo's
    ``BaseOpenAI`` evaluator hierarchy.
    """

    dynamic_config = EvaluatorLLMArgs()
    default_threshold = 0.15

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        api_url: str | None = None,
        prompt_mode: str = "standard",
        expected_criteria: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        timeout: float | None = None,
        session_id: str | None = None,
    ):
        self.model = model or "gpt-4o"
        self.api_key = api_key
        self.api_url = api_url
        self.prompt_mode = prompt_mode
        self.expected_criteria = expected_criteria
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout
        self.session_id = session_id
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI
            kwargs: dict[str, Any] = {}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.api_url:
                kwargs["base_url"] = self.api_url
            if self.session_id:
                kwargs["default_headers"] = {"X-Session-ID": self.session_id}
            self._client = OpenAI(**kwargs)
        return self._client

    def grade(
        self,
        query: str,
        title: str,
        abstract: str = "",
        expected_criteria: str | None = None,
    ) -> RelevanceGrade:
        """Grade a single (query, result) pair."""
        system_prompt = _get_system_prompt(self.prompt_mode)
        user_message = _build_user_message(
            query, title, abstract,
            expected_criteria=expected_criteria or self.expected_criteria,
        )

        client = self._get_client()
        last_grade = RelevanceGrade(error="LLM grading failed")
        usage: TokenUsage | None = None
        for attempt in range(3):
            try:
                completion = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=self.timeout,
                )
                usage = BaseOpenAI._merge_token_usage(
                    usage,
                    BaseOpenAI._extract_token_usage(
                        completion,
                        model_name=self.model,
                        provider="openai",
                    ),
                )
                response_text = completion.choices[0].message.content or ""
                last_grade = _parse_grade_response(response_text)
                last_grade.usage = usage
                if not last_grade.error:
                    return last_grade
                error: Exception | str = last_grade.error
            except Exception as exc:
                error = exc
                last_grade = RelevanceGrade(error=str(exc))
                last_grade.usage = usage

            logger.warning(
                "LLM grading attempt %s/3 failed for query=%r title=%r: %s",
                attempt + 1,
                query,
                title,
                error,
            )
            if attempt < 2:
                time.sleep(attempt + 1)
        return last_grade

    @classmethod
    def _config_value(cls, name: str, default: Any = None) -> Any:
        return getattr(cls.dynamic_config, name, default)

    @classmethod
    def _build_from_config(cls) -> "LLMSearchResultRelevance":
        return cls(
            model=cls.dynamic_config.model,
            api_key=cls.dynamic_config.key,
            api_url=cls.dynamic_config.api_url,
            prompt_mode=str(cls._config_value("prompt_mode", "detailed") or "detailed"),
            expected_criteria=cls._config_value("expected_criteria", None),
            max_tokens=int(cls._config_value("max_tokens", 1024) or 1024),
            temperature=float(cls._config_value("temperature", 0.0) or 0.0),
            timeout=cls._config_value("timeout", None),
            session_id=cls._config_value("session_id", None),
        )

    @staticmethod
    def _extract_title(result: dict[str, Any]) -> str:
        return str(result.get("title") or result.get("display_name") or "")

    @staticmethod
    def _extract_abstract(result: dict[str, Any]) -> str:
        if result.get("_eval_profile") == "agentic":
            return str(result.get("chunk") or result.get("abstract") or "")
        return str(
            result.get("abstract")
            or result.get("summary")
            or result.get("content")
            or ""
        )

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """Executor entry point: evaluate one flattened query-result pair."""
        result = getattr(input_data, "search_result", None)
        if not isinstance(result, dict):
            result = input_data.to_dict()
        query = str(getattr(input_data, "query", "") or result.get("_eval_query") or result.get("query") or "")

        title = cls._extract_title(result)
        abstract = cls._extract_abstract(result)
        grade = _grade_doi_result(query, result)
        if grade is None:
            grader = cls._build_from_config()
            grade = grader.grade(
                query=query,
                title=title,
                abstract=abstract,
            )
        agentic_profile = result.get("_eval_profile") == "agentic"
        score = grade.query_relevance if agentic_profile else grade.score
        threshold = float(cls._config_value("threshold", cls.default_threshold) or cls.default_threshold)
        content_issue_evidence = _content_issue_evidence(title, abstract) if grade.content_issues else []
        effective_content_issues = bool(content_issue_evidence)

        labels: list[str] = []
        if grade.error:
            labels.append("Relevance.Error_Parse")
        if score < threshold:
            labels.append("Relevance.Error_Relevance_Low")
        if effective_content_issues:
            labels.append("Relevance.Error_Content_Issues")

        status = bool(labels)
        if not labels:
            labels = ["QUALITY_GOOD"]

        reason = grade.to_dict()
        if agentic_profile:
            reason["judge_overall_score"] = grade.score
            reason["score"] = score
            reason["score_basis"] = "query_relevance"
        reason["raw_content_issues"] = grade.content_issues
        reason["content_issues"] = effective_content_issues
        reason["content_issue_evidence"] = content_issue_evidence

        return EvalDetail(
            metric=cls.__name__,
            status=status,
            score=round(score, 5),
            label=labels,
            reason=[reason],
            usage=grade.usage,
        )


def aggregate_grades(
    grades: list[RelevanceGrade],
    method: str = "mean",
) -> OpenEvalSummary:
    """Aggregate a list of grades into summary metrics."""
    if method not in ("mean", "median"):
        logger.warning(
            "Aggregation method %r is not supported for pointwise open eval; "
            "defaulting to mean/median metrics.",
            method,
        )
    if not grades:
        return OpenEvalSummary()

    valid = [g for g in grades if not g.error]
    errors = len(grades) - len(valid)

    if not valid:
        return OpenEvalSummary(graded_pairs=len(grades), error_count=errors)

    scores = [g.score for g in valid]
    return OpenEvalSummary(
        mean_score=statistics.mean(scores),
        median_score=statistics.median(scores),
        mean_query_relevance=statistics.mean(g.query_relevance for g in valid),
        mean_result_quality=statistics.mean(g.result_quality for g in valid),
        content_issues_rate=sum(1 for g in valid if g.content_issues) / len(valid),
        mean_confidence=statistics.mean(g.confidence for g in valid),
        graded_pairs=len(grades),
        error_count=errors,
    )
