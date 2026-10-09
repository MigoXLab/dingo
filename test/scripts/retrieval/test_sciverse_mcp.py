"""Unit tests for dingo.retrieval.backends.sciverse_mcp"""

import pytest

from dingo.retrieval.backends.sciverse_mcp import SciverseMCPClient


class TestParseHits:
    def test_maps_semantic_search_fields(self):
        hits = [
            {
                "chunk_id": "c1",
                "doc_id": "d-aaa",
                "chunk": "attention is all you need",
                "score": 0.91,
                "title": "Transformer",
                "abstract": "abstract text",
                "offset": 128,
            }
        ]

        results = SciverseMCPClient._parse_hits(hits)

        assert len(results) == 1
        r = results[0]
        assert r.paper_id == "d-aaa"
        assert r.title == "Transformer"
        assert r.abstract == "attention is all you need"
        assert r.score == 0.91
        assert r.raw == hits[0]

    def test_dedups_chunks_of_same_paper_keeping_best_rank(self):
        # semantic_search returns up to ~3 chunks per paper; retrieval metrics
        # need one entry per paper, ranked. Keep the first (best) chunk's rank.
        hits = [
            {"doc_id": "d-aaa", "chunk": "chunk 1", "score": 0.9},
            {"doc_id": "d-bbb", "chunk": "other paper", "score": 0.8},
            {"doc_id": "d-aaa", "chunk": "chunk 2 same paper", "score": 0.7},
        ]

        results = SciverseMCPClient._parse_hits(hits)

        assert [r.paper_id for r in results] == ["d-aaa", "d-bbb"]
        assert results[0].abstract == "chunk 1"

    def test_skips_hits_without_doc_id(self):
        hits = [
            {"doc_id": "", "chunk": "no id", "score": 0.9},
            {"doc_id": "d-ok", "chunk": "has id", "score": 0.8},
        ]

        results = SciverseMCPClient._parse_hits(hits)

        assert [r.paper_id for r in results] == ["d-ok"]


class TestExtractHitsFromResult:
    def test_parses_hits_from_text_content_block(self):
        # MCP tool results carry the JSON payload inside text content blocks.
        class _Block:
            type = "text"
            text = '{"hits": [{"doc_id": "d1", "chunk": "x", "score": 0.5}]}'

        class _Result:
            content = [_Block()]

        hits = SciverseMCPClient._extract_hits_from_result(_Result())

        assert hits == [{"doc_id": "d1", "chunk": "x", "score": 0.5}]

    def test_returns_empty_when_no_hits_key(self):
        class _Block:
            type = "text"
            text = '{"results": []}'

        class _Result:
            content = [_Block()]

        assert SciverseMCPClient._extract_hits_from_result(_Result()) == []

    def test_returns_empty_on_non_json_text(self):
        class _Block:
            type = "text"
            text = "not json at all"

        class _Result:
            content = [_Block()]

        assert SciverseMCPClient._extract_hits_from_result(_Result()) == []


class _FakeBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeResult:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]


class _FakeSession:
    """Records call_tool invocations and returns a canned result."""

    def __init__(self, result_text):
        self._result_text = result_text
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return _FakeResult(self._result_text)


def _fake_open_session(session):
    """Build a factory returning an async context manager yielding *session*."""
    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc):
            return False

    def _factory():
        return _Ctx()

    return _factory


class TestSearch:
    def _client_with_session(self, session):
        client = SciverseMCPClient(
            api_url="https://scp.example/mcp",
            api_token="k",
            rate_limit=0,
        )
        # Inject the fake session, bypassing the real MCP connection.
        client._open_session = _fake_open_session(session)
        return client

    def test_search_calls_semantic_search_and_returns_results(self):
        session = _FakeSession(
            '{"hits": ['
            '{"doc_id": "d1", "chunk": "a", "score": 0.9, "title": "T1"},'
            '{"doc_id": "d1", "chunk": "dup", "score": 0.5},'
            '{"doc_id": "d2", "chunk": "b", "score": 0.4, "title": "T2"}'
            ']}'
        )
        client = self._client_with_session(session)

        resp = client.search("how does attention work?", limit=25)

        assert resp.status_code == 200
        assert resp.error is None
        assert session.calls == [
            ("semantic_search", {"query": "how does attention work?", "top_k": 25})
        ]
        assert [r.paper_id for r in resp.results] == ["d1", "d2"]

    def test_search_reports_connection_error(self):
        client = SciverseMCPClient(
            api_url="https://scp.example/mcp", api_token="k", rate_limit=0
        )

        def _boom(*_a, **_k):
            raise RuntimeError("connect failed")

        client._open_session = _boom

        resp = client.search("q")

        assert resp.status_code == 0
        assert resp.results == []
        assert "connect failed" in resp.error


class TestSearchIntegration:
    """Exercises the real MCP client path (no network reachable)."""

    def test_unreachable_server_degrades_to_error_response(self):
        pytest.importorskip("mcp")
        client = SciverseMCPClient(
            api_url="http://127.0.0.1:1/does-not-exist",
            api_token="k",
            timeout=2.0,
            rate_limit=0,
        )

        resp = client.search("q", limit=3)

        # A dead endpoint must surface as an error response, never raise.
        assert resp.status_code == 0
        assert resp.results == []
        assert resp.error
