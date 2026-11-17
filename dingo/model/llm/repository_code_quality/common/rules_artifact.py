"""Detection of non-code artifacts such as archives and RCS/CVS version files."""

from __future__ import annotations
import re
from typing import Any

ARCHIVE_SUFFIXES = (
    ".tar.gz",
    ".tar.bz2",
    ".tar.xz",
    ".tgz",
    ".tbz2",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".jar",
    ".rar",
    ".7z",
)
RCS_SUFFIX = ",v"

_RCS_HEAD_RE = re.compile(r"(?m)^head\s+\d+(?:\.\d+)+;\s*$")
_RCS_META_RE = re.compile(r"(?m)^(?:branch|symbols|locks|access|comment)\s*[^=\n]*;\s*$")


def _path_values(data: Any) -> list[str]:
    values = []
    for name in ("repo_file_path", "file_name", "path"):
        value = getattr(data, name, None)
        if isinstance(value, str) and value:
            values.append(value)
    meta = getattr(data, "file_meta", None)
    if isinstance(meta, dict):
        for name in ("file_path", "file_name", "repo_file_path", "path"):
            value = meta.get(name)
            if isinstance(value, str) and value and value not in values:
                values.append(value)
    return values


def _basename(path: str) -> str:
    return path.replace("\\", "/").strip().rstrip("/").rsplit("/", 1)[-1].lower()


def artifact_findings(data: Any) -> list[dict[str, str]]:
    """Flag records whose path or content is an archive/RCS artifact, not code."""
    evidence = []
    for path in _path_values(data):
        basename = _basename(path)
        if basename.endswith(ARCHIVE_SUFFIXES):
            evidence.append(f"archive suffix in path {path!r}")
        elif basename.endswith(RCS_SUFFIX):
            evidence.append(f"RCS/CVS version archive path {path!r}")

    content = getattr(data, "content", None)
    if isinstance(content, str):
        head = content[:4096]
        if _RCS_HEAD_RE.search(head) and len(_RCS_META_RE.findall(head)) >= 2:
            evidence.append("RCS/CVS archive header (head plus metadata lines) in content")

    if not evidence:
        return []
    return [{
        "label": "Effectiveness.Archive_Artifact",
        "reason": f"Record is a non-code artifact: {'; '.join(evidence)}.",
    }]
