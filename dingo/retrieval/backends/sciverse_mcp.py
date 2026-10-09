"""
Sciverse MCP backend for retrieval evaluation.

Connects to the Sciverse SCP Server through the SCP Hub MCP gateway
(streamable-http transport) and evaluates its ``semantic_search`` tool
against MTEB retrieval benchmarks.

Unlike the ``agentic`` / ``meta_search`` backends (which reach Sciverse over
plain REST at ``api.sciverse.space``), this backend speaks MCP to the SCP Hub
gateway and authenticates with the ``SCP-HUB-API-KEY`` header.

The MCP client API is asynchronous, but ``SearchClient.search`` is synchronous
and called concurrently from a ThreadPoolExecutor. Each ``search`` opens its
own event loop and its own MCP connection (``asyncio.run``), so concurrent
worker threads never share a session — the safe way to parallelize a
single-in-flight streamable-http transport.

    dingo eval-retrieval \
      --backend sciverse_mcp \
      --tasks SciFact \
      --api-url https://scp.intern-ai.org.cn/api/v1/mcp/43/Sciverse \
      --api-token YOUR_SCP_HUB_API_KEY \
      --limit 100 \
      --max-queries 5 \
      -o outputs/retrieval_eval
"""

from __future__ import annotations
import asyncio
import json
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from typing import Any

from dingo.retrieval.search_client import PaperResult, SearchClient, SearchResponse, register_backend

logger = logging.getLogger(__name__)

#: Header the SCP Hub gateway authenticates with (your SCP Platform key).
_API_KEY_HEADER = "SCP-HUB-API-KEY"


@register_backend("sciverse_mcp")
class SciverseMCPClient(SearchClient):
    name = "sciverse-mcp-api"

    def __init__(
        self,
        api_url: str = "https://scp.intern-ai.org.cn/api/v1/mcp/43/Sciverse",
        api_token: str | None = None,
        timeout: float = 30.0,
        rate_limit: float = 1.0,
        **_kwargs: Any,
    ) -> None:
        self.server_url = api_url
        self.timeout = timeout
        self.api_key = api_token or os.environ.get("SCP_HUB_API_KEY")
        self.rate_limit = max(0.0, float(rate_limit))
        self._last_request_time = 0.0
        self._lock = threading.Lock()

        if not self.api_key:
            logger.warning(
                "sciverse_mcp: no api_token/SCP_HUB_API_KEY set; "
                "the SCP Hub gateway will reject requests."
            )
        logger.info(
            "SciverseMCP backend: %s (api_key=%s, rate_limit=%.1fs)",
            self.server_url,
            "set" if self.api_key else "unset",
            self.rate_limit,
        )

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

    @asynccontextmanager
    async def _open_session(self):
        """Open an MCP session over streamable-http, yielding it, then close.

        Each call establishes its own connection and event loop, so concurrent
        worker threads never share a session.
        """
        from mcp import ClientSession
        # streamablehttp_client takes headers/timeout directly; the newer
        # streamable_http_client drops them in favor of a pre-built http_client,
        # which does not fit the SCP-HUB-API-KEY header injection here.
        from mcp.client.streamable_http import streamablehttp_client

        headers = {_API_KEY_HEADER: self.api_key} if self.api_key else {}
        async with streamablehttp_client(
            url=self.server_url,
            headers=headers,
            timeout=self.timeout,
        ) as (
            read,
            write,
            _get_session_id,
        ):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session

    async def _search_async(self, query: str, limit: int) -> list[dict[str, Any]]:
        async with self._open_session() as session:
            result = await session.call_tool(
                "semantic_search",
                arguments={"query": query, "top_k": int(limit)},
            )
        return self._extract_hits_from_result(result)

    def search(self, query: str, limit: int = 100) -> SearchResponse:
        self._rate_limit_wait()
        start = time.monotonic()
        try:
            hits = asyncio.run(self._search_async(query, limit))
            elapsed_ms = (time.monotonic() - start) * 1000
            return SearchResponse(
                query=query,
                results=self._parse_hits(hits),
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
    def _result_text(result: Any) -> str:
        """Concatenate the text content blocks of an MCP tool result."""
        if isinstance(result, dict):
            content_list = result.get("content") or []
        else:
            content_list = getattr(result, "content", []) or []
        texts: list[str] = []
        for item in content_list:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text") or "")
            elif getattr(item, "type", None) == "text":
                texts.append(getattr(item, "text", "") or "")
        return "".join(texts)

    @classmethod
    def _extract_hits_from_result(cls, result: Any) -> list[dict[str, Any]]:
        """Extract the ``hits`` array from a ``semantic_search`` tool result."""
        text = cls._result_text(result)
        if not text:
            return []
        try:
            payload = json.loads(text)
        except (ValueError, TypeError):
            logger.warning("sciverse_mcp: semantic_search returned non-JSON text")
            return []
        if not isinstance(payload, dict):
            return []
        hits = payload.get("hits")
        return hits if isinstance(hits, list) else []

    @staticmethod
    def _parse_hits(hits: list[dict[str, Any]]) -> list[PaperResult]:
        """Map ``semantic_search`` hits to PaperResult, one per paper.

        A paper contributes up to ~3 chunks; retrieval metrics rank papers,
        not chunks. Keep the first (highest-ranked) chunk of each doc_id and
        drop hits with no doc_id — they cannot be scored against qrels.
        """
        results: list[PaperResult] = []
        seen: set[str] = set()
        for hit in hits:
            if not isinstance(hit, dict):
                continue
            doc_id = str(hit.get("doc_id") or "")
            if not doc_id or doc_id in seen:
                continue
            seen.add(doc_id)
            results.append(
                PaperResult(
                    paper_id=doc_id,
                    title=str(hit.get("title") or ""),
                    abstract=str(hit.get("chunk") or ""),
                    score=float(hit.get("score") or 0.0),
                    raw=hit,
                )
            )
        return results
