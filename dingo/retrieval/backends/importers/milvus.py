"""Milvus ingestion interface placeholder"""

from collections.abc import Sequence

from dingo.retrieval.import_client import ImportRecord, ImportResult


class MilvusImportClient:
    """Write retrieval records to Milvus"""

    def write_batch(self, records: Sequence[ImportRecord]) -> ImportResult:
        # TODO: Implement Milvus batch ingestion
        raise NotImplementedError('Milvus ingestion interface is pending')
