"""Milvus vector queries using an injected client and an existing collection"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from math import isfinite
from numbers import Real
from typing import Any

from dingo.retrieval.search_client import SearchClient


def _is_timeout(error: Exception) -> bool:
    # PyMilvus preserves gRPC deadlines and wraps retry exhaustion in MilvusException
    try:
        import grpc
    except ImportError:
        grpc = None
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, TimeoutError):
            return True
        if grpc is not None:
            if isinstance(current, grpc.FutureTimeoutError):
                return True
            if isinstance(current, grpc.RpcError) and current.code() == grpc.StatusCode.DEADLINE_EXCEEDED:
                return True
        is_milvus = any(
            cls.__name__ == "MilvusException" and cls.__module__ == "pymilvus.exceptions"
            for cls in type(current).__mro__
        )
        if is_milvus:
            if grpc is not None and current.code == grpc.StatusCode.DEADLINE_EXCEEDED:
                return True
            if re.match(r"^\[[^\]]+\] Retry timeout:", current.message):
                return True
        current = current.__cause__ or current.__context__
    return False


@dataclass(frozen=True)
class VectorHit:
    """Vector record ID and its distance from the query"""

    id: int | str
    distance: float


class MilvusSearchClient(SearchClient[Sequence[float], list[VectorHit]]):
    """Execute one dense query and preserve the service's complete hit order"""

    name: str = "milvus"

    def __init__(
        self,
        client: Any,
        *,
        collection_name: str,
        id_field: str,
        vector_field: str,
        timeout: float,
        search_params: Mapping[str, object] | None = None,
    ) -> None:
        names = (collection_name, id_field, vector_field)
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise ValueError("Collection and field names must be nonempty strings")
        if id_field == vector_field:
            raise ValueError("ID and vector fields must differ")
        if isinstance(timeout, bool) or not isinstance(timeout, Real) or not isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be positive and finite")
        if search_params is not None and not isinstance(search_params, Mapping):
            raise ValueError("Search parameters must be a mapping")
        self.client = client
        self.collection_name = collection_name
        self.id_field = id_field
        self.vector_field = vector_field
        self.timeout = timeout
        self.search_params = search_params

    def search(self, query: Sequence[float], limit: int = 100) -> list[VectorHit]:
        if type(limit) is not int or limit <= 0:
            raise ValueError("Limit must be a positive integer")
        if isinstance(query, (str, bytes, Mapping)):
            raise ValueError("Query must be a numeric vector")
        try:
            vector = []
            for value in query:
                if isinstance(value, bool) or not isinstance(value, Real):
                    raise ValueError("Query values must be numeric")
                vector.append(float(value))
            if not vector or not all(isfinite(value) for value in vector):
                raise ValueError("Query vector must be nonempty and finite")
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Query must be a nonempty finite numeric vector") from exc

        kwargs = {
            "collection_name": self.collection_name,
            "data": [vector],
            "anns_field": self.vector_field,
            "limit": limit,
            "timeout": self.timeout,
        }
        if self.search_params is not None:
            kwargs["search_params"] = self.search_params
        try:
            result = self.client.search(**kwargs)
        except Exception as exc:
            if _is_timeout(exc):
                raise TimeoutError("Milvus search timed out") from exc
            raise
        if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], list):
            raise ValueError("Invalid Milvus response for a single query")

        hits = []
        for hit in result[0]:
            if not isinstance(hit, Mapping):
                raise ValueError("Invalid Milvus hit")
            # PyMilvus exposes primary keys under the configured field name or id
            hit_id = hit.get(self.id_field, hit.get("id"))
            distance = hit.get("distance")
            if type(hit_id) not in (int, str) or (isinstance(hit_id, str) and not hit_id.strip()):
                raise ValueError("Invalid Milvus hit ID")
            if isinstance(distance, bool) or not isinstance(distance, Real):
                raise ValueError("Invalid Milvus hit distance")
            try:
                distance = float(distance)
            except (ValueError, OverflowError) as exc:
                raise ValueError("Invalid Milvus hit distance") from exc
            if not isfinite(distance):
                raise ValueError("Invalid Milvus hit distance")
            hits.append(VectorHit(id=hit_id, distance=distance))
        return hits
