"""Milvus ingestion using an injected client and an existing collection"""

from collections.abc import Mapping, Sequence
from math import isfinite
from numbers import Real
from typing import Any

from dingo.retrieval.import_client import ImportRecord, ImportResult


class MilvusImportClient:
    """Insert IDs and vectors once per batch; SDK transport retries remain external"""

    def __init__(
        self,
        client: Any,
        *,
        collection_name: str,
        id_field: str,
        vector_field: str,
        timeout: float,
    ) -> None:
        names = (collection_name, id_field, vector_field)
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise ValueError("Collection and field names must be nonempty strings")
        if id_field == vector_field:
            raise ValueError("ID and vector fields must differ")
        if isinstance(timeout, bool) or not isinstance(timeout, Real) or not isfinite(timeout) or timeout <= 0:
            raise ValueError("Timeout must be positive and finite")
        self.client = client
        self.collection_name = collection_name
        self.id_field = id_field
        self.vector_field = vector_field
        self.timeout = timeout

    def write_batch(self, records: Sequence[ImportRecord]) -> ImportResult:
        submitted = len(records)
        if not submitted:
            return ImportResult(0, 0, 0, 0)

        rows = []
        source_ids: set[int | str] = set()
        try:
            for record in records:
                source_id = record.source_id
                if type(source_id) not in (int, str) or (isinstance(source_id, str) and not source_id.strip()):
                    raise ValueError("Source IDs must be integers or nonblank strings")
                if source_id in source_ids:
                    raise ValueError("Source IDs must be unique within a batch")
                source_ids.add(source_id)
                if record.vector is None or isinstance(record.vector, (str, bytes, Mapping)):
                    raise ValueError("Milvus requires a numeric vector for every record")
                vector = []
                for value in record.vector:
                    if isinstance(value, bool) or not isinstance(value, Real):
                        raise ValueError("Vector values must be numeric")
                    vector.append(float(value))
                if not vector or not all(isfinite(value) for value in vector):
                    raise ValueError("Vectors must be nonempty and finite")
                if rows and len(vector) != len(rows[0][self.vector_field]):
                    raise ValueError("Vector dimensions must match within a batch")
                rows.append({self.id_field: source_id, self.vector_field: vector})
        except (AttributeError, TypeError, ValueError, OverflowError) as exc:
            return ImportResult(submitted, 0, submitted, 0, f"Invalid batch payload ({type(exc).__name__})")

        try:
            receipt = self.client.insert(
                collection_name=self.collection_name,
                data=rows,
                timeout=self.timeout,
            )
        except Exception as exc:
            return ImportResult(submitted, 0, 0, submitted, f"Milvus insert failed ({type(exc).__name__})")

        accepted = receipt.get("insert_count") if isinstance(receipt, Mapping) else None
        if type(accepted) is not int or not 0 <= accepted <= submitted:
            return ImportResult(submitted, 0, 0, submitted, "Invalid Milvus insert count")
        if "ids" in receipt:
            ids = receipt["ids"]
            if (
                not isinstance(ids, Sequence)
                or isinstance(ids, (str, bytes, bytearray))
                or len(ids) != accepted
                or any(type(source_id) not in (int, str) for source_id in ids)
                or len(set(ids)) != accepted
                or not source_ids.issuperset(ids)
            ):
                return ImportResult(submitted, 0, 0, submitted, "Milvus insert IDs contradict the batch")

        unknown = submitted - accepted
        error = "Milvus acknowledged only part of the batch" if unknown else None
        return ImportResult(submitted, accepted, 0, unknown, error)
