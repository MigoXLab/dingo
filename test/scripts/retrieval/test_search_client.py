"""Unit tests for dingo.retrieval.search_client"""

import pytest

from dingo.retrieval.search_client import PaperResult, SearchClient, SearchResponse, create_client, list_backends, register_backend


class TestPaperResult:
    def test_creation(self):
        p = PaperResult(paper_id="123", title="Test Paper", score=0.95)
        assert p.paper_id == "123"
        assert p.title == "Test Paper"
        assert p.score == 0.95
        assert p.abstract == ""
        assert p.authors == []


class TestSearchResponse:
    def test_creation(self):
        r = SearchResponse(
            query="test query",
            results=[PaperResult(paper_id="1", title="Paper 1")],
            response_time_ms=150.0,
            status_code=200,
        )
        assert r.query == "test query"
        assert len(r.results) == 1
        assert r.error is None

    def test_with_error(self):
        r = SearchResponse(
            query="test",
            results=[],
            response_time_ms=0.0,
            status_code=500,
            error="Internal error",
        )
        assert r.error == "Internal error"


class TestBackendRegistry:
    def test_list_backends_includes_agentic(self):
        backends = list_backends()
        assert "agentic" in backends

    def test_create_unknown_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            create_client("nonexistent_backend")

    def test_create_agentic_client(self):
        client = create_client(
            "agentic",
            api_url="http://localhost:8080",
            timeout=5.0,
        )
        assert client.name in ("agentic-search-api", "sciverse-public-api")

    def test_register_custom_backend(self):
        @register_backend("test_custom")
        class TestCustomClient(SearchClient):
            name = "test-custom"

            def search(self, query: str, limit: int = 100) -> SearchResponse:
                return SearchResponse(
                    query=query,
                    results=[],
                    response_time_ms=0.0,
                    status_code=200,
                )

        client = create_client("test_custom")
        assert client.name == "test-custom"
        resp = client.search("hello")
        assert resp.status_code == 200
