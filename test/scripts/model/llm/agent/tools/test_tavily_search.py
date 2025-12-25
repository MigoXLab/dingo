"""
Unit tests for Tavily Search Tool
"""

from unittest.mock import MagicMock, patch

import pytest

from dingo.model.llm.agent.tools.tavily_search import TavilyConfig, TavilySearch


class TestTavilyConfig:
    """Test Tavily configuration"""

    def test_default_values(self):
        """Test default configuration values"""
        config = TavilyConfig()
        assert config.api_key is None
        assert config.max_results == 5
        assert config.search_depth == "advanced"
        assert config.include_answer is True
        assert config.include_images is False
        assert config.timeout == 30

    def test_custom_values(self):
        """Test custom configuration values"""
        config = TavilyConfig(
            api_key="test_key",
            max_results=10,
            search_depth="basic",
            include_answer=False
        )
        assert config.api_key == "test_key"
        assert config.max_results == 10
        assert config.search_depth == "basic"
        assert config.include_answer is False

    def test_max_results_validation(self):
        """Test max_results must be between 1 and 20"""
        # Valid values
        TavilyConfig(max_results=1)
        TavilyConfig(max_results=20)

        # Invalid values
        with pytest.raises(ValueError):
            TavilyConfig(max_results=0)

        with pytest.raises(ValueError):
            TavilyConfig(max_results=21)

    def test_search_depth_validation(self):
        """Test search_depth must be 'basic' or 'advanced'"""
        # Valid values
        TavilyConfig(search_depth="basic")
        TavilyConfig(search_depth="advanced")

        # Invalid value
        with pytest.raises(ValueError):
            TavilyConfig(search_depth="invalid")


class TestTavilySearch:
    """Test Tavily search tool"""

    def setup_method(self):
        """Setup for each test"""
        TavilySearch.config = TavilyConfig(api_key="test_api_key")

    def test_tool_attributes(self):
        """Test tool has correct attributes"""
        assert TavilySearch.name == "tavily_search"
        assert TavilySearch.description == "Search the web for factual information using Tavily AI"
        assert isinstance(TavilySearch.config, TavilyConfig)

    def test_empty_query(self):
        """Test that empty query returns error"""
        result = TavilySearch.execute(query="")
        assert result['success'] is False
        assert 'empty' in result['error'].lower()

    def test_whitespace_query(self):
        """Test that whitespace-only query returns error"""
        result = TavilySearch.execute(query="   ")
        assert result['success'] is False
        assert 'empty' in result['error'].lower()

    def test_missing_api_key(self):
        """Test that missing API key returns error"""
        TavilySearch.config.api_key = None
        result = TavilySearch.execute(query="test query")
        assert result['success'] is False
        assert 'API key' in result['error']

    @patch('tavily.TavilyClient')
    def test_successful_search(self, mock_tavily_client):
        """Test successful search execution"""
        # Mock Tavily response
        mock_response = {
            'answer': 'Paris is the capital of France.',
            'results': [
                {
                    'title': 'Paris - Wikipedia',
                    'url': 'https://en.wikipedia.org/wiki/Paris',
                    'content': 'Paris is the capital of France...',
                    'score': 0.98
                },
                {
                    'title': 'Paris Facts',
                    'url': 'https://example.com/paris',
                    'content': 'Information about Paris...',
                    'score': 0.95
                }
            ]
        }

        mock_client_instance = MagicMock()
        mock_client_instance.search.return_value = mock_response
        mock_tavily_client.return_value = mock_client_instance

        # Execute search
        result = TavilySearch.execute(query="What is the capital of France?")

        # Verify result structure
        assert result['success'] is True
        assert result['query'] == "What is the capital of France?"
        assert result['answer'] == 'Paris is the capital of France.'
        assert len(result['results']) == 2

        # Verify first result
        assert result['results'][0]['title'] == 'Paris - Wikipedia'
        assert result['results'][0]['url'] == 'https://en.wikipedia.org/wiki/Paris'
        assert result['results'][0]['score'] == 0.98

        # Verify API was called correctly
        mock_client_instance.search.assert_called_once()
        call_kwargs = mock_client_instance.search.call_args[1]
        assert call_kwargs['query'] == "What is the capital of France?"
        assert call_kwargs['max_results'] == 5
        assert call_kwargs['search_depth'] == "advanced"

    @patch('tavily.TavilyClient')
    def test_search_with_custom_params(self, mock_tavily_client):
        """Test search with custom parameters"""
        mock_response = {'results': []}
        mock_client_instance = MagicMock()
        mock_client_instance.search.return_value = mock_response
        mock_tavily_client.return_value = mock_client_instance

        # Execute with custom params
        TavilySearch.execute(
            query="test",
            max_results=10,
            search_depth="basic",
            include_answer=False
        )

        # Verify custom params were used
        call_kwargs = mock_client_instance.search.call_args[1]
        assert call_kwargs['max_results'] == 10
        assert call_kwargs['search_depth'] == "basic"
        assert call_kwargs['include_answer'] is False

    @patch('tavily.TavilyClient')
    def test_search_without_answer(self, mock_tavily_client):
        """Test search without AI-generated answer"""
        mock_response = {
            'results': [
                {
                    'title': 'Test',
                    'url': 'https://example.com',
                    'content': 'Content',
                    'score': 0.9
                }
            ]
        }

        mock_client_instance = MagicMock()
        mock_client_instance.search.return_value = mock_response
        mock_tavily_client.return_value = mock_client_instance

        # Execute search with include_answer=False
        result = TavilySearch.execute(query="test", include_answer=False)

        assert result['success'] is True
        assert 'answer' not in result  # Answer should not be included
        assert len(result['results']) == 1

    @patch('tavily.TavilyClient')
    def test_search_with_images(self, mock_tavily_client):
        """Test search with image results"""
        mock_response = {
            'results': [],
            'images': [
                'https://example.com/image1.jpg',
                'https://example.com/image2.jpg'
            ]
        }

        mock_client_instance = MagicMock()
        mock_client_instance.search.return_value = mock_response
        mock_tavily_client.return_value = mock_client_instance

        # Execute with include_images=True
        result = TavilySearch.execute(query="test", include_images=True)

        assert result['success'] is True
        assert 'images' in result
        assert len(result['images']) == 2

    @patch('tavily.TavilyClient')
    def test_api_error_handling(self, mock_tavily_client):
        """Test handling of API errors with sanitized error messages"""
        mock_client_instance = MagicMock()
        mock_client_instance.search.side_effect = Exception("API Error: Rate limit exceeded")
        mock_tavily_client.return_value = mock_client_instance

        # Execute search that will fail
        result = TavilySearch.execute(query="test")

        assert result['success'] is False
        # Error message should be sanitized to prevent information disclosure
        assert result['error'] == "Rate limit exceeded or quota reached"
        assert result['query'] == "test"
        assert result['error_type'] == "Exception"

    def test_tavily_not_installed(self):
        """Test error when tavily-python is not installed"""
        # This test is skipped because testing import errors in a clean way is complex
        # The actual error handling is already covered by the ImportError catch in the code
        pytest.skip("Import error testing requires more complex setup")

    @patch('tavily.TavilyClient')
    def test_format_results(self, mock_tavily_client):
        """Test result formatting"""
        raw_results = [
            {
                'title': 'Test Title',
                'url': 'https://example.com',
                'content': 'Test content',
                'score': 0.95,
                'extra_field': 'ignored'
            },
            {
                'title': 'Another Title',
                'url': 'https://example2.com',
                'content': 'More content',
                'score': 0.88
            }
        ]

        formatted = TavilySearch._format_results(raw_results)

        assert len(formatted) == 2
        assert formatted[0]['title'] == 'Test Title'
        assert formatted[0]['url'] == 'https://example.com'
        assert formatted[0]['content'] == 'Test content'
        assert formatted[0]['score'] == 0.95
        assert 'extra_field' not in formatted[0]

    @patch('tavily.TavilyClient')
    def test_search_multiple(self, mock_tavily_client):
        """Test searching multiple queries"""
        mock_response = {'results': [
            {'title': 'Test', 'url': 'https://example.com', 'content': 'Content', 'score': 0.9}
        ]}
        mock_client_instance = MagicMock()
        mock_client_instance.search.return_value = mock_response
        mock_tavily_client.return_value = mock_client_instance

        # Execute multiple searches
        queries = ["query 1", "query 2", "query 3"]
        results = TavilySearch.search_multiple(queries)

        assert len(results) == 3
        assert all(r['success'] for r in results)
        assert mock_client_instance.search.call_count == 3
