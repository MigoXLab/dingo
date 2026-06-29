"""
Multi-dimensional LLM-as-Judge evaluators for search result quality.

Two registered evaluators:

- ``LLMSearchQualityPointwise``: fan-out per result, scores **relevance** and
  **content_effectiveness** for each (query, result) pair independently.
- ``LLMSearchQualityListwise``: one LLM call per query, scores **authority**,
  **timeliness**, and **diversity** using the full result set metadata.

Both follow the standard Dingo evaluator contract:
``@Model.llm_register`` + ``eval(Data) -> EvalDetail``.

Data model convention (same as ``LLMSearchResultRelevance``):
  - ``Data.prompt``           – query text
  - ``Data.search_results``   – list of dicts with keys:
      rank, title, abstract, venue, year, citation_count, authors, paper_type, score
"""

from __future__ import annotations
import concurrent.futures
import json
import logging
import statistics
import time
from typing import Any, List

from dingo.io.input import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom config keys that must not leak to the OpenAI API
# ---------------------------------------------------------------------------
_CUSTOM_CONFIG_KEYS = frozenset({
    "top_k", "max_grading_workers", "eval_mode",
})

# ---------------------------------------------------------------------------
# Pointwise prompts
# ---------------------------------------------------------------------------

POINTWISE_SYSTEM_PROMPT = """\
You are an expert academic search evaluator. Your task is to evaluate the quality \
of a single search result for a given query.

Score TWO dimensions on a 0.0-1.0 scale:

1. **relevance** — How well the result matches the query intent.
   - 1.0: Perfect match — directly answers or addresses the query
   - 0.7-0.9: Clearly relevant, minor gaps
   - 0.4-0.6: Partially relevant, significant gaps
   - 0.1-0.3: Tangentially related at best
   - 0.0: Completely irrelevant

   Query-type-aware scoring:
   - Keyword query ("BiMLP", "LLM"): paper must discuss that topic
   - Author name query ("Michael Pecht"): paper must be by or about that person
   - Title query (full paper title): must be the paper itself or highly related
   - Chinese query: evaluate whether the paper's topic matches the Chinese query semantics

2. **content_effectiveness** — Quality and informativeness of the content presented.
   - 1.0: Rich, complete abstract; clearly conveys contribution and findings
   - 0.7-0.9: Good abstract with minor gaps
   - 0.4-0.6: Sparse or overly generic abstract
   - 0.1-0.3: Minimal/garbled/truncated content
   - 0.0: No useful content at all

Respond ONLY with a JSON object:
{"relevance": 0.0-1.0, "content_effectiveness": 0.0-1.0, "reasoning": "brief explanation"}"""


LISTWISE_SYSTEM_PROMPT = """\
You are an expert academic search evaluator. Given a query and its TOP-N search results \
(with metadata: title, venue, year, citations, authors, type), evaluate the result set \
as a whole on THREE dimensions, each scored 0.0-1.0:

1. **authority** — Overall academic authority of the result set.
   Consider:
   - Venue quality distribution (top journals/conferences vs preprints vs unknown)
   - Citation impact (highly cited papers vs zero-citation)
   - Author credibility
   - Paper types (peer-reviewed journal articles vs arXiv preprints)
   Scoring guide:
   - 1.0: Dominated by high-impact venues and highly cited papers
   - 0.5: Mix of reputable and unknown sources
   - 0.0: All from low-quality or unknown venues with no citations

2. **timeliness** — Whether the result set's publication years are appropriate for the query.
   Consider:
   - For cutting-edge topics (e.g. "LLM", "DeepSeek"): should include very recent papers (2024-2026)
   - For classic topics (e.g. "Deep Residual Learning"): should include the seminal paper
   - For general topics: reasonable year spread
   - Penalize result sets that are entirely outdated or miss important recent work
   Scoring guide:
   - 1.0: Year distribution perfectly matches query needs
   - 0.5: Partially appropriate time coverage
   - 0.0: Entirely inappropriate year distribution

3. **diversity** — Whether the result set covers different aspects/sub-topics.
   Consider:
   - Topic variety (different angles on the query)
   - Venue diversity (not all from one source)
   - Methodological diversity (theory, experiment, survey, application)
   - Penalize near-duplicate results or results all from one narrow sub-area
   Scoring guide:
   - 1.0: Rich variety covering multiple relevant perspectives
   - 0.5: Some variety but noticeable gaps or redundancy
   - 0.0: All results are near-identical or from one narrow angle

Respond ONLY with a JSON object:
{"authority": 0.0-1.0, "timeliness": 0.0-1.0, "diversity": 0.0-1.0, "reasoning": "brief explanation"}"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _parse_json_response(text: str) -> dict[str, Any]:
    return json.loads(_strip_code_fence(text))


def _format_authors_short(authors: Any) -> str:
    """Compact author string from list or pre-formatted string."""
    if isinstance(authors, str):
        return authors[:120]
    if isinstance(authors, list):
        names = []
        for a in authors[:5]:
            if isinstance(a, dict):
                names.append(a.get("name", ""))
            else:
                names.append(str(a))
        result = ", ".join(n for n in names if n)
        if len(authors) > 5:
            result += f" (+{len(authors) - 5} more)"
        return result
    return ""


def _get_extra_int(cls, key: str, default: int) -> int:
    extra = getattr(cls.dynamic_config, "model_extra", None) or {}
    val = extra.get(key, default)
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _send_with_filter(cls, messages: List) -> str:
    """Send messages filtering out custom config keys from extra_params."""
    if cls.dynamic_config.model:
        model_name = cls.dynamic_config.model
    else:
        model_name = cls.client.models.list().data[0].id

    extra_params = dict(cls.dynamic_config.model_extra or {})
    for k in _CUSTOM_CONFIG_KEYS:
        extra_params.pop(k, None)
    cls.validate_config(extra_params)

    from dingo.utils.exception import ExceedMaxTokens
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


# ===========================================================================
# LLMSearchQualityPointwise
# ===========================================================================

@Model.llm_register("LLMSearchQualityPointwise")
class LLMSearchQualityPointwise(BaseOpenAI):
    """Fan-out pointwise evaluator: relevance + content_effectiveness per result.

    Reads ``Data.prompt`` (query) and ``Data.search_results`` (list of dicts).
    Calls LLM once per result, aggregates to one EvalDetail per Data row.
    """

    _required_fields = []

    @classmethod
    def send_messages(cls, messages: List):
        return _send_with_filter(cls, messages)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        query = getattr(input_data, "prompt", "") or ""
        search_results = getattr(input_data, "search_results", None) or []

        if not search_results:
            return EvalDetail(
                metric=cls.__name__,
                score=0.0,
                label=["QUALITY_BAD.NoSearchResults"],
                reason=["No search results to evaluate"],
            )

        if cls.client is None:
            cls.create_client()

        top_k = _get_extra_int(cls, "top_k", 20)
        max_workers = _get_extra_int(cls, "max_grading_workers", 4)
        results_to_grade = search_results[:top_k]

        per_result_grades: list[dict[str, Any]] = [{}] * len(results_to_grade)

        def _grade_one(idx: int, result: dict) -> tuple[int, dict[str, Any]]:
            title = result.get("title", "")
            abstract = result.get("abstract", "")
            snippet = abstract[:3000]
            if len(abstract) > 3000:
                snippet += "\n[truncated]"

            user_msg = (
                f"Query: {query}\n\n"
                f"Result Title: {title}\n"
                f"Result Abstract:\n{snippet if snippet else '[no abstract available]'}"
            )
            messages = [
                {"role": "system", "content": POINTWISE_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ]

            for attempt in range(3):
                try:
                    resp = cls.send_messages(messages)
                    parsed = _parse_json_response(resp)
                    return idx, {
                        "rank": result.get("rank", idx + 1),
                        "title": title[:100],
                        "relevance": float(parsed.get("relevance", 0.0)),
                        "content_effectiveness": float(parsed.get("content_effectiveness", 0.0)),
                        "reasoning": str(parsed.get("reasoning", ""))[:300],
                    }
                except Exception as e:
                    logger.warning(
                        "Pointwise grading failed (attempt %d/3) for result %d: %s",
                        attempt + 1, idx, e,
                    )
                    if attempt < 2:
                        time.sleep(1)

            return idx, {
                "rank": result.get("rank", idx + 1),
                "title": title[:100],
                "relevance": 0.0,
                "content_effectiveness": 0.0,
                "error": "LLM grading failed after 3 attempts",
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_grade_one, i, r): i
                for i, r in enumerate(results_to_grade)
            }
            for future in concurrent.futures.as_completed(futures):
                idx, grade = future.result()
                per_result_grades[idx] = grade

        relevance_scores = [g["relevance"] for g in per_result_grades if "error" not in g]
        ce_scores = [g["content_effectiveness"] for g in per_result_grades if "error" not in g]
        error_count = sum(1 for g in per_result_grades if "error" in g)

        mean_rel = statistics.mean(relevance_scores) if relevance_scores else 0.0
        mean_ce = statistics.mean(ce_scores) if ce_scores else 0.0

        reasons = [
            f"mean_relevance={mean_rel:.4f}, mean_content_effectiveness={mean_ce:.4f}, "
            f"graded={len(relevance_scores)}, errors={error_count}",
        ]
        for g in per_result_grades:
            reasons.append(json.dumps(g, ensure_ascii=False))

        has_bad = mean_rel < 0.5
        return EvalDetail(
            metric=cls.__name__,
            score=round(mean_rel, 5),
            status=has_bad,
            label=[f"QUALITY_BAD.{cls.__name__}"] if has_bad else ["QUALITY_GOOD"],
            reason=reasons,
        )


# ===========================================================================
# LLMSearchQualityListwise
# ===========================================================================

@Model.llm_register("LLMSearchQualityListwise")
class LLMSearchQualityListwise(BaseOpenAI):
    """Listwise evaluator: authority + timeliness + diversity for the result set.

    One LLM call per Data row (one query's full result set).
    """

    _required_fields = []

    @classmethod
    def send_messages(cls, messages: List):
        return _send_with_filter(cls, messages)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        query = getattr(input_data, "prompt", "") or ""
        search_results = getattr(input_data, "search_results", None) or []

        if not search_results:
            return EvalDetail(
                metric=cls.__name__,
                score=0.0,
                label=["QUALITY_BAD.NoSearchResults"],
                reason=["No search results to evaluate"],
            )

        if cls.client is None:
            cls.create_client()

        top_k = _get_extra_int(cls, "top_k", 20)
        results_to_eval = search_results[:top_k]

        table_lines = []
        for i, r in enumerate(results_to_eval):
            venue = r.get("venue", "N/A") or "N/A"
            year = r.get("year") or "N/A"
            cites = r.get("citation_count")
            cite_str = str(cites) if cites is not None else "N/A"
            authors = _format_authors_short(r.get("authors", ""))
            paper_type = r.get("paper_type", "N/A") or "N/A"
            title = (r.get("title", "") or "")[:120]
            table_lines.append(
                f"[{i + 1}] Title: {title}\n"
                f"    Venue: {venue} | Year: {year} | Citations: {cite_str} | "
                f"Type: {paper_type}\n"
                f"    Authors: {authors}"
            )

        user_msg = (
            f"Query: {query}\n\n"
            f"Search Results ({len(results_to_eval)} papers):\n\n"
            + "\n\n".join(table_lines)
        )

        messages = [
            {"role": "system", "content": LISTWISE_SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        for attempt in range(3):
            try:
                resp = cls.send_messages(messages)
                parsed = _parse_json_response(resp)

                authority = float(parsed.get("authority", 0.0))
                timeliness = float(parsed.get("timeliness", 0.0))
                diversity = float(parsed.get("diversity", 0.0))
                reasoning = str(parsed.get("reasoning", ""))[:500]

                overall = round(
                    authority * 0.4 + timeliness * 0.3 + diversity * 0.3, 5,
                )

                has_bad = overall < 0.5
                return EvalDetail(
                    metric=cls.__name__,
                    score=overall,
                    status=has_bad,
                    label=[f"QUALITY_BAD.{cls.__name__}"] if has_bad else ["QUALITY_GOOD"],
                    reason=[
                        f"authority={authority:.3f}, timeliness={timeliness:.3f}, "
                        f"diversity={diversity:.3f}, overall={overall:.4f}",
                        reasoning,
                        json.dumps({
                            "authority": authority,
                            "timeliness": timeliness,
                            "diversity": diversity,
                        }),
                    ],
                )
            except Exception as e:
                logger.warning(
                    "Listwise grading failed (attempt %d/3): %s", attempt + 1, e,
                )
                if attempt < 2:
                    time.sleep(1)

        return EvalDetail(
            metric=cls.__name__,
            score=0.0,
            status=True,
            label=[f"QUALITY_BAD.{cls.__name__}"],
            reason=["LLM grading failed after 3 attempts"],
        )
