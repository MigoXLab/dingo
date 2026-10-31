"""Deterministic hard gates for repository record input and content."""

from __future__ import annotations
import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any

MIN_CONTENT_CHARS = 20
MAX_CONTENT_CHARS = 2_000_000
MAX_LINE_CHARS = 20_000
MAX_AVG_LINE_CHARS = 1_000

_PLACEHOLDERS = {"n/a", "na", "null", "none", "undefined", "nil", "empty", "-", "--"}
_ERROR_PATTERNS = tuple(
    re.compile(pattern, re.I)
    for pattern in (
        r"\b(?:403|404|500|502|503|504)\b",
        r"\bnot\s+found\b",
        r"\baccess\s+denied\b",
        r"\bforbidden\b",
        r"\bunauthorized\b",
        r"\bpermission\s+denied\b",
        r"\brequest\s+failed\b",
        r"\bfetch\s+failed\b",
        r"\bextract(?:ion)?\s+failed\b",
    )
)
_MOJIBAKE_LITERALS = ("â€™", "â€œ", "â€", "ðŸ")
_MOJIBAKE_SEQUENCES = (
    re.compile(r"Ã[\u0080-\u00bf\u2010-\u203a]"),
    re.compile(r"Â[\u0080-\u00bf\u2010-\u203a]"),
)
_ANSI_CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_FORM_FEED_LANGUAGES = {
    "c", "common lisp", "cpp", "emacs lisp", "fortran", "lisp", "objective-c", "pascal",
    "plaintext", "python", "roff", "scheme", "text",
}
_FORM_FEED_SUFFIXES = {
    ".c", ".cc", ".cpp", ".el", ".f", ".f90", ".lisp", ".man", ".md", ".pas", ".py",
    ".roff", ".rst", ".scm", ".txt",
}


def _finding(label: str, reason: str) -> dict[str, str]:
    return {"label": f"Effectiveness.{label}", "reason": reason}


def _record_value(data: Any, *names: str) -> Any:
    for name in names:
        value = getattr(data, name, None)
        if value is not None:
            return value
    return None


def _file_suffixes(data: Any) -> set[str]:
    values = (
        _record_value(data, "repo_file_path"),
        _record_value(data, "file_name"),
        _record_value(data, "path"),
    )
    return {Path(str(value)).suffix.lower() for value in values if value}


def _literal_control_positions(content: str, data: Any) -> set[int]:
    try:
        from pygments import lex
        from pygments.lexers import get_lexer_by_name, get_lexer_for_filename
        from pygments.token import String
        from pygments.util import ClassNotFound
    except ImportError:
        return set()

    lexer = None
    language = str(_record_value(data, "language") or "")
    file_name = str(_record_value(data, "file_name", "repo_file_path", "path") or "")
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
        return set()

    positions: set[int] = set()
    offset = 0
    for token_type, value in lex(content, lexer):
        if token_type in String:
            positions.update(
                offset + index
                for index, character in enumerate(value)
                if (ord(character) < 32 and character not in "\t\n\r") or 127 <= ord(character) <= 159
            )
        offset += len(value)
    return positions


def _allowed_control(content: str, index: int, data: Any) -> bool:
    character = content[index]
    language = str(_record_value(data, "language") or "").strip().lower()
    suffixes = _file_suffixes(data)
    if character == "\x0c":
        return language in _FORM_FEED_LANGUAGES or bool(suffixes & _FORM_FEED_SUFFIXES)
    if character == "\x1b":
        return _ANSI_CSI.match(content, index) is not None
    if character == "\x07":
        return language == "roff" or bool(suffixes & {".man", ".roff"})
    if character == "\x1a":
        return (
            content.count("\x1a") == 1
            and not content[index + 1:].strip("\r\n")
            and (language in {"xbase", "clipper", "foxpro", "text", "plaintext"}
                 or bool(suffixes & {".prg", ".txt"}))
        )
    return False


def input_content_findings(data: Any) -> list[dict[str, str]]:
    """Evaluate the seven requested hard rules in stable label order."""
    content = getattr(data, "content", None)
    if not isinstance(content, str):
        return []

    findings: list[dict[str, str]] = []
    stripped = content.strip()
    if not stripped:
        findings.append(_finding("Empty_Content", "Content is empty or whitespace-only."))

    if len(stripped) <= 32 and stripped.lower() in _PLACEHOLDERS:
        findings.append(_finding("Placeholder_Content", f"Whole content is placeholder {stripped!r}."))
    if len(stripped) <= 128:
        matched_error = next((pattern.pattern for pattern in _ERROR_PATTERNS if pattern.search(stripped)), None)
        if matched_error:
            findings.append(_finding(
                "Error_Placeholder_Content",
                f"Short content is an error/fetch placeholder: {stripped!r} (pattern={matched_error!r}).",
            ))

    surrogate_count = sum(unicodedata.category(character) == "Cs" for character in content)
    mojibake_count = sum(content.count(value) for value in _MOJIBAKE_LITERALS)
    mojibake_count += sum(len(pattern.findall(content)) for pattern in _MOJIBAKE_SEQUENCES)
    replacement_count = content.count("\ufffd")
    replacement_exceeded = replacement_count > 20 or (
        bool(content) and replacement_count / len(content) > 0.01
    )
    if surrogate_count or mojibake_count or replacement_exceeded:
        findings.append(_finding(
            "Invalid_Unicode",
            f"Invalid Unicode evidence: surrogate={surrogate_count}, mojibake={mojibake_count}, "
            f"replacement={replacement_count}.",
        ))

    literal_positions = _literal_control_positions(content, data)
    illegal_positions = []
    for index, character in enumerate(content):
        codepoint = ord(character)
        if not ((codepoint < 32 and character not in "\t\n\r") or 127 <= codepoint <= 159):
            continue
        if index in literal_positions or _allowed_control(content, index, data):
            continue
        illegal_positions.append(index)
    if illegal_positions:
        evidence = ", ".join(f"U+{ord(content[index]):04X}@{index}" for index in illegal_positions[:20])
        findings.append(_finding(
            "Illegal_Control_Characters",
            f"Found {len(illegal_positions)} unexplained C0/C1 control character(s): {evidence}.",
        ))

    length = len(content)
    line_lengths = [len(line) for line in content.splitlines()] or [length]
    max_line = max(line_lengths)
    avg_line = sum(line_lengths) / len(line_lengths)
    if (
        length < MIN_CONTENT_CHARS
        or length > MAX_CONTENT_CHARS
        or max_line > MAX_LINE_CHARS
        or avg_line > MAX_AVG_LINE_CHARS
    ):
        findings.append(_finding(
            "Extreme_Length",
            f"Extreme content dimensions: chars={length}, max_line={max_line}, avg_line={avg_line:.1f}; "
            f"limits={MIN_CONTENT_CHARS}..{MAX_CONTENT_CHARS}/{MAX_LINE_CHARS}/{MAX_AVG_LINE_CHARS}.",
        ))

    declared_sha256 = _record_value(data, "sha256", "dedup_content_sha256")
    if isinstance(declared_sha256, str) and re.fullmatch(r"[0-9a-fA-F]{64}", declared_sha256):
        try:
            actual_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        except UnicodeEncodeError:
            actual_sha256 = None
        if actual_sha256 is not None and actual_sha256.lower() != declared_sha256.lower():
            findings.append(_finding(
                "Content_SHA256_Mismatch",
                f"Declared content SHA-256 does not match: declared={declared_sha256}, actual={actual_sha256}.",
            ))
    return findings
