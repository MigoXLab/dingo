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
        assert "meta_search" in backends
        assert "openalex" in backends

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

    def test_create_meta_search_client(self):
        client = create_client(
            "meta_search",
            api_url="https://api.sciverse.space",
            api_token="test-token",
            timeout=5.0,
            rate_limit=0,
            freshness_boost="MILD",
            filters={"year_from": 2020},
        )
        assert client.name == "sciverse-meta-search-api"
        payload = client._build_public_payload("test query", 10)
        assert payload["query"] == "test query"
        assert "limit" not in payload
        assert "top_k" not in payload
        assert "type" not in payload
        assert payload["page"] == 1
        assert payload["page_size"] == 10
        assert payload["freshness_boost"] == "MILD"
        assert payload["filters"] == [
            {
                "field": "publication_published_year",
                "operator": "FILTER_OP_GTE",
                "value": 2020,
            }
        ]

    def test_create_openalex_client_defaults_to_search(self):
        client = create_client(
            "openalex",
            api_url="https://api.openalex.org",
            api_token="test-token",
            timeout=5.0,
            rate_limit=0,
        )
        assert client.name == "openalex-api"
        params = client._build_params("test query", 100)
        assert params["search"] == "test query"
        assert "search.semantic" not in params
        assert params["per_page"] == 100
        assert params["api_key"] == "test-token"

    def test_create_openalex_client_semantic_search(self):
        client = create_client(
            "openalex",
            search_type="semantic",
            api_token="test-token",
            rate_limit=0,
        )
        params = client._build_params("test query", 100)
        assert params["search.semantic"] == "test query"
        assert "search" not in params
        assert params["per_page"] == 50
        assert client.rate_limit == 1.0

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


class TestOpenAlexClient:
    def test_abstract_from_inverted_index(self):
        from dingo.retrieval.backends.openalex import OpenAlexClient

        abstract = OpenAlexClient._abstract_from_inverted_index(
            {"hello": [0], "world": [1], "again": [2]}
        )

        assert abstract == "hello world again"

    def test_parse_openalex_result(self):
        from dingo.retrieval.backends.openalex import OpenAlexClient

        result = OpenAlexClient._parse_result(
            {
                "id": "https://openalex.org/W123",
                "display_name": "A Test Work",
                "abstract_inverted_index": {"test": [0], "abstract": [1]},
                "publication_year": 2024,
                "relevance_score": 12.5,
            },
            rank=3,
        )

        assert result.paper_id == "https://openalex.org/W123"
        assert result.title == "A Test Work"
        assert result.abstract == "test abstract"
        assert result.year == 2024
        assert result.score == 12.5
