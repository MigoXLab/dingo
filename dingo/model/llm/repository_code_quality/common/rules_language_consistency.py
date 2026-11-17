"""Language-label vs content consistency audit ported from the handover audit.

The signature engine and verdict logic are ported from
code_validator/src/tools/language_audit/sample_content_language_audit.py
(engine content-signatures-v3.3). Confirmed mismatches are hard findings;
suspected mismatches stay review-level so ambiguous dialects never hard-fail.
"""

from __future__ import annotations
import re
from typing import Any

ALIASES = {
    "c++": "cpp",
    "cplusplus": "cpp",
    "objectivec": "objective-c",
    "objc": "objective-c",
    "obj-c": "objective-c",
    "objective-c++": "objective-c++",
    "objc++": "objective-c++",
    "c#": "csharp",
    "f#": "fsharp",
    "f-sharp": "fsharp",
    "golang": "go",
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "rb": "ruby",
    "rs": "rust",
    "shell script": "shell",
    "bash": "shell",
}


def canonical(value: Any) -> str:
    normalized = re.sub(r"[\s_]+", "-", str(value or "").strip().lower())
    normalized = re.sub(r"-+", "-", normalized)
    return ALIASES.get(normalized, normalized)


ENGINE_VERSION = "content-signatures-v3.3"
DISPLAY_NAMES = {"power-query-m": "Power Query M", "avs/express": "AVS/Express"}
ALIASES.update({
    "c-plus-plus": "cpp", "c-sharp": "csharp", "f-sharp": "fsharp",
    "f-sharp-script": "fsharp", "objective-cpp": "objective-c++",
    "power-query-m": "power-query-m", "powershell": "powershell",
    # Dingo-side extension: dataset label taxonomies (e.g. linguist) use TSQL
    # for Transact-SQL content; without it every TSQL record confirms as a
    # mismatch against sql signatures.
    "tsql": "sql",
    "plpgsql": "sql",
})
# A related language can share the signatures below without being an alias.
COMPATIBLE = (
    frozenset({"c", "cpp", "objective-c", "objective-c++", "lpc", "mql4", "mql5"}),
    frozenset({"javascript", "typescript", "jsx", "tsx"}),
    frozenset({"java", "groovy"}),
    frozenset({"python", "cython", "starlark"}),
    frozenset({"haskell", "purescript", "elm", "idris"}),
)

# Unambiguous extensions only: declaration strength, never able to confirm a
# mismatch alone, but a label-vs-extension conflict surfaces as suspected.
AMBIGUOUS_EXTENSIONS = frozenset({".m", ".h", ".v", ".pl"})
# Document containers inherently mix languages (prose plus fenced code), so
# their content is never judged for language; only label-vs-suffix conflicts
# are reported.
DOCUMENT_SUFFIXES = {".txt": "text", ".text": "text", ".md": "markdown",
                     ".markdown": "markdown"}
DOCUMENT_LABELS = frozenset({"text", "markdown"})
EXTENSION_LANGUAGES = {
    ".java": "java", ".cs": "csharp", ".kt": "kotlin", ".kts": "kotlin",
    ".dart": "dart", ".swift": "swift", ".scala": "scala", ".go": "go",
    ".rs": "rust", ".py": "python", ".pyw": "python", ".rb": "ruby",
    ".ts": "typescript", ".tsx": "tsx", ".php": "php", ".hs": "haskell",
    ".pm": "perl",
    ".ex": "elixir", ".exs": "elixir", ".jl": "julia", ".r": "r",
    ".lua": "lua", ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".sql": "sql", ".service": "systemd", ".ps1": "powershell",
    ".groovy": "groovy", ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp",
    ".hpp": "cpp", ".c": "c", ".vue": "vue", ".css": "css", ".scss": "scss",
    ".less": "less", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".xml": "xml", ".md": "markdown", ".html": "html",
    ".htm": "html", ".ini": "ini",
}


PATH_FIELDS = ("repo_file_path", "file_name", "original_filename",
               "content_s3_path", "path", "file_path")


def record_path_suffix(record: dict[str, Any]) -> str:
    """Lowercase filename suffix of the record's path-like field, or ""."""
    for field in PATH_FIELDS:
        value = record.get(field)
        if not value:
            continue
        name = str(value).replace("\\", "/").strip().rstrip("/").rsplit("/", 1)[-1]
        if not name or "." not in name or name.startswith("."):
            continue
        return name[name.rfind("."):].lower()
    return ""


def record_path_languages(record: dict[str, Any]) -> list[str]:
    """Declaration languages implied by the record's file path, if any."""
    for field in PATH_FIELDS:
        value = record.get(field)
        if not value:
            continue
        name = str(value).replace("\\", "/").strip().rstrip("/").rsplit("/", 1)[-1]
        if not name or "." not in name or name.startswith("."):
            continue
        suffix = name[name.rfind("."):].lower()
        if suffix in AMBIGUOUS_EXTENSIONS:
            continue
        language = EXTENSION_LANGUAGES.get(suffix)
        if language:
            return [language]
    return []


# id, candidate languages, specificity, expression
SIGNATURES = (
    ("m-section", ("power-query-m",), "specific", r"(?m)^\s*section\s+[\w.]+\s*;"),
    ("m-shared", ("power-query-m",), "specific", r"(?m)^\s*shared\s+[\w.]+\s*="),
    ("avs-library", ("avs/express",), "specific", r"\bflibrary\s+\w+\s*\{"),
    ("avs-project", ("avs/express",), "specific", r"\bXP_COMM_PROJ\."),
    ("matlab-anonymous", ("matlab",), "specific", r"@\s*\([^)]*\)"),
    ("matlab-function", ("matlab",), "specific", r"(?m)^\s*function\s+(?:\[[^]\n]+\]|\w+)\s*=\s*\w+"),
    ("matlab-disp", ("matlab",), "supporting", r"\bdisp\s*\("),
    ("fsharp-module", ("fsharp",), "supporting", r"(?m)^\s*module\s+[\w.]+\s*$"),
    ("fsharp-let", ("fsharp",), "supporting", r"(?m)^\s*let\s+(?:rec\s+)?\w+(?:\s+\w+)*\s*=.*[^;{}]$"),
    ("python-def", ("python",), "specific", r"(?m)^\s*(?:async\s+)?def\s+\w+\s*\([^\n]*\)\s*(?:->[^:\n]+)?:(?!\s*[\w.:<>\[\]]+\s*=[^=])"),
    ("python-class", ("python",), "specific", r"(?m)^\s*class\s+\w+\s*(?:\([^\n]*\))?\s*:"),
    ("python-import", ("python",), "supporting", r"(?m)^\s*from\s+[\w.]+\s+import\s+"),
    ("java-package", ("java",), "specific", r"(?m)^\s*package\s+[\w.]+\s*;"),
    ("java-import", ("java",), "specific", r"(?m)^\s*import\s+(?:static\s+)?[\w.]+(?:\.\*)?\s*;"),
    ("public-class", ("java", "csharp"), "supporting", r"\bpublic\s+(?:(?:final|sealed|abstract|partial)\s+)?class\s+\w+"),
    ("csharp-using", ("csharp",), "specific", r"(?m)^\s*using\s+System(?:\.[\w.]+)?\s*;"),
    ("csharp-namespace", ("csharp", "cpp"), "supporting", r"\bnamespace\s+[\w.]+\s*[;{]"),
    ("c-include", ("c", "cpp", "objective-c", "objective-c++"), "supporting", r"(?m)^\s*#\s*include\b"),
    ("cpp-std", ("cpp",), "specific", r"\bstd::(?:vector|string|cout|cin|cerr|endl|map|set|unordered_map|unique_ptr|shared_ptr|make_unique|make_shared|array|function|optional|thread|mutex|sort|move|copy)\b"),
    ("cpp-template", ("cpp",), "specific", r"\btemplate\s*<[^>\n]+>"),
    ("cpp-class", ("cpp", "java", "csharp"), "supporting", r"\bclass\s+\w+(?:\s*:[^{\n]+)?\s*\{"),
    ("objc-interface", ("objective-c", "objective-c++"), "specific", r"@(?:interface|implementation|protocol)\s+\w+"),
    ("objc-end", ("objective-c", "objective-c++"), "specific", r"(?m)^\s*@end\b"),
    ("go-package", ("go",), "specific", r"(?m)^\s*package\s+\w+\s*$"),
    ("go-function", ("go",), "specific", r"(?m)^(?![^\n]*->)[ \t]*func\s+(?:\([^\n]+\)\s*)?\w+\s*\("),
    ("rust-function", ("rust",), "specific", r"\b(?:pub\s+)?fn\s+\w+\s*(?:<[^>]+>)?\s*\("),
    ("rust-use", ("rust",), "specific", r"(?m)^\s*use\s+[\w:]+::[\w:]+(?:::\*)?(?:\s+as\s+\w+)?\s*;"),
    ("rust-let-mut", ("rust",), "supporting", r"\blet\s+mut\s+\w+"),
    ("js-function", ("javascript", "typescript"), "supporting", r"\bfunction\s+\w+\s*\("),
    ("js-variable", ("javascript", "typescript"), "supporting", r"(?m)^\s*(?:export\s+)?(?:let|const|var)\s+\w+\s*="),
    ("js-arrow", ("javascript", "typescript"), "supporting", r"(?:\([^\n;]*\)|\b\w+)\s*=>"),
    ("ts-interface", ("typescript", "tsx"), "specific", r"\binterface\s+\w+(?:\s+extends\s+[^\n{]+)?\s*\{"),
    ("ts-type", ("typescript", "tsx"), "specific", r"(?m)^\s*(?:export\s+)?type\s+\w+\s*="),
    ("php-open", ("php",), "specific", r"<\?php\b"),
    ("ruby-def", ("ruby",), "specific", r"(?m)^\s*def\s+\w+(?:\([^\n]*\))?\s*$"),
    ("ruby-end", ("ruby",), "supporting", r"(?m)^\s*end\s*$"),
    ("ruby-attr", ("ruby",), "specific", r"(?m)^\s*attr_(?:accessor|reader|writer)\b"),
    ("ruby-module", ("ruby",), "supporting", r"(?m)^\s*module\s+\w+"),
    ("ruby-do-block", ("ruby",), "supporting", r"(?m)\bdo\s*\|\s*\w+[^|\n]*\|\s*$"),
    ("php-array", ("php",), "specific", r"\barray\s*\("),
    ("csharp-attribute", ("csharp",), "specific", r"(?m)^\s*\[\s*(?:assembly\s*:\s*)?(?:Obsolete|TestFixture|Test\w*|Http(?:Get|Post|Put|Delete)|Route|DataContract|Serializable|JsonProperty|MaxLength|Required)\b"),
    ("js-export", ("javascript", "typescript"), "specific", r"(?m)^\s*export\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\b"),
    ("js-import-from", ("javascript", "typescript"), "specific", r"(?m)^\s*import\s+[\w*{},\s]+?\s+from\s*['\" ]"),
    ("matlab-script-function", ("matlab",), "specific", r"(?m)^\s*function\s+\w+\s*$"),
    ("matlab-classdef", ("matlab",), "specific", r"(?m)^\s*classdef\s+\w+"),
    ("matlab-paren-end-range", ("matlab",), "specific", r"\(\s*\d+\s*:[^()\n]*\bend\b[^()\n]*\)|\(\s*:[^()\n]*\bend\b[^()\n]*\)"),
    ("matlab-bare-statement", ("matlab",), "specific", r"(?m)^\s*(?:figure|hold\s+on|hold\s+off|clc|clf|close\s+all|clear\s+all|drawnow)\s*;?\s*$"),
    ("matlab-builtin", ("matlab",), "supporting", r"\b(?:figure|clc|close\s+all|histogram|meshgrid|subplot|num2str|str2double|cellfun|arrayfun|xlim|ylim|xlabel|ylabel|legend|title|fprintf|sprintf|disp)\s*\("),
    ("systemd-unit-section", ("systemd",), "specific", r"(?m)^\[Unit\]\s*$"),
    ("systemd-service-section", ("systemd",), "specific", r"(?m)^\[Service\]\s*$"),
    ("systemd-install-section", ("systemd",), "specific", r"(?m)^\[Install\]\s*$"),
    ("systemd-directive", ("systemd",), "supporting", r"(?m)^\s*(?:ExecStart|ExecStop|ExecReload|WantedBy|RequiredBy|After|Before|Conflicts|DefaultDependencies|Restart|WorkingDirectory)\s*="),
    ("mumps-kids-header", ("mumps",), "specific", r"(?m)^\s*;;\d+(?:\.\d+)?;[^;\n]+;\*\*"),
    ("mumps-extrinsic", ("mumps",), "specific", r"\$\$[\w%]+\^[\w%]+"),
    ("mumps-do-caret", ("mumps",), "specific", r"(?m)^\s*[. \t]*D\s+[A-Za-z%]\w*\^[A-Za-z%]\w*"),
    ("mumps-dot-block", ("mumps",), "specific", r"(?m)^[ \t]+\.[ \t]*(?:[SKWNDQIFE]\b|SET|KILL|WRITE|QUIT|NEW|DO|IF|FOR|ELSE|;)"),
    ("mumps-pattern-match", ("mumps",), "specific", r"\?\d[\d.]*[NAU]"),
    ("mumps-global-ref", ("mumps",), "supporting", r"(?m)^\s*(?:SET|S|KILL|K|WRITE|W|DO|D|QUIT|Q|NEW|N)\s+\^%?\w+"),
    ("kotlin-fun", ("kotlin",), "specific", r"(?m)^\s*(?:@\w+\s+)?(?:private\s+|internal\s+|public\s+|protected\s+)?(?:open\s+|override\s+|final\s+|suspend\s+|inline\s+|operator\s+|infix\s+)*fun\s+\w+"),
    ("kotlin-data-class", ("kotlin",), "specific", r"\bdata\s+class\s+\w+"),
    ("kotlin-dotted-package", ("kotlin",), "supporting", r"(?m)^\s*package\s+\w+\.[\w.]+\s*$"),
    ("dart-package-import", ("dart",), "specific", r"(?m)^\s*import\s+['\" ]*package:"),
    ("dart-main", ("dart",), "specific", r"(?m)^\s*(?:Future<void>|void)\s+main\s*\("),
    ("dart-directives", ("dart",), "supporting", r"(?m)^\s*(?:part|library|export)\s+[ \t]*[;'\" ]"),
    ("dart-bare-import", ("dart",), "specific", r"(?m)^\s*import\s+[ \t]*;"),
    ("swift-func-arrow", ("swift",), "specific", r"(?m)^\s*(?:@\w+\s+)?(?:public\s+|private\s+|fileprivate\s+|internal\s+|open\s+|static\s+|override\s+|final\s+|mutating\s+)*(?:func|init)\s*[(<\w][^{\n]*->\s*[\w?<>\[\]:. ]+\s*\{"),
    ("swift-guard", ("swift",), "specific", r"\bguard\s+(?:let|var)\s+\w+"),
    ("scala-case-class", ("scala",), "specific", r"(?m)^\s*case\s+class\s+\w+"),
    ("scala-object", ("scala",), "specific", r"(?m)^\s*object\s+\w+[^\n]*\{\s*$"),
    ("shell-function", ("shell",), "specific", r"(?m)^\s*(?:function\s+\w+|[A-Za-z_]\w*)\s*\(\)\s*\{"),
    ("shell-if-then", ("shell",), "specific", r"(?m)^\s*if\s+\[[^\n]*\]\s*;\s*then\b"),
    ("shell-fi", ("shell",), "supporting", r"(?m)^\s*fi\s*$"),
    ("sql-create-table", ("sql",), "specific", r"(?mi)^\s*CREATE\s+(?:TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\w.\"`\[]+"),
    ("sql-select-from", ("sql",), "specific", r"(?mi)\bSELECT\s+[\w.*,\s`\"\[]+?\s+FROM\s+"),
    ("r-library", ("r",), "specific", r"(?m)^\s*(?:library|require)\s*\(\s*[\w.]+\s*\)"),
    ("r-arrow-assign", ("r",), "specific", r"(?m)^\s*[\w.$\"\[\]]+\s*<-"),
    ("lua-local-function", ("lua",), "specific", r"(?m)^\s*local\s+function\s+\w+"),
    ("lua-require", ("lua",), "specific", r"(?m)^\s*(?:local\s+\w+\s*=\s*)?require\s*[\"(\s]"),
    ("hs-signature", ("haskell",), "specific", r"(?m)^\w+\s*::\s"),
    ("hs-import-paren", ("haskell",), "specific", r"(?m)^\s*import\s+[\w.]+\s*\("),
    ("ex-defmodule", ("elixir",), "specific", r"(?m)^\s*defmodule\s+\w"),
    ("ex-def-do", ("elixir",), "specific", r"(?m)^\s*defp?\s+\w+[^\n]*\bdo\s*$"),
    ("julia-struct", ("julia",), "specific", r"(?m)^\s*(?:mutable\s+)?struct\s+\w+\s*$"),
    ("julia-using", ("julia",), "specific", r"(?m)^\s*using\s+\w+\s*$"),
    ("perl-my", ("perl",), "specific", r"(?m)^\s*my\s+\$\w+"),
    ("perl-use-strict", ("perl",), "specific", r"(?m)^\s*use\s+(?:strict|warnings|utf8|lib)\s*;"),
    ("powershell-param", ("powershell",), "specific", r"(?mi)^\s*param\s*\("),
    ("powershell-cmdlet", ("powershell",), "specific", r"\bWrite-(?:Host|Output|Error|Verbose)\b|\bGet-\w+Property\b"),
)
COMPILED_SIGNATURES = tuple(
    (rule_id, languages, strength, re.compile(pattern))
    for rule_id, languages, strength, pattern in SIGNATURES
)

# Neutral masking preserves offsets and avoids choosing a lexer using the label
# we are trying to audit. These are conservative common delimiters, not a parser.
NON_CODE_RE = re.compile(
    r'"""[\s\S]*?(?:"""|$)'
    r"|/\*[\s\S]*?(?:\*/|$)|//[^\n]*"
    r"|(?m:^[ \t]*\#(?![ \t]*(?:include|import|define|if|else|endif|pragma|!))[^\n]*)"
    r"|(?m:^[ \t]*%[^\n]*)"
    r'|"(?:\\[\s\S]|[^"\\\n])*"|`[^`]*`'
    + "|" + chr(39) * 3 + r"[\s\S]*?(?:" + chr(39) * 3 + "|$)"
    + "|" + chr(39) + r"(?:\\[^\n]|[^" + chr(39) + r"\\\n])*" + chr(39)
)


def mask_non_code(content: str) -> str:
    return NON_CODE_RE.sub(lambda match: re.sub(r"[^\n\r]", " ", match.group()), content)


# Masked string literals become space runs; huge ones (e.g. 164KB .po
# catalogs) drive quadratic backtracking in signatures whose \s* prefixes can
# cross newlines and re-anchor per line. Whitespace runs (newlines included)
# are compacted to a short fixed form that preserves one line anchor. No
# signature needs >32 contiguous blanks; evidence byte offsets become
# approximate on compacted files.
_WHITESPACE_RUN = re.compile(r"\s{32,}")


def content_evidence(content: str) -> list[dict[str, Any]]:
    masked = _WHITESPACE_RUN.sub(" " * 16 + "\n" + " " * 16, mask_non_code(content))
    evidence = []
    for rule_id, languages, strength, pattern in COMPILED_SIGNATURES:
        match = pattern.search(masked)
        if match:
            evidence.append({
                "rule_id": rule_id, "languages": list(languages),
                "strength": strength, "source": "content",
                "start_byte": len(content[:match.start()].encode("utf-8")),
                "end_byte": len(content[:match.end()].encode("utf-8")),
            })
    # A shebang is a declaration, not executable syntax evidence.
    first_line = content.split("\n", 1)[0]
    if first_line.startswith("#!"):
        for name, pattern in (("python", r"\bpython[\d.]*\b"),
                              ("shell", r"\b(?:ba|da|z|k)?sh\b"),
                              ("ruby", r"\bruby\b"), ("javascript", r"\bnode\b")):
            if re.search(pattern, first_line):
                evidence.append({"rule_id": "shebang", "languages": [name],
                                 "strength": "declaration", "source": "shebang"})
                break
    return evidence


def _related(left: str, right: str) -> bool:
    return left == right or any({left, right} <= group for group in COMPATIBLE)


def _collapsed_family(strong: "set[str]") -> "frozenset[str] | None":
    """The related family covering every strong name, or None when they conflict."""
    if not strong:
        return None
    for name in strong:
        family = {other for other in strong if _related(name, other)}
        if family == strong:
            return frozenset(family)
    return None


def _classify_record(
    record: dict[str, Any], *, max_chars: int = 200_000,
) -> dict[str, Any]:
    """Audit the final label without using it to constrain detection candidates.

    Enry contributes advisory file candidates; its uniqueness is not confidence.
    No parser or model is downloaded or initialized for the builtin backend.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    raw_content = record.get("content")
    raw_label = record.get("language")
    language = canonical(raw_label)
    result = {
        "language": raw_label, "canonical_language": language,
        "engine_version": ENGINE_VERSION,
        "content_detected": [], "evidence": [], "file_candidates": [],
        "warnings": [], "status": "undetermined", "reason": "insufficient content evidence",
    }
    if not isinstance(raw_content, str) or not isinstance(raw_label, str) or not language:
        result["reason"] = "content and nonempty language must be strings"
        return result
    if any(0xD800 <= ord(char) <= 0xDFFF for char in raw_content):
        result["reason"] = "content contains invalid Unicode surrogates"
        return result
    # Document containers (.txt/.md) mix prose with many languages by design,
    # so content evidence cannot judge their language; only a conflict between
    # a code label and the declared document type is worth surfacing.
    document_declared = DOCUMENT_SUFFIXES.get(record_path_suffix(record))
    if document_declared:
        if language not in DOCUMENT_LABELS:
            result.update(status="suspected_mismatch",
                          reason="filename suffix declares a document container; "
                                 f"{language} label conflicts with it")
        else:
            result["reason"] = "document container suffix; content language intentionally not judged"
        return result
    content = raw_content[:max_chars]
    result["content_truncated"] = len(raw_content) > max_chars
    evidence = content_evidence(content)
    path_languages = record_path_languages(record)
    if path_languages:
        evidence.append({"rule_id": "path-extension", "languages": path_languages,
                         "strength": "declaration", "source": "filename",
                         "start_byte": 0, "end_byte": 0})
    result["evidence"] = evidence
    # Filename evidence may propose candidates, but container review only
    # reacts to content-borne candidates so extension hits do not balloon mixed.
    content_candidates = {name for item in evidence if item["source"] != "filename"
                          for name in item["languages"]}
    candidates = {name for item in evidence for name in item["languages"]}
    result["candidate_languages"] = sorted(candidates)
    result["content_detected"] = [DISPLAY_NAMES.get(name, name) for name in sorted(candidates)]
    # Independent specific signals must agree. Shared syntax and declarations
    # cannot confirm a mismatch, and compatible dialects retain uncertainty.
    strong = {name for item in evidence if item["strength"] == "specific"
              for name in item["languages"]}
    if strong:
        result["content_detected"] = [DISPLAY_NAMES.get(name, name) for name in sorted(strong)]
    supporting = [item for item in evidence if item["strength"] == "supporting"
                  and language in item["languages"]]
    supported_label = language in strong or len(supporting) >= 2
    container = language in {"markdown", "jupyter-notebook", "html", "vue", "svelte"}
    embedded = bool(re.search(r"(?m)^\s*```|<script\b", content))
    if strong and any(not _related(a, b) for a in strong for b in strong):
        result.update(status="mixed_content", reason="conflicting specific language signatures")
    elif embedded or (container and content_candidates):
        result.update(status="mixed_content", reason="embedded code requires container-aware review")
    elif supported_label and language in candidates and (not strong or all(_related(language, name) for name in strong)):
        result.update(status="consistent", reason="content evidence supports the declared language")
    elif language in candidates and not strong:
        result["reason"] = "shared or isolated syntax cannot verify the declared language"
    elif candidates:
        # Dialect siblings (objective-c/objective-c++, ts/tsx) collapse into one
        # family for confirmation; family-internal specific rules still must be
        # independent (two distinct rule ids).
        family = _collapsed_family(strong)
        specific_rules = {item["rule_id"] for item in evidence
                          if item["strength"] == "specific"
                          and family is not None and set(item["languages"]) <= family}
        support_rules = {item["rule_id"] for item in evidence
                         if item["strength"] == "supporting"
                         and set(item["languages"]) <= (family or strong)}
        # Matlab audited pairs: anonymous function plus disp, or a script-form
        # function plus a builtin call, are independent syntax+library evidence.
        paired_matlab = ("matlab-anonymous" in specific_rules and "matlab-disp" in support_rules) or (
            "matlab-script-function" in specific_rules
            and bool({"matlab-builtin", "matlab-disp"} & support_rules)
        )
        filename_only = all(item["source"] == "filename" for item in evidence)
        if family and (len(specific_rules) >= 2 or paired_matlab) and not any(_related(language, name) for name in strong):
            result.update(status="confirmed_mismatch", reason="independent specific content signatures support another language")
        else:
            result.update(status="suspected_mismatch",
                          reason="file extension conflicts with the declared language; content evidence insufficient"
                                 if filename_only else "alternative or ambiguous candidates require review")
    elif result["file_candidates"]:
        result["reason"] = "file candidates alone cannot verify content language"
    if result["content_truncated"] and result["status"] in {"consistent", "confirmed_mismatch"}:
        result.update(status="undetermined", reason="content scan limit reached; whole-file language was not verified")
    return result


def _record_dict(data: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "content": getattr(data, "content", None),
        "language": getattr(data, "language", None),
    }
    for field in PATH_FIELDS:
        value = getattr(data, field, None)
        if isinstance(value, str) and value:
            record[field] = value
    meta = getattr(data, "file_meta", None)
    if isinstance(meta, dict):
        for field in PATH_FIELDS:
            if field in record:
                continue
            value = meta.get(field)
            if isinstance(value, str) and value:
                record[field] = value
    return record


def _apply_dingo_adjustments(verdict: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Dingo-side tweaks over the ported verdict to cut known false-positive noise.

    The handover audit keeps these shapes at suspected_mismatch; for dataset
    cleaning they are dialect/suffix/signature collisions, not mislabels.
    """
    if verdict["status"] != "suspected_mismatch":
        return verdict
    language = canonical(record.get("language"))
    detected = set(verdict.get("content_detected") or [])
    evidence = verdict.get("evidence") or []
    specific_ids = {item["rule_id"] for item in evidence if item.get("strength") == "specific"}
    basenames = []
    for field in PATH_FIELDS:
        value = record.get(field)
        if isinstance(value, str):
            basenames.append(value.replace("\\", "/").rsplit("/", 1)[-1].lower())
    if language == "cmake" and any(name == "cmakelists.txt" for name in basenames):
        return {**verdict, "status": "consistent",
                "reason": "dingo adjustment: CMakeLists.txt suffix is conventional for cmake"}
    if language in {"tsx", "jsx"} and detected and all(_related(language, name) for name in detected):
        return {**verdict, "status": "consistent",
                "reason": "dingo adjustment: tsx/jsx are supersets of the js/ts signatures"}
    if (
        detected == {"shell"}
        and specific_ids <= {"shell-function"}
        and language in {"javascript", "typescript", "jsx", "tsx"}
    ):
        return {**verdict, "status": "consistent",
                "reason": "dingo adjustment: empty-argument JS functions collide with shell-function signature"}
    return verdict


def _verdict(data: Any) -> dict[str, Any] | None:
    record = _record_dict(data)
    if not isinstance(record.get("content"), str) or not isinstance(record.get("language"), str):
        return None
    return _apply_dingo_adjustments(_classify_record(record), record)


def language_consistency_findings(data: Any) -> list[dict[str, str]]:
    """Hard findings for content-confirmed language mislabels."""
    verdict = _verdict(data)
    if not verdict or verdict["status"] != "confirmed_mismatch":
        return []
    detected = ", ".join(verdict.get("content_detected") or []) or "unknown"
    return [{
        "label": "Effectiveness.Language_Content_Mismatch",
        "reason": (
            f"Declared language {verdict['language']!r} contradicts content signatures "
            f"(detected: {detected}); {verdict.get('reason', '')}."
        ),
    }]


def language_consistency_review_findings(data: Any) -> list[dict[str, str]]:
    """Review-level findings for suspected (not confirmed) language mislabels."""
    verdict = _verdict(data)
    if not verdict or verdict["status"] != "suspected_mismatch":
        return []
    detected = ", ".join(verdict.get("content_detected") or []) or "unknown"
    return [{
        "label": "Effectiveness.Language_Mismatch_Review",
        "reason": (
            f"Declared language {verdict['language']!r} needs review against content evidence "
            f"(candidates: {detected}); {verdict.get('reason', '')}."
        ),
    }]
