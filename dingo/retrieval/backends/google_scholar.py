"""
Google Scholar backend for retrieval evaluation.

Google Scholar does not provide an official public API. This backend uses the
SerpAPI Google Scholar endpoint:
  GET {api_url}?engine=google_scholar&q=...&api_key=...

dingo eval-retrieval \
  --backend google_scholar \
  --tasks SciFact \
  --api-url https://serpapi.com/search.json \
  --api-token YOUR_SERPAPI_KEY \
  --limit 100 \
  --max-queries 5 \
  --rate-limit 1.0 \
  -o outputs/retrieval_eval

You can also set SERPAPI_API_KEY or GOOGLE_SCHOLAR_API_KEY.
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

_DEFAULT_PAGE_SIZE = 20


@register_backend("google_scholar")
class GoogleScholarClient(SearchClient):
    name = "google-scholar-serpapi"

    def __init__(
        self,
        api_url: str = "https://serpapi.com/search.json",
        api_token: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        rate_limit: float = 1.0,
        **_kwargs: Any,
    ) -> None:
        self.base_url = api_url.rstrip("/")
        self.timeout = timeout
        self.api_key = (
            api_token
            or os.environ.get("SERPAPI_API_KEY")
            or os.environ.get("GOOGLE_SCHOLAR_API_KEY")
        )
        self.rate_limit = max(0.0, float(rate_limit))
        self._last_request_time = 0.0
        self._lock = threading.Lock()
        self._session = self._init_session(max_retries, retry_backoff)

        logger.info(
            "GoogleScholar backend: %s (api_key=%s, rate_limit=%.1fs)",
            self.base_url,
            "set" if self.api_key else "unset",
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

    def search(self, query: str, limit: int = 100) -> SearchResponse:
        if not self.api_key:
            return SearchResponse(
                query=query,
                results=[],
                response_time_ms=0.0,
                status_code=0,
                error=(
                    "Google Scholar backend requires api_token, SERPAPI_API_KEY, "
                    "or GOOGLE_SCHOLAR_API_KEY"
                ),
            )

        target = max(0, int(limit))
        results: list[PaperResult] = []
        status_code = 200
        start_time = time.monotonic()

        try:
            for start in range(0, target, _DEFAULT_PAGE_SIZE):
                self._rate_limit_wait()
                page_size = min(_DEFAULT_PAGE_SIZE, target - start)
                params = {
                    "engine": "google_scholar",
                    "q": query,
                    "api_key": self.api_key,
                    "num": page_size,
                    "start": start,
                }
                resp = self._session.get(
                    self.base_url,
                    params=params,
                    timeout=self.timeout,
                )
                status_code = resp.status_code
                elapsed_ms = (time.monotonic() - start_time) * 1000
                if resp.status_code != 200:
                    return SearchResponse(
                        query=query,
                        results=results,
                        response_time_ms=elapsed_ms,
                        status_code=resp.status_code,
                        error=f"HTTP {resp.status_code}: {resp.text[:300]}",
                    )

                data = resp.json()
                if data.get("error"):
                    return SearchResponse(
                        query=query,
                        results=results,
                        response_time_ms=elapsed_ms,
                        status_code=resp.status_code,
                        error=str(data["error"]),
                    )

                organic_results = data.get("organic_results") or []
                if not organic_results:
                    break

                for item in organic_results:
                    if not isinstance(item, dict):
                        continue
                    rank = len(results) + 1
                    results.append(self._parse_result(item, rank))
                    if len(results) >= target:
                        break

                if len(organic_results) < page_size or len(results) >= target:
                    break

            elapsed_ms = (time.monotonic() - start_time) * 1000
            return SearchResponse(
                query=query,
                results=results,
                response_time_ms=elapsed_ms,
                status_code=status_code,
            )
        except Exception as e:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            return SearchResponse(
                query=query,
                results=results,
                response_time_ms=elapsed_ms,
                status_code=0,
                error=str(e),
            )

    @staticmethod
    def _parse_result(item: dict[str, Any], rank: int) -> PaperResult:
        publication_info = item.get("publication_info") or {}
        authors = GoogleScholarClient._parse_authors(publication_info)
        year = GoogleScholarClient._parse_year(publication_info.get("summary", ""))
        paper_id = str(
            item.get("result_id")
            or item.get("cluster_id")
            or item.get("link")
            or item.get("title")
            or ""
        )
        return PaperResult(
            paper_id=paper_id,
            title=str(item.get("title") or ""),
            abstract=str(item.get("snippet") or ""),
            score=1.0 / rank,
            authors=authors,
            year=year,
            raw=item,
        )

    @staticmethod
    def _parse_authors(publication_info: dict[str, Any]) -> list[str]:
        authors = publication_info.get("authors") or []
        if isinstance(authors, list) and authors:
            return [
                str(author.get("name") or "")
                for author in authors
                if isinstance(author, dict) and author.get("name")
            ]

        summary = str(publication_info.get("summary") or "")
        if not summary:
            return []
        author_part = summary.split(" - ", 1)[0]
        return [name.strip() for name in author_part.split(",") if name.strip()]

    @staticmethod
    def _parse_year(text: str) -> int | None:
        for token in str(text).replace(",", " ").split():
            if token.isdigit() and len(token) == 4:
                year = int(token)
                if 1000 <= year <= 3000:
                    return year
        return None
