"""
arXiv Search Tool

This module provides integration with arXiv API for academic paper search and verification.
arXiv is a free distribution service and open-access archive for scholarly articles in
the fields of physics, mathematics, computer science, and more.

Dependencies:
    arxiv>=2.4.0

Configuration:
    max_results: Maximum number of search results (default: 5, range: 1-50)
    sort_by: Sort order - "relevance", "lastUpdatedDate", or "submittedDate" (default: "relevance")
    sort_order: "ascending" or "descending" (default: "descending")
    rate_limit_delay: Delay between requests in seconds (default: 3.0)
    timeout: Request timeout in seconds (default: 30)
    api_key: Not required for arXiv (public API)
    fetch_affiliations: Fetch author+institution text from arXiv HTML paper page (default: False).
        When enabled, adds an ``affiliations_text`` field to each result by scraping
        the ``ltx_authors`` section.  Silently skipped for papers without HTML version.
"""

import re
import threading
import time
from typing import Any, Dict, List, Optional

import requests as _requests
from pydantic import Field

from dingo.io.input import RequiredField
from dingo.model.llm.agent.tools.base_tool import BaseTool, ToolConfig
from dingo.model.llm.agent.tools.tool_registry import tool_register
from dingo.utils import log


class ArxivConfig(ToolConfig):
    """Configuration for arXiv search tool"""
    api_key: Optional[str] = None  # Override parent - not needed for arXiv
    max_results: int = Field(default=5, ge=1, le=50)
    sort_by: str = Field(default="relevance", pattern="^(relevance|lastUpdatedDate|submittedDate)$")
    sort_order: str = Field(default="descending", pattern="^(ascending|descending)$")
    rate_limit_delay: float = Field(default=3.0, ge=0.0)
    timeout: int = Field(default=30, ge=1)
    fetch_affiliations: bool = Field(
        default=False,
        description=(
            "Fetch author+institution text from arXiv HTML page for each result. "
            "Adds 'affiliations_text' field. Requires one extra HTTP request per result. "
            "Enable for institutional/attribution claim verification."
        ),
    )


@tool_register
class ArxivSearch(BaseTool):
    """
    arXiv search tool for academic paper verification.

    Provides search capabilities for academic papers in arXiv's open-access archive.
    Supports searching by arXiv ID, DOI, title, author, and keywords with automatic
    detection of query type.

    Features:
    - Auto-detection of arXiv IDs and DOIs
    - No API key required (public API)
    - Rate limiting to respect arXiv guidelines
    - Support for multiple search modes
    - Comprehensive paper metadata

    arXiv ID Patterns:
    - New format: 2301.12345 or 2301.12345v1 (with version)
    - Old format: hep-ph/0123456 or hep-ph/0123456v1

    DOI Pattern:
    - Standard DOI: 10.1234/example.doi

    Usage:
        # Auto-detect search type
        result = ArxivSearch.execute(query="1706.03762")

        # Explicit search by title
        result = ArxivSearch.execute(
            query="Attention is All You Need",
            search_type="title"
        )

        # Result structure:
        {
            'success': True,
            'query': '1706.03762',
            'search_type': 'arxiv_id',
            'results': [
                {
                    'arxiv_id': '1706.03762',
                    'title': 'Attention is All You Need',
                    'authors': ['Vaswani, Ashish', ...],
                    'summary': 'We propose a new...',
                    'published': '2017-06-12',
                    'updated': '2017-12-06',
                    'pdf_url': 'http://arxiv.org/pdf/1706.03762v5',
                    'doi': '10.48550/arXiv.1706.03762',
                    'categories': ['cs.CL', 'cs.LG'],
                    'journal_ref': 'NIPS 2017'
                },
                ...
            ]
        }
    """

    name = "arxiv_search"
    description = (
        "Search arXiv for academic papers by ID, DOI, title, or author. "
        "Returns paper metadata: title, authors list, abstract, publication date, "
        "PDF URL, and categories. "
        "When fetch_affiliations is enabled, results also include 'affiliations_text': "
        "a compact author+institution string parsed from the HTML paper page "
        "(e.g. '1 Shanghai AI Laboratory  2 Abaka AI  3 2077AI'), which is the "
        "authoritative source for institutional attribution claims. "
        "Use this tool for verifying claims about academic papers, author names, "
        "publication dates, and institutional/organizational affiliations."
    )
    config: ArxivConfig = ArxivConfig()

    _required_fields = [RequiredField.CONTENT]
    _last_request_time: float = 0.0
    _rate_limit_lock: threading.Lock = threading.Lock()

    @classmethod
    def execute(cls, query: str, search_type: str = "auto", **kwargs) -> Dict[str, Any]:
        """
        Execute arXiv search.

        Args:
            query: Search query string (arXiv ID, DOI, title, author, or keywords)
            search_type: Search mode - "auto", "id", "doi", "title", "author" (default: "auto")
            **kwargs: Optional overrides for configuration
                - max_results: Override max_results config
                - sort_by: Override sort_by config
                - sort_order: Override sort_order config

        Returns:
            Dict with search results:
            {
                'success': bool,
                'query': str,
                'search_type': str,
                'results': List[Dict],
                'count': int
            }

        Raises:
            ImportError: If arxiv library is not installed
            ValueError: If query is empty or search_type is invalid
            Exception: For API errors
        """
        # Validate inputs
        if not query or not query.strip():
            log.error("arXiv search query cannot be empty")
            return {
                'success': False,
                'error': 'Search query cannot be empty',
                'query': query
            }

        valid_search_types = ["auto", "id", "doi", "title", "author"]
        if search_type not in valid_search_types:
            log.error(f"Invalid search_type: {search_type}")
            return {
                'success': False,
                'error': f'Invalid search_type. Must be one of: {", ".join(valid_search_types)}',
                'query': query
            }

        # Import arxiv library (lazy import)
        try:
            import arxiv
        except ImportError:
            error_msg = (
                "arxiv library is not installed but required for arXiv search.\n\n"
                "Install with:\n"
                "  pip install -r requirements/agent.txt\n"
                "Or:\n"
                "  pip install arxiv\n"
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

        # Apply rate limiting
        cls._apply_rate_limiting()

        # Execute search
        try:
            log.info(f"Executing arXiv search: {query[:100]}... (type: {search_type})")

            # Build search query based on type
            detected_type, arxiv_query = cls._build_arxiv_query(query, search_type)

            # Get configuration
            max_results = kwargs.get('max_results', cls.config.max_results)
            sort_by_str = kwargs.get('sort_by', cls.config.sort_by)
            sort_order_str = kwargs.get('sort_order', cls.config.sort_order)

            # Map sort_by string to arxiv.SortCriterion
            sort_by_map = {
                'relevance': arxiv.SortCriterion.Relevance,
                'lastUpdatedDate': arxiv.SortCriterion.LastUpdatedDate,
                'submittedDate': arxiv.SortCriterion.SubmittedDate
            }
            sort_by = sort_by_map.get(sort_by_str, arxiv.SortCriterion.Relevance)

            # Map sort_order string to arxiv.SortOrder
            sort_order_map = {
                'ascending': arxiv.SortOrder.Ascending,
                'descending': arxiv.SortOrder.Descending
            }
            sort_order = sort_order_map.get(sort_order_str, arxiv.SortOrder.Descending)

            # Create search
            search = arxiv.Search(
                query=arxiv_query,
                max_results=max_results,
                sort_by=sort_by,
                sort_order=sort_order
            )

            # Execute search and collect results
            results = []
            entry_ids = []
            client = arxiv.Client()
            for paper in client.results(search):
                results.append(cls._format_paper(paper))
                entry_ids.append(paper.entry_id)

            # Optionally enrich results with author+institution text from HTML pages.
            # The arXiv Atom API rarely includes affiliation data; the HTML page is
            # the only reliable machine-readable source.
            if cls.config.fetch_affiliations and results:
                for i, entry_id in enumerate(entry_ids):
                    html_url = entry_id.replace('/abs/', '/html/')
                    affiliations_text = cls._fetch_html_affiliations(
                        html_url, timeout=cls.config.timeout
                    )
                    if affiliations_text is not None:
                        results[i]['affiliations_text'] = affiliations_text

            # Format response
            result = {
                'success': True,
                'query': query,
                'search_type': detected_type,
                'results': results,
                'count': len(results)
            }

            log.info(f"arXiv search successful: {len(results)} results")
            return result

        except Exception as e:
            log.error(f"arXiv search failed: {e}")

            # Sanitize error message to prevent information disclosure
            error_str = str(e).lower()
            if "timeout" in error_str:
                error_msg = "Search request timed out"
            elif "network" in error_str or "connection" in error_str:
                error_msg = "Network connection error"
            elif "rate limit" in error_str or "429" in error_str:
                error_msg = "Rate limit exceeded (HTTP 429) — arXiv API throttled this request"
            else:
                error_msg = f"Search failed: {type(e).__name__}"

            return {
                'success': False,
                'error': error_msg,
                'query': query,
                'error_type': type(e).__name__
            }

    @classmethod
    def _build_arxiv_query(cls, query: str, search_type: str) -> tuple:
        """
        Build arXiv API query based on search type.

        Auto-detection priority:
        1. arXiv ID (e.g., "2301.12345" or "hep-ph/0123456")
        2. DOI (e.g., "10.1234/example")
        3. Title/keyword search

        Args:
            query: User query
            search_type: "auto", "id", "doi", "title", or "author"

        Returns:
            Tuple of (detected_type: str, arxiv_query: str)
        """
        query = query.strip()

        # Auto-detect or explicit type
        if search_type == "auto":
            # Check for arXiv ID
            if cls._is_arxiv_id(query):
                detected_type = "arxiv_id"
                # Clean up arXiv ID (remove "arXiv:" prefix if present)
                clean_id = query.replace("arXiv:", "").replace("arxiv:", "").strip()
                arxiv_query = f"id:{clean_id}"

            # Check for DOI
            elif cls._is_doi(query):
                detected_type = "doi"
                arxiv_query = f"doi:{query}"

            # Default to title search
            else:
                detected_type = "title"
                arxiv_query = f"ti:{query}"

        elif search_type == "id":
            detected_type = "arxiv_id"
            clean_id = query.replace("arXiv:", "").replace("arxiv:", "").strip()
            arxiv_query = f"id:{clean_id}"

        elif search_type == "doi":
            detected_type = "doi"
            arxiv_query = f"doi:{query}"

        elif search_type == "title":
            detected_type = "title"
            arxiv_query = f"ti:{query}"

        elif search_type == "author":
            detected_type = "author"
            arxiv_query = f"au:{query}"

        else:
            # Fallback
            detected_type = "title"
            arxiv_query = f"ti:{query}"

        return detected_type, arxiv_query

    @classmethod
    def _is_arxiv_id(cls, text: str) -> bool:
        """
        Check if text matches arXiv ID pattern.

        Patterns:
        - New format: YYMM.NNNNN or YYMM.NNNNNvN (e.g., 2301.12345, 2301.12345v1)
        - Old format: archive/NNNNNNN or archive/NNNNNNNvN (e.g., hep-ph/0123456)

        Args:
            text: Text to check

        Returns:
            True if text matches arXiv ID pattern
        """
        text = text.strip().replace("arXiv:", "").replace("arxiv:", "")

        # New format: YYMM.NNNNN(vN)?
        new_pattern = r'^\d{4}\.\d{4,5}(v\d+)?$'
        if re.match(new_pattern, text):
            return True

        # Old format: archive/NNNNNNN(vN)?
        old_pattern = r'^[a-z\-]+/\d{7}(v\d+)?$'
        if re.match(old_pattern, text):
            return True

        return False

    @classmethod
    def _is_doi(cls, text: str) -> bool:
        """
        Check if text matches DOI pattern.

        Pattern: 10.NNNN/... (standard DOI format)

        Args:
            text: Text to check

        Returns:
            True if text matches DOI pattern
        """
        text = text.strip()
        doi_pattern = r'^10\.\d{4,9}/[-._;()/:A-Z0-9]+$'
        return bool(re.match(doi_pattern, text, re.IGNORECASE))

    @classmethod
    def _format_paper(cls, paper) -> Dict[str, Any]:
        """
        Format arxiv.Result to standard dictionary.

        Args:
            paper: arxiv.Result object

        Returns:
            Formatted paper dictionary
        """
        return {
            'arxiv_id': paper.entry_id.split('/')[-1],  # Extract ID from full URL
            'title': paper.title,
            'authors': [author.name for author in paper.authors],
            'summary': paper.summary,
            'published': paper.published.strftime('%Y-%m-%d') if paper.published else None,
            'updated': paper.updated.strftime('%Y-%m-%d') if paper.updated else None,
            'pdf_url': paper.pdf_url,
            'doi': paper.doi,
            'categories': paper.categories,
            'primary_category': paper.primary_category,
            'journal_ref': paper.journal_ref,
            'comment': paper.comment
        }

    @classmethod
    def _apply_rate_limiting(cls):
        """
        Apply rate limiting to respect arXiv guidelines.

        arXiv recommends at least 3 seconds between requests.
        This method enforces the configured rate_limit_delay.
        Thread-safe: uses _rate_limit_lock to prevent concurrent requests
        from bypassing the rate limit.
        """
        with cls._rate_limit_lock:
            current_time = time.time()
            time_since_last_request = current_time - cls._last_request_time

            if time_since_last_request < cls.config.rate_limit_delay:
                sleep_time = cls.config.rate_limit_delay - time_since_last_request
                log.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)

            cls._last_request_time = time.time()

    @classmethod
    def detect_paper_references(cls, text: str) -> Dict[str, List[str]]:
        """
        Utility: Detect paper references in text.

        Searches for arXiv IDs and DOIs in text and returns them.
        Useful for preprocessing text to find papers to look up.

        Args:
            text: Text to search for paper references

        Returns:
            Dict with 'arxiv_ids' and 'dois' keys containing found references

        Example:
            text = "See arXiv:1706.03762 and DOI 10.1234/example"
            refs = ArxivSearch.detect_paper_references(text)
            # refs = {
            #     'arxiv_ids': ['1706.03762'],
            #     'dois': ['10.1234/example']
            # }
        """
        # Find arXiv IDs
        arxiv_ids = []

        # New format: YYMM.NNNNN(vN)? - use non-capturing group to avoid tuple returns
        new_pattern = r'\b\d{4}\.\d{4,5}(?:v\d+)?\b'
        arxiv_ids.extend(re.findall(new_pattern, text))

        # Old format: archive/NNNNNNN(vN)? - use non-capturing group
        old_pattern = r'\b[a-z\-]+/\d{7}(?:v\d+)?\b'
        arxiv_ids.extend(re.findall(old_pattern, text))

        # Also look for explicit "arXiv:..." mentions
        arxiv_prefix_pattern = r'arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+/\d{7}(?:v\d+)?)'
        arxiv_ids.extend(re.findall(arxiv_prefix_pattern, text, re.IGNORECASE))

        # Find DOIs
        doi_pattern = r'\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b'
        dois = re.findall(doi_pattern, text, re.IGNORECASE)

        # Deduplicate
        arxiv_ids = list(set(arxiv_ids))
        dois = list(set(dois))

        return {
            'arxiv_ids': arxiv_ids,
            'dois': dois
        }

    @classmethod
    def _fetch_html_affiliations(cls, html_url: str, timeout: int = 15) -> Optional[str]:
        """
        Fetch author+institution text from an arXiv HTML paper page.

        Extracts the ``ltx_authors`` div from the LaTeXML-rendered HTML page,
        which contains author names with footnoted institution identifiers
        (e.g. "1 Shanghai AI Laboratory  2 Abaka AI").

        Args:
            html_url: Full URL, e.g. ``https://arxiv.org/html/2412.07626v2``.
            timeout: HTTP request timeout in seconds.

        Returns:
            Cleaned plain-text of the ``ltx_authors`` section, or ``None`` if
            unavailable (no HTML version, network error, or missing element).
        """
        try:
            resp = _requests.get(
                html_url,
                headers={"user-agent": "dingo-arxiv-tool/1.0"},
                timeout=timeout,
            )
            if resp.status_code != 200:
                log.debug("arXiv HTML page unavailable (%d): %s", resp.status_code, html_url)
                return None
            match = re.search(r'class="ltx_authors"[^>]*>(.*?)</div>', resp.text, re.DOTALL)
            if not match:
                log.debug("ltx_authors section not found in HTML page: %s", html_url)
                return None
            text = re.sub(r'<[^>]+>', ' ', match.group(1))
            text = re.sub(r'\s+', ' ', text).strip()
            return text if text else None
        except Exception as exc:
            log.debug("Failed to fetch HTML affiliations from %s: %s", html_url, exc)
            return None

    @classmethod
    def validate_config(cls):
        """
        Validate tool configuration.

        arXiv doesn't require an API key, so we override the parent's
        api_key validation.
        """
        # arXiv is a public API - no API key required
        # Just validate that config exists
        if not hasattr(cls, 'config'):
            raise ValueError(f"{cls.name}: Missing configuration")
