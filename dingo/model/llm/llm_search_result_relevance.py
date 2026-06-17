"""
Exa-style pointwise search result relevance grader.

Grades each (query, result) pair independently, outputting structured scores
for query_relevance, result_quality, content_issues, confidence, and an
overall score on a 0.0-1.0 scale.

Two prompt modes are available (from Exa's "How we do evals" blog post):
- ``standard``: minimal 10-line prompt, high correlation with detailed
- ``detailed``: full 46-line prompt with scoring rubric and examples

Registered as ``@Model.llm_register('LLMSearchResultRelevance')``.
Uses the fan-out pattern: one Data row (query + N search results) produces
one EvalDetail with aggregated score.
"""

from __future__ import annotations
import json
import logging
import statistics
import time
from dataclasses import dataclass
from typing import Any, List

from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI

logger = logging.getLogger(__name__)

STANDARD_SYSTEM_PROMPT = """\
You are a helpful assistant that grades the relevance of search results for given queries.
Your task is to assign a relevance score between 0.0 and 1.0 to each result, based on
how good a result is for the query.

For each search result, carefully read the query and the result. Assign a value for
each criterion as follows:
- Provide a brief explanation of your reasoning.
- Assign a query_relevance score between 0.0 and 1.0.
- Assign a result_quality score between 0.0 and 1.0.
- Indicate if there are any content_issues (true/false).
- Assign a confidence score between 0.0 and 1.0.
- Assign an overall score between 0.0 and 1.0."""

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

3. content_issues: A boolean indicating whether there are problems with the content, such as \
truncation, missing information, or improper parsing. If the result is incomplete or garbled, \
set this to true.

4. confidence: How certain you are about your grading. If the result snippet is clear and \
directly answers the query, confidence should be high. If you need external information to \
validate whether the result is a good match for the query, your confidence should be lower.

5. score: Your overall assessment of the result, on a scale from 0.0 (irrelevant) to 1.0 \
(perfect match), taking into account both relevance and quality.

For each search result, carefully read the query and the result. Assign a value for \
each criterion as follows:
- Provide a brief explanation of your reasoning.
- Assign a query_relevance score between 0.0 and 1.0.
- Assign a result_quality score between 0.0 and 1.0.
- Indicate if there are any content_issues (true/false).
- Assign a confidence score between 0.0 and 1.0.
- Assign an overall score between 0.0 and 1.0.

Be consistent and use decimal points for fine-grained differentiation. If you are unsure \
due to missing or unclear information, lower your confidence and make a best guess as to the score."""


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
    return "\n".join(parts)


def _parse_grade_response(response_text: str) -> RelevanceGrade:
    """Parse LLM JSON response into a RelevanceGrade."""
    text = response_text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return RelevanceGrade(error=f"JSON parse failed: {text[:200]}")

    try:
        if not isinstance(data, dict):
            return RelevanceGrade(error=f"JSON is not a dictionary: {text[:200]}")
        return RelevanceGrade(
            score=float(data.get("score", 0.0)),
            query_relevance=float(data.get("query_relevance", 0.0)),
            result_quality=float(data.get("result_quality", 0.0)),
            content_issues=bool(data.get("content_issues", False)),
            confidence=float(data.get("confidence", 0.0)),
            reasoning=str(data.get("reasoning", "")),
        )
    except (ValueError, TypeError) as e:
        return RelevanceGrade(error=f"Failed to parse grade response: {e}. Text: {text[:200]}")


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


@Model.llm_register("LLMSearchResultRelevance")
class LLMSearchResultRelevance(BaseOpenAI):
    """Exa-style pointwise search result relevance grader.

    Evaluates search results for a given query using the fan-out pattern:
    one Data row with N search results produces one EvalDetail with the
    mean relevance score.

    Data fields:
    - ``prompt``: the search query text
    - ``search_results``: list of result dicts (each with ``title``, ``abstract``)
    - ``expected_criteria`` (optional): criteria for a good result

    Config (via dynamic_config.model_extra):
    - ``prompt_mode``: "standard" or "detailed" (default: "standard")
    - ``top_k``: max results to grade per query (default: 5)
    - ``expected_criteria``: global criteria string (overridden by Data field)
    - ``threshold``: score threshold for pass/fail (default: 0.5)
    """

    _required_fields = [RequiredField.PROMPT]
    prompt = ""

    _custom_config_keys = frozenset({
        "prompt_mode", "top_k", "expected_criteria", "threshold",
    })

    @classmethod
    def send_messages(cls, messages: List):
        """Override to strip custom config keys before calling the OpenAI API."""
        from dingo.utils.exception import ExceedMaxTokens

        if cls.dynamic_config.model:
            model_name = cls.dynamic_config.model
        else:
            model_name = cls.client.models.list().data[0].id

        extra_params = {
            k: v for k, v in (cls.dynamic_config.model_extra or {}).items()
            if k not in cls._custom_config_keys
        }
        cls.validate_config(extra_params)

        completions = cls.client.chat.completions.create(
            model=model_name,
            messages=messages,
            **extra_params,
        )

        if completions.choices[0].finish_reason == "length":
            raise ExceedMaxTokens(
                f"Exceed max tokens: {extra_params.get('max_tokens', 4000)}"
            )

        return str(completions.choices[0].message.content)

    @classmethod
    def _get_prompt_mode(cls) -> str:
        return (cls.dynamic_config.model_extra or {}).get("prompt_mode", "standard")

    @classmethod
    def _get_top_k(cls) -> int:
        return int((cls.dynamic_config.model_extra or {}).get("top_k", 5))

    @classmethod
    def _get_expected_criteria(cls) -> str | None:
        return (cls.dynamic_config.model_extra or {}).get("expected_criteria")

    @classmethod
    def _get_threshold(cls) -> float:
        return float((cls.dynamic_config.model_extra or {}).get("threshold", 0.5))

    @classmethod
    def build_messages(cls, input_data: Data) -> List:
        """Build message bundles for each (query, result) pair.

        Returns a list of dicts: [{"result_index": i, "messages": [...]}]
        """
        query = getattr(input_data, "prompt", "") or ""
        search_results = getattr(input_data, "search_results", None) or []
        expected_criteria = (
            getattr(input_data, "expected_criteria", None)
            or cls._get_expected_criteria()
        )
        top_k = cls._get_top_k()
        prompt_mode = cls._get_prompt_mode()
        system_prompt = _get_system_prompt(prompt_mode)

        messages_list = []
        for i, result in enumerate(search_results[:top_k]):
            if not isinstance(result, dict):
                continue
            title = result.get("title", "")
            abstract = result.get("abstract", "")
            user_msg = _build_user_message(query, title, abstract, expected_criteria)
            messages_list.append({
                "result_index": i,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
            })
        return messages_list

    @classmethod
    def process_response(cls, responses: List[str]) -> EvalDetail:
        """Aggregate per-result LLM responses into one EvalDetail."""
        grades: list[RelevanceGrade] = []
        reasons: list[str] = []

        for i, response in enumerate(responses):
            grade = _parse_grade_response(response)
            grades.append(grade)
            if grade.error:
                reasons.append(f"Result {i + 1}: ERROR - {grade.error}")
            else:
                reasons.append(
                    f"Result {i + 1}: score={grade.score:.2f} "
                    f"(relevance={grade.query_relevance:.2f}, "
                    f"quality={grade.result_quality:.2f}) - {grade.reasoning[:100]}"
                )

        valid_scores = [g.score for g in grades if not g.error]
        mean_score = statistics.mean(valid_scores) if valid_scores else 0.0

        result = EvalDetail(metric=cls.__name__, score=round(mean_score, 5))
        threshold = cls._get_threshold()

        if mean_score >= threshold:
            result.status = False
            result.label = [QualityLabel.QUALITY_GOOD]
        else:
            result.status = True
            result.label = ["QUALITY_BAD.SEARCH_RELEVANCE_LOW"]

        reason_summary = (
            f"Mean relevance: {mean_score:.4f} "
            f"({len(valid_scores)} graded, {len(grades) - len(valid_scores)} errors)"
        )
        result.reason = [reason_summary] + reasons
        return result

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """Fan-out evaluation: grade each search result independently."""
        search_results = getattr(input_data, "search_results", None) or []
        if not search_results:
            result = EvalDetail(metric=cls.__name__, score=0.0)
            result.status = True
            result.label = ["QUALITY_BAD.NO_SEARCH_RESULTS"]
            result.reason = ["No search results to grade"]
            return result

        messages_list = cls.build_messages(input_data)
        if not messages_list:
            result = EvalDetail(metric=cls.__name__, score=0.0)
            result.status = True
            result.label = ["QUALITY_BAD.NO_VALID_RESULTS"]
            result.reason = ["No valid search results to grade"]
            return result

        if cls.client is None:
            cls.create_client()

        responses = []
        for item in messages_list:
            messages = item["messages"]
            attempts = 0
            response = None

            while attempts < 3:
                try:
                    response = cls.send_messages(messages)
                    break
                except Exception as e:
                    attempts += 1
                    logger.warning(
                        "LLM grading failed (attempt %d/3) for result %d: %s",
                        attempts, item["result_index"], e,
                    )
                    time.sleep(1)

            if response is None:
                responses.append('{"error": "All retry attempts failed"}')
            else:
                responses.append(response)

        return cls.process_response(responses)

    @classmethod
    def grade_single(
        cls,
        query: str,
        title: str,
        abstract: str = "",
        expected_criteria: str | None = None,
    ) -> RelevanceGrade:
        """Grade a single (query, result) pair directly.

        Convenience method for use by RetrievalExecutor's parallel grading.
        Uses the class-level client and config.
        """
        if cls.client is None:
            cls.create_client()

        prompt_mode = cls._get_prompt_mode()
        system_prompt = _get_system_prompt(prompt_mode)
        user_message = _build_user_message(
            query, title, abstract,
            expected_criteria=expected_criteria or cls._get_expected_criteria(),
        )

        try:
            response = cls.send_messages([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ])
            return _parse_grade_response(response)
        except Exception as e:
            logger.warning("LLM grading failed for query=%r title=%r: %s", query, title, e)
            return RelevanceGrade(error=str(e))
