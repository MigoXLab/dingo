"""JSONL converter with streaming cross-record duplicate annotation."""

from __future__ import annotations
import json
from typing import Callable, Dict, Union

from dingo.config import InputArgs
from dingo.data.converter.base import BaseConverter
from dingo.io import Data

DERIVED_DUPLICATE_FIELD = "repository_duplicate_findings"


@BaseConverter.register("repository_jsonl")
class RepositoryJsonlConverter(BaseConverter):
    """JSONL parsing plus sequential cross-record duplicate annotation.

    The duplicate index lives in the converter closure, so annotation runs in
    input order during the load phase and stays deterministic while evaluation
    is concurrent. Findings travel to the evaluator as the extra field
    ``repository_duplicate_findings``; Dingo only auto-strips derived fields
    for ms-swift outputs, so flagged records keep the field in saved raw_data
    as duplicate provenance.
    """

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        from dingo.model.llm.repository_code_quality.common.rules_similarity import RepositoryDuplicateIndex, record_reference

        index = RepositoryDuplicateIndex()
        sequence = 0

        def _convert(raw: Union[str, Dict]):
            nonlocal sequence
            sequence += 1
            record = json.loads(raw) if isinstance(raw, str) else raw
            data = Data(**record)
            findings = index.annotate(data, record_reference(data, f"record-{sequence}"))
            if findings:
                setattr(data, DERIVED_DUPLICATE_FIELD, findings)
            return data

        return _convert
