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
        assert "google_scholar" in backends

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

    def test_create_google_scholar_client(self):
        client = create_client(
            "google_scholar",
            api_url="https://serpapi.com/search.json",
            api_token="test-token",
            timeout=5.0,
            rate_limit=0,
        )
        assert client.name == "google-scholar-serpapi"

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


class TestGoogleScholarClient:
    def test_parse_serpapi_result(self):
        from dingo.retrieval.backends.google_scholar import GoogleScholarClient

        item = {
            "result_id": "abc123",
            "title": "A Test Paper",
            "snippet": "This is the abstract.",
            "publication_info": {
                "summary": "A Author, B Author - Journal, 2024",
                "authors": [{"name": "A Author"}, {"name": "B Author"}],
            },
        }

        result = GoogleScholarClient._parse_result(item, rank=2)

        assert result.paper_id == "abc123"
        assert result.title == "A Test Paper"
        assert result.abstract == "This is the abstract."
        assert result.score == 0.5
        assert result.authors == ["A Author", "B Author"]
        assert result.year == 2024
