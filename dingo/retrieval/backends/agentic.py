"""
agentic-search backend for retrieval evaluation.

Supports two modes:

  Local (default):
    POST {api_url}/v1/search  -- direct connection to the Go service, no auth.

  Public (when api_token is set):
    POST {api_url}/agentic-search  -- SciVerse public gateway with Bearer auth.
    Rate limit defaults to 1 RPS.
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
                "Public mode enabled: %s/agentic-search (rate_limit=%.1fs)",
                self.base_url,
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
            url = f"{self.base_url}/agentic-search"
            headers: dict[str, str] = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json",
            }
            payload: dict[str, Any] = {
                "query": query,
                "top_k": int(limit),
            }
        else:
            url = f"{self.base_url}/v1/search"
            headers = {}
            payload = {
                "query": query,
                "top_k": int(limit),
                "retrieval": self.retrieval_mode,
            }

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
            hits = data.get("hits") or []
            results: list[PaperResult] = []
            for hit in hits:
                if not isinstance(hit, dict):
                    continue
                doc_id = str(hit.get("doc_id") or "")
                title = str(hit.get("title") or "")
                snippet = str(hit.get("snippet") or hit.get("chunk") or "")
                score = float(hit.get("score", 0) or 0)
                results.append(
                    PaperResult(
                        paper_id=doc_id,
                        title=title,
                        abstract=snippet,
                        score=score,
                        raw=hit,
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
