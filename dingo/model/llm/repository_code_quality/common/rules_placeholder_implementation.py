"""Detection of TODO stub and NotImplemented placeholder implementations."""

from __future__ import annotations
import re
from typing import Any, Iterator, Sequence

TEMPLATE_CONTENT_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"todo auto-generated method stub",
        r"todo implement (?:this|me)",
        r"notimplemented(?:exception|error)",
    )
)
NON_PRODUCTION_PATH_SEGMENTS = {
    "__tests__", "fixture", "fixtures", "mock", "mocks", "spec", "specs",
    "test", "tests", "testing",
}
NON_PRODUCTION_FILENAME_RE = re.compile(
    r"(?:^|[._-])(?:test|tests|spec|mock|fake|fixture|contract)(?:[._-]|$)|"
    r"(?:test|tests|spec|mock|fake|fixture|contract)\.(?:java|kt|cs|py|js|ts|tsx)$",
    re.IGNORECASE,
)
ABSTRACT_OR_INTERFACE_RE = re.compile(
    r"\babstract\s+class\b|\b(?:public\s+|protected\s+|private\s+|internal\s+)?interface\s+\w+|"
    r"@abstractmethod\b|\bclass\s+\w+\s*\([^)]*\b(?:ABC|Protocol)\b",
    re.IGNORECASE,
)
EXTENSION_POINT_CLASS_RE = re.compile(
    r"\bclass\s+(?:Base\w*|Abstract\w*|\w*(?:Provider|Adapter|Backend|Plugin|Step))\b",
    re.IGNORECASE,
)
BRACE_METHOD_RE = re.compile(
    r"(?ms)^[ \t]*(?:(?:public|protected|private|internal|static|final|virtual|override|async|"
    r"synchronized|sealed|partial|unsafe|new)\s+)*(?:[\w.$?<>\[\],]+\s+)+(?P<name>\w+)\s*"
    r"\([^;{}]*\)\s*(?:throws\s+[^{]+)?\{(?P<body>[^{}]*)\}",
)
PLACEHOLDER_MARKER_RE = re.compile(
    r"todo\s+(?:auto-generated\s+method\s+stub|implement\s+(?:this|me))",
    re.IGNORECASE,
)
UNCONDITIONAL_NOT_IMPLEMENTED_RE = re.compile(
    r"^throw\s+new\s+(?:System\.)?NotImplementedException\s*\([^;]*\)\s*;?$",
    re.IGNORECASE,
)
PLACEHOLDER_RETURN_RE = re.compile(
    r"^return\s+(?:null|0(?:\.0+)?|false|true|\"\"|''|default(?:\s*\([^)]*\))?)\s*;?$",
    re.IGNORECASE,
)


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


def _is_nonproduction_code_path(paths: Sequence[str]) -> bool:
    for path in paths:
        normalized = path.replace("\\", "/").strip().lower()
        if not normalized:
            continue
        parts = [part for part in normalized.split("/") if part]
        if any(part in NON_PRODUCTION_PATH_SEGMENTS for part in parts[:-1]):
            return True
        if parts and NON_PRODUCTION_FILENAME_RE.search(parts[-1]):
            return True
    return False


def _strip_method_comments(body: str) -> str:
    without_blocks = re.sub(r"/\*.*?\*/", " ", body, flags=re.DOTALL)
    without_lines = re.sub(r"(?m)//.*$|^\s*#.*$", " ", without_blocks)
    return re.sub(r"\s+", " ", without_lines).strip()


def _python_classes_with_local_subclasses(content: str) -> set[str]:
    bases: set[str] = set()
    for match in re.finditer(r"(?m)^\s*class\s+\w+\s*\((?P<bases>[^)]*)\)\s*:", content):
        for base in match.group("bases").split(","):
            name = re.sub(r"\[.*", "", base).strip().rsplit(".", 1)[-1]
            if name:
                bases.add(name)
    return bases


def _iter_python_method_bodies(content: str) -> Iterator[tuple[str, str]]:
    lines = content.splitlines()
    class_stack: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        class_match = re.match(r"class\s+(\w+)", stripped)
        if class_match:
            class_stack = [item for item in class_stack if item[0] < indent]
            class_stack.append((indent, class_match.group(1)))
        if class_stack and indent > class_stack[-1][0] and re.match(r"(?:async\s+)?def\s+\w+\s*\(", stripped):
            body_lines: list[str] = []
            index += 1
            while index < len(lines):
                candidate = lines[index]
                candidate_stripped = candidate.lstrip()
                candidate_indent = len(candidate) - len(candidate_stripped)
                if candidate_stripped and candidate_indent <= indent:
                    break
                body_lines.append(candidate)
                index += 1
            yield class_stack[-1][1], "\n".join(body_lines)
            continue
        index += 1


def _template_review_context(content_head: str, method_name: str) -> str | None:
    lowered_name = method_name.lower()
    if ABSTRACT_OR_INTERFACE_RE.search(content_head):
        return "abstract_or_interface_contract"
    if EXTENSION_POINT_CLASS_RE.search(content_head):
        return "extension_point_class"
    if lowered_name in {"convertback", "writejson"} and re.search(
        r"\b(?:IValueConverter|JsonConverter|CanWrite\s*(?:=>|\{[^}]*return)\s*false)\b",
        content_head,
        re.IGNORECASE | re.DOTALL,
    ):
        return "one_way_converter"
    if re.fullmatch(
        r"(?:window(?:opened|closing|closed|iconified|deiconified|activated|deactivated)|"
        r"on(?:progresschanged|starttrackingtouch|stoptrackingtouch|cancel|complete)|"
        r"before|after)",
        lowered_name,
    ):
        return "optional_callback"
    return None


def _placeholder_decision(
    content: str, content_head: str, paths: Sequence[str] = ()
) -> tuple[str, str] | None:
    if _is_nonproduction_code_path(paths):
        return None
    if not any(pattern.search(content_head) for pattern in TEMPLATE_CONTENT_PATTERNS):
        return None

    for match in BRACE_METHOD_RE.finditer(content[:50_000]):
        method_name = match.group("name")
        body = match.group("body")
        executable = _strip_method_comments(body)
        reason = None
        if UNCONDITIONAL_NOT_IMPLEMENTED_RE.fullmatch(executable):
            reason = "unconditional_not_implemented"
        elif PLACEHOLDER_MARKER_RE.search(body):
            if not executable:
                reason = "empty_method_with_placeholder"
            elif PLACEHOLDER_RETURN_RE.fullmatch(executable):
                reason = "placeholder_return"
        if reason:
            review_context = _template_review_context(content_head, method_name)
            if review_context:
                return "review", f"{reason}, context={review_context}, method={method_name}"
            return "fail", f"{reason}, method={method_name}"

    python_content = content[:50_000]
    local_python_bases = _python_classes_with_local_subclasses(python_content)
    for class_name, body in _iter_python_method_bodies(python_content):
        if class_name in local_python_bases:
            continue
        executable = _strip_method_comments(body)
        extension_contract = bool(
            re.fullmatch(
                r"(?:Base|Abstract)\w*|\w*(?:Provider|Adapter|Backend|Plugin|Step)",
                class_name,
                re.IGNORECASE,
            )
        )
        if re.fullmatch(r"raise\s+NotImplementedError(?:\s*\([^\n]*\))?", executable, re.IGNORECASE):
            if ABSTRACT_OR_INTERFACE_RE.search(content_head) or extension_contract:
                return (
                    "review",
                    f"unconditional_not_implemented, context=abstract_python_contract, class={class_name}",
                )
            return "fail", f"unconditional_not_implemented, class={class_name}"
        if PLACEHOLDER_MARKER_RE.search(body) and re.fullmatch(
            r"(?:pass|return\s+(?:None|0|False|True|\"\"|''))", executable, re.IGNORECASE
        ):
            if ABSTRACT_OR_INTERFACE_RE.search(content_head) or extension_contract:
                return (
                    "review",
                    f"placeholder_return, context=abstract_python_contract, class={class_name}",
                )
            return "fail", f"placeholder_return, class={class_name}"
    return None


def _decision(data: Any) -> tuple[str, str] | None:
    content = getattr(data, "content", None)
    if not isinstance(content, str):
        return None
    return _placeholder_decision(content, content[:8000], _path_values(data))


def placeholder_implementation_findings(data: Any) -> list[dict[str, str]]:
    """Hard findings for TODO stubs and unconditional NotImplemented bodies."""
    decision = _decision(data)
    if not decision or decision[0] != "fail":
        return []
    _, reason = decision
    if reason.startswith("unconditional_not_implemented"):
        label = "NotImplemented_Placeholder"
    else:
        label = "Todo_Empty_Implementation"
    return [{
        "label": f"Effectiveness.{label}",
        "reason": f"Placeholder implementation without real logic: {reason}.",
    }]


def placeholder_implementation_review_findings(data: Any) -> list[dict[str, str]]:
    """Review-level findings when an abstract/extension contract explains the stub."""
    decision = _decision(data)
    if not decision or decision[0] != "review":
        return []
    _, reason = decision
    return [{
        "label": "Effectiveness.Placeholder_Implementation_Review",
        "reason": f"Placeholder implementation matches an abstract or extension contract: {reason}.",
    }]
