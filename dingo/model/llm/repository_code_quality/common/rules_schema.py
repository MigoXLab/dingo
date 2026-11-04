"""Deterministic schema checks for repository-code JSONL records."""

from __future__ import annotations
import re
from typing import Any

REQUIRED_FIELDS = ("track_id", "source", "content", "language")
SHA256_FIELDS = ("sha256", "dedup_content_sha256")
_SOURCE_PATTERN = re.compile(
    r"^(?:s3://\S+|https?://\S+|file://\S+|/\S*|[A-Za-z0-9_.-]+)$"
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _finding(name: str, reason: str) -> dict[str, str]:
    return {"label": f"Effectiveness.{name}", "reason": reason}


def _record_dict(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return data
    if callable(getattr(data, "to_dict", None)):
        return data.to_dict()
    if callable(getattr(data, "model_dump", None)):
        return data.model_dump()
    return dict(getattr(data, "__dict__", {}))


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    return type(value).__name__


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def schema_findings(data: Any) -> list[dict[str, str]]:
    """Validate the handed-off repository record schema in stable rule order."""

    record = _record_dict(data)
    findings: list[dict[str, str]] = []
    missing = [name for name in REQUIRED_FIELDS if name not in record]
    if missing:
        findings.append(_finding("Missing_Required", f"Missing required field(s): {', '.join(missing)}."))

    empty = [name for name in REQUIRED_FIELDS if name in record and _is_empty(record[name])]
    sha_name = next((name for name in SHA256_FIELDS if name in record), None)
    if sha_name and _is_empty(record[sha_name]):
        empty.append(sha_name)
    if empty:
        findings.append(_finding("Empty_Required", f"Required/non-empty field(s) are empty: {', '.join(empty)}."))

    mismatches = []
    expected_types = {
        "track_id": "string or integer",
        "source": "string",
        "content": "string",
        "language": "string",
    }
    for name, expected in expected_types.items():
        if name not in record or record[name] is None:
            continue
        value = record[name]
        valid = (
            isinstance(value, str)
            if name != "track_id"
            else isinstance(value, (str, int)) and not isinstance(value, bool)
        )
        if not valid:
            mismatches.append(f"{name}={_type_name(value)} (want {expected})")
    if sha_name and record[sha_name] is not None and not isinstance(record[sha_name], str):
        mismatches.append(f"{sha_name}={_type_name(record[sha_name])} (want string)")
    if mismatches:
        findings.append(_finding("Field_Type_Mismatch", "Field type mismatch: " + "; ".join(mismatches) + "."))

    out_of_range = []
    source = record.get("source")
    language = record.get("language")
    if isinstance(source, str) and len(source) > 4096:
        out_of_range.append(f"source length={len(source)}, max=4096")
    if isinstance(language, str) and len(language) > 64:
        out_of_range.append(f"language length={len(language)}, max=64")
    if out_of_range:
        findings.append(_finding("Field_Length_Out_Of_Range", "Field length out of range: " + "; ".join(out_of_range) + "."))

    regex_mismatches = []
    if isinstance(source, str) and source and not _SOURCE_PATTERN.fullmatch(source):
        regex_mismatches.append("source must be a supported URI, absolute path, or simple source name without whitespace")
    sha = record.get(sha_name) if sha_name else None
    if isinstance(sha, str) and sha and not _SHA256_PATTERN.fullmatch(sha):
        regex_mismatches.append(f"{sha_name} must be 64 lowercase hexadecimal characters")
    if regex_mismatches:
        findings.append(_finding("Field_Regex_Mismatch", "Field format mismatch: " + "; ".join(regex_mismatches) + "."))
    return findings
