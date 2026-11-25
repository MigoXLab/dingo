"""Deterministic hard gates for repository record input and content."""

from __future__ import annotations
import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

try:
    import unicodedata2 as _unicode_data
except ImportError:
    _unicode_data = unicodedata

try:
    import regex as _unicode_regex
except ImportError:
    _unicode_regex = None

MIN_CONTENT_CHARS = 20
MAX_CONTENT_CHARS = 2_000_000
MAX_LINE_CHARS = 20_000
MAX_AVG_LINE_CHARS = 1_000
_PRIVATE_USE_COMMENT_MAX_COUNT = 20
_CONTEXTUAL_FORMAT_CHAR_MAX_COUNT = 0

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
_NON_ASCII_RE = re.compile(r"[^\x00-\x7f]")
_BIDI_FORMAT_CHARS = frozenset("\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")
_ZERO_WIDTH_CHARS = {"\u200b", "\u200c", "\u200d"}
_DOCUMENT_FORMAT_LANGUAGES = {
    "asciidoc", "html", "json", "json with comments", "jsonc", "markdown", "md",
    "plaintext", "restructuredtext", "rich text format", "rst", "text", "xml",
}
_DOCUMENT_FORMAT_SUFFIXES = {
    ".adoc", ".asc", ".html", ".htm", ".json", ".md", ".markdown", ".rst", ".rtf",
    ".txt", ".xaml", ".xml",
}
_ICON_CONTEXT_TOKENS = {"font", "glyph", "icon", "nerd", "powerbar", "powerline", "statusbar"}
_UNICODE_UNASSIGNED_RE = _unicode_regex.compile(r"\A\p{Cn}\Z") if _unicode_regex else None
_CURRENT_UNICODE_ASSIGNMENT_AVAILABLE = (
    _UNICODE_UNASSIGNED_RE is not None or _unicode_data is not unicodedata
)


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


def _path_values(data: Any) -> list[str]:
    values = []
    for name in ("repo_file_path", "file_name", "path"):
        value = getattr(data, name, None)
        if value:
            values.append(str(value))
    return values


def _normalize_path_value(path: str) -> str:
    clean = path.replace("\\", "/").strip()
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", clean):
        parsed = urlsplit(clean)
        clean = unquote(parsed.path)
        if parsed.scheme.lower() == "s3":
            clean = clean.lstrip("/")
    return clean.strip("/")


def _canonical_language(value: Any) -> str:
    return re.sub(r"[\s_-]+", " ", str(value or "").strip().lower())


def _unicode_category(character: str) -> str:
    category = _unicode_data.category(character)
    if (
        category == "Cn"
        and _UNICODE_UNASSIGNED_RE is not None
        and not _UNICODE_UNASSIGNED_RE.fullmatch(character)
    ):
        return "Assigned"
    return category


def _is_document_format_record(language: Any, paths: list[str]) -> bool:
    if _canonical_language(language) in _DOCUMENT_FORMAT_LANGUAGES:
        return True
    return any(
        Path(_normalize_path_value(path)).suffix.lower() in _DOCUMENT_FORMAT_SUFFIXES
        for path in paths
        if _normalize_path_value(path)
    )


def _is_emoji_codepoint(character: str) -> bool:
    if not character:
        return False
    codepoint = ord(character)
    return (
        0x1F000 <= codepoint <= 0x1FAFF
        or 0x2600 <= codepoint <= 0x27BF
        or 0x2300 <= codepoint <= 0x23FF
    )


def _adjacent_emoji_base(content: str, index: int, direction: int) -> str:
    cursor = index + direction
    while 0 <= cursor < len(content):
        character = content[cursor]
        codepoint = ord(character)
        if character == "\ufe0f" or 0x1F3FB <= codepoint <= 0x1F3FF:
            cursor += direction
            continue
        return character
    return ""


def _is_expected_script_format_character(
    content: str, index: int, language: Any, paths: list[str]
) -> bool:
    character = content[index]
    if character == "\ufeff" and index == 0:
        return True
    if character == "\u00ad":
        previous = content[index - 1] if index else ""
        following = content[index + 1] if index + 1 < len(content) else ""
        return (
            previous.isalpha()
            and following.isalpha()
            and _is_document_format_record(language, paths)
        )
    if character in _BIDI_FORMAT_CHARS:
        line_start = max(content.rfind("\n", 0, index) + 1, index - 256)
        newline = content.find("\n", index)
        line_end = len(content) if newline < 0 else min(newline, index + 256)
        nearby = content[line_start:index] + content[index + 1:line_end]
        return any(
            "\u0590" <= candidate <= "\u08ff"
            or "\ufb1d" <= candidate <= "\ufdff"
            or "\ufe70" <= candidate <= "\ufeff"
            for candidate in nearby
        )
    if character not in _ZERO_WIDTH_CHARS:
        return False
    previous = content[index - 1] if index else ""
    following = content[index + 1] if index + 1 < len(content) else ""
    if (
        character == "\u200d"
        and _is_emoji_codepoint(_adjacent_emoji_base(content, index, -1))
        and _is_emoji_codepoint(_adjacent_emoji_base(content, index, 1))
    ):
        return True
    if character == "\u200b":
        return bool(re.fullmatch(r"[\u1780-\u17ff]", previous)) and bool(
            re.fullmatch(r"[\u1780-\u17ff]", following)
        )
    arabic = r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff\ufb50-\ufdff\ufe70-\ufeff]"
    return bool(re.fullmatch(arabic, previous)) and bool(re.fullmatch(arabic, following))


def _is_format_character_in_comment(content: str, index: int) -> bool:
    line_start = content.rfind("\n", 0, index) + 1
    line_end = content.find("\n", index)
    if line_end < 0:
        line_end = len(content)
    line = content[line_start:line_end]
    prefix = line[:index - line_start]
    stripped = line.lstrip()
    if stripped.startswith(("//", "#", "*", "<!--", "-- ")):
        return True
    return "//" in prefix or "<!--" in prefix


def _is_reviewable_format_character(
    content: str, index: int, language: Any, paths: list[str]
) -> bool:
    character = content[index]
    if character == "\u00ad" or character in _BIDI_FORMAT_CHARS:
        return _is_document_format_record(language, paths)
    if character not in _ZERO_WIDTH_CHARS:
        return False
    previous = content[index - 1] if index else ""
    following = content[index + 1] if index + 1 < len(content) else ""
    if _is_document_format_record(language, paths) and not (
        previous.isalnum() and following.isalnum()
    ):
        return True
    return content.count(character) == 1 and _is_format_character_in_comment(content, index)


def _abap_comment_start(line: str) -> int | None:
    """Return the start of an ABAP comment, keeping string literals executable."""
    if line.startswith("*"):
        return 0

    delimiter: str | None = None
    index = 0
    while index < len(line):
        character = line[index]
        if delimiter:
            if delimiter == "|" and character == "\\":
                index += 2
                continue
            if character == delimiter:
                if (
                    delimiter in {"'", "`"}
                    and index + 1 < len(line)
                    and line[index + 1] == delimiter
                ):
                    index += 2
                    continue
                delimiter = None
        elif character in {"'", "`", "|"}:
            delimiter = character
        elif character == '"':
            return index
        index += 1
    return None


def _contextual_character_counts(
    content: str, language: Any, paths: list[str]
) -> tuple[int, int, int, int]:
    is_abap = _canonical_language(language) == "abap"
    private_non_comment = 0
    private_in_comments = 0
    unassigned_count = 0
    private_positions: list[int] = []

    for match in _NON_ASCII_RE.finditer(content):
        category = _unicode_category(match.group())
        if category == "Co":
            private_positions.append(match.start())
        elif category == "Cn":
            unassigned_count += 1

    if not is_abap:
        private_non_comment = len(private_positions)
    else:
        cached_line_start = -1
        cached_line_end = -1
        cached_comment_start: int | None = None
        for position in private_positions:
            if not (cached_line_start <= position < cached_line_end):
                cached_line_start = content.rfind("\n", 0, position) + 1
                newline = content.find("\n", position)
                cached_line_end = len(content) if newline < 0 else newline + 1
                cached_comment_start = _abap_comment_start(
                    content[cached_line_start:cached_line_end]
                )
            relative_position = position - cached_line_start
            if cached_comment_start is not None and relative_position >= cached_comment_start:
                private_in_comments += 1
            else:
                private_non_comment += 1
    unexpected_format_count = sum(
        1
        for index, character in enumerate(content)
        if _unicode_category(character) == "Cf"
        and not _is_expected_script_format_character(content, index, language, paths)
        and not _is_reviewable_format_character(content, index, language, paths)
    )
    return private_non_comment, private_in_comments, unassigned_count, unexpected_format_count


def _private_use_is_expected(content: str, paths: list[str]) -> bool:
    normalized_paths = " ".join(_normalize_path_value(path).lower() for path in paths)
    if not any(token in normalized_paths for token in _ICON_CONTEXT_TOKENS):
        return False
    lowered = content.lower()
    return any(token in lowered for token in _ICON_CONTEXT_TOKENS)


def _contextual_character_anomaly_reason(
    content: str, language: Any, paths: list[str]
) -> str | None:
    private_non_comment, private_in_comments, unassigned_count, unexpected_format_count = (
        _contextual_character_counts(content, language, paths)
    )
    comment_limit = _PRIVATE_USE_COMMENT_MAX_COUNT
    format_limit = _CONTEXTUAL_FORMAT_CHAR_MAX_COUNT
    private_use_count = private_non_comment + private_in_comments
    expected_private_use = private_use_count > 0 and _private_use_is_expected(content, paths)
    is_abap = _canonical_language(language) == "abap"
    private_use_fails = not expected_private_use and (
        private_non_comment > 0
        or (is_abap and private_in_comments > comment_limit)
        or (not is_abap and private_in_comments > 0)
    )
    unassigned_fails = unassigned_count > 0 and (
        _CURRENT_UNICODE_ASSIGNMENT_AVAILABLE or private_use_fails
    )
    format_fails = unexpected_format_count > format_limit
    anomaly_count = (
        (private_use_count if private_use_fails else 0)
        + (unassigned_count if unassigned_fails else 0)
        + (unexpected_format_count if format_fails else 0)
    )
    if not anomaly_count:
        return None

    details = [
        f"count={anomaly_count}",
        f"format={unexpected_format_count if format_fails else 0}",
        f"private_use_non_comment={private_non_comment}",
        f"private_use_comment={private_in_comments}",
        f"unassigned={unassigned_count if unassigned_fails else 0}",
    ]
    if unassigned_count and not unassigned_fails:
        details.append(f"unassigned_observed={unassigned_count}")
    if expected_private_use:
        details.append("private_use_context=icon_or_font")
    if private_in_comments > comment_limit:
        details.append(f"private_use_comment_limit={comment_limit}")
    return ", ".join(details)


def _contextual_format_character_review_reason(
    content: str, language: Any, paths: list[str]
) -> str | None:
    count = sum(
        1
        for index, character in enumerate(content)
        if _unicode_category(character) == "Cf"
        and not _is_expected_script_format_character(content, index, language, paths)
        and _is_reviewable_format_character(content, index, language, paths)
    )
    return f"count={count}, context=document_boundary_or_comment" if count else None


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


def contextual_character_findings(data: Any) -> list[dict[str, str]]:
    """Hard findings for unexpected zero-width, private-use, or unassigned code points.

    Composed by ``LLMRepositoryCodeQualityPipelineV2``; the V1 pipeline keeps the
    original hard-rule set only.
    """
    content = getattr(data, "content", None)
    if not isinstance(content, str):
        return []
    reason = _contextual_character_anomaly_reason(
        content, _record_value(data, "language"), _path_values(data)
    )
    if not reason:
        return []
    return [_finding(
        "Contextual_Character_Anomaly",
        f"Unexpected zero-width format, private-use, or unassigned code point(s): {reason}.",
    )]


def input_content_review_findings(data: Any) -> list[dict[str, str]]:
    """Return review-level findings that report but never hard-gate a record."""
    content = getattr(data, "content", None)
    if not isinstance(content, str):
        return []
    reason = _contextual_format_character_review_reason(
        content, _record_value(data, "language"), _path_values(data)
    )
    if not reason:
        return []
    return [_finding(
        "Contextual_Format_Character_Review",
        f"Format character(s) in document boundary or comment context need review: {reason}.",
    )]
