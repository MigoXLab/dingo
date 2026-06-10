"""
Sciverse search backends for retrieval evaluation.

Supports two modes:

  Local (default):
    POST {api_url}/v1/search  -- direct connection to the Go service, no auth.

  Public (when api_token is set):
    POST {api_url}/agentic-search  -- SciVerse public gateway with Bearer auth.
    POST {api_url}/meta-search     -- SciVerse metadata search gateway.
    Rate limit defaults to 1 RPS.

Examples:

  dingo eval-retrieval \
    --backend agentic \
    --tasks SciFact \
    --api-url https://api.sciverse.space \
    --api-token YOUR_SCIVERSE_API_TOKEN \
    --limit 100 \
    --max-queries 5 \
    -o outputs/retrieval_eval

  dingo eval-retrieval \
    --backend meta_search \
    --tasks SciFact \
    --api-url https://api.sciverse.space \
    --api-token YOUR_SCIVERSE_API_TOKEN \
    --limit 100 \
    --max-queries 5 \
    -o outputs/retrieval_eval

For the meta_search example above, each query is sent as:

  POST https://api.sciverse.space/meta-search
  {
    "query": "<MTEB query text>",
    "filters": [],
    "page": 1,
    "page_size": 100
  }

Additional CLI options map to the meta-search body as follows:
  --filters-json '{"year_from": 2010}'
    -> filters=[{"field": "publication_published_year",
                 "operator": "FILTER_OP_GTE",
                 "value": 2010}]
  --freshness-boost MILD
    -> freshness_boost="MILD"
  --sort-by citation_count
    -> sort=[{"field": "citation_count", "order": "SORT_ORDER_DESC"}]
       and query is omitted because meta-search does not allow query and sort
       in the same request.
"""

from __future__ import annotations
import logging
import os
import threading
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from dingo.retrieval.search_client import PaperResult, SearchClient, SearchResponse, register_backend

logger = logging.getLogger(__name__)


@register_backend("agentic")
class AgenticSearchClient(SearchClient):
    name = "agentic-search-api"
    public_endpoint = "agentic-search"
    local_endpoint = "v1/search"

    # Common Sciverse metadata field names observed across API variants.
    id_fields = (
        "doc_id",
        "paper_id",
        "paperId",
        "corpus_id",
        "corpusid",
        "id",
        "doi",
    )
    title_fields = ("title", "paper_title", "name")
    text_fields = ("snippet", "chunk", "abstract", "summary", "description")

    def __init__(
        self,
        api_url: str = "http://127.0.0.1:8080",
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 0.5,
        rate_limit: float = 0.0,
        retrieval_mode: str = "hybrid",
        sub_queries: int | None = None,
        api_token: str | None = None,
        **_kwargs: Any,
    ) -> None:
        self.base_url = api_url.rstrip("/")
        self.timeout = timeout
        self.retrieval_mode = (retrieval_mode or "hybrid").strip().lower()
        self.sub_queries = int(sub_queries) if sub_queries is not None else None
        self._last_request_time = 0.0
        self._lock = threading.Lock()

        self.api_token = api_token or os.environ.get("SCIVERSE_API_TOKEN")
        self._public_mode = bool(self.api_token)

        if self._public_mode and rate_limit <= 0:
            rate_limit = 1.0
        self.rate_limit = max(0.0, float(rate_limit))

        if self._public_mode:
            self.name = "sciverse-public-api"
            logger.info(
                "Public mode enabled: %s/%s (rate_limit=%.1fs)",
                self.base_url,
                self.public_endpoint,
                self.rate_limit,
            )

        self._session = self._init_session(max_retries, retry_backoff)

    @staticmethod
    def _init_session(max_retries: int, backoff: float) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _rate_limit_wait(self) -> None:
        if self.rate_limit <= 0:
            return
        with self._lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.rate_limit:
                time.sleep(self.rate_limit - elapsed)
            self._last_request_time = time.monotonic()

    def search(self, query: str, limit: int = 100) -> SearchResponse:
        self._rate_limit_wait()

        if self._public_mode:
            url = f"{self.base_url}/{self.public_endpoint}"
            headers: dict[str, str] = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }
            payload = self._build_public_payload(query, limit)
        else:
            url = f"{self.base_url}/{self.local_endpoint}"
            headers = {}
            payload = self._build_local_payload(query, limit)

        if self.sub_queries is not None:
            payload["sub_queries"] = self.sub_queries

        start = time.monotonic()
        try:
            resp = self._session.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )
            elapsed_ms = (time.monotonic() - start) * 1000
            if resp.status_code != 200:
                return SearchResponse(
                    query=query,
                    results=[],
                    response_time_ms=elapsed_ms,
                    status_code=resp.status_code,
                    error=f"HTTP {resp.status_code}: {resp.text[:300]}",
                )

            data = resp.json()
            results = self._parse_response(data)

            return SearchResponse(
                query=query,
                results=results,
                response_time_ms=elapsed_ms,
                status_code=200,
            )
        except Exception as e:
            elapsed_ms = (time.monotonic() - start) * 1000
            return SearchResponse(
                query=query,
                results=[],
                response_time_ms=elapsed_ms,
                status_code=0,
                error=str(e),
            )

    def _build_public_payload(self, query: str, limit: int) -> dict[str, Any]:
        return {
            "query": query,
            "top_k": int(limit),
        }

    def _build_local_payload(self, query: str, limit: int) -> dict[str, Any]:
        return {
            "query": query,
            "top_k": int(limit),
            "retrieval": self.retrieval_mode,
        }

    def _parse_response(self, data: Any) -> list[PaperResult]:
        hits = self._extract_hits(data)
        results: list[PaperResult] = []
        for rank, hit in enumerate(hits, start=1):
            if not isinstance(hit, dict):
                continue
            paper_id = self._first_str(hit, self.id_fields)
            title = self._first_str(hit, self.title_fields)
            snippet = self._first_str(hit, self.text_fields)
            score = self._parse_score(hit, rank)
            results.append(
                PaperResult(
                    paper_id=paper_id,
                    title=title,
                    abstract=snippet,
                    score=score,
                    raw=hit,
                )
            )
        return results

    @staticmethod
    def _extract_hits(data: Any) -> list[Any]:
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for key in ("hits", "results", "items", "papers", "data", "records"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        nested = data.get("data")
        if isinstance(nested, dict):
            for key in ("hits", "results", "items", "papers", "records"):
                value = nested.get(key)
                if isinstance(value, list):
                    return value
        return []

    @staticmethod
    def _first_str(hit: dict[str, Any], fields: tuple[str, ...]) -> str:
        for field in fields:
            value = hit.get(field)
            if value not in (None, ""):
                return str(value)
        return ""

    @staticmethod
    def _parse_score(hit: dict[str, Any], rank: int) -> float:
        for field in ("score", "rank_score", "relevance_score", "rerank_score"):
            value = hit.get(field)
            if value in (None, ""):
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
        return 1.0 / rank


@register_backend("meta_search")
class MetaSearchClient(AgenticSearchClient):
    """Sciverse meta-search backend.

    The public Sciverse API exposes metadata search as ``POST /meta-search``.
    This client intentionally shares auth, retry, rate-limit, and result parsing
    with ``AgenticSearchClient`` so both backends can be compared by changing
    only ``executor.retrieval.backend``.
    """

    name = "sciverse-meta-search-api"
    public_endpoint = "meta-search"
    local_endpoint = "meta-search"

    def __init__(
        self,
        *args,
        search_type: str = "paper",
        sort_by: str | None = None,
        freshness_boost: str | None = None,
        filters: list[dict[str, Any]] | dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.search_type = search_type
        self.sort_by = sort_by
        self.freshness_boost = freshness_boost
        self.filters = self._normalize_filters(filters)
        super().__init__(*args, **kwargs)
        if self._public_mode:
            self.name = "sciverse-meta-search-api"

    def _build_public_payload(self, query: str, limit: int) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "query": query,
            "filters": self.filters,
            "page": 1,
            "page_size": int(limit),
        }
        if self.sort_by:
            payload.pop("query", None)
            payload["sort"] = [{"field": self.sort_by, "order": "SORT_ORDER_DESC"}]
        if self.freshness_boost:
            payload["freshness_boost"] = self.freshness_boost
        return payload

    def _build_local_payload(self, query: str, limit: int) -> dict[str, Any]:
        return self._build_public_payload(query, limit)

    @staticmethod
    def _normalize_filters(
        filters: list[dict[str, Any]] | dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        if filters is None:
            return []
        if isinstance(filters, dict):
            filters = [filters]

        normalized: list[dict[str, Any]] = []
        for item in filters:
            if not isinstance(item, dict):
                continue
            if "field" in item and "value" in item:
                item = dict(item)
                item.setdefault("operator", MetaSearchClient._default_filter_operator(item))
                normalized.append(item)
                continue
            for field, value in item.items():
                normalized.append(MetaSearchClient._normalize_filter_shortcut(field, value))
        return normalized

    @staticmethod
    def _default_filter_operator(item: dict[str, Any]) -> str:
        value = item.get("value")
        if isinstance(value, list):
            return "FILTER_OP_IN"
        return "FILTER_OP_EQ"

    @staticmethod
    def _normalize_filter_shortcut(field: str, value: Any) -> dict[str, Any]:
        shortcuts = {
            "year": ("publication_published_year", "FILTER_OP_EQ"),
            "year_from": ("publication_published_year", "FILTER_OP_GTE"),
            "year_to": ("publication_published_year", "FILTER_OP_LTE"),
            "venue": ("publication_venue_name_unified", "FILTER_OP_EQ"),
            "venues": ("publication_venue_name_unified", "FILTER_OP_IN"),
            "doi": ("doi", "FILTER_OP_EQ"),
        }
        mapped_field, operator = shortcuts.get(
            field,
            (field, "FILTER_OP_IN" if isinstance(value, list) else "FILTER_OP_EQ"),
        )
        return {
            "field": mapped_field,
            "operator": operator,
            "value": value,
        }
