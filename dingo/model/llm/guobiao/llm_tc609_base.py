"""Shared helpers for TC609 LLM evaluators."""

import json

MAX_DATA_CONTENT_CHARS = 30000


def serialize_data_content(data_content) -> str:
    """Serialize the complete data_content value for TC609 LLM evaluation."""
    return json.dumps(data_content, ensure_ascii=False, indent=2)[
        :MAX_DATA_CONTENT_CHARS
    ]
