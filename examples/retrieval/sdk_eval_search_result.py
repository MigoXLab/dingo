"""Evaluate search results with relevance, effectiveness, and authority metrics.

This script uses Dingo LocalExecutor for result-level metric execution, then
aggregates executor outputs back to query-level CSV/JSON reports.
"""

from __future__ import annotations
import argparse
import concurrent.futures
import json
import math
import os
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from search_result_eval_utils import (add_common_args, get_title, load_queries, load_query_result_jsonl, rank_discounted_mean, summarize, write_classified_jsonl, write_csv,  # noqa: E402,E501
                                      write_json)

from dingo.config import InputArgs  # noqa: E402
from dingo.exec import Executor  # noqa: E402
from dingo.model.llm.llm_search_result_relevance import is_doi_query  # noqa: E402
from dingo.retrieval.sciverse_quality import SciverseQualityEnricher  # noqa: E402
from dingo.retrieval.search_client import PaperResult, create_client  # noqa: E402

EFFECTIVENESS_LABEL_TO_ISSUE = {
    "Effectiveness.Error_Title_Miss": "missing_title",
    "Effectiveness.Error_Abstract_Miss": "missing_abstract",
    "Effectiveness.Error_Title_Recovered": "title_recovered",
    "Effectiveness.Error_Abstract_Recovered": "abstract_recovered",
    "Effectiveness.Error_Chunk_Miss": "missing_chunk",
    "Effectiveness.Error_Keywords_Miss": "missing_keywords",
    "Effectiveness.Error_Author_Miss": "missing_author",
    "Effectiveness.Error_HTML_Tag": "html_tag",
    "Effectiveness.Error_Mojibake": "mojibake",
    "Effectiveness.Error_Invisible_Char": "invisible_char",
    "Effectiveness.Error_Unreadable_Text": "unreadable_text",
    "Effectiveness.Error_Special_Char_Noise": "special_char_noise",
    "Effectiveness.Error_LLM_Quality_Parse": "llm_quality_parse_error",
    "Effectiveness.Error_Effectiveness_Low": "effectiveness_low",
    "Effectiveness.Error_Source_DocID_Miss": "missing_source_doc_id",
    "Effectiveness.Error_Source_Offset_Miss": "missing_source_offset",
    "Effectiveness.Error_Source_Not_Found": "source_not_found",
    "Effectiveness.Error_Source_Empty": "source_empty",
    "Effectiveness.Error_Source_Offset_Invalid": "source_offset_invalid",
    "Effectiveness.Error_Source_Check_Failed": "source_check_failed",
    "Effectiveness.Error_Chunk_Source_Inconsistent": "chunk_source_inconsistent",
}


def load_env_file(env_path: Path = DEFAULT_ENV_PATH) -> None:
    """Load an optional local .env without overriding process environment."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate search result quality with Dingo executor.")
    add_common_args(parser)
    parser.add_argument("--openai-api-key", default=os.environ.get("OPENAI_API_KEY"))
    parser.add_argument("--openai-base-url", default=os.environ.get("OPENAI_BASE_URL"))
    parser.add_argument("--openai-model", default=os.environ.get("OPENAI_MODEL", "gpt-5.4-mini"))
    parser.add_argument(
        "--openai-session-id",
        default=os.environ.get("OPENAI_SESSION_ID") or os.environ.get("CODEX_SESSION_ID"),
        help="Optional X-Session-ID header for agent-only OpenAI-compatible gateways.",
    )
    parser.add_argument("--openai-temperature", type=float, default=float(os.environ.get("OPENAI_TEMPERATURE", "0.0")))
    parser.add_argument("--prompt-mode", choices=("standard", "detailed"), default="detailed")
    parser.add_argument("--llm-max-tokens", type=int, default=1024)
    parser.add_argument("--llm-timeout", type=float, default=60.0)
    parser.add_argument("--llm-workers", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--effectiveness-llm-max-tokens", type=int, default=512)
    parser.add_argument(
        "--disable-effectiveness-llm-quality",
        action="store_true",
        help="Disable LLM readability/corruption judgment for effectiveness.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Optional unified threshold override for all three dimensions.",
    )
    parser.add_argument("--relevance-threshold", type=float, default=0.60)
    parser.add_argument("--effectiveness-threshold", type=float, default=0.80)
    parser.add_argument("--authority-threshold", type=float, default=0.30)
    parser.add_argument(
        "--retrieval-backend",
        choices=("precomputed", "agentic", "meta_search", "openalex"),
        default="precomputed",
        help="Use precomputed results or retrieve queries before evaluation.",
    )
    parser.add_argument(
        "--search-api-url",
        default=os.environ.get("SEARCH_API_URL"),
        help="Search API root or full endpoint; defaults to SEARCH_API_URL.",
    )
    parser.add_argument(
        "--search-api-token",
        default=None,
        help="Optional token override; prefer SCIVERSE_API_TOKEN or OPENALEX_API_KEY.",
    )
    parser.add_argument("--search-type", default=None)
    parser.add_argument(
        "--filters-json",
        default=None,
        help="Meta-search filters as a JSON object or an array of filter objects.",
    )
    parser.add_argument("--search-timeout", type=float, default=60.0)
    parser.add_argument("--search-workers", type=int, default=4)
    parser.add_argument("--search-rate-limit", type=float, default=None)
    parser.add_argument("--search-max-retries", type=int, default=3)
    parser.add_argument(
        "--source-check-interval",
        type=float,
        default=2.0,
        help="Minimum seconds between Sciverse enrichment requests (default: 2.0).",
    )
    parser.add_argument("--source-content-limit", type=int, default=200)
    parser.add_argument("--source-prefix-length", type=int, default=50)
    parser.add_argument("--source-offset-tolerance", type=int, choices=(0,), default=0,
                        help="Original-offset verification only; offset correction is disabled.")
    parser.add_argument("--metadata-batch-size", type=int, default=100)
    parser.add_argument("--disable-source-verification", action="store_true")
    parser.add_argument("--disable-authority-enrichment", action="store_true")
    parser.add_argument("--eval-profile", choices=("auto", "meta_search", "agentic"), default="auto",
                        help="Explicit result profile for precomputed input; auto preserves existing metadata.")
    parser.add_argument("--enrich-precomputed", action="store_true",
                        help="Fetch source and authority evidence for cached Agentic hits without repeating search.")
    parser.add_argument(
        "--save-detailed",
        action="store_true",
        help="Save detailed_results.json with query-level records and embedded result rows.",
    )
    return parser.parse_args()


def _openalex_authors(raw: dict[str, Any]) -> list[dict[str, str]]:
    authors: list[dict[str, str]] = []
    for authorship in raw.get("authorships") or []:
        author = authorship.get("author") or {}
        name = author.get("display_name") or authorship.get("raw_author_name") or ""
        if name:
            authors.append({"name": str(name), "orcid": str(author.get("orcid") or "")})
    return authors


def _openalex_keywords(raw: dict[str, Any]) -> list[str]:
    keywords: list[str] = []
    for item in raw.get("keywords") or []:
        value = item.get("display_name") if isinstance(item, dict) else item
        if value:
            keywords.append(str(value))
    return keywords


def normalize_search_result(paper: PaperResult, backend: str) -> dict[str, Any]:
    """Map backend-specific output to the fields consumed by all three metrics."""
    raw = dict(paper.raw or {})
    if backend == "agentic":
        raw["doc_id"] = str(raw.get("doc_id") or paper.paper_id or "")
        raw["title"] = str(raw.get("title") or paper.title or "")
        raw["chunk"] = str(raw.get("chunk") or raw.get("snippet") or paper.abstract or "")
        raw["abstract"] = str(raw.get("abstract") or "")
        raw["relevance_score"] = paper.score
        raw["_eval_profile"] = "agentic"
        return raw
    if backend == "meta_search":
        raw.setdefault("title", paper.title)
        raw.setdefault("abstract", paper.abstract)
        raw.setdefault("relevance_score", paper.score)
        return raw

    primary_location = raw.get("primary_location") or {}
    source = primary_location.get("source") or {}
    publisher = source.get("host_organization_name") or ""
    return {
        "unique_id": raw.get("id") or paper.paper_id,
        "title": paper.title,
        "abstract": paper.abstract,
        "keywords": _openalex_keywords(raw),
        "author": _openalex_authors(raw),
        "doi": raw.get("doi") or "",
        "citation_count": raw.get("cited_by_count") or 0,
        "influential_citation_count": 0,
        "publication_venue_name_unified": source.get("display_name") or "",
        "publication_venue_type": source.get("type") or "",
        "publication_venue_issn": source.get("issn") or [],
        "publication_publisher": [publisher] if publisher else [],
        "publication_published_year": raw.get("publication_year") or paper.year,
        "metadata_type": raw.get("type") or "paper",
        "language": raw.get("language") or "",
        "relevance_score": paper.score,
        "access_is_oa": str(bool((raw.get("open_access") or {}).get("is_oa"))).lower(),
        "openalex_raw": raw,
    }


def _build_search_client(args: argparse.Namespace):
    kwargs: dict[str, Any] = {
        "timeout": args.search_timeout,
        "max_retries": args.search_max_retries,
    }
    if args.search_api_token:
        kwargs["api_token"] = args.search_api_token
    if args.search_api_url:
        kwargs["api_url"] = args.search_api_url
    elif args.retrieval_backend in {"agentic", "meta_search"}:
        kwargs["api_url"] = os.environ.get(
            "SCIVERSE_API_URL", "https://api.sciverse.space"
        )
    elif args.retrieval_backend == "openalex":
        kwargs["api_url"] = os.environ.get(
            "OPENALEX_API_URL", "https://api.openalex.org"
        )
    if args.search_type:
        kwargs["search_type"] = args.search_type
    if args.filters_json:
        filters = json.loads(args.filters_json)
        if not isinstance(filters, (dict, list)) or (
            isinstance(filters, list)
            and not all(isinstance(item, dict) for item in filters)
        ):
            raise ValueError(
                "--filters-json must decode to a JSON object or an array of objects"
            )
        kwargs["filters"] = filters
    if args.search_rate_limit is not None:
        kwargs["rate_limit"] = args.search_rate_limit
    return create_client(args.retrieval_backend, **kwargs)


def retrieve_queries(
    args: argparse.Namespace,
    output_path: Path,
    request_log_path: Path,
) -> dict[str, Any]:
    queries = load_queries(args.input_jsonl, args.max_queries)
    if not queries:
        raise ValueError(f"No queries found in {args.input_jsonl}")

    client = _build_search_client(args)

    def search_one(index_query: tuple[int, str]) -> tuple[int, dict[str, Any], dict[str, Any]]:
        index, query = index_query
        response = client.search(query, limit=args.top_k)
        results = [
            normalize_search_result(paper, args.retrieval_backend)
            for paper in response.results[: args.top_k]
        ]
        item = {"query": query, "results": results}
        log = {
            "query_index": index,
            "query": query,
            "status_code": response.status_code,
            "response_time_ms": round(response.response_time_ms, 3),
            "result_count": len(results),
            "error": response.error or "",
        }
        return index, item, log

    completed: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.search_workers) as pool:
        futures = [pool.submit(search_one, item) for item in enumerate(queries, start=1)]
        for future in concurrent.futures.as_completed(futures):
            completed.append(future.result())
    completed.sort(key=lambda item: item[0])

    enrichment_summary = enrich_agentic_results(
        args, [result for _, item, _ in completed for result in item["results"]]
    ) if args.retrieval_backend == "agentic" else {}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as result_file, request_log_path.open(
        "w", encoding="utf-8"
    ) as log_file:
        for _, item, log in completed:
            result_file.write(json.dumps(item, ensure_ascii=False) + "\n")
            log_file.write(json.dumps(log, ensure_ascii=False) + "\n")

    logs = [log for _, _, log in completed]
    latencies = [float(log["response_time_ms"]) for log in logs]
    summary = {
        "backend": args.retrieval_backend,
        "query_count": len(logs),
        "result_count": sum(int(log["result_count"]) for log in logs),
        "success_count": sum(1 for log in logs if not log["error"]),
        "error_count": sum(1 for log in logs if log["error"]),
        "empty_count": sum(1 for log in logs if not log["error"] and not log["result_count"]),
        "mean_response_time_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
        "max_response_time_ms": round(max(latencies), 3) if latencies else 0.0,
    }
    if enrichment_summary:
        summary["enrichment"] = enrichment_summary
    return summary


def enrich_agentic_results(args: argparse.Namespace, results: list[dict[str, Any]]) -> dict[str, Any]:
    """Enrich fresh or cached Agentic hits identically before LocalExecutor."""
    enrichment_summary: dict[str, Any] = {}
    if results:
        api_token = args.search_api_token or os.environ.get("SCIVERSE_API_TOKEN")
        if not api_token:
            raise ValueError("Agentic subjective evaluation requires a Sciverse API token")
        enricher = SciverseQualityEnricher(
            api_url=args.search_api_url or os.environ.get("SCIVERSE_API_URL", "https://api.sciverse.space"),
            api_token=api_token,
            timeout=args.search_timeout,
            max_retries=args.search_max_retries,
            request_interval=args.source_check_interval,
            content_limit=args.source_content_limit,
            prefix_length=args.source_prefix_length,
            offset_tolerance=args.source_offset_tolerance,
        )
        all_results = results
        if not args.disable_authority_enrichment:
            enrichment_summary["authority_metadata"] = enricher.enrich_authority_metadata(
                all_results,
                batch_size=args.metadata_batch_size,
            )
        if not args.disable_source_verification:
            issue_counts: dict[str, int] = {}
            error_count = 0
            for result in all_results:
                verification = enricher.verify_source(result)
                result.update(verification.to_result_fields())
                if verification.issue:
                    issue_counts[verification.issue] = issue_counts.get(verification.issue, 0) + 1
                if verification.error:
                    error_count += 1
            enrichment_summary["source_verification"] = {
                "checked_results": len(all_results),
                "prefix_length": args.source_prefix_length,
                "content_limit": args.source_content_limit,
                "offset_tolerance": args.source_offset_tolerance,
                "issue_counts": issue_counts,
                "error_count": error_count,
            }

    return enrichment_summary


def flatten_query_results(
    input_path: Path,
    output_path: Path,
    *,
    top_k: int,
    max_queries: int | None,
    eval_profile: str = "auto",
) -> tuple[int, list[str]]:
    items = load_query_result_jsonl(input_path, max_queries)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    empty_queries: list[str] = []
    with output_path.open("w", encoding="utf-8") as f:
        for query_index, item in enumerate(items, start=1):
            query = item["query"]
            if not item["results"][:top_k]:
                empty_queries.append(query)
            for rank, result in enumerate(item["results"][:top_k], start=1):
                result_payload = dict(result)
                if eval_profile != "auto":
                    result_payload["_eval_profile"] = eval_profile
                result_payload["_eval_query"] = query
                row = {
                    "query": query,
                    "query_index": query_index,
                    "rank": rank,
                    "title": get_title(result),
                    "search_result": result_payload,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                count += 1
    return count, empty_queries


def metric_thresholds(args: argparse.Namespace) -> dict[str, float]:
    """Resolve a legacy unified threshold or dimension-specific defaults."""
    unified = getattr(args, "threshold", None)
    if unified is not None:
        value = float(unified)
        return {"relevance": value, "effectiveness": value, "authority": value}
    return {
        "relevance": float(getattr(args, "relevance_threshold", 0.60)),
        "effectiveness": float(getattr(args, "effectiveness_threshold", 0.80)),
        "authority": float(getattr(args, "authority_threshold", 0.30)),
    }


def build_executor_input(args: argparse.Namespace, flattened_path: Path) -> dict[str, Any]:
    thresholds = metric_thresholds(args)
    relevance_config = {
        "model": args.openai_model,
        "key": args.openai_api_key,
        "api_url": args.openai_base_url,
        "temperature": args.openai_temperature,
        "prompt_mode": args.prompt_mode,
        "max_tokens": args.llm_max_tokens,
        "timeout": args.llm_timeout,
        "session_id": args.openai_session_id,
        "threshold": thresholds["relevance"],
    }
    effectiveness_config = {
        "model": args.openai_model,
        "key": args.openai_api_key,
        "api_url": args.openai_base_url,
        "temperature": args.openai_temperature,
        "max_tokens": args.effectiveness_llm_max_tokens,
        "timeout": args.llm_timeout,
        "session_id": args.openai_session_id,
        "threshold": thresholds["effectiveness"],
        "enable_llm_quality": not args.disable_effectiveness_llm_quality,
    }
    authority_config = {"threshold": thresholds["authority"]}
    return {
        "task_name": "search_result_quality",
        "input_path": str(flattened_path),
        "output_path": str(args.output_dir),
        "dataset": {"source": "local", "format": "jsonl"},
        "executor": {
            "max_workers": args.llm_workers,
            "batch_size": args.batch_size,
            "result_save": {
                "bad": True,
                "good": True,
                "all_labels": True,
                "merge": True,
            },
        },
        "evaluator": [
            {
                "fields": {"search_result": "search_result"},
                "evals": [
                    {"name": "LLMSearchResultRelevance", "config": relevance_config},
                    {"name": "LLMSearchResultEffectiveness", "config": effectiveness_config},
                    {"name": "LLMSearchResultAuthority", "config": authority_config},
                ],
            }
        ],
    }


def load_executor_records(executor_output_path: str) -> list[dict[str, Any]]:
    all_results_path = Path(executor_output_path) / "all_results.jsonl"
    if not all_results_path.exists():
        raise FileNotFoundError(f"Executor merged result file not found: {all_results_path}")
    records = []
    with all_results_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def get_metric_detail(record: dict[str, Any], metric: str) -> dict[str, Any]:
    details = record.get("eval_details", {}).get("search_result", [])
    for detail in details:
        if detail.get("metric") == metric:
            return detail
    return {}


def first_reason(detail: dict[str, Any]) -> dict[str, Any]:
    reason = detail.get("reason") or []
    if reason and isinstance(reason[0], dict):
        return reason[0]
    return {}


def filtered_effectiveness_issues(detail: dict[str, Any]) -> str:
    labels = detail.get("label") or []
    issues = []
    for label in labels:
        issue = EFFECTIVENESS_LABEL_TO_ISSUE.get(label)
        if issue and issue not in issues:
            issues.append(issue)
    return "|".join(issues)


def build_reports(
    records: list[dict[str, Any]],
    args: argparse.Namespace,
    executor_summary,
    empty_queries: list[str] | None = None,
    retrieval_summary: dict[str, Any] | None = None,
) -> tuple[dict, list[dict], list[dict], list[dict], list[dict]]:
    thresholds = metric_thresholds(args)
    threshold_config: float | dict[str, float] = (
        float(args.threshold) if getattr(args, "threshold", None) is not None else thresholds
    )
    records = sorted(
        records,
        key=lambda r: (
            int(r.get("raw_data", {}).get("query_index") or 0),
            int(r.get("raw_data", {}).get("rank") or 0),
        ),
    )

    result_rows = []
    by_query: dict[str, list[dict[str, Any]]] = {}
    full_results_by_query: dict[str, list[dict[str, Any]]] = {}
    rank_relevance_error_count = 0
    rank_effectiveness_llm_quality_error_count = 0

    for record in records:
        raw = record.get("raw_data", {})
        query = raw.get("query", "")
        relevance_detail = get_metric_detail(record, "LLMSearchResultRelevance")
        effectiveness_detail = get_metric_detail(record, "LLMSearchResultEffectiveness")
        authority_detail = get_metric_detail(record, "LLMSearchResultAuthority")
        relevance_reason = first_reason(relevance_detail)
        effectiveness_reason = first_reason(effectiveness_detail)
        authority_reason = first_reason(authority_detail)

        relevance = round(float(relevance_detail.get("score") or 0.0), 5)
        effectiveness_raw = effectiveness_detail.get("score")
        effectiveness = None if effectiveness_raw is None else round(float(effectiveness_raw), 5)
        authority = round(float(authority_detail.get("score") or 0.0), 5)

        relevance_error = str(relevance_reason.get("error") or "")
        effectiveness_error = str(effectiveness_reason.get("llm_quality_error") or "")
        if relevance_error:
            rank_relevance_error_count += 1
        if effectiveness_error:
            rank_effectiveness_llm_quality_error_count += 1

        row = {
            "query": query,
            "rank": raw.get("rank"),
            "doc_id": str((raw.get("search_result") or {}).get("doc_id") or ""),
            "title": raw.get("title", ""),
            "relevance": relevance,
            "query_relevance": round(float(relevance_reason.get("query_relevance") or 0.0), 5),
            "result_quality": round(float(relevance_reason.get("result_quality") or 0.0), 5),
            "relevance_content_issues": bool(relevance_reason.get("content_issues", False)),
            "relevance_content_issue_evidence": "|".join(relevance_reason.get("content_issue_evidence") or []),
            "relevance_error": relevance_error,
            "relevance_reasoning": relevance_reason.get("reasoning", ""),
            "effectiveness": effectiveness,
            "effectiveness_issues": filtered_effectiveness_issues(effectiveness_detail),
            "chunk_score": round(float(effectiveness_reason.get("chunk_score") or 0.0), 5),
            "title_score": round(float(effectiveness_reason.get("title_score") or 0.0), 5),
            "abstract_score": round(float(effectiveness_reason.get("abstract_score") or 0.0), 5),
            "source_score": effectiveness_reason.get("source_score"),
            "source_exists": effectiveness_reason.get("source_exists"),
            "chunk_consistency": effectiveness_reason.get("chunk_consistency"),
            "source_check_error": effectiveness_reason.get("source_check_error", ""),
            "effectiveness_llm_quality_reason": effectiveness_reason.get("llm_quality_reason", ""),
            "effectiveness_llm_quality_error": effectiveness_error,
            "authority": authority,
            "citation_score": round(float(authority_reason.get("citation_score") or 0.0), 5),
            "influential_citation_score": round(float(authority_reason.get("influential_citation_score") or 0.0), 5),
            "venue_score": round(float(authority_reason.get("venue_score") or 0.0), 5),
            "doi_score": round(float(authority_reason.get("doi_score") or 0.0), 5),
            "authority_reason": authority_reason.get("reason", ""),
            "authority_citation_basis": authority_reason.get("citation_basis", ""),
            "authority_metadata_status": authority_reason.get("metadata_status", ""),
            "authority_metadata_error": authority_reason.get("metadata_error", ""),
        }
        result_rows.append(row)
        by_query.setdefault(query, []).append(row)
        full_result = dict(raw.get("search_result") or {})
        full_result.pop("_eval_query", None)
        full_result["_evaluation"] = {
            "rank": raw.get("rank"),
            "relevance": relevance,
            "effectiveness": effectiveness,
            "authority": authority,
        }
        full_results_by_query.setdefault(query, []).append(full_result)

    query_rows = []
    detailed = []
    classified_records = []
    for query, rows in by_query.items():
        relevance_scores = [float(row["relevance"]) for row in rows]
        effectiveness_scores = [row["effectiveness"] for row in rows]
        authority_rows: list[dict[str, Any]] = []
        seen_authority_docs: set[str] = set()
        for row in rows:
            doc_key = str(row.get("doc_id") or f"__rank_{row.get('rank')}")
            if doc_key in seen_authority_docs:
                continue
            seen_authority_docs.add(doc_key)
            authority_rows.append(row)
        authority_scores = [float(row["authority"]) for row in authority_rows]
        if is_doi_query(query):
            query_relevance = round(
                max(
                    (
                        float(row["relevance"])
                        / math.log2(max(1, int(row.get("rank") or index)) + 1)
                    )
                    for index, row in enumerate(rows, start=1)
                ),
                5,
            )
            relevance_aggregation = "doi_exact_match_rank_discount"
        else:
            query_relevance = round(rank_discounted_mean(relevance_scores), 5)
            relevance_aggregation = "rank_discounted_mean"
        query_effectiveness = rank_discounted_mean(effectiveness_scores)
        if query_effectiveness is not None:
            query_effectiveness = round(query_effectiveness, 5)
        query_authority = round(rank_discounted_mean(authority_scores), 5)

        labels = []
        if query_relevance < thresholds["relevance"]:
            labels.append("QUALITY_BAD.SEARCH_RESULT_RELEVANCE_LOW")
        relevance_errors = sum(1 for row in rows if row["relevance_error"])
        if any(score is None for score in effectiveness_scores):
            labels.append("REVIEW_EXECUTION_ERROR.Effectiveness_Incomplete")
        if query_effectiveness is not None and query_effectiveness < thresholds["effectiveness"]:
            labels.append("QUALITY_BAD.SEARCH_RESULT_EFFECTIVENESS_LOW")
        if query_authority < thresholds["authority"]:
            labels.append("QUALITY_BAD.SEARCH_RESULT_AUTHORITY_LOW")

        eval_status = bool(labels)
        if not labels:
            labels = ["QUALITY_GOOD.SEARCH_RESULT_METRICS_PASS"]

        query_row = {
            "query": query,
            "result_count": len(rows),
            "valid_relevance_count": len(rows) - relevance_errors,
            "relevance_error_count": relevance_errors,
            "relevance": query_relevance,
            "relevance_aggregation": relevance_aggregation,
            "effectiveness_aggregation": "rank_discounted_mean",
            "authority_aggregation": "rank_discounted_mean_unique_doc",
            "effectiveness": query_effectiveness,
            "authority": query_authority,
            "eval_status": eval_status,
            "label": "|".join(labels),
        }
        query_rows.append(query_row)
        detail = {**query_row, "results": rows}
        detailed.append(detail)
        classified_records.append({
            "query": query,
            "metric": "search_result_quality",
            "threshold": threshold_config,
            "eval_status": eval_status,
            "labels": labels,
            "relevance": query_relevance,
            "relevance_aggregation": relevance_aggregation,
            "effectiveness_aggregation": "rank_discounted_mean",
            "authority_aggregation": "rank_discounted_mean_unique_doc",
            "effectiveness": query_effectiveness,
            "authority": query_authority,
            "relevance_error_count": relevance_errors,
            "thresholds": {
                "relevance": thresholds["relevance"],
                "effectiveness": thresholds["effectiveness"],
                "authority": thresholds["authority"],
            },
            "results": full_results_by_query.get(query, []),
        })

    for query in empty_queries or []:
        labels = [
            "QUALITY_BAD.SEARCH_RESULT_RELEVANCE_LOW",
            "QUALITY_BAD.SEARCH_RESULT_EFFECTIVENESS_LOW",
            "QUALITY_BAD.SEARCH_RESULT_AUTHORITY_LOW",
        ]
        query_row = {
            "query": query,
            "result_count": 0,
            "valid_relevance_count": 0,
            "relevance_error_count": 0,
            "relevance": 0.0,
            "relevance_aggregation": (
                "doi_exact_match_rank_discount" if is_doi_query(query) else "rank_discounted_mean"
            ),
            "effectiveness_aggregation": "rank_discounted_mean",
            "authority_aggregation": "rank_discounted_mean_unique_doc",
            "effectiveness": 0.0,
            "authority": 0.0,
            "eval_status": True,
            "label": "|".join(labels),
        }
        query_rows.append(query_row)
        detailed.append({**query_row, "results": []})
        classified_records.append({
            "query": query,
            "metric": "search_result_quality",
            "threshold": threshold_config,
            "eval_status": True,
            "labels": labels,
            "relevance": 0.0,
            "relevance_aggregation": (
                "doi_exact_match_rank_discount" if is_doi_query(query) else "rank_discounted_mean"
            ),
            "effectiveness_aggregation": "rank_discounted_mean",
            "authority_aggregation": "rank_discounted_mean_unique_doc",
            "effectiveness": 0.0,
            "authority": 0.0,
            "relevance_error_count": 0,
            "thresholds": {
                "relevance": thresholds["relevance"],
                "effectiveness": thresholds["effectiveness"],
                "authority": thresholds["authority"],
            },
            "results": [],
        })

    summary = {
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metric": "search_result_quality",
        "top_k": args.top_k,
        "threshold": threshold_config,
        "thresholds": thresholds,
        "query_aggregation": "rank_discounted_mean",
        "llm": {
            "model": args.openai_model,
            "prompt_mode": args.prompt_mode,
            "max_tokens": args.llm_max_tokens,
            "temperature": args.openai_temperature,
            "timeout": args.llm_timeout,
            "workers": args.llm_workers,
            "effectiveness_llm_quality_enabled": not args.disable_effectiveness_llm_quality,
            "effectiveness_llm_max_tokens": args.effectiveness_llm_max_tokens,
        },
        "run_output_path": str(executor_summary.output_path),
        "metrics": {
            "relevance": summarize([float(row["relevance"]) for row in query_rows]),
            "effectiveness": summarize([float(row["effectiveness"]) for row in query_rows
                                        if row["effectiveness"] is not None]),
            "authority": summarize([float(row["authority"]) for row in query_rows]),
        },
        "query_count": len(query_rows),
        "result_count": len(result_rows),
        "effectiveness_unscored_count": sum(row["effectiveness"] is None for row in result_rows),
        "rank_relevance_error_count": rank_relevance_error_count,
        "rank_effectiveness_llm_quality_error_count": rank_effectiveness_llm_quality_error_count,
        "num_bad": sum(1 for row in query_rows if row["eval_status"]),
        "num_good": sum(1 for row in query_rows if not row["eval_status"]),
    }
    ratio_labels = (
        "QUALITY_BAD.SEARCH_RESULT_RELEVANCE_LOW",
        "QUALITY_BAD.SEARCH_RESULT_EFFECTIVENESS_LOW",
        "QUALITY_BAD.SEARCH_RESULT_AUTHORITY_LOW",
        "QUALITY_GOOD.SEARCH_RESULT_METRICS_PASS",
    )
    if query_rows:
        label_counts = {label: 0 for label in ratio_labels}
        for row in query_rows:
            row_labels = {
                label.strip()
                for label in str(row.get("label") or "").split("|")
                if label.strip()
            }
            for label in label_counts:
                if label in row_labels:
                    label_counts[label] += 1
        summary["type_ratio"] = {
            "search_result_quality": {
                label: count / len(query_rows)
                for label, count in label_counts.items()
            }
        }
    if retrieval_summary:
        summary["retrieval"] = retrieval_summary
    return summary, query_rows, result_rows, detailed, classified_records


def clear_executor_classification_dirs(run_dir: Path) -> None:
    """Remove result-level classifications before writing query-level output."""
    for name in ("bad", "good"):
        path = run_dir / name
        if path.exists():
            shutil.rmtree(path)


def write_issue_lists(run_dir: Path, records: list[dict[str, Any]]) -> None:
    """Export one JSONL per result-level issue, retaining raw evidence for review."""
    issues: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        labels = set()
        for details in (record.get("eval_details") or {}).values():
            for detail in details:
                labels.update(label for label in detail.get("label") or []
                              if label != "QUALITY_GOOD")
        for label in labels:
            issues.setdefault(label, []).append(record)
    issue_dir = run_dir / "issues"
    issue_dir.mkdir(exist_ok=True)
    for label, rows in issues.items():
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", label)
        with (issue_dir / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_json(run_dir / "issue_counts.json", {label: len(rows) for label, rows in sorted(issues.items())})


def main() -> None:
    load_env_file()
    args = parse_args()
    os.environ.setdefault("LOCAL_DEPLOYMENT_MODE", "true")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    temp_suffix = f"{int(time.time())}_{os.getpid()}"
    flattened_path = args.output_dir / f".search_result_quality_input_{temp_suffix}.jsonl"
    retrieval_results_path = args.output_dir / f".search_result_retrieval_{temp_suffix}.jsonl"
    retrieval_log_path = args.output_dir / f".search_result_retrieval_log_{temp_suffix}.jsonl"
    retrieval_summary: dict[str, Any] = {"backend": args.retrieval_backend}
    try:
        evaluation_input_path = args.input_jsonl
        flatten_max_queries = args.max_queries
        if args.retrieval_backend != "precomputed":
            retrieval_summary = retrieve_queries(
                args,
                retrieval_results_path,
                retrieval_log_path,
            )
            evaluation_input_path = retrieval_results_path
            flatten_max_queries = None

        if args.retrieval_backend == "precomputed" and args.enrich_precomputed:
            if args.eval_profile != "agentic":
                raise ValueError("--enrich-precomputed requires --eval-profile agentic")
            items = load_query_result_jsonl(evaluation_input_path, args.max_queries)
            for item in items:
                item["results"] = item["results"][:args.top_k]
            retrieval_summary["enrichment"] = enrich_agentic_results(
                args, [result for item in items for result in item["results"]]
            )
            with retrieval_results_path.open("w", encoding="utf-8") as handle:
                for item in items:
                    handle.write(json.dumps(item, ensure_ascii=False) + "\n")
            evaluation_input_path = retrieval_results_path
            flatten_max_queries = None

        total, empty_queries = flatten_query_results(
            evaluation_input_path,
            flattened_path,
            top_k=args.top_k,
            max_queries=flatten_max_queries,
            eval_profile=args.eval_profile,
        )
        if total:
            input_data = build_executor_input(args, flattened_path)
            executor_summary = Executor.exec_map["local"](InputArgs(**input_data)).execute()
            run_dir = Path(executor_summary.output_path)
            executor_records = load_executor_records(executor_summary.output_path)
            clear_executor_classification_dirs(run_dir)
        else:
            run_dir = args.output_dir / datetime.now().strftime("%Y%m%d_%H%M%S_empty")
            run_dir.mkdir(parents=True, exist_ok=True)
            executor_summary = SimpleNamespace(output_path=str(run_dir))
            executor_records = []

        summary, query_rows, result_rows, detailed, classified_records = build_reports(
            executor_records,
            args,
            executor_summary,
            empty_queries,
            retrieval_summary,
        )

        write_json(run_dir / "summary.json", summary)
        write_issue_lists(run_dir, executor_records)
        if args.save_detailed:
            write_json(run_dir / "detailed_results.json", {"summary": summary, "queries": detailed})
        write_csv(run_dir / "query_scores.csv", query_rows)
        write_csv(run_dir / "result_scores.csv", result_rows)
        write_classified_jsonl(
            run_dir,
            classified_records,
            save_good=args.save_good,
        )
        if args.retrieval_backend != "precomputed":
            shutil.copyfile(retrieval_results_path, run_dir / "retrieval_results.jsonl")
            shutil.copyfile(retrieval_log_path, run_dir / "retrieval_request_log.jsonl")
        elif args.enrich_precomputed:
            shutil.copyfile(retrieval_results_path, run_dir / "retrieval_results.jsonl")
        print(f"Saved to {run_dir.resolve()}")
    finally:
        for temp_path in (flattened_path, retrieval_results_path, retrieval_log_path):
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except PermissionError:
                    # A worker may still be releasing a Windows file handle
                    # after an executor exception. Preserve the reusable input
                    # instead of masking the original evaluation failure.
                    pass


if __name__ == "__main__":
    main()
