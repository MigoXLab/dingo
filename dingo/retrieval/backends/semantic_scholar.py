"""
Semantic Scholar backend for retrieval evaluation.

Uses the S2 Academic Graph API:
  GET {api_url}/graph/v1/paper/search?query=...&limit=...&fields=...

Authentication is optional — set S2_API_KEY env var or pass api_token
to increase rate limits.

dingo eval-retrieval \
  --backend semantic_scholar \
  --tasks SciFact \
  --api-url https://api.semanticscholar.org \
  --api-token YOUR_S2_API_KEY \
  --limit 100 \
  --max-queries 5 \
  -o outputs/retrieval_eval

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

_DEFAULT_FIELDS = "paperId,title,abstract,authors,year,citationCount"


@register_backend("semantic_scholar")
class SemanticScholarClient(SearchClient):
    name = "semantic-scholar-api"

    def __init__(
        self,
        api_url: str = "https://api.semanticscholar.org",
        api_token: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff: float = 1.0,
        rate_limit: float = 1.0,
        **_kwargs: Any,
    ) -> None:
        self.base_url = api_url.rstrip("/")
        self.timeout = timeout
        self._last_request_time = 0.0
        self._lock = threading.Lock()

        self.api_key = api_token or os.environ.get("S2_API_KEY")
        self.rate_limit = max(0.0, float(rate_limit))

        self._session = self._init_session(max_retries, retry_backoff)

        logger.info(
            "SemanticScholar backend: %s (api_key=%s, rate_limit=%.1fs)",
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
        self._rate_limit_wait()

        limit = min(limit, 100)
        url = f"{self.base_url}/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": limit,
            "fields": _DEFAULT_FIELDS,
        }
        headers: dict[str, str] = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        start = time.monotonic()
        try:
            resp = self._session.get(
                url, params=params, headers=headers, timeout=self.timeout
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
            papers = data.get("data") or []
            total = data.get("total", len(papers))

            results: list[PaperResult] = []
            for i, paper in enumerate(papers):
                if not isinstance(paper, dict):
                    continue
                paper_id = paper.get("paperId") or ""
                title = paper.get("title") or ""
                abstract = paper.get("abstract") or ""
                authors_raw = paper.get("authors") or []
                authors = [
                    a.get("name", "") for a in authors_raw if isinstance(a, dict)
                ]
                year = paper.get("year")
                score = 1.0 - (i / max(total, 1))
                results.append(
                    PaperResult(
                        paper_id=paper_id,
                        title=title,
                        abstract=abstract,
                        score=score,
                        authors=authors,
                        year=year,
                        raw=paper,
                    )
                )

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
