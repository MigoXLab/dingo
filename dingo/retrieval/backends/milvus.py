"""Milvus vector query interface placeholder"""

from collections.abc import Sequence
from dataclasses import dataclass

from dingo.retrieval.search_client import SearchClient


@dataclass(frozen=True)
class VectorHit:
    """Vector record ID and its distance from the query"""

    id: int | str
    distance: float


class MilvusSearchClient(SearchClient[Sequence[float], list[VectorHit]]):
    """Query Milvus for nearest vector records"""

    name: str = "milvus"

    def search(self, query: Sequence[float], limit: int = 100) -> list[VectorHit]:
        # TODO: Implement Milvus vector search
        raise NotImplementedError('Milvus query interface is pending')
