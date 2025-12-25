"""
Tavily Web Search Tool

This module provides integration with Tavily AI's search API for web-based fact verification
and information gathering. Tavily provides AI-optimized search specifically designed for LLMs
and AI agents.

Dependencies:
    tavily-python>=0.3.0

Configuration:
    api_key: Tavily API key (required)
    max_results: Maximum number of search results (default: 5)
    search_depth: "basic" or "advanced" (default: "advanced")
    include_answer: Whether to include AI-generated answer (default: True)
    include_images: Whether to include images in results (default: False)
    include_raw_content: Include full page content (default: False)
"""

from typing import Any, Dict, List, Optional

from pydantic import Field

from dingo.model.llm.agent.tools.base_tool import BaseTool, ToolConfig
from dingo.model.llm.agent.tools.tool_registry import tool_register
from dingo.utils import log


class TavilyConfig(ToolConfig):
    """Configuration for Tavily search tool"""
    api_key: Optional[str] = None
    max_results: int = Field(default=5, ge=1, le=20)
    search_depth: str = Field(default="advanced", pattern="^(basic|advanced)$")
    include_answer: bool = True
    include_images: bool = False
    include_raw_content: bool = False
    timeout: int = 30


@tool_register
class TavilySearch(BaseTool):
    """
    Tavily web search tool for fact verification and information gathering.

    Provides AI-optimized web search capabilities specifically designed for LLM agents.
    Returns search results with optional AI-generated answers, images, and full content.

    Features:
    - AI-optimized search results
    - Automatic fact verification
    - Support for both basic and advanced search modes
    - Optional AI-generated answers
    - Configurable result count and content depth

    Usage:
        result = TavilySearch.execute(query="What is the capital of France?")

        # Result structure:
        {
            'success': True,
            'query': 'What is the capital of France?',
            'answer': 'Paris is the capital of France.',
            'results': [
                {
                    'title': 'Paris - Wikipedia',
                    'url': 'https://en.wikipedia.org/wiki/Paris',
                    'content': 'Paris is the capital and most populous city of France...',
                    'score': 0.98
                },
                ...
            ]
        }
    """

    name = "tavily_search"
    description = "Search the web for factual information using Tavily AI"
    config: TavilyConfig = TavilyConfig()

    @classmethod
    def execute(cls, query: str, **kwargs) -> Dict[str, Any]:
        """
        Execute web search using Tavily API.

        Args:
            query: Search query string
            **kwargs: Optional overrides for configuration
                - max_results: Override max_results config
                - search_depth: Override search_depth config
                - include_answer: Override include_answer config
                - include_images: Override include_images config

        Returns:
            Dict with search results:
            {
                'success': bool,
                'query': str,
                'answer': str (if include_answer=True),
                'results': List[Dict],
                'images': List[str] (if include_images=True)
            }

        Raises:
            ImportError: If tavily-python is not installed
            ValueError: If API key is missing or query is empty
            Exception: For API errors
        """
        # Validate inputs
        if not query or not query.strip():
            log.error("Tavily search query cannot be empty")
            return {
                'success': False,
                'error': 'Search query cannot be empty',
                'query': query
            }

        # Validate configuration
        try:
            cls.validate_config()
        except ValueError as e:
            log.error(f"Tavily configuration error: {e}")
            return {
                'success': False,
                'error': str(e),
                'query': query
            }

        # Import Tavily client (lazy import)
        try:
            from tavily import TavilyClient
        except ImportError:
            error_msg = (
                "tavily-python is not installed but required for web search.\n\n"
                "Install with:\n"
                "  pip install -r requirements/agent.txt\n"
                "Or:\n"
                "  pip install tavily-python\n"
                "Or:\n"
                "  pip install 'dingo-python[agent]'"
            )
            log.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'query': query,
                'error_type': 'DependencyError'
            }

        # Execute search
        try:
            log.info(f"Executing Tavily search: {query[:100]}...")

            # Initialize client
            client = TavilyClient(api_key=cls.config.api_key)

            # Prepare search parameters
            search_params = {
                'query': query,
                'max_results': kwargs.get('max_results', cls.config.max_results),
                'search_depth': kwargs.get('search_depth', cls.config.search_depth),
                'include_answer': kwargs.get('include_answer', cls.config.include_answer),
                'include_images': kwargs.get('include_images', cls.config.include_images),
                'include_raw_content': kwargs.get('include_raw_content', cls.config.include_raw_content),
            }

            # Execute search
            response = client.search(**search_params)

            # Format results
            result = {
                'success': True,
                'query': query,
                'results': cls._format_results(response.get('results', []))
            }

            # Add optional fields
            if search_params['include_answer'] and 'answer' in response:
                result['answer'] = response['answer']

            if search_params['include_images'] and 'images' in response:
                result['images'] = response['images']

            log.info(f"Tavily search successful: {len(result['results'])} results")
            return result

        except Exception as e:
            log.error(f"Tavily search failed: {e}")

            # Sanitize error message to prevent information disclosure
            error_str = str(e).lower()
            if "api key" in error_str or "authentication" in error_str or "unauthorized" in error_str:
                error_msg = "Invalid or missing API key"
            elif "rate limit" in error_str or "quota" in error_str:
                error_msg = "Rate limit exceeded or quota reached"
            elif "timeout" in error_str:
                error_msg = "Search request timed out"
            elif "network" in error_str or "connection" in error_str:
                error_msg = "Network connection error"
            else:
                error_msg = f"Search failed: {type(e).__name__}"

            return {
                'success': False,
                'error': error_msg,
                'query': query,
                'error_type': type(e).__name__
            }

    @classmethod
    def _format_results(cls, results: List[Dict]) -> List[Dict]:
        """
        Format search results to standard structure.

        Args:
            results: Raw results from Tavily API

        Returns:
            List of formatted result dictionaries
        """
        formatted = []

        for r in results:
            formatted.append({
                'title': r.get('title', ''),
                'url': r.get('url', ''),
                'content': r.get('content', ''),
                'score': r.get('score', 0.0),
                # Optional fields
                **({'raw_content': r['raw_content']} if 'raw_content' in r else {})
            })

        return formatted

    @classmethod
    def search_multiple(cls, queries: List[str], **kwargs) -> List[Dict[str, Any]]:
        """
        Execute multiple searches in sequence.

        Args:
            queries: List of search queries
            **kwargs: Configuration overrides

        Returns:
            List of search results, one per query
        """
        results = []

        for query in queries:
            result = cls.execute(query, **kwargs)
            results.append(result)

        return results
