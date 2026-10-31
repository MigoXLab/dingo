"""Deterministic intra-document and cross-record similarity rules for repository code."""

from __future__ import annotations
import hashlib
import re
import zlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

TOKEN_SHINGLE_SIZE = 5
MIN_NEAR_TOKENS = 30
MIN_NEAR_SHINGLES = 10

_LICENSE_MARKER = re.compile(
    r"(?i)\b(?:copyright|licensed? under|spdx-license-identifier|permission is hereby granted|apache license|gnu (?:general public|lesser general public) license|mozilla public license|redistribution and use)\b"
)
_COMMENT_LINE = re.compile(r"^\s*(?://+|#+|;+|--+|/\*+|\*+|<!--|REM\b)", re.I)


def intra_document_repetition(content: str) -> dict[str, Any] | None:
    if len(content) < 200:
        return None
    encoded = content.encode("utf-8", errors="ignore")
    compression_ratio = len(zlib.compress(encoded, level=1)) / max(len(encoded), 1)
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    unique_line_ratio = len(set(lines)) / len(lines) if len(lines) >= 20 else None
    if compression_ratio >= 0.08 and (unique_line_ratio is None or unique_line_ratio >= 0.08):
        return None
    return {
        "label": "Similarity.Intra_Document_Repetition",
        "reason": (
            f"Mechanical repetition detected: compression_ratio={compression_ratio:.4f}, "
            f"unique_line_ratio={unique_line_ratio if unique_line_ratio is not None else 'n/a'}."
        ),
    }


def _fallback_tokens(content: str) -> list[str]:
    return [
        token.lower() if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token) else token
        for token in re.findall(
            r"[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|(?:==|!=|<=|>=|=>|->|::|&&|\|\|)|[^\s]",
            content,
        )
    ]


def code_tokens(content: str, language: str = "", file_name: str = "") -> list[str]:
    try:
        from pygments import lex
        from pygments.lexers import get_lexer_by_name, get_lexer_for_filename
        from pygments.token import Comment, Text
        from pygments.util import ClassNotFound
    except ImportError:
        return _fallback_tokens(content)
    lexer = None
    if language:
        try:
            lexer = get_lexer_by_name(language)
        except ClassNotFound:
            pass
    if lexer is None and file_name:
        try:
            lexer = get_lexer_for_filename(file_name, content[:4096])
        except ClassNotFound:
            pass
    if lexer is None:
        return _fallback_tokens(content)
    tokens = []
    for token_type, value in lex(content, lexer):
        if token_type in Comment or (token_type in Text and not value.strip()):
            continue
        tokens.extend(part for part in value.split() if part)
    return tokens


def _shingles(tokens: list[str]) -> frozenset[int]:
    return frozenset(
        int.from_bytes(hashlib.blake2b("\x1f".join(tokens[index:index + TOKEN_SHINGLE_SIZE]).encode(), digest_size=8).digest(), "big")
        for index in range(len(tokens) - TOKEN_SHINGLE_SIZE + 1)
    )


def license_header(content: str) -> str | None:
    lines = content.splitlines()[:100]
    marked = [index for index, line in enumerate(lines) if _LICENSE_MARKER.search(line)]
    if not marked:
        return None
    end = min(len(lines), max(marked) + 8)
    selected = []
    for line in lines[:end]:
        if _COMMENT_LINE.search(line) or _LICENSE_MARKER.search(line) or (selected and not line.strip()):
            selected.append(line)
        elif selected:
            break
    text = "\n".join(selected)
    text = re.sub(r"(?i)copyright\s*(?:\(c\)|©)?\s*\d{4}(?:\s*[-,]\s*\d{4})?", "copyright <year>", text)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text if len(text) >= 40 else None


@dataclass(frozen=True)
class _Fingerprint:
    ref: str
    token_count: int
    normalized_hash: str
    shingles: frozenset[int]


class RepositoryDuplicateIndex:
    """Streaming index for normalized, near, and license-header duplicates."""

    def __init__(self, near_threshold: float = 0.90):
        self.near_threshold = near_threshold
        self.normalized: dict[str, str] = {}
        self.license_headers: dict[str, str] = {}
        self.representatives: list[_Fingerprint] = []
        self.bands: dict[tuple[int, tuple[int, ...]], set[int]] = defaultdict(set)

    @staticmethod
    def _signature(shingles: frozenset[int], permutations: int = 32) -> tuple[int, ...]:
        maximum = (1 << 64) - 1
        result = []
        for index in range(permutations):
            salt = (index + 1) * 0x9E3779B97F4A7C15
            result.append(min(((value ^ salt) * 0xC2B2AE3D27D4EB4F) & maximum for value in shingles))
        return tuple(result)

    def annotate(self, data: Any, ref: str) -> list[dict[str, Any]]:
        content = getattr(data, "content", None)
        if not isinstance(content, str):
            return []
        language = str(getattr(data, "language", "") or "")
        file_name = str(getattr(data, "file_name", "") or getattr(data, "path", "") or "")
        findings: list[dict[str, Any]] = []
        header = license_header(content)
        if header:
            digest = hashlib.sha256(header.encode()).hexdigest()
            first = self.license_headers.setdefault(digest, ref)
            if first != ref:
                findings.append({"label": "Similarity.License_Header_Duplicate", "reason": f"License header duplicates {first}."})

        tokens = code_tokens(content, language, file_name)
        if len(tokens) < MIN_NEAR_TOKENS:
            return findings
        normalized_hash = hashlib.sha256("\x1f".join(tokens).encode()).hexdigest()
        first = self.normalized.setdefault(normalized_hash, ref)
        if first != ref:
            findings.append({"label": "Similarity.Normalized_Token_Duplicate", "reason": f"Normalized token sequence duplicates {first}."})
            return findings
        shingles = _shingles(tokens)
        if len(shingles) < MIN_NEAR_SHINGLES:
            return findings
        signature = self._signature(shingles)
        candidate_ids: set[int] = set()
        band_keys = []
        # Two rows per band favors recall; exact Jaccard below remains the gate.
        for band, start in enumerate(range(0, len(signature), 2)):
            key = (band, signature[start:start + 2])
            band_keys.append(key)
            candidate_ids.update(self.bands[key])
        best = None
        for candidate_id in candidate_ids:
            candidate = self.representatives[candidate_id]
            ratio = min(len(tokens), candidate.token_count) / max(len(tokens), candidate.token_count)
            if ratio < 0.80:
                continue
            similarity = len(shingles & candidate.shingles) / len(shingles | candidate.shingles)
            if similarity >= self.near_threshold and (best is None or similarity > best[0]):
                best = (similarity, candidate.ref)
        if best:
            findings.append({"label": "Similarity.Token_Shingle_Near_Duplicate", "reason": f"Token shingle Jaccard={best[0]:.4f} against {best[1]}."})
            return findings
        representative_id = len(self.representatives)
        self.representatives.append(_Fingerprint(ref, len(tokens), normalized_hash, shingles))
        for key in band_keys:
            self.bands[key].add(representative_id)
        return findings


def record_reference(data: Any, fallback: str) -> str:
    for name in ("track_id", "data_id", "source", "file_name", "path"):
        value = getattr(data, name, None)
        if value not in (None, ""):
            return str(value)
    return fallback
