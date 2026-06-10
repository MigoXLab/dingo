"""
OpenAlex backend for retrieval evaluation.

Uses the OpenAlex Works API:
  GET {api_url}/works?search.semantic=...&per_page=...
  GET {api_url}/works?search=...&per_page=...

Regular search is the default so retrieval evaluation can request top 100
results consistently. Use --search-type semantic to enable OpenAlex semantic
search. Semantic search is limited to 50 results and 1 request/second, so this
backend caps semantic requests at 50 results and defaults to a 1 second rate
limit when semantic mode is selected.

dingo eval-retrieval \
  --backend openalex \
  --tasks SciFact \
  --api-url https://api.openalex.org \
  --api-token YOUR_OPENALEX_API_KEY \
  --limit 100 \
  -o outputs/retrieval_eval

Use --search-type semantic for semantic search:

dingo eval-retrieval \
  --backend openalex \
  --tasks SciFact \
  --api-token YOUR_OPENALEX_API_KEY \
  --limit 50 \
  --search-type semantic \
  --rate-limit 1.0 \
  -o outputs/retrieval_eval

You can also set OPENALEX_API_KEY.
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

_DEFAULT_SELECT = (
    "id,doi,display_name,title,abstract_inverted_index,publication_year,"
    "relevance_score,cited_by_count"
)


@register_backend("openalex")
class OpenAlexClient(SearchClient):
    name = "openalex-api"

    def __init__(
        self,
        api_url: str = "https://api.openalex.org",
        api_token: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        rate_limit: float = 0.0,
        search_type: str = "search",
        **_kwargs: Any,
    ) -> None:
        self.base_url = api_url.rstrip("/")
        self.api_key = api_token or os.environ.get("OPENALEX_API_KEY")
        self.timeout = timeout
        self.search_type = (search_type or "search").strip().lower()
        if self.search_type not in {"semantic", "search"}:
            self.search_type = "search"
        if self.search_type == "semantic" and rate_limit <= 0:
            rate_limit = 1.0
        self.rate_limit = max(0.0, float(rate_limit))
        self._last_request_time = 0.0
        self._lock = threading.Lock()
        self._session = self._init_session(max_retries, retry_backoff)

        logger.info(
            "OpenAlex backend: %s (api_key=%s, search_type=%s, rate_limit=%.1fs)",
            self.base_url,
            "set" if self.api_key else "unset",
            self.search_type,
            self.rate_limit,
        )

    @staticmethod
    def _init_session(max_retries: int, backoff: float) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=backoff,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _rate_limit_wait(self) -> None:
        if self.rate_limit <= 0:
            return
        sleep_time = 0.0
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            if elapsed < self.rate_limit:
                sleep_time = self.rate_limit - elapsed
            self._last_request_time = now + sleep_time
        if sleep_time > 0:
            time.sleep(sleep_time)

    def _build_params(self, query: str, limit: int) -> dict[str, Any]:
        target = max(0, int(limit))
        if self.search_type == "semantic":
            target = min(target, 50)
            search_param = "search.semantic"
        else:
            target = min(target, 100)
            search_param = "search"

        params: dict[str, Any] = {
            search_param: query,
            "per_page": target,
            "select": _DEFAULT_SELECT,
        }
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def search(self, query: str, limit: int = 100) -> SearchResponse:
        self._rate_limit_wait()
        params = self._build_params(query, limit)
        start = time.monotonic()
        try:
            resp = self._session.get(
                f"{self.base_url}/works",
                params=params,
                timeout=self.timeout,
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
            results = [
                self._parse_result(item, rank)
                for rank, item in enumerate(data.get("results") or [], start=1)
                if isinstance(item, dict)
            ]
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

    @staticmethod
    def _parse_result(item: dict[str, Any], rank: int) -> PaperResult:
        return PaperResult(
            paper_id=str(item.get("id") or item.get("doi") or ""),
            title=str(item.get("display_name") or item.get("title") or ""),
            abstract=OpenAlexClient._abstract_from_inverted_index(
                item.get("abstract_inverted_index")
            ),
            score=OpenAlexClient._parse_score(item, rank),
            year=OpenAlexClient._parse_year(item.get("publication_year")),
            raw=item,
        )

    @staticmethod
    def _parse_score(item: dict[str, Any], rank: int) -> float:
        value = item.get("relevance_score")
        try:
            return float(value)
        except (TypeError, ValueError):
            return 1.0 / rank

    @staticmethod
    def _parse_year(value: Any) -> int | None:
        try:
            year = int(value)
        except (TypeError, ValueError):
            return None
        return year if 1000 <= year <= 3000 else None

    @staticmethod
    def _abstract_from_inverted_index(value: Any) -> str:
        if not isinstance(value, dict):
            return ""
        positions: dict[int, str] = {}
        for word, indexes in value.items():
            if not isinstance(indexes, list):
                continue
            for index in indexes:
                try:
                    positions[int(index)] = str(word)
                except (TypeError, ValueError):
                    continue
        if not positions:
            return ""
        return " ".join(positions[index] for index in sorted(positions))
