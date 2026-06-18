#!/usr/bin/env python3
"""Validate parsed patent fields against the raw XML stored in `content`.

Field extraction rules are driven by ../doc/patent_mapping.csv.  The script is
intentionally conservative: fields with a confident XML extractor are compared;
metadata/library fields and unsupported free-form rules are reported as skipped.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import pymysql
except ImportError:  # pragma: no cover - runtime dependency check
    pymysql = None  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
DEFAULT_CONFIG_PATH = Path("sci_base_qa_test_config.json")
TEMPLATE_CONFIG_PATH = ASSETS_DIR / "settings.template.json"
DEFAULT_MAPPING_CSV = ASSETS_DIR / "patent_mapping.csv"
REPORT_ROOT = Path("report")
DEFAULT_TABLE = "test.iceberg_test_patent_parsed_info_acc_d"
DEFAULT_XML_FIELD = "xml_content"

LIBRARY_MODULE = "库信息"
SKIP_FIELDS = {
    "content",  # table content is processed full text; raw XML lives in xml_content for this table.
}
FIELD_ALIASES = {
    "patent_national_classifications": "national_classifications",
    "patent_domestic_classifications": "domestic_classifications",
    "patent_fi_classifications": "fi_classifications",
    "patent_cpc_classifications": "cpc_classifications",
    "patent_locarno_classes": "locarno_classes",
}
ORDER_INSENSITIVE_TYPES = ("list", "array")
ELEMENT_COVERAGE_SAMPLE_LIMIT = 80
SAMPLE_MODE_RANDOM = "random"
SAMPLE_MODE_BRANCH_COVERAGE = "branch-coverage"
SAMPLE_MODE_ALIASES = {
    "random": SAMPLE_MODE_RANDOM,
    "branch-coverage": SAMPLE_MODE_BRANCH_COVERAGE,
}
BRANCH_COVERAGE_CANDIDATE_MULTIPLIER = 20


@dataclass(frozen=True)
class PatentRule:
    field_name: str
    xml_mapping: str
    data_type: str
    description: str
    validation_rule: str
    nullable: str
    module: str


@dataclass
class ExtractResult:
    value: Any
    status: str = "ok"
    reason: str = ""
    branch: str = ""


Extractor = Callable[[ET.Element, PatentRule], ExtractResult]


class JsonEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            if obj == obj.to_integral_value():
                return int(obj)
            return float(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Copy the template and fill in credentials:\n"
            f"  cp {TEMPLATE_CONFIG_PATH} {path}"
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def connect_starrocks(config_path: Path):
    if pymysql is None:
        raise RuntimeError("pymysql is required. Install pymysql before running DB validation.")
    cfg = load_config(config_path)
    mysql_cfg = cfg["mysql"]
    retry_cfg = cfg.get("retry", {}) if isinstance(cfg.get("retry"), dict) else {}
    max_attempts = max(1, int(retry_cfg.get("max_attempts", 3)))
    delay = max(0.0, float(retry_cfg.get("initial_delay_sec", 2.0)))
    backoff = max(1.0, float(retry_cfg.get("backoff_factor", 2.0)))
    read_timeout = int(mysql_cfg.get("read_timeout_sec", 600))

    def is_retryable(exc: Exception) -> bool:
        if pymysql is not None and isinstance(exc, pymysql.err.OperationalError):
            code = exc.args[0] if exc.args else None
            if code in (2003, 2006, 2013):
                return True
        return any(token in str(exc).lower() for token in ("lost connection", "can't connect", "timeout"))

    for attempt in range(1, max_attempts + 1):
        try:
            return pymysql.connect(
                host=mysql_cfg["host"],
                port=int(mysql_cfg["port"]),
                user=mysql_cfg["user"],
                password=mysql_cfg["password"],
                charset=mysql_cfg.get("charset", "utf8mb4"),
                connect_timeout=30,
                read_timeout=read_timeout,
            )
        except Exception as exc:
            if attempt >= max_attempts or not is_retryable(exc):
                raise
            _log(f"[retry] MySQL 连接失败 ({type(exc).__name__}: {exc})，{delay:.1f}s 后重试")
            time.sleep(delay)
            delay *= backoff
    raise RuntimeError("MySQL connection retry exhausted unexpectedly")


def qualify_table_name(table: str, catalog: Optional[str], database: str = "dws") -> str:
    parts = [part.strip() for part in table.split(".") if part.strip()]
    if len(parts) >= 3:
        return table
    if len(parts) == 2:
        return f"{catalog}.{table}" if catalog else table
    if len(parts) == 1:
        return f"{catalog}.{database}.{table}" if catalog else f"{database}.{table}"
    return table


def quote_identifier(identifier: str) -> str:
    parts = [part.strip() for part in identifier.split(".") if part.strip()]
    if not parts:
        raise ValueError(f"Invalid identifier: {identifier!r}")
    return ".".join(f"`{part.replace('`', '``')}`" for part in parts)


def fetch_records(conn: Any, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
    with conn.cursor() as cursor:
        cursor.execute(sql, params)
        if cursor.description is None:
            return []
        cols = [field[0] for field in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]


def load_patent_rules(path: Path) -> List[PatentRule]:
    rules: List[PatentRule] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"预期字段名", "xml映射字段", "数据类型", "字段描述", "有效性规则", "可空", "模块"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"映射文件 {path} 缺少列: {', '.join(sorted(missing))}")
        for row in reader:
            field_name = clean_header_value(row.get("预期字段名"))
            if not field_name:
                continue
            rules.append(
                PatentRule(
                    field_name=field_name,
                    xml_mapping=clean_header_value(row.get("xml映射字段")),
                    data_type=clean_header_value(row.get("数据类型")),
                    description=clean_header_value(row.get("字段描述")),
                    validation_rule=clean_header_value(row.get("有效性规则")),
                    nullable=clean_header_value(row.get("可空")),
                    module=clean_header_value(row.get("模块")),
                )
            )
    return rules


def clean_header_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().strip('"').strip()


def safe_filename_token(value: Optional[Any]) -> str:
    text = "all" if value in (None, "") else str(value)
    return re.sub(r"[^0-9A-Za-z_-]+", "_", text).strip("_") or "all"


def normalize_sample_mode(value: Any) -> str:
    text = str(value or SAMPLE_MODE_BRANCH_COVERAGE).strip()
    normalized = SAMPLE_MODE_ALIASES.get(text.lower()) or SAMPLE_MODE_ALIASES.get(text)
    if normalized is None:
        raise ValueError(
            f"Unsupported sample_mode: {value!r}. "
            f"Use {SAMPLE_MODE_RANDOM!r} or {SAMPLE_MODE_BRANCH_COVERAGE!r}."
        )
    return normalized


def default_report_path(dt: Optional[str], sample_mode: str, full: bool) -> Path:
    mode = "full" if full else sample_mode
    report_dir = REPORT_ROOT / f"meta_patent_parsed_info_dt_{safe_filename_token(dt)}_{safe_filename_token(mode)}"
    return report_dir / "xml_field_mismatch.jsonl"


def summary_paths(report_path: Path) -> Tuple[Path, Path]:
    return report_path.parent / "summary.json", report_path.parent / "readable_summary.md"


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":", 1)[-1]


def norm_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def node_name(node: ET.Element) -> str:
    return norm_name(local_name(node.tag))


def text_content(node: Optional[ET.Element]) -> str:
    if node is None:
        return ""
    return normalize_space(" ".join(t for t in node.itertext() if t and t.strip()))


def normalize_space(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def attr_value(node: Optional[ET.Element], name: str) -> str:
    if node is None:
        return ""
    wanted = norm_name(name)
    for key, value in node.attrib.items():
        if norm_name(local_name(key)) == wanted:
            return normalize_space(value)
    return ""


def children(node: ET.Element, *names: str) -> List[ET.Element]:
    wanted = {norm_name(name) for name in names}
    return [child for child in list(node) if node_name(child) in wanted]


def descendants(node: ET.Element, *names: str) -> List[ET.Element]:
    wanted = {norm_name(name) for name in names}
    return [elem for elem in node.iter() if elem is not node and node_name(elem) in wanted]


def first_descendant(node: ET.Element, *names: str) -> Optional[ET.Element]:
    items = descendants(node, *names)
    return items[0] if items else None


def child_text(node: ET.Element, *names: str) -> str:
    for child in children(node, *names):
        txt = text_content(child)
        if txt:
            return txt
    return ""


def first_descendant_text(node: ET.Element, *names: str) -> str:
    found = first_descendant(node, *names)
    return text_content(found)


def has_ancestor(node: ET.Element, parent_map: Dict[ET.Element, ET.Element], *names: str) -> bool:
    wanted = {norm_name(name) for name in names}
    cur = node
    while cur in parent_map:
        cur = parent_map[cur]
        if node_name(cur) in wanted:
            return True
    return False


def parent_map(root: ET.Element) -> Dict[ET.Element, ET.Element]:
    return {child: parent for parent in root.iter() for child in list(parent)}


def xml_element_path(node: ET.Element, parents: Dict[ET.Element, ET.Element]) -> str:
    parts = [local_name(node.tag)]
    cur = node
    while cur in parents:
        cur = parents[cur]
        parts.append(local_name(cur.tag))
    return "/".join(reversed(parts))


def collect_xml_elements(root: ET.Element) -> List[Dict[str, Any]]:
    parents = parent_map(root)
    elements: Dict[str, Dict[str, Any]] = {}
    for node in root.iter():
        path = xml_element_path(node, parents)
        item = elements.setdefault(
            path,
            {
                "path": path,
                "name": local_name(node.tag),
                "occurrences": 0,
                "has_text": False,
                "has_attrs": False,
            },
        )
        item["occurrences"] += 1
        if text_content(node):
            item["has_text"] = True
        if node.attrib:
            item["has_attrs"] = True
    return sorted(elements.values(), key=lambda item: item["path"])


def mapping_element_names(mapping: str) -> set:
    if not mapping:
        return set()
    # Remove examples and prose-ish tail as much as possible while retaining XML node tokens.
    cleaned = re.sub(r"[@][A-Za-z0-9_:-]+(?:='[^']*')?", "", mapping)
    cleaned = re.sub(r"\bdataFormat\b|\boriginal\b|\bstandard\b|\broot\b|根", " ", cleaned, flags=re.I)
    tokens = re.findall(r"(?:[A-Za-z_][A-Za-z0-9_-]*:)?[A-Za-z_][A-Za-z0-9_-]*", cleaned)
    ignore = {
        "business",
        "base",
        "xml",
    }
    names = set()
    for token in tokens:
        name = local_name(token)
        if name in ignore:
            continue
        # Keep field-like XML node names; skip prose fragments that are usually lower-case words.
        if name and (name[0].isupper() or name in {"lang", "status", "country", "docNumber", "kind", "datePublication"}):
            names.add(name)
    return names


def mapped_xml_element_names(rules: Sequence[PatentRule]) -> set:
    names = set()
    for rule in rules:
        if rule.module == LIBRARY_MODULE or rule.field_name in SKIP_FIELDS:
            continue
        names.update(mapping_element_names(rule.xml_mapping))
    return names


def non_library_rule_fields(rules: Sequence[PatentRule]) -> set:
    return {
        rule.field_name
        for rule in rules
        if rule.module != LIBRARY_MODULE and rule.field_name not in SKIP_FIELDS
    }


def actual_parsed_fields(row: Dict[str, Any], rules: Sequence[PatentRule]) -> List[str]:
    fields = []
    for rule in rules:
        if rule.module == LIBRARY_MODULE or rule.field_name in SKIP_FIELDS:
            continue
        if is_non_empty(actual_field_value(row, rule.field_name)):
            fields.append(rule.field_name)
    return sorted(set(fields))


def build_element_coverage(
    row: Dict[str, Any],
    root: ET.Element,
    rules: Sequence[PatentRule],
    *,
    key: Any,
    dt: Optional[str],
) -> Dict[str, Any]:
    xml_elements = collect_xml_elements(root)
    mapped_names = mapped_xml_element_names(rules)
    parsed_fields = actual_parsed_fields(row, rules)
    rule_fields = non_library_rule_fields(rules)
    xml_significant = [
        elem
        for elem in xml_elements
        if elem.get("has_text") or elem.get("has_attrs")
    ]
    unmapped = [
        elem
        for elem in xml_significant
        if elem["name"] not in mapped_names
    ]
    parsed_without_mapping = [
        field
        for field in parsed_fields
        if field not in rule_fields
    ]
    return {
        "key": key,
        "dt": dt,
        "parsed_field_count": len(parsed_fields),
        "parsed_fields": parsed_fields,
        "xml_element_count": len(xml_elements),
        "xml_significant_element_count": len(xml_significant),
        "xml_elements": xml_elements,
        "mapped_xml_element_name_count": len(mapped_names),
        "unmapped_xml_element_count": len(unmapped),
        "unmapped_xml_elements": unmapped[:ELEMENT_COVERAGE_SAMPLE_LIMIT],
        "unmapped_xml_elements_truncated": max(0, len(unmapped) - ELEMENT_COVERAGE_SAMPLE_LIMIT),
        "parsed_fields_without_xml_mapping": parsed_without_mapping,
    }


def first_by_path(root: ET.Element, path_names: Sequence[str], attrs: Optional[Dict[str, str]] = None) -> Optional[ET.Element]:
    current = [root]
    for raw_name in path_names:
        wanted = norm_name(raw_name)
        next_nodes: List[ET.Element] = []
        for node in current:
            next_nodes.extend(child for child in node.iter() if child is not node and node_name(child) == wanted)
        current = next_nodes
        if not current:
            return None
    attrs = attrs or {}
    for node in current:
        if all(attr_value(node, key) == value for key, value in attrs.items()):
            return node
    return current[0] if current else None


def publication_document_ids(root: ET.Element) -> List[ET.Element]:
    out: List[ET.Element] = []
    refs = descendants(root, "PublicationReference")
    refs.sort(key=lambda node: data_format_rank(attr_value(node, "dataFormat")))
    for pub in refs:
        doc_ids = descendants(pub, "DocumentID")
        doc_ids.sort(key=lambda node: data_format_rank(attr_value(node, "dataFormat")))
        out.extend(doc_ids)
    return out


def publication_refs(root: ET.Element, data_format: Optional[str] = None) -> List[ET.Element]:
    refs = descendants(root, "PublicationReference")
    if data_format is not None:
        wanted = data_format.lower()
        refs = [ref for ref in refs if attr_value(ref, "dataFormat").lower() == wanted]
    refs.sort(key=lambda node: data_format_rank(attr_value(node, "dataFormat")))
    return refs


def document_ids_from_refs(refs: Sequence[ET.Element], data_format: Optional[str] = None) -> List[ET.Element]:
    out: List[ET.Element] = []
    for ref in refs:
        doc_ids = descendants(ref, "DocumentID")
        if data_format is not None:
            wanted = data_format.lower()
            doc_ids = [doc_id for doc_id in doc_ids if attr_value(doc_id, "dataFormat").lower() in {"", wanted}]
        doc_ids.sort(key=lambda node: data_format_rank(attr_value(node, "dataFormat")))
        out.extend(doc_ids)
    return out


def application_document_ids(root: ET.Element) -> List[ET.Element]:
    out: List[ET.Element] = []
    refs = descendants(root, "ApplicationReference")
    refs.sort(key=lambda node: data_format_rank(attr_value(node, "dataFormat")))
    for app in refs:
        doc_ids = descendants(app, "DocumentID")
        doc_ids.sort(key=lambda node: data_format_rank(attr_value(node, "dataFormat")))
        out.extend(doc_ids)
    return out


def data_format_rank(value: str) -> int:
    lowered = value.lower()
    if lowered == "original":
        return 0
    if lowered == "standard":
        return 1
    return 2


def choose_doc_id(nodes: Sequence[ET.Element]) -> Optional[ET.Element]:
    if not nodes:
        return None
    for node in nodes:
        parent = node
        data_formats = [attr_value(n, "dataFormat").lower() for n in [node, *list(node.iter())]]
        if "original" in data_formats:
            return parent
    for node in nodes:
        data_formats = [attr_value(n, "dataFormat").lower() for n in [node, *list(node.iter())]]
        if "standard" in data_formats:
            return node
    return nodes[0]


def document_number_from_doc_id(doc_id: Optional[ET.Element]) -> str:
    if doc_id is None:
        return ""
    parts = [
        child_text(doc_id, "WIPOST3Code", "CountryCode", "OfficeCode"),
        child_text(doc_id, "DocNumber", "DocumentNumber"),
        child_text(doc_id, "Kind"),
    ]
    return "".join(part for part in parts if part)


def preferred_by_data_format(nodes: Sequence[ET.Element]) -> List[ET.Element]:
    originals = [node for node in nodes if attr_value(node, "dataFormat").lower() == "original"]
    if originals:
        return originals
    standards = [node for node in nodes if attr_value(node, "dataFormat").lower() == "standard"]
    if standards:
        return standards
    return list(nodes)


def date_from_doc_id(doc_id: Optional[ET.Element]) -> str:
    return child_text(doc_id, "Date") if doc_id is not None else ""


def country_from_doc_id(doc_id: Optional[ET.Element]) -> str:
    if doc_id is None:
        return ""
    return child_text(doc_id, "WIPOST3Code", "CountryCode", "OfficeCode")


def kind_from_doc_id(doc_id: Optional[ET.Element]) -> str:
    return child_text(doc_id, "Kind") if doc_id is not None else ""


def root_attr(root: ET.Element, name: str) -> str:
    return attr_value(root, name)


def unique_nonempty(values: Iterable[Any]) -> List[str]:
    seen = set()
    out: List[str] = []
    for value in values:
        text = normalize_space(value)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def branch_result(value: Any, branch: str) -> ExtractResult:
    return ExtractResult(value, branch=branch if is_non_empty(value) else "empty")


def result_branch(extracted: ExtractResult) -> str:
    if extracted.status != "ok":
        return extracted.status
    if extracted.branch:
        return extracted.branch
    return "xml_value" if is_non_empty(extracted.value) else "empty"


def extract_document_number(root: ET.Element, rule: PatentRule) -> ExtractResult:
    value = document_number_from_doc_id(choose_doc_id(document_ids_from_refs(publication_refs(root, "original"), "original")))
    if value:
        return branch_result(value, "pub_original")
    value = document_number_from_doc_id(choose_doc_id(publication_document_ids(root)))
    if value:
        return branch_result(value, "pub_fallback")
    value = "".join(
        part for part in [root_attr(root, "country"), root_attr(root, "docNumber"), root_attr(root, "kind")] if part
    )
    return branch_result(value, "root_attrs")


def extract_document_kind_code(root: ET.Element, rule: PatentRule) -> ExtractResult:
    refs = publication_refs(root, "original")
    value = kind_from_doc_id(choose_doc_id(document_ids_from_refs(refs, "original")))
    if value:
        return branch_result(value, "pub_original")
    return branch_result(root_attr(root, "kind"), "root_kind")


def extract_document_kind_text(root: ET.Element, rule: PatentRule) -> ExtractResult:
    node = first_by_path(root, ["SpecificBibliographicData", "OriginalKindCode"])
    return branch_result(text_content(node), "specific_bibliographic_data")


def extract_document_status_code(root: ET.Element, rule: PatentRule) -> ExtractResult:
    for abstract in descendants(root, "Abstract"):
        status = attr_value(abstract, "status")
        if status:
            return branch_result(status, "abstract_status")
    return branch_result(root_attr(root, "status"), "root_status")


def extract_document_wipo_country_code(root: ET.Element, rule: PatentRule) -> ExtractResult:
    refs = publication_refs(root, "original")
    value = country_from_doc_id(choose_doc_id(document_ids_from_refs(refs, "original")))
    if value:
        return branch_result(value, "pub_original")
    return branch_result(root_attr(root, "country"), "root_country")


def extract_publication_date(root: ET.Element, rule: PatentRule) -> ExtractResult:
    value = date_from_doc_id(choose_doc_id(publication_document_ids(root)))
    if value:
        return branch_result(value, "publication_document_id")
    return branch_result(root_attr(root, "datePublication"), "root_date_publication")


def extract_publication_language(root: ET.Element, rule: PatentRule) -> ExtractResult:
    return branch_result(root_attr(root, "lang"), "root_lang")


def extract_publication_office_code(root: ET.Element, rule: PatentRule) -> ExtractResult:
    for pub in descendants(root, "PublicationReference"):
        source_db = attr_value(pub, "sourceDB")
        if source_db:
            return branch_result(source_db, "publication_source_db")
    value = country_from_doc_id(choose_doc_id(publication_document_ids(root)))
    if value:
        return branch_result(value, "publication_document_id")
    return branch_result(root_attr(root, "country"), "root_country")


def extract_invention_title(root: ET.Element, rule: PatentRule) -> ExtractResult:
    lang = root_attr(root, "lang")
    titles = descendants(root, "InventionTitle")
    if lang:
        for title in titles:
            if attr_value(title, "lang").lower() == lang.lower():
                return branch_result(text_content(title), "lang_match")
    return ExtractResult("", branch="empty")


def extract_ipc(root: ET.Element, rule: PatentRule) -> ExtractResult:
    vals: List[str] = []
    branch = "empty"
    for ipc_node in descendants(root, "ClassificationIPC"):
        candidates: List[ET.Element] = []
        for name in ("MainClassification", "FurtherClassification"):
            candidates.extend(descendants(ipc_node, name))
        preferred = preferred_by_data_format(candidates)
        for node in preferred:
            if branch == "empty":
                fmt = attr_value(node, "dataFormat").lower()
                branch = f"classification_ipc_{fmt}" if fmt else "classification_ipc"
            vals.append(text_content(node))
    return branch_result(unique_nonempty(vals), branch)


def extract_ipc_text(root: ET.Element, rule: PatentRule) -> ExtractResult:
    vals: List[str] = []
    for ipc_node in descendants(root, "ClassificationIPC"):
        for node in descendants(ipc_node, "Text"):
            vals.extend(part.strip() for part in text_content(node).splitlines())
    return branch_result(unique_nonempty(vals), "classification_ipc_text")


def extract_ipc_edition_statement(root: ET.Element, rule: PatentRule) -> ExtractResult:
    for ipc_node in descendants(root, "ClassificationIPC"):
        text = first_descendant_text(ipc_node, "EditionStatement")
        if text:
            return branch_result(text, "classification_ipc_edition_statement")
    return ExtractResult("", branch="empty")


def extract_classification_objects(root: ET.Element, rule: PatentRule) -> ExtractResult:
    names_by_field = {
        "ipcr_classifications": ("ClassificationIPCR", "ClassificationIPCRDetails"),
        "patent_national_classifications": ("ClassificationNational",),
        "patent_domestic_classifications": ("ClassificationDomestic", "DomesticClassification", "DomesticPatentClassification"),
        "patent_fi_classifications": ("ClassificationFI", "FIClassification", "ClassificationFIData"),
        "patent_locarno_classes": ("ClassificationLocarno",),
    }
    names = names_by_field.get(rule.field_name, ())
    values: List[Any] = []
    branch = "empty"
    for container in descendants(root, *names):
        if branch == "empty":
            branch = local_name(container.tag)
        texts = unique_nonempty(
            text_content(node)
            for node in container.iter()
            if node is not container and node_name(node) in {"mainclassification", "furtherclassification", "text"}
        )
        values.extend(texts)
    return branch_result(unique_nonempty(values), branch)


def extract_cpc(root: ET.Element, rule: PatentRule) -> ExtractResult:
    values: List[str] = []
    for pat_cls in descendants(root, "PatentClassification"):
        scheme = first_descendant(pat_cls, "ClassificationScheme")
        if scheme is not None and attr_value(scheme, "scheme").upper() != "CPC":
            continue
        symbol = first_descendant_text(pat_cls, "ClassificationSymbol") or text_content(pat_cls)
        values.append(symbol)
    return branch_result(unique_nonempty(values), "patent_classification_cpc")


def extract_abstract(root: ET.Element, rule: PatentRule) -> ExtractResult:
    vals = [text_content(node) for node in descendants(root, "Abstract")]
    return branch_result("\n".join(unique_nonempty(vals)), "abstract")


def extract_description(root: ET.Element, rule: PatentRule) -> ExtractResult:
    items = []
    for idx, node in enumerate(descendants(root, "Description"), start=1):
        txt = text_content(node)
        if txt:
            items.append({"seq": idx, "text": txt})
    return branch_result(items, "description")


def extract_claims(root: ET.Element, rule: PatentRule) -> ExtractResult:
    claims = []
    for idx, claim in enumerate(descendants(root, "Claim"), start=1):
        text = text_content(claim)
        if not text:
            continue
        claims.append(
            {
                "claim_id": attr_value(claim, "id") or attr_value(claim, "num") or str(idx),
                "claim_num": attr_value(claim, "num") or str(idx),
                "claim_text": text,
            }
        )
    return branch_result(claims, "claims")


def extract_drawings(root: ET.Element, rule: PatentRule) -> ExtractResult:
    drawings = []
    for idx, figure in enumerate(descendants(root, "Figure"), start=1):
        image = first_descendant(figure, "Image")
        if image is None:
            continue
        drawings.append(
            {
                "figure_id": attr_value(figure, "id") or str(idx),
                "image_file": attr_value(image, "file") or attr_value(image, "filename") or attr_value(image, "href"),
            }
        )
    return branch_result(drawings, "drawings")


def extract_parties(root: ET.Element, rule: PatentRule) -> ExtractResult:
    field_to_names = {
        "applicants": ("Applicant",),
        "assignees": ("Assignee",),
        "inventors": ("Inventor",),
        "designers": ("Designer",),
        "patent_agents": ("Agent", "Agency"),
        "patent_agency": ("PatentAgency",),
    }
    names = field_to_names.get(rule.field_name, ())
    people = []
    branch = "empty"
    for node in descendants(root, *names):
        if branch == "empty":
            branch = local_name(node.tag)
        address_book = first_descendant(node, "AddressBook") or node
        name = first_descendant_text(address_book, "Name") or first_descendant_text(address_book, "LastName")
        country = first_descendant_text(address_book, "CountryCode") or first_descendant_text(address_book, "WIPOST3Code")
        text = text_content(address_book)
        if name or text:
            item = {"name": name or text}
            if country:
                item["country"] = country
            people.append(item)
    return branch_result(dedup_dicts(people), branch)


def extract_priority_numbers(root: ET.Element, rule: PatentRule) -> ExtractResult:
    vals = []
    for node in descendants(root, "PriorityClaim"):
        for doc_id in descendants(node, "DocumentID"):
            vals.append(child_text(doc_id, "DocNumber", "DocumentNumber"))
    return branch_result(unique_nonempty(vals), "priority_claim_document_id")


def extract_priority_filing_dates(root: ET.Element, rule: PatentRule) -> ExtractResult:
    vals = []
    for node in descendants(root, "PriorityClaim"):
        for doc_id in descendants(node, "DocumentID"):
            vals.append(child_text(doc_id, "Date"))
    return branch_result(unique_nonempty(vals), "priority_claim_document_id")


def extract_priority_office_codes(root: ET.Element, rule: PatentRule) -> ExtractResult:
    vals = []
    branch = "empty"
    for node in descendants(root, "PriorityClaim"):
        office = first_descendant_text(node, "OfficeCode")
        generating = first_descendant_text(node, "GeneratingOffice")
        if office and branch == "empty":
            branch = "priority_office_code"
        if generating and branch == "empty":
            branch = "priority_generating_office"
        vals.append(office)
        vals.append(generating)
        for doc_id in descendants(node, "DocumentID"):
            country = country_from_doc_id(doc_id)
            if country and branch == "empty":
                branch = "priority_document_id_country"
            vals.append(country)
    return branch_result(unique_nonempty(vals), branch)


def extract_public_availability_date(root: ET.Element, rule: PatentRule) -> ExtractResult:
    token_map = {
        "public_availability_unexamined_view_date": ("unexamined", "view"),
        "public_availability_examined_view_date": ("examined", "view"),
        "public_availability_unexamined_print_date": ("unexamined", "print"),
        "public_availability_examined_print_date": ("examined", "print"),
        "claims_only_public_date": ("claimsonly",),
        "granted_view_date": ("granted", "view"),
        "corrected_document_issue_date": ("corrected",),
    }
    tokens = token_map.get(rule.field_name, ())
    for container in descendants(root, "PublicAvailabilityDate"):
        for node in container.iter():
            name = node_name(node)
            if tokens and all(token in name for token in tokens):
                date_text = first_descendant_text(node, "Date")
                if date_text:
                    return branch_result(date_text, local_name(node.tag))
    return ExtractResult("", branch="empty")


def extract_grant_publication_date(root: ET.Element, rule: PatentRule) -> ExtractResult:
    for container in descendants(root, "PublicAvailabilityDate"):
        for node in container.iter():
            if "grant" in node_name(node):
                date_text = first_descendant_text(node, "Date")
                if date_text:
                    return branch_result(date_text, local_name(node.tag))
    return ExtractResult("", branch="empty")


def extract_application_numbers(root: ET.Element, rule: PatentRule) -> ExtractResult:
    vals: List[str] = []
    refs = descendants(root, "ApplicationReference")
    original_refs = [ref for ref in refs if attr_value(ref, "dataFormat").lower() == "original"]
    for ref in original_refs:
        doc_id = choose_doc_id(descendants(ref, "DocumentID"))
        vals.append(document_number_from_doc_id(doc_id) or child_text(doc_id, "DocNumber") if doc_id is not None else "")
    return branch_result(unique_nonempty(vals), "application_original")


def extract_filing_dates(root: ET.Element, rule: PatentRule) -> ExtractResult:
    return branch_result(
        unique_nonempty(date_from_doc_id(doc_id) for doc_id in application_document_ids(root)),
        "application_document_id",
    )


def extract_original_filing_language(root: ET.Element, rule: PatentRule) -> ExtractResult:
    for app in descendants(root, "ApplicationReference"):
        lang = attr_value(app, "lang")
        if lang:
            return branch_result(lang, "application_lang")
    return branch_result(root_attr(root, "lang"), "root_lang")


def extract_effective_rights_date(root: ET.Element, rule: PatentRule) -> ExtractResult:
    dates = unique_nonempty(date_from_doc_id(doc_id) for doc_id in application_document_ids(root))
    return branch_result(dates[0] if dates else "", "application_document_id")


def extract_designated_states(root: ET.Element, rule: PatentRule) -> ExtractResult:
    container_names = ("PctOrRegionalFilingData",) if rule.field_name == "pct_designated_states" else ("RegionalFilingData",)
    vals: List[str] = []
    for container in descendants(root, *container_names):
        for node in descendants(container, "DesignatedState", "WIPOST3Code", "CountryCode"):
            vals.append(text_content(node))
    return branch_result(unique_nonempty(vals), "_".join(container_names).lower())


def extract_date_by_container(root: ET.Element, rule: PatentRule) -> ExtractResult:
    token_map = {
        "pct_national_phase_date": ("PctNationalPhaseEntry", "NationalPhaseEntry"),
        "pct_effect_ceased_date": ("PctRefiledRevised", "RefiledRevisedApplication"),
        "search_report_deferred_publication_date": ("SearchReportDifferentPublication",),
        "spc_application_date": ("SPC",),
        "microorganism_deposit_date": ("BiologicalDeposit", "MicroorganismDeposit", "MicroorganismDepositDetails", "DepositInstitution"),
    }
    for container in descendants(root, *token_map.get(rule.field_name, ())):
        date_text = first_descendant_text(container, "Date") or first_descendant_text(container, "DepositDate")
        if date_text:
            return branch_result(date_text, local_name(container.tag))
    return ExtractResult("", branch="empty")


def extract_generic_object_by_tokens(root: ET.Element, rule: PatentRule) -> ExtractResult:
    tokens = [token for token in re.split(r"[_\s]+", rule.field_name.lower()) if token and token not in {"patent", "data", "info"}]
    objects = []
    for node in root.iter():
        name = node_name(node)
        if tokens and any(token in name for token in tokens):
            txt = text_content(node)
            if txt:
                objects.append({"node": local_name(node.tag), "text": txt})
    if rule.data_type.lower().startswith("list"):
        return branch_result(dedup_dicts(objects), "token_match")
    return branch_result(objects[0] if objects else {}, "token_match")


def extract_generic_text_by_tokens(root: ET.Element, rule: PatentRule) -> ExtractResult:
    tokens = [token for token in re.split(r"[_\s]+", rule.field_name.lower()) if token]
    for node in root.iter():
        name = node_name(node)
        if tokens and any(token in name for token in tokens):
            txt = text_content(node)
            if txt:
                return branch_result(txt, local_name(node.tag))
    return ExtractResult("", branch="empty")


def dedup_dicts(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dedup: Dict[str, Dict[str, Any]] = {}
    for item in items:
        compact = {k: v for k, v in item.items() if is_non_empty(v)}
        if not compact:
            continue
        dedup[canonical_json(compact)] = compact
    return [dedup[key] for key in sorted(dedup)]


FIELD_EXTRACTORS: Dict[str, Extractor] = {
    "document_number": extract_document_number,
    "document_kind_text": extract_document_kind_text,
    "document_kind_code": extract_document_kind_code,
    "document_status_code": extract_document_status_code,
    "document_wipo_country_code": extract_document_wipo_country_code,
    "publication_date": extract_publication_date,
    "publication_language": extract_publication_language,
    "publication_office_code": extract_publication_office_code,
    "invention_title": extract_invention_title,
    "ipc": extract_ipc,
    "ipc_text": extract_ipc_text,
    "ipc_edition_statement": extract_ipc_edition_statement,
    "ipcr_classifications": extract_classification_objects,
    "patent_national_classifications": extract_classification_objects,
    "patent_domestic_classifications": extract_classification_objects,
    "patent_fi_classifications": extract_classification_objects,
    "patent_cpc_classifications": extract_cpc,
    "patent_locarno_classes": extract_classification_objects,
    "abstract": extract_abstract,
    "description": extract_description,
    "claims": extract_claims,
    "drawings": extract_drawings,
    "applicants": extract_parties,
    "assignees": extract_parties,
    "inventors": extract_parties,
    "designers": extract_parties,
    "patent_agents": extract_parties,
    "patent_agency": extract_parties,
    "priority_numbers": extract_priority_numbers,
    "priority_filing_dates": extract_priority_filing_dates,
    "priority_office_codes": extract_priority_office_codes,
    "priority_country_codes": extract_priority_office_codes,
    "public_availability_unexamined_view_date": extract_public_availability_date,
    "public_availability_examined_view_date": extract_public_availability_date,
    "public_availability_unexamined_print_date": extract_public_availability_date,
    "public_availability_examined_print_date": extract_public_availability_date,
    "grant_publication_date": extract_grant_publication_date,
    "claims_only_public_date": extract_public_availability_date,
    "granted_view_date": extract_public_availability_date,
    "corrected_document_issue_date": extract_public_availability_date,
    "application_numbers": extract_application_numbers,
    "filing_dates": extract_filing_dates,
    "original_filing_language": extract_original_filing_language,
    "effective_rights_date": extract_effective_rights_date,
    "pct_designated_states": extract_designated_states,
    "regional_designated_states": extract_designated_states,
    "pct_national_phase_date": extract_date_by_container,
    "pct_effect_ceased_date": extract_date_by_container,
    "search_report_deferred_publication_date": extract_date_by_container,
    "spc_application_date": extract_date_by_container,
    "microorganism_deposit_date": extract_date_by_container,
}


def get_extractor(rule: PatentRule) -> Optional[Extractor]:
    if rule.field_name in FIELD_EXTRACTORS:
        return FIELD_EXTRACTORS[rule.field_name]
    return None


def parse_xml(raw: Any) -> ET.Element:
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="replace")
    text = str(raw or "").strip()
    if not text:
        raise ValueError("empty XML content")
    text = re.sub(r"^\s*<\?xml[^>]*\?>", "", text, count=1).lstrip()
    return ET.fromstring(text)


def json_loads_maybe(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and stripped[0] in "[{":
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    return value


def canonicalize(value: Any) -> Any:
    value = json_loads_maybe(value)
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): canonicalize(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [canonicalize(v) for v in value]
    if isinstance(value, str):
        return normalize_space(value)
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(canonicalize(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), cls=JsonEncoder)


def is_non_empty(value: Any) -> bool:
    value = json_loads_maybe(value)
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in {"", "{}", "[]"}
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def normalize_dateish(value: Any) -> Any:
    text = normalize_space(value)
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) == 8:
        return digits
    return text


def flatten_strings(value: Any) -> List[str]:
    value = json_loads_maybe(value)
    out: List[str] = []
    if value is None:
        return out
    if isinstance(value, dict):
        for v in value.values():
            out.extend(flatten_strings(v))
        return out
    if isinstance(value, list):
        for item in value:
            out.extend(flatten_strings(item))
        return out
    text = normalize_space(value)
    if text:
        out.append(text)
    return out


def compact_text_for_compare(value: Any) -> str:
    text = " ".join(flatten_strings(value))
    text = normalize_space(text).lower()
    return re.sub(r"[^0-9a-z\u3040-\u30ff\u3400-\u9fff]+", "", text)


def text_equivalent(expected: Any, actual: Any, field_name: str) -> bool:
    expected_text = compact_text_for_compare(expected)
    actual_text = compact_text_for_compare(actual)
    if not expected_text and not actual_text:
        return True
    if not expected_text or not actual_text:
        return False
    if expected_text == actual_text:
        return True
    if field_name in {"abstract", "description", "claims"}:
        shorter, longer = sorted((expected_text, actual_text), key=len)
        return bool(shorter) and shorter in longer
    return False


def compare_values(expected: Any, actual: Any, data_type: str, field_name: str = "") -> Optional[Dict[str, Any]]:
    expected = canonicalize(expected)
    actual = canonicalize(actual)
    type_text = data_type.lower()
    if not is_non_empty(expected) and not is_non_empty(actual):
        return None
    if not is_non_empty(expected) and is_non_empty(actual):
        return {"expected": expected, "actual": actual, "reason": "xml_empty_but_field_nonempty"}
    if is_non_empty(expected) and not is_non_empty(actual):
        return {"expected": expected, "actual": actual, "reason": "xml_nonempty_but_field_empty"}
    if "date" in type_text:
        if normalize_dateish(expected) != normalize_dateish(actual):
            return {"expected": expected, "actual": actual}
        return None
    if field_name in {"abstract", "description", "claims"} and text_equivalent(expected, actual, field_name):
        return None
    if type_text.startswith(ORDER_INSENSITIVE_TYPES):
        expected_set = set(flatten_strings(expected))
        actual_set = set(flatten_strings(actual))
        if expected_set and not expected_set.issubset(actual_set):
            return {"expected": sorted(expected_set), "actual": sorted(actual_set)}
        return None
    if type_text == "object":
        expected_tokens = set(flatten_strings(expected))
        actual_tokens = set(flatten_strings(actual))
        if expected_tokens and not expected_tokens.intersection(actual_tokens):
            return {"expected": expected, "actual": actual}
        return None
    expected_text = normalize_space(expected)
    actual_text = normalize_space(actual)
    if expected_text != actual_text and not text_equivalent(expected, actual, field_name):
        return {"expected": expected, "actual": actual}
    return None


def compact_record_for_report(record: Dict[str, Any], xml_field: str) -> Dict[str, Any]:
    keys = (
        "document_number",
        "document_kind_code",
        "publication_date",
        "invention_title",
        "sha256",
        "origin_url",
        "origin_path",
        "dt",
        "patent_source",
    )
    return {key: canonicalize(record.get(key)) for key in keys if is_non_empty(record.get(key)) and key != xml_field}


def actual_field_value(row: Dict[str, Any], field_name: str) -> Any:
    if field_name in row:
        return row.get(field_name)
    alias = FIELD_ALIASES.get(field_name)
    if alias:
        return row.get(alias)
    return None


def build_sample_query(
    table: str,
    dt: Optional[str],
    limit: Optional[int],
    *,
    key_field: str,
    xml_field: str,
    sample_mode: str,
) -> Tuple[str, List[Any]]:
    sample_mode = normalize_sample_mode(sample_mode)
    params: List[Any] = []
    where = [f"`{xml_field}` IS NOT NULL", f"`{xml_field}` != ''"]
    if dt is not None:
        where.append("`dt` = %s")
        params.append(dt)
    if sample_mode == SAMPLE_MODE_RANDOM:
        order = "RAND()"
    else:
        order = f"CRC32(COALESCE(CAST(`{key_field}` AS STRING), CAST(`{xml_field}` AS STRING)))"
    limit_sql = "" if limit is None else f" LIMIT {int(limit)}"
    sql = (
        f"SELECT * FROM {quote_identifier(table)} "
        f"WHERE {' AND '.join(where)} ORDER BY {order}{limit_sql}"
    )
    return sql, params


def discover_dt_values(conn: Any, table: str) -> List[str]:
    sql = (
        f"SELECT DISTINCT `dt` FROM {quote_identifier(table)} "
        "WHERE `dt` IS NOT NULL AND `dt` != '' ORDER BY `dt`"
    )
    return [str(r["dt"]) for r in fetch_records(conn, sql)]


def validate_row(
    row: Dict[str, Any],
    rules: Sequence[PatentRule],
    *,
    xml_field: str,
    include_xml_field: bool,
    selected_fields: Optional[set],
) -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]], Dict[str, str]]:
    mismatches: Dict[str, Dict[str, Any]] = {}
    warnings: List[Dict[str, Any]] = []
    branches: Dict[str, str] = {}
    try:
        root = parse_xml(row.get(xml_field))
    except Exception as exc:
        branches[xml_field] = "xml_parse_failed"
        return {xml_field: {"expected": "valid XML", "actual": type(exc).__name__, "reason": str(exc)}}, warnings, branches

    for rule in rules:
        if selected_fields is not None and rule.field_name not in selected_fields:
            continue
        if rule.field_name in SKIP_FIELDS:
            warnings.append({"field": rule.field_name, "status": "skipped", "reason": "processed_fulltext_field"})
            continue
        if rule.field_name == xml_field and not include_xml_field:
            warnings.append({"field": rule.field_name, "status": "skipped", "reason": "raw_xml_field"})
            continue
        if rule.module == LIBRARY_MODULE:
            continue
        extractor = get_extractor(rule)
        if extractor is None:
            warnings.append({"field": rule.field_name, "status": "skipped", "reason": "unsupported_mapping"})
            continue
        try:
            extracted = extractor(root, rule)
        except Exception as exc:
            warnings.append({"field": rule.field_name, "status": "extract_error", "reason": str(exc)})
            continue
        branches[rule.field_name] = result_branch(extracted)
        if extracted.status != "ok":
            warnings.append({"field": rule.field_name, "status": extracted.status, "reason": extracted.reason})
            continue
        diff = compare_values(
            extracted.value,
            actual_field_value(row, rule.field_name),
            rule.data_type,
            rule.field_name,
        )
        if diff is not None:
            mismatches[rule.field_name] = diff
    return mismatches, warnings, branches


def extract_row_branches(
    row: Dict[str, Any],
    rules: Sequence[PatentRule],
    *,
    xml_field: str,
    include_xml_field: bool,
    selected_fields: Optional[set],
) -> Dict[str, str]:
    _, _, branches = validate_row(
        row,
        rules,
        xml_field=xml_field,
        include_xml_field=include_xml_field,
        selected_fields=selected_fields,
    )
    return branches


def select_branch_coverage_rows(
    rows: Sequence[Dict[str, Any]],
    rules: Sequence[PatentRule],
    *,
    limit: Optional[int],
    xml_field: str,
    include_xml_field: bool,
    selected_fields: Optional[set],
) -> List[Dict[str, Any]]:
    if limit is None or len(rows) <= limit:
        return list(rows)
    selected: List[Dict[str, Any]] = []
    deferred: List[Dict[str, Any]] = []
    covered: set = set()
    for row in rows:
        branches = extract_row_branches(
            row,
            rules,
            xml_field=xml_field,
            include_xml_field=include_xml_field,
            selected_fields=selected_fields,
        )
        new_branches = {
            (field, branch)
            for field, branch in branches.items()
            if branch and branch != "empty" and (field, branch) not in covered
        }
        if new_branches:
            selected.append(row)
            covered.update(new_branches)
            if len(selected) >= limit:
                break
        else:
            deferred.append(row)
    if len(selected) < limit:
        selected.extend(deferred[: limit - len(selected)])
    return selected


def summarize_branch_coverage(field_branch_counts: Dict[str, Counter]) -> Dict[str, Any]:
    by_field = {
        field: len(counter)
        for field, counter in sorted(field_branch_counts.items())
        if counter
    }
    return {
        "field_count": len(by_field),
        "total_branch_count": sum(by_field.values()),
        "by_field": by_field,
    }


def build_report_summary(
    report_path: Path,
    result: Dict[str, Any],
    mismatch_rows: Sequence[Dict[str, Any]],
    warning_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    field_counts: Counter = Counter()
    field_samples: Dict[str, List[Dict[str, Any]]] = {}
    for row in mismatch_rows:
        for field, diff in (row.get("mismatches") or {}).items():
            field_counts[field] += 1
            samples = field_samples.setdefault(field, [])
            if len(samples) < 3:
                samples.append(
                    {
                        "key": row.get("key"),
                        "dt": row.get("dt"),
                        "expected": truncate_value(diff.get("expected"), max_chars=600) if isinstance(diff, dict) else None,
                        "actual": truncate_value(diff.get("actual"), max_chars=600) if isinstance(diff, dict) else None,
                        "reason": diff.get("reason") if isinstance(diff, dict) else None,
                    }
                )
    warning_counts = Counter(item.get("field") for row in warning_rows for item in row.get("warnings", []))
    return {
        "report": str(report_path),
        "total_problem_rows": len(mismatch_rows),
        "result": {k: v for k, v in result.items() if k != "sample_mismatches"},
        "field_counts": dict(field_counts.most_common()),
        "field_samples": {field: field_samples[field] for field, _ in field_counts.most_common(8)},
        "warning_field_counts": dict(warning_counts.most_common()),
        "warning_rows": len(warning_rows),
    }


def truncate_value(value: Any, max_chars: int = 600) -> Any:
    value = canonicalize(value)
    if isinstance(value, dict):
        return {k: truncate_value(v, max_chars=max_chars) for k, v in value.items()}
    if isinstance(value, list):
        clipped = [truncate_value(item, max_chars=max_chars) for item in value[:5]]
        if len(value) > 5:
            clipped.append(f"... ({len(value) - 5} more)")
        return clipped
    if isinstance(value, str) and len(value) > max_chars:
        return value[:max_chars] + f"... ({len(value) - max_chars} more chars)"
    return value


def compact_mismatch_rows(rows: Sequence[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    compacted: List[Dict[str, Any]] = []
    for row in rows[:limit]:
        compacted.append(
            {
                "key": row.get("key"),
                "dt": row.get("dt"),
                "status": row.get("status"),
                "record": truncate_value(row.get("record"), max_chars=240),
                "mismatches": truncate_value(row.get("mismatches"), max_chars=360),
            }
        )
    return compacted


def write_report_summary(
    report_path: Path,
    result: Dict[str, Any],
    mismatch_rows: Sequence[Dict[str, Any]],
    warning_rows: Sequence[Dict[str, Any]],
) -> None:
    summary_json_path, summary_md_path = summary_paths(report_path)
    summary = build_report_summary(report_path, result, mismatch_rows, warning_rows)
    with summary_json_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, cls=JsonEncoder)

    lines = [
        "# Patent XML 字段校验报告摘要",
        "",
        f"- 分区: `{result.get('dt')}`",
        f"- 抽样: `{result.get('sample_mode')}`, 数量 `{result.get('sample_size')}`",
        f"- 结果: 已校验 `{result.get('checked')}`，通过 `{result.get('passed')}`，失败 `{result.get('failed')}`",
        f"- XML 解析失败: `{result.get('xml_parse_failed')}`",
        f"- 明细报告: `{report_path}`",
        f"- 报告目录: `{report_path.parent}`",
        "",
        "## 字段问题分布",
        "",
    ]
    for field, count in summary["field_counts"].items():
        lines.append(f"- `{field}`: {count}")
    if not summary["field_counts"]:
        lines.append("- 无")
    lines.extend(["", "## 字段问题样例", ""])
    for field, samples in summary["field_samples"].items():
        lines.append(f"### {field} ({summary['field_counts'].get(field)})")
        lines.append("")
        for sample in samples:
            lines.append(f"- key `{sample.get('key')}`, dt `{sample.get('dt')}`, reason `{sample.get('reason')}`")
            lines.append(f"  - expected: `{json.dumps(sample.get('expected'), ensure_ascii=False, cls=JsonEncoder)}`")
            lines.append(f"  - actual: `{json.dumps(sample.get('actual'), ensure_ascii=False, cls=JsonEncoder)}`")
            lines.append("")
    lines.extend(["", "## 跳过/告警字段", ""])
    for field, count in summary["warning_field_counts"].items():
        lines.append(f"- `{field}`: {count}")
    if not summary["warning_field_counts"]:
        lines.append("- 无")
    branch_coverage = summary.get("result", {}).get("branch_coverage", {})
    lines.extend(["", "## 字段 Branch 覆盖", ""])
    lines.append(f"- 覆盖字段数: `{branch_coverage.get('field_count', 0)}`")
    lines.append(f"- 覆盖 branch 总数: `{branch_coverage.get('total_branch_count', 0)}`")
    for field, count in (branch_coverage.get("by_field") or {}).items():
        lines.append(f"- `{field}`: {count}")
    with summary_md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def validate_db(
    *,
    config_path: Path,
    table: str,
    dt: Optional[str],
    limit: Optional[int],
    sample_mode: str,
    report_path: Optional[Path],
    mapping_csv: Path = DEFAULT_MAPPING_CSV,
    xml_field: str = DEFAULT_XML_FIELD,
    key_field: str = "document_number",
    include_xml_field: bool = False,
    fields: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    sample_mode = normalize_sample_mode(sample_mode)
    rules = load_patent_rules(mapping_csv)
    selected_fields = set(fields) if fields else None
    cfg = load_config(config_path)
    mysql_cfg = cfg.get("mysql", {}) if isinstance(cfg.get("mysql"), dict) else {}
    catalog = mysql_cfg.get("catalog")
    database = str(mysql_cfg.get("database") or "dws")
    table = qualify_table_name(table, catalog, database)
    _log(
        f"[info] 专利 XML 字段校验开始：dt={dt!r}, limit={limit}, sample_mode={sample_mode}, "
        f"table={table}, xml_field={xml_field}"
    )

    checked = passed = failed = xml_parse_failed = 0
    mismatch_rows: List[Dict[str, Any]] = []
    warning_rows: List[Dict[str, Any]] = []
    field_branch_counts: Dict[str, Counter] = {}

    with connect_starrocks(config_path) as conn:
        _log("[info] StarRocks 连接成功")
        dt_list = [dt] if dt is not None else discover_dt_values(conn, table)
        if dt is None:
            _log(f"[info] 自动发现 {len(dt_list)} 个 dt 分区，逐分区验证")

        for partition_dt in dt_list:
            _log(f"[info] 分区 {partition_dt}：开始抽样记录…")
            query_limit = limit
            if sample_mode == SAMPLE_MODE_BRANCH_COVERAGE and limit is not None:
                query_limit = max(int(limit), int(limit) * BRANCH_COVERAGE_CANDIDATE_MULTIPLIER)
            sql, params = build_sample_query(
                table,
                partition_dt,
                query_limit,
                key_field=key_field,
                xml_field=xml_field,
                sample_mode=sample_mode,
            )
            t0 = time.monotonic()
            rows = fetch_records(conn, sql, params)
            if sample_mode == SAMPLE_MODE_BRANCH_COVERAGE:
                candidate_count = len(rows)
                rows = select_branch_coverage_rows(
                    rows,
                    rules,
                    limit=limit,
                    xml_field=xml_field,
                    include_xml_field=include_xml_field,
                    selected_fields=selected_fields,
                )
                _log(
                    f"[info] 分区 {partition_dt}：branch 候选 {candidate_count} 条，"
                    f"保留 {len(rows)} 条"
                )
            _log(f"[info] 分区 {partition_dt}：抽到 {len(rows)} 条，耗时 {time.monotonic() - t0:.1f}s，开始解析 XML…")
            for idx, row in enumerate(rows, start=1):
                checked += 1
                if idx == 1 or idx % 20 == 0:
                    _log(f"[info] 分区 {partition_dt}：已比对 {idx}/{len(rows)} 条")
                key = row.get(key_field) or row.get("sha256") or f"{partition_dt}:{idx}"
                mismatches, warnings, branches = validate_row(
                    row,
                    rules,
                    xml_field=xml_field,
                    include_xml_field=include_xml_field,
                    selected_fields=selected_fields,
                )
                for field, branch in branches.items():
                    if not branch:
                        continue
                    field_branch_counts.setdefault(field, Counter())[branch] += 1
                if xml_field in mismatches:
                    xml_parse_failed += 1
                if warnings:
                    warning_rows.append({"key": key, "dt": partition_dt, "warnings": warnings})
                if mismatches:
                    failed += 1
                    mismatch_rows.append(
                        {
                            "key": key,
                            "dt": partition_dt,
                            "status": "field_mismatch",
                            "record": compact_record_for_report(row, xml_field),
                            "mismatches": mismatches,
                        }
                    )
                else:
                    passed += 1

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as f:
            for row in mismatch_rows:
                f.write(json.dumps(row, ensure_ascii=False, cls=JsonEncoder) + "\n")
        warning_path = report_path.parent / "xml_field_warning.jsonl"
        with warning_path.open("w", encoding="utf-8") as f:
            for row in warning_rows:
                f.write(json.dumps(row, ensure_ascii=False, cls=JsonEncoder) + "\n")

    result = {
        "status": "ok",
        "kind": "patent_xml",
        "table": table,
        "key_field": key_field,
        "xml_field": xml_field,
        "dt": dt,
        "sample_mode": sample_mode,
        "sample_size": limit,
        "checked": checked,
        "passed": passed,
        "failed": failed,
        "xml_parse_failed": xml_parse_failed,
        "warning_rows": len(warning_rows),
        "branch_coverage": summarize_branch_coverage(field_branch_counts),
        "report_path": str(report_path) if report_path is not None else None,
        "sample_mismatches": compact_mismatch_rows(mismatch_rows),
    }
    if report_path is not None:
        write_report_summary(report_path, result, mismatch_rows, warning_rows)
    print(json.dumps(result, ensure_ascii=False, cls=JsonEncoder))
    return result


def cli() -> None:
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    config_args, _ = config_parser.parse_known_args()
    cfg = load_config(config_args.config) if config_args.config.exists() else {}
    patent_cfg = cfg.get("patent_parsed_info", {}) if isinstance(cfg.get("patent_parsed_info"), dict) else {}

    default_csv = patent_cfg.get("mapping_csv")
    default_csv_path = PROJECT_ROOT / default_csv if default_csv else DEFAULT_MAPPING_CSV

    parser = argparse.ArgumentParser(description="Validate parsed patent DB fields against raw XML content.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="shared settings JSON path")
    parser.add_argument("--mapping-csv", type=Path, default=default_csv_path, help="patent field mapping CSV")
    parser.add_argument("--table", default=patent_cfg.get("table", DEFAULT_TABLE))
    parser.add_argument("--dt", default=patent_cfg.get("dt"), help="dt partition filter")
    parser.add_argument("--limit", type=int, default=int(patent_cfg.get("limit", 200)))
    parser.add_argument("--full", action="store_true", help="validate all sampled partition rows without LIMIT")
    parser.add_argument("--xml-field", default=patent_cfg.get("xml_field", DEFAULT_XML_FIELD))
    parser.add_argument("--key-field", default=patent_cfg.get("key_field", "document_number"))
    parser.add_argument(
        "--sample-mode",
        choices=(SAMPLE_MODE_RANDOM, SAMPLE_MODE_BRANCH_COVERAGE),
        default=normalize_sample_mode(patent_cfg.get("sample_mode", SAMPLE_MODE_BRANCH_COVERAGE)),
        help="random: 随机抽样；branch-coverage: 覆盖所有 branch 抽样",
    )
    parser.add_argument(
        "--fields",
        default=patent_cfg.get("fields"),
        help="comma separated field allowlist, e.g. document_number,publication_date",
    )
    parser.add_argument("--include-xml-field", action="store_true", help="also compare the XML field itself")
    parser.add_argument("--report", type=Path, default=patent_cfg.get("report_path"), help="JSONL report path")
    args = parser.parse_args()

    fields = None
    if args.fields:
        fields = [field.strip() for field in str(args.fields).split(",") if field.strip()]
    report_path = Path(args.report) if args.report else default_report_path(
        args.dt,
        args.sample_mode,
        args.full,
    )
    validate_db(
        config_path=args.config,
        table=args.table,
        dt=args.dt,
        limit=None if args.full else args.limit,
        sample_mode=args.sample_mode,
        report_path=report_path,
        mapping_csv=args.mapping_csv,
        xml_field=args.xml_field,
        key_field=args.key_field,
        include_xml_field=args.include_xml_field,
        fields=fields,
    )


from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule
from dingo.model.rule.scibase.report_utils import bool_param, int_param, write_temp_settings


def _fields_param(value: Any) -> Optional[List[str]]:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()]


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    ["sci_base_qa_test", "meta_patent_parsed_info"],
)
class RuleSciBaseMetaPatentParsedInfoReport(BaseRule):
    _metric_info = {
        "category": "Rule-Based Metadata Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleSciBaseMetaPatentParsedInfoReport",
        "description": "Run SciBase patent XML parsed-field validation with branch coverage sampling.",
        "paper_title": "",
        "paper_url": "",
        "paper_authors": "",
        "evaluation_results": "",
    }

    _required_fields = [RequiredField.METADATA]
    dynamic_config = EvaluatorRuleArgs(parameters={})

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        del input_data
        params = cls.dynamic_config.parameters or {}
        full = bool_param(params, "full", False)
        sample_mode = normalize_sample_mode(params.get("sample_mode", SAMPLE_MODE_BRANCH_COVERAGE))
        report_path = Path(params["report_path"]) if params.get("report_path") else None
        if report_path is None and params.get("output_dir"):
            report_path = Path(str(params["output_dir"])) / "xml_field_mismatch.jsonl"
        if report_path is None:
            report_path = default_report_path(
                params.get("dt"),
                sample_mode,
                full,
            )

        config_path = write_temp_settings(params)
        result = validate_db(
            config_path=config_path,
            table=str(params.get("target_table") or params.get("table") or DEFAULT_TABLE),
            dt=params.get("dt"),
            limit=None if full else int_param(params, "limit", 200),
            sample_mode=sample_mode,
            report_path=report_path,
            mapping_csv=Path(str(params.get("mapping_csv") or DEFAULT_MAPPING_CSV)),
            xml_field=str(params.get("xml_field") or DEFAULT_XML_FIELD),
            key_field=str(params.get("key_field") or "document_number"),
            include_xml_field=bool_param(params, "include_xml_field", False),
            fields=_fields_param(params.get("fields")),
        )
        branch_coverage = result.get("branch_coverage") or {}
        is_bad = bool(result.get("failed") or result.get("xml_parse_failed"))
        return EvalDetail(
            metric=cls.__name__,
            status=is_bad,
            label=[
                f"{cls.metric_type}.{cls.__name__}" if is_bad else "QUALITY_GOOD",
            ],
            reason=[
                str(report_path.parent),
                f"checked={result.get('checked')}",
                f"failed={result.get('failed')}",
                f"branch_fields={branch_coverage.get('field_count', 0)}",
                f"branch_total={branch_coverage.get('total_branch_count', 0)}",
            ],
        )


if __name__ == "__main__":
    cli()
