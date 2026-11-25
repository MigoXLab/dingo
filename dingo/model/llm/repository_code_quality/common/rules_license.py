"""License declaration detection for repository code records.

License header blocks are data-cleaning targets: the whole header block
(including copyright lines mixed into it) is meant to be stripped downstream.
Four shapes are explicitly NOT license findings:

1. copyright-only notices (copyright / (c) / All rights reserved);
2. confidential or restrictive clauses that grant nothing;
3. references to a license (see LICENSE file, License sections, tags, URLs);
4. literal uses of the word "license" unrelated to copyright licensing.

Reference shapes that carry no granting clauses are emitted as review-level
findings so humans can resolve them; the other three shapes stay silent.

Detection is two-stage: this module produces candidates (family, line span, and a
bounded excerpt) and ``LLMRepositoryLicenseReview`` decides whether the quoted
region is licensing boilerplate or license wording carried by data content.
"""

from __future__ import annotations
import re
from typing import Any

HEAD_LINE_LIMIT = 100
BLOCK_EXPANSION_LIMIT = 60
EXCERPT_MAX_LINES = 40
EXCERPT_LINE_CHARS = 200
EXCERPT_MAX_CHARS = 1600
# LICENSE, COPYING, LICENSE.txt, LICENSE-MIT, COPYING.LESSER ... but never source
# files that merely carry the word (license_manager.py, LicenseUtils.java).
_LICENSE_FILE_SUFFIX = (
    r"(?:txt|md|markdown|rst|adoc|lesser|\d+(?:\.\d+)*|"
    r"(?:apache|mit|gpl|lgpl|agpl|bsd|mpl|epl|cddl|isc|zlib|unlicense|cc0)"
    r"(?:[._-]\d+(?:\.\d+)*)?)"
)
LICENSE_FILE_RE = re.compile(
    rf"(?i)^(?:licen[cs]e|copying)(?:[._-]{_LICENSE_FILE_SUFFIX})*$"
)
_MARKER_PREFIX_RE = re.compile(r"^[/*#;%'\"!=<>\-\s]+")
# Continuation test for line-comment blocks: only license wording keeps the block open.
_LICENSE_TEXT_RE = re.compile(
    r"(?i)licen[cs]e|copyright|\u00a9|warrant|redistribut|free software|permission|"
    r"hereby granted|merchantab|fitness|public domain|spdx|all rights reserved|"
    r"terms (?:of|and)|obtain a copy|compliance|distributed under|governed by|you may"
)

_GPL_MENTION = re.compile(r"GNU General Public License", re.I)
_GPL_CONTEXT = re.compile(
    r"free software|redistribut|terms of|later version|along with this program", re.I
)

LICENSE_FAMILIES: tuple[tuple[str, object], ...] = (
    ("AGPL", re.compile(r"GNU Affero General Public License", re.I)),
    ("LGPL", re.compile(r"GNU (?:Lesser|Library) General Public License", re.I)),
    ("GPL", ("gnu-gpl",)),
    ("APACHE_2_0", re.compile(
        r"Licensed under the Apache License, Version 2\.0|apache\.org/licenses/LICENSE-2\.0", re.I
    )),
    ("MIT", re.compile(
        r"Permission is hereby granted, free of charge, to any person obtaining a copy", re.I
    )),
    ("SPDX_IDENTIFIER", re.compile(r"SPDX-License-Identifier:\s*[^\s,;]+", re.I)),
    ("BSD_CLAUSES", re.compile(
        r"Redistribution and use in source and binary forms, with or without modification", re.I
    )),
    ("BSD_GO_STYLE", re.compile(r"governed by a BSD-style license", re.I)),
    ("MPL", re.compile(r"Mozilla Public License,? ?v(?:ersion)?\.? ?2\.0|mozilla\.org/MPL/2\.0", re.I)),
    ("EPL", re.compile(r"Eclipse Public License", re.I)),
    ("CDDL", re.compile(r"Common Development and Distribution License", re.I)),
    ("WTFPL", re.compile(r"Do What The? Fuck You Want To Public License|\bWTFPL\b", re.I)),
    ("ISC", re.compile(
        r"Permission to use, copy, modify, and(?:/or)? distribute this software for any purpose|"
        r"\bISC License\b", re.I
    )),
    ("ZLIB", re.compile(
        r"freely, including commercially|Altered source versions must be plainly marked as such|"
        r"zlib/libpng license", re.I
    )),
    ("RUST_DUAL", ("rust-dual",)),
    ("CREATIVE_COMMONS", re.compile(
        r"Creative Commons (?:Attribution|BY\b|BY-|NonCommercial|NoDerivatives|ShareAlike|"
        r"CC0|Public Domain|License)|"
        r"\bCC(?:-|\s)?BY(?:-SA|-NC(?:-ND)?|-ND)?(?:-|\s)?\d",
        re.I,
    )),
    ("UNLICENSE", re.compile(
        r"free and unencumbered software released into the public domain", re.I
    )),
    ("PUBLIC_DOMAIN", re.compile(
        r"released (?:in|into) the public domain|public domain dedication|\bCC0\b", re.I
    )),
)

_LICENSE_REFERENCE_PATTERNS = (
    re.compile(r"(?i)creativecommons\.org/licenses/"),
    re.compile(r"(?im)^\s*(?:[/#*;]+|//)?\s*licen[cs]e\s*:\s*\S"),
    re.compile(r"(?i)@licen[cs]e\b"),
    re.compile(r"(?i)see the (?:licen[cs]e|copying) file"),
    re.compile(r"(?im)^\s{0,3}#{1,6}\s*licen[cs]e\s*$"),
    re.compile(
        r"(?i)(?:licen[cs]ed|released|distributed|available) under(?: the terms of)?"
        r"(?: the )?[A-Za-z0-9.+ -]{2,40}licen[cs]e\b"
    ),
    re.compile(r"(?i)licen[cs]e (?:is )?(?:available|provided|included) (?:in|at|under)\b"),
)

_RESTRICTIVE_PATTERNS = (
    re.compile(r"(?i)\bconfidential\b"),
    re.compile(r"(?i)no licen[cs]e is granted"),
    re.compile(r"(?i)may not (?:be )?(?:copied|reproduced|distributed|modified)"),
    re.compile(r"(?i)internal use only"),
    re.compile(r"(?i)proprietary(?: and confidential)?\b"),
)

_COPYRIGHT_ONLY_PATTERNS = (
    re.compile(r"(?i)\bcopyright\b"),
    re.compile(r"\u00a9"),
    re.compile(r"(?i)\ball rights reserved\b"),
)

# Line-comment prefixes plus block-comment delimiters, so a license block written
# inside /* */, --[[ ]], (* *) or =begin/=end expands across its continuation lines.
_LINE_COMMENT_PREFIXES = ("//", "*", "#", ";", "--", "%", "'", '"', ")")
_BLOCK_COMMENTS = (("/*", "*/"), ("--[[", "]]"), ("(*", "*)"), ("<!--", "-->"), ("=begin", "=end"))


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


def _is_license_document(data: Any) -> bool:
    """True when the record's file name is itself a license document."""
    for path in _path_values(data):
        name = path.replace("\\", "/").strip().rstrip("/").rsplit("/", 1)[-1]
        if LICENSE_FILE_RE.match(name):
            return True
    return False


def _match_family(family: str, region: str) -> re.Match | None:
    if family == "GPL":
        if _GPL_MENTION.search(region) and _GPL_CONTEXT.search(region):
            return _GPL_MENTION.search(region)
        return None
    if family == "RUST_DUAL":
        if re.search(r"(?i)licensed under either of|dual-licen[cs]ed", region) and re.search(
            r"\bMIT\b", region
        ) and re.search(r"(?i)apache licen[cs]e", region):
            return re.search(r"(?i)licensed under either of|dual-licen[cs]ed", region)
        return None
    pattern = next(spec for name, spec in LICENSE_FAMILIES if name == family)
    return pattern.search(region)  # type: ignore[union-attr]


def _matched_families(region: str) -> list[tuple[str, re.Match]]:
    matches = []
    for family, _ in LICENSE_FAMILIES:
        match = _match_family(family, region)
        if match:
            matches.append((family, match))
    return matches


def _comment_line_flags(lines: list[str]) -> tuple[list[bool], list[bool]]:
    """Mark comment lines and, separately, lines inside a delimited block comment."""
    flags = []
    block_flags = []
    closer = None
    for line in lines:
        stripped = line.strip()
        if closer is not None:
            flags.append(True)
            block_flags.append(True)
            if closer in stripped:
                closer = None
            continue
        opener = next((pair for pair in _BLOCK_COMMENTS if stripped.startswith(pair[0])), None)
        if opener is not None:
            flags.append(True)
            block_flags.append(True)
            if opener[1] not in stripped[len(opener[0]):]:
                closer = opener[1]
            continue
        flags.append(bool(stripped) and stripped.startswith(_LINE_COMMENT_PREFIXES))
        block_flags.append(False)
    return flags, block_flags


def _continues_license_block(line: str, is_comment: bool, in_block: bool) -> bool:
    """Block interiors always continue; line comments must still read as license text."""
    if in_block:
        return True
    if not is_comment:
        return False
    text = _MARKER_PREFIX_RE.sub("", line.strip()).strip()
    return not text or bool(_LICENSE_TEXT_RE.search(text))


def _header_block_span(content: str, match_start: int) -> tuple[int, int]:
    lines = content.splitlines()
    flags, block_flags = _comment_line_flags(lines)
    offset = 0
    match_line = len(lines) - 1
    for index, line in enumerate(lines):
        if offset <= match_start < offset + len(line) + 1:
            match_line = index
            break
        offset += len(line) + 1

    start = match_line
    for _ in range(BLOCK_EXPANSION_LIMIT):
        if start == 0 or not _continues_license_block(lines[start - 1], flags[start - 1], block_flags[start - 1]):
            break
        start -= 1
    end = match_line
    for _ in range(BLOCK_EXPANSION_LIMIT):
        if end + 1 >= len(lines) or not _continues_license_block(lines[end + 1], flags[end + 1], block_flags[end + 1]):
            break
        end += 1
    return start + 1, end + 1


def _excerpt(lines: list[str], start: int, end: int) -> str:
    window = lines[start - 1:end][:EXCERPT_MAX_LINES]
    return "\n".join(line[:EXCERPT_LINE_CHARS] for line in window)[:EXCERPT_MAX_CHARS]


def license_candidates(data: Any) -> list[dict[str, Any]]:
    """Stage one: license declaration candidates for model adjudication."""
    content = getattr(data, "content", None)
    if not isinstance(content, str):
        return []
    lines = content.splitlines()
    region = "\n".join(lines[:HEAD_LINE_LIMIT])
    matches = _matched_families(region)
    license_document = _is_license_document(data)
    if not matches and not license_document:
        return []
    families = [family for family, _ in matches]
    if license_document:
        # The whole file is license text rather than a header block inside code.
        families = families or ["LICENSE_FILE"]
        start, end = 1, max(len(lines), 1)
    else:
        first_start = min(match.start() for _, match in matches)
        start, end = _header_block_span(content, first_start)
    return [{
        "families": families,
        "line_start": start,
        "line_end": end,
        "license_document": license_document,
        "excerpt": _excerpt(lines, start, end),
        "summary": (
            f"license declaration block ({', '.join(families)}) spans lines {start}-{end}"
        ),
    }]


def license_rule_finding(candidate: dict[str, Any]) -> dict[str, str]:
    """Deterministic hard finding for one confirmed license candidate."""
    return {
        "label": "Security.License_Header",
        "reason": (
            f"License declaration block ({', '.join(candidate['families'])}) spans lines "
            f"{candidate['line_start']}-{candidate['line_end']}; "
            "cleaning target: remove the whole header block including embedded copyright lines."
        ),
    }


def license_findings(data: Any) -> list[dict[str, str]]:
    """Deterministic findings, kept as the fail-open verdict without model review."""
    candidates = license_candidates(data)
    return [license_rule_finding(candidates[0])] if candidates else []


def license_review_findings(data: Any) -> list[dict[str, str]]:
    """Review-level findings for license references without granting clauses."""
    content = getattr(data, "content", None)
    if not isinstance(content, str):
        return []
    lines = content.splitlines()
    region = "\n".join(lines[:HEAD_LINE_LIMIT])
    if _matched_families(region) or _is_license_document(data):
        return []
    for pattern in _LICENSE_REFERENCE_PATTERNS:
        match = pattern.search(region)
        if match:
            return [{
                "label": "Security.License_Reference_Review",
                "reason": (
                    "License reference without granting clauses needs human resolution: "
                    f"{match.group(0)!r}."
                ),
            }]
    return []


def non_license_shapes(data: Any) -> list[str]:
    """Diagnostic helper: which non-license shapes a record exhibits."""
    content = getattr(data, "content", None)
    if not isinstance(content, str):
        return []
    lines = content.splitlines()
    region = "\n".join(lines[:HEAD_LINE_LIMIT])
    shapes = []
    if any(pattern.search(region) for pattern in _RESTRICTIVE_PATTERNS):
        shapes.append("restrictive_or_confidential")
    if any(pattern.search(region) for pattern in _COPYRIGHT_ONLY_PATTERNS):
        shapes.append("copyright_only")
    if any(pattern.search(region) for pattern in _LICENSE_REFERENCE_PATTERNS):
        shapes.append("license_reference")
    return shapes
