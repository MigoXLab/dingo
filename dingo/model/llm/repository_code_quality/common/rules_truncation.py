"""Rule-first repository code truncation detection."""

from __future__ import annotations
import re
import threading
from pathlib import Path
from typing import Any

MIN_CONTENT_CHARS = 80
MAX_CONTENT_CHARS = 2_000_000
TAIL_BYTES = 512

_LANGUAGE_ALIASES = {
    "c++": "cpp", "c plus plus": "cpp", "c#": "csharp", "c sharp": "csharp",
    "f sharp": "f#", "golang": "go", "javascript jsx": "javascript", "jsx": "javascript",
    "objective c": "objc", "objective-c": "objc", "objectivec": "objc",
    "shell": "bash", "typescript jsx": "tsx",
}
_DIRECT_PARSER_NAMES = frozenset(
    """
    actionscript ada agda apex astro bibtex bitbake c cairo clarity clojure cmake
    cpp csharp css cuda d dart dockerfile elixir elm erlang fennel fish fortran
    gleam glsl gn go graphql groovy hack haskell haxe hcl hlsl html ini janet java
    javascript json jsonnet julia kotlin llvm lua markdown matlab mermaid meson
    netlinx nim ninja nix ocaml org pascal perl php pony powershell prisma puppet
    purescript python r racket ruby rust scala scheme scss smali sparql sql squirrel
    starlark svelte swift tcl thrift toml tsx twig typescript verilog vhdl vue
    xcompose xml yaml zig
    """.split()
)
_PARSER_CAPABILITIES = {name: (name,) for name in _DIRECT_PARSER_NAMES}
_PARSER_CAPABILITIES.update({
    "assembly": ("asm",), "bash": ("bash",), "cap'n proto": ("capnp",),
    "common lisp": ("commonlisp",), "emacs lisp": ("elisp",), "f#": ("fsharp",),
    "formatted": ("fortran",), "fortran free form": ("fortran",),
    "gd": ("gdscript",), "gdscript": ("gdscript",), "git attributes": ("gitattributes",),
    "go module": ("gomod",), "ignore list": ("gitignore",),
    "linker script": ("linkerscript",), "makefile": ("make",), "objc": ("objc",),
    "open policy agent": ("rego",), "protocol buffer": ("proto",),
    "restructuredtext": ("rst",), "solidity": ("solidity",), "star": ("starlark",),
    "systemverilog": ("verilog",), "tex": ("latex",), "vim script": ("vim",),
    "webassembly": ("wat", "wast"),
})
_STRUCTURED_LANGUAGES = {
    "asciidoc", "csv", "html", "ini", "json", "json with comments",
    "jsonc", "markdown", "md", "plaintext", "restructuredtext", "rich text format",
    "rst", "text", "toml", "xml", "yaml", "yml",
}
_STRUCTURED_SUFFIXES = {
    ".adoc", ".asc", ".cfg", ".conf", ".csv", ".html", ".htm", ".ini", ".json",
    ".lock", ".md", ".markdown", ".properties", ".rst", ".rtf", ".toml", ".txt",
    ".xaml", ".xml", ".yaml", ".yml",
}
_STRUCTURED_NAMES = {
    "cargo.lock", "gemfile.lock", "package-lock.json", "pdm.lock", "pnpm-lock.yaml",
    "poetry.lock", "yarn.lock",
}
_TRAILING_OPERATOR = re.compile(
    r"(?:=>|->|&&|\|\||==|!=|<=|>=|\+=|-=|\*=|/=|%=|::|\?\?|[=+*/%&|^!<>.\\-])$"
)
_PARSERS: dict[str, Any | None] = {}
_PARSER_LOCKS: dict[str, threading.Lock] = {}
_PARSER_INIT_LOCK = threading.Lock()


def _value(data: Any, *names: str) -> Any:
    for name in names:
        value = getattr(data, name, None)
        if value is not None:
            return value
    return None


def _canonical_language(value: Any) -> str:
    normalized = re.sub(r"[\s_-]+", " ", str(value or "").strip().lower())
    return _LANGUAGE_ALIASES.get(normalized, normalized)


def _parser_names(data: Any) -> tuple[str, ...]:
    language = _canonical_language(_value(data, "language"))
    file_name = str(_value(data, "file_name", "repo_file_path", "path") or "")
    suffix = Path(file_name).suffix.lower()
    if language == "c" and suffix in {".cc", ".cpp", ".cxx", ".hpp", ".hh", ".hxx"}:
        return ("cpp",)
    if language in {"c", "cpp"} and suffix == ".h":
        return (language, "cpp" if language == "c" else "c")
    if language == "typescript" and suffix == ".tsx":
        return ("tsx",)
    return _PARSER_CAPABILITIES.get(language, ())


def _is_structured(data: Any) -> bool:
    language = _canonical_language(_value(data, "language"))
    file_name = str(_value(data, "file_name", "repo_file_path", "path") or "")
    path = Path(file_name)
    name = path.name.lower()
    return (
        language in _STRUCTURED_LANGUAGES
        or path.suffix.lower() in _STRUCTURED_SUFFIXES
        or name in _STRUCTURED_NAMES
        or name.startswith(".env")
    )


def _get_parser(parser_name: str) -> Any | None:
    if parser_name in _PARSERS:
        return _PARSERS[parser_name]
    with _PARSER_INIT_LOCK:
        if parser_name not in _PARSERS:
            parser = None
            try:
                from tree_sitter_language_pack import get_parser

                parser = get_parser(parser_name)
            except (ImportError, LookupError, OSError, TypeError, ValueError):
                pass
            _PARSERS[parser_name] = parser
            _PARSER_LOCKS[parser_name] = threading.Lock()
    return _PARSERS[parser_name]


def _error_evidence(content: str, parser_name: str) -> dict[str, int] | None:
    parser = _get_parser(parser_name)
    if parser is None:
        return None
    try:
        source = content.encode("utf-8")
        with _PARSER_LOCKS[parser_name]:
            root = parser.parse(source).root_node
    except (UnicodeEncodeError, AttributeError, RuntimeError, TypeError, ValueError):
        return None
    tail_start = max(0, len(source) - TAIL_BYTES)
    evidence = {"error_nodes": 0, "missing_nodes": 0, "tail_error_nodes": 0, "tail_missing_nodes": 0}
    stack = [root]
    while stack:
        node = stack.pop()
        is_error = getattr(node, "type", None) == "ERROR"
        is_missing = bool(getattr(node, "is_missing", False))
        if is_error or is_missing:
            evidence["error_nodes"] += int(is_error)
            evidence["missing_nodes"] += int(is_missing)
            if int(getattr(node, "end_byte", 0)) >= tail_start:
                evidence["tail_error_nodes"] += int(is_error)
                evidence["tail_missing_nodes"] += int(is_missing)
        stack.extend(getattr(node, "children", ()) or ())
    return evidence


def _mask_non_code(content: str, parser_name: str) -> tuple[str, str | None]:
    result = list(content)
    state = "code"
    quote = ""
    index = 0
    while index < len(content):
        character = content[index]
        following = content[index + 1] if index + 1 < len(content) else ""
        if state == "code":
            if character == "/" and following == "/":
                result[index] = result[index + 1] = " "
                state = "line_comment"
                index += 2
                continue
            if character == "/" and following == "*":
                result[index] = result[index + 1] = " "
                state = "block_comment"
                index += 2
                continue
            if parser_name == "python" and character == "#":
                result[index] = " "
                state = "line_comment"
                index += 1
                continue
            if character in {"'", '"', "`"}:
                quote = character
                state = "string"
                result[index] = " "
                index += 1
                continue
        elif state == "line_comment":
            if character in "\r\n":
                state = "code"
            else:
                result[index] = " "
        elif state == "block_comment":
            result[index] = character if character in "\r\n" else " "
            if character == "*" and following == "/":
                result[index + 1] = " "
                state = "code"
                index += 2
                continue
        else:
            result[index] = character if character in "\r\n" else " "
            if character == "\\" and following:
                result[index + 1] = following if following in "\r\n" else " "
                index += 2
                continue
            if character == quote:
                state = "code"
                quote = ""
        index += 1
    unterminated = state if state in {"block_comment", "string"} else None
    return "".join(result), unterminated


def truncation_tail_signals(content: str, parser_name: str) -> list[str]:
    """Find lexical EOF signals after comments and string contents are masked."""
    masked, unterminated = _mask_non_code(content, parser_name)
    signals = []
    if unterminated:
        signals.append(f"unterminated_{unterminated}")
    delimiter_names = {"(": "paren", "[": "bracket", "{": "brace"}
    closing = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for character in masked:
        if character in delimiter_names:
            stack.append(character)
        elif character in closing and stack and stack[-1] == closing[character]:
            stack.pop()
    signals.extend(f"unclosed_{delimiter_names[item]}" for item in sorted(set(stack)))
    stripped = masked.rstrip()
    if stripped:
        last_line = stripped.rsplit("\n", 1)[-1].strip()
        if last_line.endswith(("(", "[", "{")):
            signals.append("trailing_open_delimiter")
        if _TRAILING_OPERATOR.search(last_line):
            signals.append("trailing_operator")
        if last_line.endswith(","):
            signals.append("trailing_comma")
        if parser_name == "python" and last_line.endswith(":"):
            signals.append("python_suite_header_without_body")
    return sorted(set(signals))


def code_truncation_finding(data: Any) -> dict[str, str] | None:
    """Return a finding only when parser-tail and lexical-tail evidence agree."""
    content = getattr(data, "content", None)
    if not isinstance(content, str) or not MIN_CONTENT_CHARS <= len(content) <= MAX_CONTENT_CHARS:
        return None
    if _is_structured(data):
        return None
    parser_names = _parser_names(data)
    if not parser_names:
        return None
    available = []
    for parser_name in parser_names:
        evidence = _error_evidence(content, parser_name)
        if evidence is not None:
            available.append((parser_name, evidence))
    if not available:
        return None
    if any(not (item["error_nodes"] or item["missing_nodes"]) for _, item in available):
        return None
    parser_name, evidence = min(
        available,
        key=lambda item: item[1]["error_nodes"] + item[1]["missing_nodes"],
    )
    signals = truncation_tail_signals(content, parser_name)
    if not signals or not (evidence["tail_error_nodes"] or evidence["tail_missing_nodes"]):
        return None
    return {
        "label": "Completeness.Code_Truncation",
        "reason": (
            f"Likely code truncation: parser={parser_name}, tail_bytes={TAIL_BYTES}, "
            f"tail_error_nodes={evidence['tail_error_nodes']}, "
            f"tail_missing_nodes={evidence['tail_missing_nodes']}, "
            f"tail_signals={'+'.join(signals)}."
        ),
    }
