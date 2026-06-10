"""
Abstract search client interface for retrieval evaluation.

All search backends implement SearchClient. The evaluation executor
only depends on this interface.

Adding a new backend:

    from dingo.retrieval.search_client import SearchClient, SearchResponse, register_backend

    @register_backend("my_backend")
    class MyClient(SearchClient):
        name = "my-backend"

        def __init__(self, **kwargs):
            ...

        def search(self, query: str, limit: int = 100) -> SearchResponse:
            ...

dingo eval-retrieval --backend google_scholar --tasks SciFact \
    --api-token YOUR_SERPAPI_KEY \
    --limit 100 --rate-limit 1.0 \

"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PaperResult:
    paper_id: str
    title: str
    abstract: str = ""
    score: float = 0.0
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    raw: dict = field(default_factory=dict)


@dataclass
class SearchResponse:
    query: str
    results: list[PaperResult]
    response_time_ms: float
    status_code: int
    error: Optional[str] = None


class SearchClient(ABC):
    name: str = "unknown"

    @abstractmethod
    def search(self, query: str, limit: int = 100) -> SearchResponse:
        ...

    def dry_run(self, query: str, limit: int = 5) -> None:
        response = self.search(query, limit=limit)
        if response.error:
            logger.error(f"Error: {response.error}")
            return
        logger.info(
            f"Got {len(response.results)} results in "
            f"{response.response_time_ms:.0f}ms"
        )
        for i, p in enumerate(response.results, 1):
            print(f"  [{i}] {p.title}")
            print(f"      ID: {p.paper_id} | Score: {p.score:.4f}")


_BACKENDS: dict[str, type[SearchClient]] = {}
_BACKENDS_LOADED = False


def register_backend(name: str):
    def decorator(cls: type[SearchClient]):
        _BACKENDS[name] = cls
        return cls

    return decorator


def _load_builtin_backends():
    global _BACKENDS_LOADED
    if _BACKENDS_LOADED:
        return
    _BACKENDS_LOADED = True
    import importlib

    for mod_name in (
        "dingo.retrieval.backends.agentic",
        "dingo.retrieval.backends.google_scholar",
        "dingo.retrieval.backends.openalex",
        "dingo.retrieval.backends.semantic_scholar",
    ):
        try:
            importlib.import_module(mod_name)
        except ImportError:
            pass


def list_backends() -> list[str]:
    _load_builtin_backends()
    return sorted(_BACKENDS.keys())


def create_client(name: str, **kwargs) -> SearchClient:
    _load_builtin_backends()
    if name not in _BACKENDS:
        available = ", ".join(list_backends()) or "(none)"
        raise ValueError(
            f"Unknown backend {name!r}. Available: {available}. "
            f"Make sure the backend module is imported."
        )
    cls = _BACKENDS[name]
    return cls(**kwargs)
