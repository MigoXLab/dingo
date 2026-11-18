"""Backend-neutral contract for writing batches of retrieval records."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass
class ImportRecord:
    """A source ID with optional vector, metadata, title, and text."""

    source_id: int | str
    vector: Sequence[float] | None = None
    metadata: Mapping[str, object] | None = None
    title: str | None = None
    text: str | None = None


@dataclass(frozen=True)
class ImportResult:
    """Account for every submitted record in a batch.

    Accepted records were acknowledged by the service. Rejected records have
    a confirmed failure. Unknown records have an unconfirmed outcome.
    The optional error describes a batch-level issue.
    """

    submitted: int
    accepted: int
    rejected: int
    unknown: int
    error: str | None = None

    def __post_init__(self) -> None:
        if min(self.submitted, self.accepted, self.rejected, self.unknown) < 0:
            raise ValueError("Import counts must be nonnegative")
        if self.accepted + self.rejected + self.unknown != self.submitted:
            raise ValueError("Accepted, rejected, and unknown counts must sum to submitted")


# TODO: Implement this protocol for other import backends
class ImportClient(Protocol):
    """Write records to a retrieval backend."""

    def write_batch(self, records: Sequence[ImportRecord]) -> ImportResult:
        """Write a batch and return counts for its outcomes."""
        ...
