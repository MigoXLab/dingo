#!/usr/bin/env python3
"""DB validator for unified metadata and Xinghe fulltext union table.

The validator is read-only. It compares the unified target table with three
source tables (paper unique, ebook unique, Xinghe fulltext), validates target
field values, and reports target field NULL / empty rates.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

try:
    import pymysql
except ImportError:  # pragma: no cover - runtime dependency check
    pymysql = None  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
DEFAULT_CONFIG_PATH = Path("sci_base_qa_test_config.json")
TEMPLATE_CONFIG_PATH = ASSETS_DIR / "settings.template.json"
DEFAULT_MAPPING_CSV = ASSETS_DIR / "union_unique_data_mapping.csv"
DEFAULT_JOURNAL_MAPPING_CSV = ASSETS_DIR / "journal_name_mapping_execute_20260512.csv"
REPORT_ROOT = Path("report")
DEFAULT_PAPER_TABLE = "dws_meta_paper_doi_unique_acc_d"
DEFAULT_EBOOK_TABLE = "dws_meta_ebook_isbn_unique_acc_d"
DEFAULT_XINGHE_TABLE = "ads_xinghe_library_acc"
DEFAULT_TARGET_TABLE = "ads_meta_unified_unique_meta_data_acc_d"
XINGHE_SUPPLEMENT_FIELDS = {
    "doi",
    "title",
    "abstract",
    "language",
    "author",
    "grade_class",
    "grade",
    "supplementary_material",
}
IGNORED_TARGET_EXTRA_FIELDS = {"dt", "mesh"}
LICENSE_ALLOWED: Set[str] = {
    "cc-by",
    "cc-by-nc",
    "cc-by-sa",
    "cc-by-nd",
    "cc-by-nc-sa",
    "cc-by-nc-nd",
    "other-oa",
    "cc0",
    "",
    "public-domain",
    "publisher-specific-oa",
    "publisher-specific",
    "wiley-specific",
    "elsevier-specific",
    "oup-specific",
    "acs-specific",
    "rsc-specific",
    "iop-specific",
    "unspecified-oa",
    "implied-oa",
    "nonexclusive-distrib",
    "gpl-v1",
    "gpl-v2",
    "gpl-v3",
    "mit",
    "ogl-c",
    "pd",
}
DEFAULT_LICENSE_MAP: Dict[str, str] = {
    "http://arxiv.org/licenses/nonexclusive-distrib/1.0/": "nonexclusive-distrib",
    "https://arxiv.org/licenses/nonexclusive-distrib/1.0/": "nonexclusive-distrib",
    "arxiv-nonexclusive-distrib-1.0": "nonexclusive-distrib",
    "http://creativecommons.org/licenses/by/4.0/": "cc-by",
    "https://creativecommons.org/licenses/by/4.0/": "cc-by",
    "http://creativecommons.org/licenses/by/3.0/": "cc-by",
    "https://creativecommons.org/licenses/by/3.0/": "cc-by",
    "CC-BY-4.0": "cc-by",
    "CC-BY-3.0": "cc-by",
    "CCBY": "cc-by",
    "http://creativecommons.org/licenses/by-nc/4.0/": "cc-by-nc",
    "https://creativecommons.org/licenses/by-nc/4.0/": "cc-by-nc",
    "CCBYNC": "cc-by-nc",
    "http://creativecommons.org/licenses/by-sa/4.0/": "cc-by-sa",
    "https://creativecommons.org/licenses/by-sa/4.0/": "cc-by-sa",
    "CCBYSA": "cc-by-sa",
    "http://creativecommons.org/licenses/by-nd/4.0/": "cc-by-nd",
    "https://creativecommons.org/licenses/by-nd/4.0/": "cc-by-nd",
    "CCBYND": "cc-by-nd",
    "http://creativecommons.org/licenses/by-nc-sa/4.0/": "cc-by-nc-sa",
    "https://creativecommons.org/licenses/by-nc-sa/4.0/": "cc-by-nc-sa",
    "CCBYNCSA": "cc-by-nc-sa",
    "http://creativecommons.org/licenses/by-nc-nd/4.0/": "cc-by-nc-nd",
    "https://creativecommons.org/licenses/by-nc-nd/4.0/": "cc-by-nc-nd",
    "CCBYNCND": "cc-by-nc-nd",
    "http://creativecommons.org/publicdomain/zero/1.0/": "cc0",
    "https://creativecommons.org/publicdomain/zero/1.0/": "cc0",
    "CC0-1.0": "cc0",
    "CC0": "cc0",
}
CC_LICENSE_URL_RULES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"creativecommons\.org/licenses/by-nc-sa", re.I), "cc-by-nc-sa"),
    (re.compile(r"creativecommons\.org/licenses/by-nc-nd", re.I), "cc-by-nc-nd"),
    (re.compile(r"creativecommons\.org/licenses/by-nc(?:/|$)", re.I), "cc-by-nc"),
    (re.compile(r"creativecommons\.org/licenses/by-sa", re.I), "cc-by-sa"),
    (re.compile(r"creativecommons\.org/licenses/by-nd", re.I), "cc-by-nd"),
    (re.compile(r"creativecommons\.org/licenses/by(?:/|$)", re.I), "cc-by"),
    (re.compile(r"creativecommons\.org/publicdomain/zero", re.I), "cc0"),
    (re.compile(r"arxiv\.org/licenses/nonexclusive-distrib", re.I), "nonexclusive-distrib"),
]


def log_step(message: str) -> None:
    print(f"[info] {message}", file=sys.stderr, flush=True)


def timed_step(name: str):
    class _Timer:
        def __enter__(self):
            self.start = time.time()
            log_step(f"{name} 开始")
            return self

        def __exit__(self, exc_type, exc, tb):
            elapsed = time.time() - self.start
            status = "失败" if exc_type else "完成"
            log_step(f"{name} {status}，耗时 {elapsed:.1f}s")
            return False

    return _Timer()


def safe_filename_token(value: Optional[Any]) -> str:
    text = "all" if value in (None, "") else str(value)
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in text).strip("_") or "all"


def default_output_dir(
    target_dt: Optional[str],
    paper_dt: Optional[str],
    ebook_dt: Optional[str],
    limit: Optional[int],
    full: bool,
) -> Path:
    del paper_dt, ebook_dt, limit, full
    dt_token = safe_filename_token(target_dt)
    prefix = f"union_unique_meta_data_{dt_token}_"
    max_seq = 0
    if REPORT_ROOT.exists():
        for path in REPORT_ROOT.glob(f"{prefix}[0-9][0-9][0-9][0-9]"):
            if not path.is_dir():
                continue
            seq_text = path.name.rsplit("_", 1)[-1]
            if seq_text.isdigit():
                max_seq = max(max_seq, int(seq_text))
    return REPORT_ROOT / f"{prefix}{max_seq + 1:04d}"


@dataclass(frozen=True)
class UnionFieldSpec:
    field_name: str
    data_type: str
    paper_source: str
    ebook_source: str
    xinghe_source: str


class JsonEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            if obj == obj.to_integral_value():
                return int(obj)
            return float(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


def normalize_data_type(data_type: str) -> str:
    text = (data_type or "").strip()
    lower = text.lower()
    if lower.startswith("list["):
        inner = lower[5:-1].strip()
        return f"array<{inner}>"
    if lower == "object":
        return "map"
    if lower in ("string", "integer", "long", "float", "boolean"):
        return {
            "string": "string",
            "integer": "int",
            "long": "bigint",
            "float": "float",
            "boolean": "boolean",
        }[lower]
    if lower.startswith("timestamp"):
        return "bigint"
    return lower or text


def _is_field_ref(value: str) -> bool:
    if not value or value in ("-", "/"):
        return False
    if any("\u4e00" <= c <= "\u9fff" for c in value):
        return False
    if "'" in value:
        return False
    return True


def load_union_specs(
    path: Path,
    *,
    field_col: str = "",
    type_col: str = "",
    paper_col: str = "",
    ebook_col: str = "",
    xinghe_col: str = "",
) -> List[UnionFieldSpec]:
    specs: List[UnionFieldSpec] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        if not field_col:
            field_col = "统一字段名" if "统一字段名" in fieldnames else "字段名"
        if not type_col:
            type_col = "字段值数据类型" if "字段值数据类型" in fieldnames else "数据类型"
        if not paper_col:
            paper_col = "源字段映射(论文)" if "源字段映射(论文)" in fieldnames else "论文表对应字段"
        if not ebook_col:
            ebook_col = "源字段映射(图书)" if "源字段映射(图书)" in fieldnames else "图书表对应字段"
        if not xinghe_col:
            xinghe_col = "源字段映射(星河)" if "源字段映射(星河)" in fieldnames else "星河全文表对应字段"
        if not reader.fieldnames or field_col not in reader.fieldnames:
            available = ", ".join(fn for fn in (reader.fieldnames or []) if fn.strip())
            raise ValueError(
                f"映射文件 {path} 缺少字段列 {field_col!r}（可用列: {available}）"
            )
        for row in reader:
            name = (row.get(field_col) or "").strip()
            if not name:
                continue
            specs.append(
                UnionFieldSpec(
                    field_name=name,
                    data_type=normalize_data_type((row.get(type_col) or "").strip()),
                    paper_source=(row.get(paper_col) or "").strip(),
                    ebook_source=(row.get(ebook_col) or "").strip(),
                    xinghe_source=(row.get(xinghe_col) or "").strip(),
                )
            )
    return specs


def build_field_maps(
    specs: Sequence[UnionFieldSpec],
    metadata_type: str,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    metadata_map: Dict[str, str] = {}
    xinghe_map: Dict[str, str] = {}
    for spec in specs:
        source = spec.paper_source if metadata_type == "paper" else spec.ebook_source
        if _is_field_ref(source):
            metadata_map[source] = spec.field_name
        if _is_field_ref(spec.xinghe_source):
            xinghe_map[spec.xinghe_source] = spec.field_name
    return metadata_map, xinghe_map


def build_empty_output(specs: Sequence[UnionFieldSpec], metadata_type: str) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for spec in specs:
        output[spec.field_name] = False if spec.data_type == "boolean" else None
    output["metadata_type"] = metadata_type
    return output


def raw_key(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def normalize_key_text(value: Any) -> str:
    if value is None:
        return ""
    return html.unescape(str(value)).strip()


def key_from_unique_id(unique_id: Any, metadata_type: str) -> str:
    if unique_id in (None, ""):
        return ""
    prefix = f"{metadata_type}:"
    text = str(unique_id)
    if not text.startswith(prefix):
        return ""
    return normalize_key_text(text[len(prefix):])


def target_key_for_row(row: Dict[str, Any], metadata_type: str) -> str:
    key_field = "doi" if metadata_type == "paper" else "isbn13"
    key = normalize_key_text(row.get(key_field))
    if key:
        return key
    return key_from_unique_id(row.get("unique_id"), metadata_type)


def normalize_lookup_key(key: Any, metadata_type: str) -> str:
    if key in (None, ""):
        return ""
    text = normalize_key_text(key)
    return text.lower() if metadata_type == "paper" else text


def get_source_value(record: Dict[str, Any], source: str, source_kind: str = "") -> Any:
    if source in record:
        return record.get(source)
    if "." not in source:
        return None
    current: Any = record
    for part in source.split("."):
        current = normalize_json_like(current)
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def apply_field_map(
    output: Dict[str, Any],
    record: Optional[Dict[str, Any]],
    field_map: Dict[str, str],
    *,
    source_kind: str = "",
    overwrite: bool = True,
    fallback_only_fields: Optional[Set[str]] = None,
) -> None:
    if record is None:
        return
    fallback_only_fields = fallback_only_fields or set()
    for src, dst in field_map.items():
        value = get_source_value(record, src, source_kind)
        if value is None:
            continue
        if not overwrite or dst in fallback_only_fields:
            current = output.get(dst)
            if not is_deep_empty(current):
                continue
        if value is not None:
            output[dst] = value


def apply_xinghe_only_metadata_fallback(
    output: Dict[str, Any],
    record: Optional[Dict[str, Any]],
    *,
    metadata_type: str,
    specs: Sequence[UnionFieldSpec],
) -> None:
    if record is None:
        return
    for spec in specs:
        if output.get(spec.field_name) is not None:
            continue
        metadata_source = spec.paper_source if metadata_type == "paper" else spec.ebook_source
        candidates = []
        if _is_field_ref(metadata_source):
            candidates.append(metadata_source)
        candidates.append(spec.field_name)
        for src in candidates:
            value = get_source_value(record, src, "xinghe")
            if value is not None:
                output[spec.field_name] = value
                break


def normalize_journal_lookup_key(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split()).casefold()


def load_journal_name_mapping(
    path: Path = DEFAULT_JOURNAL_MAPPING_CSV,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    exact_map: Dict[str, str] = {}
    normalized_map: Dict[str, str] = {}
    if not path.exists():
        return exact_map, normalized_map
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            source_name = (row.get("source_journal_name") or "").strip()
            target_name = (row.get("target_journal_name") or "").strip()
            if not source_name or not target_name:
                continue
            exact_map.setdefault(source_name, target_name)
            normalized_key = normalize_journal_lookup_key(source_name)
            if normalized_key:
                normalized_map.setdefault(normalized_key, target_name)
    return exact_map, normalized_map


def lookup_journal_name_unified(value: Any) -> Any:
    if is_deep_empty(value):
        return value
    global JOURNAL_NAME_MAPPING_CACHE
    if JOURNAL_NAME_MAPPING_CACHE is None:
        JOURNAL_NAME_MAPPING_CACHE = load_journal_name_mapping()
    exact_map, normalized_map = JOURNAL_NAME_MAPPING_CACHE
    text = " ".join(str(value).strip().split())
    return exact_map.get(text) or normalized_map.get(normalize_journal_lookup_key(text)) or value


def apply_derived_fields(output: Dict[str, Any]) -> None:
    if is_deep_empty(output.get("publication_venue_name_unified")):
        output["publication_venue_name_unified"] = lookup_journal_name_unified(
            output.get("publication_venue_name")
        )


def merge_one(
    metadata_record: Optional[Dict[str, Any]],
    xinghe_record: Optional[Dict[str, Any]],
    *,
    metadata_type: str,
    specs: Sequence[UnionFieldSpec],
    metadata_map: Dict[str, str],
    xinghe_map: Dict[str, str],
    fallback_key: Optional[Any] = None,
) -> Dict[str, Any]:
    output = build_empty_output(specs, metadata_type)
    apply_field_map(output, metadata_record, metadata_map, source_kind=metadata_type)

    if xinghe_record is not None:
        sha256 = xinghe_record.get("sha256")
        output["access_xinghe_repository_has_fulltext"] = sha256 not in (None, "", [], {})
        apply_field_map(
            output,
            xinghe_record,
            xinghe_map,
            source_kind="xinghe",
            fallback_only_fields=XINGHE_SUPPLEMENT_FIELDS,
        )
        if metadata_record is None:
            apply_xinghe_only_metadata_fallback(
                output,
                xinghe_record,
                metadata_type=metadata_type,
                specs=specs,
            )

    uid_field = "doi" if metadata_type == "paper" else "isbn13"
    xinghe_key = "doi" if metadata_type == "paper" else "isbn"
    key_val = raw_key(output.get(uid_field))
    if not key_val and metadata_record is None:
        fallback = raw_key(xinghe_record.get(xinghe_key)) if xinghe_record is not None else raw_key(fallback_key)
        if fallback:
            output[uid_field] = xinghe_record.get(xinghe_key) if xinghe_record is not None else fallback
            key_val = fallback
    output["unique_id"] = f"{metadata_type}:{key_val}" if key_val else None
    apply_derived_fields(output)
    return output


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
    return pymysql.connect(
        host=mysql_cfg["host"],
        port=int(mysql_cfg["port"]),
        user=mysql_cfg["user"],
        password=mysql_cfg["password"],
        charset=mysql_cfg.get("charset", "utf8mb4"),
        connect_timeout=int(mysql_cfg.get("connect_timeout", 30)),
        read_timeout=int(mysql_cfg.get("read_timeout", 180)),
    )


def qualify_table_name(
    table: str,
    catalog: Optional[str],
    database: str = "dws",
) -> str:
    """Resolve table to catalog.database.table for StarRocks Iceberg queries."""
    parts = [part.strip() for part in table.split(".") if part.strip()]
    if len(parts) >= 3:
        return table
    if len(parts) == 2:
        db_name, table_name = parts
        if catalog:
            return f"{catalog}.{db_name}.{table_name}"
        return table
    if len(parts) == 1:
        if catalog:
            return f"{catalog}.{database}.{parts[0]}"
        return f"{database}.{parts[0]}"
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


def fetch_one(conn: Any, sql: str, params: Sequence[Any] = ()) -> Optional[Dict[str, Any]]:
    rows = fetch_records(conn, sql, params)
    return rows[0] if rows else None


def normalize_json_like(value: Any) -> Any:
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
    value = normalize_json_like(value)
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): canonicalize(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, list):
        return [canonicalize(v) for v in value]
    return value


def comparable_record(record: Dict[str, Any], fields: Iterable[str]) -> Dict[str, Any]:
    return {field: canonicalize(record.get(field)) for field in fields}


HTML_UNESCAPE_COMPARE_FIELDS = {"unique_id", "doi", "isbn13"}


def normalize_author_for_compare(value: Any) -> Any:
    value = normalize_json_like(value)
    if value is None:
        return None
    if isinstance(value, str):
        text = " ".join(value.strip().split())
        return None if text in ("", "[]", "{}") else [text]
    if isinstance(value, dict):
        name = value.get("name")
        if name is None:
            return None
        text = " ".join(str(name).strip().split())
        return None if not text else [text]
    if isinstance(value, list):
        names: List[str] = []
        for item in value:
            item = normalize_json_like(item)
            if isinstance(item, dict):
                item = item.get("name")
            if item is None:
                continue
            text = " ".join(str(item).strip().split())
            if text:
                names.append(text)
        if not names:
            return None
        return sorted(dict.fromkeys(names))
    return value


def normalize_license_value(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text:
        return ""
    if text in DEFAULT_LICENSE_MAP:
        return DEFAULT_LICENSE_MAP[text]
    trimmed = text.rstrip("/")
    if trimmed in DEFAULT_LICENSE_MAP:
        return DEFAULT_LICENSE_MAP[trimmed]
    compact = re.sub(r"[^A-Za-z0-9]", "", text).upper()
    if compact in DEFAULT_LICENSE_MAP:
        return DEFAULT_LICENSE_MAP[compact]
    lower = text.lower()
    if lower in LICENSE_ALLOWED:
        return lower
    for pattern, canonical in CC_LICENSE_URL_RULES:
        if pattern.search(text):
            return canonical
    return lower


def normalize_locations_for_compare(value: Any) -> Any:
    value = normalize_json_like(value)
    if value is None:
        return None
    if isinstance(value, str):
        if value.strip() in ("", "[]"):
            return None
        return value
    if not isinstance(value, list):
        return value
    out: List[Dict[str, Any]] = []
    for item in value:
        item = normalize_json_like(item)
        if not isinstance(item, dict):
            continue
        loc = {str(k): canonicalize(v) for k, v in item.items()}
        if "license" in loc:
            loc["license"] = normalize_license_value(loc.get("license"))
        if "is_oa" in loc and loc.get("is_oa") is not None:
            loc["is_oa"] = str(loc.get("is_oa")).lower()
        out.append({key: loc.get(key) for key in sorted(loc)})
    return out or None


def normalize_empty_for_compare(value: Any, data_type: str, field: str = "") -> Any:
    type_text = (data_type or "").strip().lower()
    if value is None:
        return None
    if field == "author":
        return normalize_author_for_compare(value)
    if field == "access_license":
        normalized_license = normalize_license_value(value)
        return normalized_license or None
    if field == "locations":
        return normalize_locations_for_compare(value)
    if field in HTML_UNESCAPE_COMPARE_FIELDS and isinstance(value, str):
        value = html.unescape(value).strip()
    if isinstance(value, list) and is_deep_empty(value):
        return None
    if type_text in ("string", "varchar", "char", "text"):
        return None if isinstance(value, str) and value.strip() == "" else value
    if type_text.startswith("array") or type_text.startswith("list"):
        if is_deep_empty(value):
            return None
        if isinstance(value, str) and value.strip() in ("", "[]"):
            return None
    if type_text.startswith("struct") or type_text.startswith("map"):
        return None if is_deep_empty(value) else value
    return value


def is_deep_empty(value: Any) -> bool:
    value = normalize_json_like(value)
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return stripped in ("", "[]", "{}")
    if isinstance(value, dict):
        return all(is_deep_empty(item) for item in value.values())
    if isinstance(value, list):
        return all(is_deep_empty(item) for item in value)
    return False


def compare_records(
    expected: Dict[str, Any],
    actual: Dict[str, Any],
    field_types: Optional[Dict[str, str]] = None,
) -> Dict[str, Dict[str, Any]]:
    mismatches: Dict[str, Dict[str, Any]] = {}
    field_types = field_types or {}
    for field, expected_value in expected.items():
        actual_value = actual.get(field)
        expected_value = normalize_empty_for_compare(expected_value, field_types.get(field, ""), field)
        actual_value = normalize_empty_for_compare(actual_value, field_types.get(field, ""), field)
        if expected_value != actual_value:
            mismatches[field] = {
                "expected": expected_value,
                "actual": actual_value,
            }
    return mismatches


def _dt_clause(dt: Optional[str], params: List[Any], alias: Optional[str] = None) -> str:
    if dt is None:
        return ""
    params.append(dt)
    prefix = f"{quote_identifier(alias)}." if alias else ""
    return f" AND {prefix}`dt` = %s"


def _limit_clause(limit: Optional[int]) -> str:
    return "" if limit is None else f" LIMIT {int(limit)}"


def split_limit(limit: Optional[int], parts: int) -> List[Optional[int]]:
    if limit is None:
        return [None] * parts
    base = max(0, int(limit)) // parts
    remainder = max(0, int(limit)) % parts
    return [base + (1 if i < remainder else 0) for i in range(parts)]


def show_columns(conn: Any, table: str) -> List[str]:
    rows = fetch_records(conn, f"SHOW COLUMNS FROM {quote_identifier(table)}")
    columns: List[str] = []
    for row in rows:
        field = row.get("Field") or row.get("field") or next(iter(row.values()))
        columns.append(str(field))
    return columns


def show_column_types(conn: Any, table: str) -> Dict[str, str]:
    rows = fetch_records(conn, f"SHOW COLUMNS FROM {quote_identifier(table)}")
    column_types: Dict[str, str] = {}
    for row in rows:
        field = row.get("Field") or row.get("field") or next(iter(row.values()))
        data_type = row.get("Type") or row.get("type") or ""
        column_types[str(field)] = str(data_type)
    return column_types


def validate_schema(
    conn: Any,
    *,
    target_table: str,
    specs: Sequence[UnionFieldSpec],
) -> Dict[str, Any]:
    expected_fields = [spec.field_name for spec in specs]
    actual_fields = show_columns(conn, target_table)
    actual_set = set(actual_fields)
    expected_set = set(expected_fields)
    return {
        "missing_fields": [field for field in expected_fields if field not in actual_set],
        "extra_fields": [
            field
            for field in actual_fields
            if field not in expected_set and field not in IGNORED_TARGET_EXTRA_FIELDS
        ],
        "expected_count": len(expected_fields),
        "actual_count": len(actual_fields),
    }


def count_table(conn: Any, table: str, dt: Optional[str]) -> int:
    params: List[Any] = []
    sql = f"SELECT COUNT(*) AS cnt FROM {quote_identifier(table)} WHERE 1=1{_dt_clause(dt, params)}"
    row = fetch_one(conn, sql, params)
    return int(row["cnt"]) if row else 0


def count_xinghe_only_distinct_key(
    conn: Any,
    *,
    xinghe_table: str,
    metadata_table: str,
    xinghe_key_field: str,
    metadata_key_field: str,
    metadata_dt: Optional[str],
) -> int:
    params: List[Any] = []
    metadata_dt_join = "AND m.`dt` = %s" if metadata_dt is not None else ""
    if metadata_dt is not None:
        params.append(metadata_dt)
    sql = (
        "SELECT COUNT(DISTINCT "
        f"x.`{xinghe_key_field}`"
        ") AS cnt "
        f"FROM {quote_identifier(xinghe_table)} x "
        f"LEFT JOIN {quote_identifier(metadata_table)} m "
        f"ON m.`{metadata_key_field}` = x.`{xinghe_key_field}` {metadata_dt_join} "
        f"WHERE x.`{xinghe_key_field}` IS NOT NULL AND x.`{xinghe_key_field}` != '' "
        f"AND m.`{metadata_key_field}` IS NULL"
    )
    row = fetch_one(conn, sql, params)
    return int(row["cnt"]) if row else 0


def source_coverage_counts(
    conn: Any,
    *,
    paper_table: str,
    ebook_table: str,
    xinghe_table: str,
    target_table: str,
    target_dt: Optional[str],
    paper_dt: Optional[str],
    ebook_dt: Optional[str],
) -> Dict[str, Any]:
    paper_source = count_table(conn, paper_table, paper_dt)
    ebook_source = count_table(conn, ebook_table, ebook_dt)
    target = count_table(conn, target_table, target_dt)
    xinghe_only_paper_count = count_xinghe_only_distinct_key(
        conn,
        xinghe_table=xinghe_table,
        metadata_table=paper_table,
        xinghe_key_field="doi",
        metadata_key_field="doi",
        metadata_dt=paper_dt,
    )
    xinghe_only_ebook_count = count_xinghe_only_distinct_key(
        conn,
        xinghe_table=xinghe_table,
        metadata_table=ebook_table,
        xinghe_key_field="isbn",
        metadata_key_field="isbn13",
        metadata_dt=ebook_dt,
    )
    expected_target_count = (
        paper_source
        + ebook_source
        + xinghe_only_paper_count
        + xinghe_only_ebook_count
    )
    result: Dict[str, Any] = {
        "paper_source": paper_source,
        "ebook_source": ebook_source,
        "xinghe_only_paper_count": xinghe_only_paper_count,
        "xinghe_only_ebook_count": xinghe_only_ebook_count,
        "expected_target_count": expected_target_count,
        "actual_target_count": target,
        "target_count_diff": target - expected_target_count,
    }
    return result


def count_xinghe_only_missing_target(
    conn: Any,
    *,
    xinghe_table: str,
    metadata_table: str,
    target_table: str,
    metadata_type: str,
    xinghe_key_field: str,
    metadata_key_field: str,
    target_dt: Optional[str],
    metadata_dt: Optional[str],
) -> int:
    params: List[Any] = []
    metadata_dt_join = "AND m.`dt` = %s" if metadata_dt is not None else ""
    if metadata_dt is not None:
        params.append(metadata_dt)
    target_dt_join = "AND t.`dt` = %s" if target_dt is not None else ""
    if target_dt is not None:
        params.append(target_dt)
    sql = (
        "SELECT COUNT(*) AS cnt "
        f"FROM {quote_identifier(xinghe_table)} x "
        f"LEFT JOIN {quote_identifier(metadata_table)} m "
        f"ON m.`{metadata_key_field}` = x.`{xinghe_key_field}` {metadata_dt_join} "
        f"LEFT JOIN {quote_identifier(target_table)} t "
        f"ON t.`unique_id` = CONCAT('{metadata_type}:', x.`{xinghe_key_field}`) {target_dt_join} "
        f"WHERE x.`{xinghe_key_field}` IS NOT NULL AND x.`{xinghe_key_field}` != '' "
        f"AND m.`{metadata_key_field}` IS NULL AND t.`unique_id` IS NULL"
    )
    row = fetch_one(conn, sql, params)
    return int(row["cnt"]) if row else 0


def skipped_coverage_counts(reason: str) -> Dict[str, Any]:
    return {"skipped": True, "reason": reason}


def failed_coverage_counts(exc: Exception) -> Dict[str, Any]:
    return {
        "skipped": True,
        "status": "failed",
        "reason": "coverage_count_failed",
        "error_type": type(exc).__name__,
        "error": str(exc),
    }


def build_target_sample_query(
    target_table: str,
    dt: Optional[str],
    limit: Optional[int],
    metadata_type: Optional[str] = None,
    sample_mode: str = "natural",
) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    type_clause = ""
    if metadata_type is not None:
        type_clause = " AND `metadata_type` = %s"
        params.append(metadata_type)
    sql = (
        f"SELECT * FROM {quote_identifier(target_table)} "
        f"WHERE `unique_id` IS NOT NULL AND `metadata_type` IN ('paper', 'ebook')"
        f"{type_clause}{_dt_clause(dt, params)}"
        f"{' AND MOD(CRC32(`unique_id`), 100) = 0' if sample_mode == 'hash' else ''}"
        f"{_limit_clause(limit)}"
    )
    return sql, params


def fetch_target_samples(
    conn: Any,
    *,
    target_table: str,
    dt: Optional[str],
    limit: Optional[int],
    sample_mode: str = "natural",
) -> List[Dict[str, Any]]:
    if limit is None:
        sql, params = build_target_sample_query(target_table, dt, None)
        return fetch_records(conn, sql, params)

    rows: List[Dict[str, Any]] = []
    for metadata_type, part_limit in zip(("paper", "ebook"), split_limit(limit, 2)):
        if part_limit == 0:
            continue
        sql, params = build_target_sample_query(target_table, dt, part_limit, metadata_type, sample_mode)
        rows.extend(fetch_records(conn, sql, params))
    return rows


def build_missing_target_sample_query(
    source_table: str,
    target_table: str,
    *,
    metadata_type: str,
    key_field: str,
    source_dt: Optional[str],
    target_dt: Optional[str],
    limit: Optional[int],
) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    source_alias = "s"
    target_dt_join = "AND t.`dt` = %s" if target_dt is not None else "AND t.`dt` = s.`dt`"
    if target_dt is not None:
        params.append(target_dt)
    sql = (
        f"SELECT {source_alias}.`{key_field}` AS sample_key, {source_alias}.`dt` AS dt "
        f"FROM {quote_identifier(source_table)} {source_alias} "
        f"LEFT JOIN {quote_identifier(target_table)} t "
        f"ON t.`unique_id` = CONCAT('{metadata_type}:', {source_alias}.`{key_field}`) "
        f"{target_dt_join} "
        f"WHERE {source_alias}.`{key_field}` IS NOT NULL AND {source_alias}.`{key_field}` != ''"
        f"{_dt_clause(source_dt, params, source_alias)} AND t.`unique_id` IS NULL "
        f"ORDER BY {source_alias}.`{key_field}`{_limit_clause(limit)}"
    )
    return sql, params


def build_xinghe_missing_target_sample_query(
    xinghe_table: str,
    target_table: str,
    *,
    metadata_type: str,
    xinghe_key_field: str,
    dt: Optional[str],
    limit: Optional[int],
) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    target_dt_join = "AND t.`dt` = %s" if dt is not None else ""
    if dt is not None:
        params.append(dt)
    sql = (
        f"SELECT x.`{xinghe_key_field}` AS sample_key, "
        "x.`data_date` AS data_date, x.`sha256` AS sha256, x.`origin_path` AS origin_path "
        f"FROM {quote_identifier(xinghe_table)} x "
        f"LEFT JOIN {quote_identifier(target_table)} t "
        f"ON t.`unique_id` = CONCAT('{metadata_type}:', x.`{xinghe_key_field}`) "
        f"{target_dt_join} "
        f"WHERE x.`{xinghe_key_field}` IS NOT NULL AND x.`{xinghe_key_field}` != ''"
        " AND t.`unique_id` IS NULL "
        f"ORDER BY x.`{xinghe_key_field}`, x.`sha256`, x.`origin_path`{_limit_clause(limit)}"
    )
    return sql, params


def build_xinghe_only_missing_target_sample_query(
    xinghe_table: str,
    metadata_table: str,
    target_table: str,
    *,
    metadata_type: str,
    xinghe_key_field: str,
    metadata_key_field: str,
    metadata_dt: Optional[str],
    target_dt: Optional[str],
    limit: Optional[int],
) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    metadata_dt_join = "AND m.`dt` = %s" if metadata_dt is not None else ""
    if metadata_dt is not None:
        params.append(metadata_dt)
    target_dt_join = "AND t.`dt` = %s" if target_dt is not None else ""
    if target_dt is not None:
        params.append(target_dt)
    sql = (
        f"SELECT x.`{xinghe_key_field}` AS sample_key, "
        "x.`data_date` AS data_date, x.`sha256` AS sha256, x.`origin_path` AS origin_path "
        f"FROM {quote_identifier(xinghe_table)} x "
        f"LEFT JOIN {quote_identifier(metadata_table)} m "
        f"ON m.`{metadata_key_field}` = x.`{xinghe_key_field}` {metadata_dt_join} "
        f"LEFT JOIN {quote_identifier(target_table)} t "
        f"ON t.`unique_id` = CONCAT('{metadata_type}:', x.`{xinghe_key_field}`) {target_dt_join} "
        f"WHERE x.`{xinghe_key_field}` IS NOT NULL AND x.`{xinghe_key_field}` != '' "
        f"AND m.`{metadata_key_field}` IS NULL AND t.`unique_id` IS NULL "
        f"ORDER BY x.`{xinghe_key_field}`, x.`sha256`, x.`origin_path`{_limit_clause(limit)}"
    )
    return sql, params


def fetch_metadata_record(
    conn: Any,
    *,
    table: str,
    metadata_type: str,
    key: Any,
    dt: Optional[str],
) -> Optional[Dict[str, Any]]:
    key_field = "doi" if metadata_type == "paper" else "isbn13"
    params: List[Any] = [str(key).lower() if metadata_type == "paper" else key]
    predicate = f"LOWER(`{key_field}`) = %s" if metadata_type == "paper" else f"`{key_field}` = %s"
    sql = (
        f"SELECT * FROM {quote_identifier(table)} WHERE {predicate}"
        f"{_dt_clause(dt, params)} ORDER BY `{key_field}` LIMIT 2"
    )
    rows = fetch_records(conn, sql, params)
    return rows[0] if rows else None


def chunked(values: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    for i in range(0, len(values), size):
        yield values[i : i + size]


def fetch_metadata_records_batch(
    conn: Any,
    *,
    table: str,
    metadata_type: str,
    keys: Sequence[Any],
    dt: Optional[str],
    batch_size: int = 500,
) -> Dict[str, Dict[str, Any]]:
    key_field = "doi" if metadata_type == "paper" else "isbn13"
    normalized_keys = [
        str(key).lower() if metadata_type == "paper" else str(key)
        for key in keys
        if key not in (None, "")
    ]
    result: Dict[str, Dict[str, Any]] = {}
    for batch in chunked(sorted(set(normalized_keys)), batch_size):
        params: List[Any] = list(batch)
        placeholders = ",".join(["%s"] * len(batch))
        predicate = (
            f"LOWER(`{key_field}`) IN ({placeholders})"
            if metadata_type == "paper"
            else f"`{key_field}` IN ({placeholders})"
        )
        sql = (
            f"SELECT * FROM {quote_identifier(table)} WHERE {predicate}"
            f"{_dt_clause(dt, params)} ORDER BY `{key_field}`"
        )
        for row in fetch_records(conn, sql, params):
            row_key = row.get(key_field)
            if row_key in (None, ""):
                continue
            map_key = normalize_lookup_key(row_key, metadata_type)
            result.setdefault(map_key, row)
    return result


def embedded_key_like_patterns(key: Any) -> List[str]:
    text = normalize_key_text(key).lower()
    if not text:
        return []
    if "<" not in text and ">" not in text:
        return []
    variants = {text, html.escape(text, quote=False).lower()}
    return [f"%{variant}%" for variant in sorted(variants) if variant]


def fetch_paper_metadata_records_by_embedded_key(
    conn: Any,
    *,
    table: str,
    key: Any,
    dt: Optional[str],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    patterns = embedded_key_like_patterns(key)
    if not patterns:
        return []
    params: List[Any] = list(patterns)
    like_clause = " OR ".join(["LOWER(`doi`) LIKE %s"] * len(patterns))
    sql = (
        f"SELECT * FROM {quote_identifier(table)} "
        f"WHERE ({like_clause}){_dt_clause(dt, params)} "
        f"ORDER BY `doi` LIMIT {int(limit)}"
    )
    return fetch_records(conn, sql, params)


def score_metadata_candidate(
    target_row: Dict[str, Any],
    candidate: Dict[str, Any],
    *,
    specs: Sequence[UnionFieldSpec],
    metadata_type: str,
) -> int:
    score = 0
    for spec in specs:
        source = spec.paper_source if metadata_type == "paper" else spec.ebook_source
        if not _is_field_ref(source):
            continue
        actual_value = normalize_empty_for_compare(
            canonicalize(target_row.get(spec.field_name)),
            spec.data_type,
            spec.field_name,
        )
        if actual_value is None:
            continue
        candidate_value = normalize_empty_for_compare(
            canonicalize(get_source_value(candidate, source, metadata_type)),
            spec.data_type,
            spec.field_name,
        )
        if candidate_value == actual_value:
            score += 1
    return score


def choose_metadata_record_for_target(
    target_row: Dict[str, Any],
    candidates: Sequence[Dict[str, Any]],
    *,
    specs: Sequence[UnionFieldSpec],
    metadata_type: str,
) -> Optional[Dict[str, Any]]:
    if not candidates:
        return None
    scored = [
        (
            score_metadata_candidate(
                target_row,
                candidate,
                specs=specs,
                metadata_type=metadata_type,
            ),
            candidate,
        )
        for candidate in candidates
    ]
    scored.sort(key=lambda item: item[0], reverse=True)
    if scored[0][0] > 0 or len(scored) == 1:
        return scored[0][1]
    return None


def fetch_xinghe_records(
    conn: Any,
    *,
    table: str,
    metadata_type: str,
    key: Any,
    dt: Optional[str],
    limit: int = 100,
) -> List[Dict[str, Any]]:
    key_field = "doi" if metadata_type == "paper" else "isbn"
    params: List[Any] = [str(key).lower() if metadata_type == "paper" else key]
    predicate = f"LOWER(`{key_field}`) = %s" if metadata_type == "paper" else f"`{key_field}` = %s"
    sql = (
        f"SELECT * FROM {quote_identifier(table)} WHERE {predicate}"
        f" ORDER BY `sha256`, `origin_path` LIMIT {int(limit)}"
    )
    return fetch_records(conn, sql, params)


def fetch_xinghe_records_batch(
    conn: Any,
    *,
    table: str,
    metadata_type: str,
    keys: Sequence[Any],
    batch_size: int = 500,
) -> Dict[str, List[Dict[str, Any]]]:
    key_field = "doi" if metadata_type == "paper" else "isbn"
    normalized_keys = [
        str(key).lower() if metadata_type == "paper" else str(key)
        for key in keys
        if key not in (None, "")
    ]
    result: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for batch in chunked(sorted(set(normalized_keys)), batch_size):
        params: List[Any] = list(batch)
        placeholders = ",".join(["%s"] * len(batch))
        predicate = (
            f"LOWER(`{key_field}`) IN ({placeholders})"
            if metadata_type == "paper"
            else f"`{key_field}` IN ({placeholders})"
        )
        sql = (
            f"SELECT * FROM {quote_identifier(table)} WHERE {predicate}"
            " ORDER BY `sha256`, `origin_path`"
        )
        for row in fetch_records(conn, sql, params):
            row_key = row.get(key_field)
            if row_key in (None, ""):
                continue
            map_key = normalize_lookup_key(row_key, metadata_type)
            result[map_key].append(row)
    return dict(result)


def fetch_xinghe_records_by_sha_batch(
    conn: Any,
    *,
    table: str,
    sha_values: Sequence[Any],
    batch_size: int = 500,
) -> Dict[str, List[Dict[str, Any]]]:
    normalized = [str(value) for value in sha_values if value not in (None, "")]
    result: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for batch in chunked(sorted(set(normalized)), batch_size):
        params: List[Any] = list(batch)
        placeholders = ",".join(["%s"] * len(batch))
        sql = (
            f"SELECT * FROM {quote_identifier(table)} "
            f"WHERE `sha256` IN ({placeholders}) "
            "ORDER BY `sha256`, `origin_path`"
        )
        for row in fetch_records(conn, sql, params):
            sha256 = row.get("sha256")
            if sha256 in (None, ""):
                continue
            result[str(sha256)].append(row)
    return dict(result)


def fetch_paper_xinghe_records_by_embedded_key(
    conn: Any,
    *,
    table: str,
    key: Any,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    patterns = embedded_key_like_patterns(key)
    if not patterns:
        return []
    params: List[Any] = list(patterns)
    like_clause = " OR ".join(["LOWER(`doi`) LIKE %s"] * len(patterns))
    sql = (
        f"SELECT * FROM {quote_identifier(table)} "
        f"WHERE ({like_clause}) "
        f"ORDER BY `sha256`, `origin_path` LIMIT {int(limit)}"
    )
    return fetch_records(conn, sql, params)


def fetch_xinghe_records_by_target_repository_fields(
    conn: Any,
    *,
    table: str,
    target_row: Dict[str, Any],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    sha256 = target_row.get("access_xinghe_repository_sha256")
    if sha256 in (None, ""):
        return []
    sql = (
        f"SELECT * FROM {quote_identifier(table)} "
        "WHERE `sha256` = %s "
        f"ORDER BY `sha256`, `origin_path` LIMIT {int(limit)}"
    )
    return fetch_records(conn, sql, [sha256])


XINGHE_TARGET_MATCH_FIELDS = (
    ("sha256", "access_xinghe_repository_sha256"),
    ("origin_path", "access_xinghe_repository_origin_path"),
    ("processed_path", "access_xinghe_repository_processed_path"),
    ("origin_url", "access_xinghe_repository_origin_url"),
)
JOURNAL_NAME_MAPPING_CACHE: Optional[Tuple[Dict[str, str], Dict[str, str]]] = None


def choose_xinghe_record_for_target(
    target_row: Dict[str, Any],
    xinghe_rows: Sequence[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not xinghe_rows:
        return None

    for source_field, target_field in XINGHE_TARGET_MATCH_FIELDS:
        target_value = target_row.get(target_field)
        if target_value in (None, ""):
            continue
        target_cmp = str(target_value).strip()
        for row in xinghe_rows:
            source_value = row.get(source_field)
            if source_value in (None, ""):
                continue
            if str(source_value).strip() == target_cmp:
                return row

    if len(xinghe_rows) == 1:
        return xinghe_rows[0]
    return None


def expected_for_target_row(
    conn: Any,
    *,
    row: Dict[str, Any],
    specs: Sequence[UnionFieldSpec],
    paper_table: str,
    ebook_table: str,
    xinghe_table: str,
    target_dt: Optional[str],
    paper_dt: Optional[str],
    ebook_dt: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    metadata_type = row.get("metadata_type")
    if metadata_type not in ("paper", "ebook"):
        return None, {"reason": "unsupported_metadata_type", "metadata_type": metadata_type}

    key = target_key_for_row(row, metadata_type)
    if not key:
        key_field = "doi" if metadata_type == "paper" else "isbn13"
        return None, {"reason": "missing_target_key", "key_field": key_field}

    metadata_table = paper_table if metadata_type == "paper" else ebook_table
    metadata_map, xinghe_map = build_field_maps(specs, metadata_type)
    row_dt = target_dt if target_dt is not None else row.get("dt")
    metadata_dt = paper_dt if metadata_type == "paper" else ebook_dt
    if metadata_dt is None:
        metadata_dt = row_dt
    metadata_record = fetch_metadata_record(
        conn,
        table=metadata_table,
        metadata_type=metadata_type,
        key=key,
        dt=metadata_dt,
    )
    xinghe_rows = fetch_xinghe_records(
        conn,
        table=xinghe_table,
        metadata_type=metadata_type,
        key=key,
        dt=row_dt,
    )
    warnings: Dict[str, Any] = {}
    xinghe_record = choose_xinghe_record_for_target(row, xinghe_rows)
    if len(xinghe_rows) > 1:
        warnings["xinghe_duplicate_candidates"] = len(xinghe_rows)
        if xinghe_record is None:
            warnings["xinghe_match"] = "ambiguous_no_repository_field_match"
    expected = merge_one(
        metadata_record,
        xinghe_record,
        metadata_type=metadata_type,
        specs=specs,
        metadata_map=metadata_map,
        xinghe_map=xinghe_map,
        fallback_key=key,
    )
    if row_dt is not None:
        expected["dt"] = row_dt
    return expected, warnings


def expected_for_target_row_from_sources(
    *,
    row: Dict[str, Any],
    specs: Sequence[UnionFieldSpec],
    metadata_record: Optional[Dict[str, Any]],
    xinghe_rows: Sequence[Dict[str, Any]],
    target_dt: Optional[str],
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    metadata_type = row.get("metadata_type")
    if metadata_type not in ("paper", "ebook"):
        return None, {"reason": "unsupported_metadata_type", "metadata_type": metadata_type}

    key = target_key_for_row(row, metadata_type)
    if not key:
        key_field = "doi" if metadata_type == "paper" else "isbn13"
        return None, {"reason": "missing_target_key", "key_field": key_field}

    metadata_map, xinghe_map = build_field_maps(specs, metadata_type)
    warnings: Dict[str, Any] = {}
    xinghe_record = choose_xinghe_record_for_target(row, xinghe_rows)
    if len(xinghe_rows) > 1:
        warnings["xinghe_duplicate_candidates"] = len(xinghe_rows)
        if xinghe_record is None:
            warnings["xinghe_match"] = "ambiguous_no_repository_field_match"
    expected = merge_one(
        metadata_record,
        xinghe_record,
        metadata_type=metadata_type,
        specs=specs,
        metadata_map=metadata_map,
        xinghe_map=xinghe_map,
        fallback_key=key,
    )
    row_dt = target_dt if target_dt is not None else row.get("dt")
    if row_dt is not None:
        expected["dt"] = row_dt
    return expected, warnings


def validate_source_field_mapping(
    conn: Any,
    *,
    specs: Sequence[UnionFieldSpec],
    paper_table: str,
    ebook_table: str,
    xinghe_table: str,
    target_table: str,
    target_dt: Optional[str],
    paper_dt: Optional[str],
    ebook_dt: Optional[str],
    limit: Optional[int],
    target_sample_mode: str = "natural",
) -> Dict[str, Any]:
    target_rows = fetch_target_samples(
        conn,
        target_table=target_table,
        dt=target_dt,
        limit=limit,
        sample_mode=target_sample_mode,
    )
    log_step(f"source field mapping 抽到目标样本 {len(target_rows)} 条")
    keys_by_type: Dict[str, List[Any]] = {"paper": [], "ebook": []}
    repository_sha_values: List[Any] = []
    for target_row in target_rows:
        metadata_type = target_row.get("metadata_type")
        if metadata_type == "paper":
            keys_by_type["paper"].append(target_key_for_row(target_row, "paper"))
        elif metadata_type == "ebook":
            keys_by_type["ebook"].append(target_key_for_row(target_row, "ebook"))
        sha256 = target_row.get("access_xinghe_repository_sha256")
        if sha256 not in (None, ""):
            repository_sha_values.append(sha256)
    metadata_records = {
        "paper": fetch_metadata_records_batch(
            conn,
            table=paper_table,
            metadata_type="paper",
            keys=keys_by_type["paper"],
            dt=paper_dt if paper_dt is not None else target_dt,
        ),
        "ebook": fetch_metadata_records_batch(
            conn,
            table=ebook_table,
            metadata_type="ebook",
            keys=keys_by_type["ebook"],
            dt=ebook_dt if ebook_dt is not None else target_dt,
        ),
    }
    xinghe_records = {
        "paper": fetch_xinghe_records_batch(
            conn,
            table=xinghe_table,
            metadata_type="paper",
            keys=keys_by_type["paper"],
        ),
        "ebook": fetch_xinghe_records_batch(
            conn,
            table=xinghe_table,
            metadata_type="ebook",
            keys=keys_by_type["ebook"],
        ),
    }
    xinghe_records_by_sha = fetch_xinghe_records_by_sha_batch(
        conn,
        table=xinghe_table,
        sha_values=repository_sha_values,
    )
    log_step(
        "source batch 查询完成："
        f"paper metadata={len(metadata_records['paper'])}, "
        f"ebook metadata={len(metadata_records['ebook'])}, "
        f"paper xinghe={len(xinghe_records['paper'])}, "
        f"ebook xinghe={len(xinghe_records['ebook'])}, "
        f"sha xinghe={len(xinghe_records_by_sha)}"
    )
    compare_fields = [spec.field_name for spec in specs]
    field_types = {spec.field_name: spec.data_type for spec in specs}
    checked = passed = failed = skipped = 0
    mismatches: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    paper_metadata_embedded_cache: Dict[str, List[Dict[str, Any]]] = {}
    paper_xinghe_embedded_cache: Dict[str, List[Dict[str, Any]]] = {}

    for target_row in target_rows:
        checked += 1
        metadata_type = target_row.get("metadata_type")
        lookup_key = normalize_lookup_key(target_key_for_row(target_row, str(metadata_type)), str(metadata_type))
        metadata_record = metadata_records.get(str(metadata_type), {}).get(lookup_key)
        xinghe_rows = xinghe_records.get(str(metadata_type), {}).get(lookup_key, [])
        if metadata_type == "paper" and lookup_key:
            if metadata_record is None:
                if lookup_key not in paper_metadata_embedded_cache:
                    paper_metadata_embedded_cache[lookup_key] = fetch_paper_metadata_records_by_embedded_key(
                        conn,
                        table=paper_table,
                        key=lookup_key,
                        dt=paper_dt if paper_dt is not None else target_dt,
                    )
                metadata_record = choose_metadata_record_for_target(
                    target_row,
                    paper_metadata_embedded_cache[lookup_key],
                    specs=specs,
                    metadata_type="paper",
                )
            if not xinghe_rows:
                if lookup_key not in paper_xinghe_embedded_cache:
                    paper_xinghe_embedded_cache[lookup_key] = fetch_paper_xinghe_records_by_embedded_key(
                        conn,
                        table=xinghe_table,
                        key=lookup_key,
                    )
                xinghe_rows = paper_xinghe_embedded_cache[lookup_key]
        if not xinghe_rows:
            sha256 = target_row.get("access_xinghe_repository_sha256")
            if sha256 not in (None, ""):
                xinghe_rows = xinghe_records_by_sha.get(str(sha256), [])
        expected, row_warnings = expected_for_target_row_from_sources(
            row=target_row,
            specs=specs,
            metadata_record=metadata_record,
            xinghe_rows=xinghe_rows,
            target_dt=target_dt,
        )
        unique_id = target_row.get("unique_id")
        if row_warnings:
            warnings.append({"unique_id": unique_id, **row_warnings})
        if expected is None:
            skipped += 1
            mismatches.append({"unique_id": unique_id, "status": "skipped", **row_warnings})
            continue
        expected_cmp = comparable_record(expected, compare_fields)
        actual_cmp = comparable_record(target_row, compare_fields)
        row_mismatches = compare_records(expected_cmp, actual_cmp, field_types)
        if row_mismatches:
            failed += 1
            mismatches.append(
                {
                    "unique_id": unique_id,
                    "dt": target_row.get("dt"),
                    "metadata_type": target_row.get("metadata_type"),
                    "status": "field_mismatch",
                    "mismatches": row_mismatches,
                }
            )
        else:
            passed += 1

    return {
        "checked": checked,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "warnings": warnings[:100],
        "mismatches": mismatches,
    }


def validate_missing_target_samples(
    conn: Any,
    *,
    paper_table: str,
    ebook_table: str,
    target_table: str,
    xinghe_table: str,
    target_dt: Optional[str],
    paper_dt: Optional[str],
    ebook_dt: Optional[str],
    limit: int,
) -> Dict[str, Any]:
    per_kind = max(1, limit // 6)
    result: Dict[str, Any] = {}
    for metadata_type, table, key_field, source_dt in (
        ("paper", paper_table, "doi", paper_dt),
        ("ebook", ebook_table, "isbn13", ebook_dt),
    ):
        sql, params = build_missing_target_sample_query(
            table,
            target_table,
            metadata_type=metadata_type,
            key_field=key_field,
            source_dt=source_dt,
            target_dt=target_dt,
            limit=per_kind,
        )
        result[f"{metadata_type}_source"] = fetch_records(conn, sql, params)
    for metadata_type, key_field in (
        ("paper", "doi"),
        ("ebook", "isbn"),
    ):
        sql, params = build_xinghe_missing_target_sample_query(
            xinghe_table,
            target_table,
            metadata_type=metadata_type,
            xinghe_key_field=key_field,
            dt=target_dt,
            limit=per_kind,
        )
        result[f"xinghe_{metadata_type}_source"] = fetch_records(conn, sql, params)
    for metadata_type, xinghe_key_field, metadata_table, metadata_key_field, metadata_dt in (
        ("paper", "doi", paper_table, "doi", paper_dt),
        ("ebook", "isbn", ebook_table, "isbn13", ebook_dt),
    ):
        sql, params = build_xinghe_only_missing_target_sample_query(
            xinghe_table,
            metadata_table,
            target_table,
            metadata_type=metadata_type,
            xinghe_key_field=xinghe_key_field,
            metadata_key_field=metadata_key_field,
            metadata_dt=metadata_dt,
            target_dt=target_dt,
            limit=per_kind,
        )
        result[f"xinghe_only_{metadata_type}_source"] = fetch_records(conn, sql, params)
    return result


def null_empty_rate_for_field(
    conn: Any,
    *,
    table: str,
    field: str,
    dt: Optional[str],
) -> Dict[str, Any]:
    params: List[Any] = []
    quoted = f"`{field.replace('`', '``')}`"
    sql = (
        "SELECT "
        "COUNT(*) AS total, "
        f"SUM(CASE WHEN {quoted} IS NULL THEN 1 ELSE 0 END) AS null_count, "
        f"SUM(CASE WHEN {quoted} IS NOT NULL "
        f"AND TRIM(CAST({quoted} AS VARCHAR)) IN ('', '[]', '{{}}') "
        "THEN 1 ELSE 0 END) AS empty_count "
        f"FROM {quote_identifier(table)} WHERE 1=1{_dt_clause(dt, params)}"
    )
    row = fetch_one(conn, sql, params)
    if not row:
        return {"field": field, "total": 0, "null_count": 0, "empty_count": 0}
    total = int(row.get("total") or 0)
    null_count = int(row.get("null_count") or 0)
    empty_count = int(row.get("empty_count") or 0)
    return {
        "field": field,
        "total": total,
        "null_count": null_count,
        "empty_count": empty_count,
        "null_rate": null_count / total if total else 0.0,
        "empty_rate": empty_count / total if total else 0.0,
    }


def empty_condition_sql(quoted_field: str, data_type: str) -> Optional[str]:
    type_text = (data_type or "").strip().lower()
    if (
        type_text in ("string", "text")
        or type_text.startswith("varchar")
        or type_text.startswith("char")
    ):
        return f"TRIM(CAST({quoted_field} AS VARCHAR)) = ''"
    if type_text.startswith("array") or type_text.startswith("list"):
        return f"CARDINALITY({quoted_field}) = 0"
    return None


def build_null_empty_rates(
    conn: Any,
    *,
    target_table: str,
    specs: Sequence[UnionFieldSpec],
    dt: Optional[str],
) -> List[Dict[str, Any]]:
    target_field_types = show_column_types(conn, target_table)
    row = fetch_null_empty_rate_row(
        conn,
        target_table=target_table,
        specs=specs,
        dt=dt,
        extra_where="",
        extra_params=[],
        target_field_types=target_field_types,
    )
    return null_empty_rates_from_row(row, specs)


def fetch_null_empty_rate_row(
    conn: Any,
    *,
    target_table: str,
    specs: Sequence[UnionFieldSpec],
    dt: Optional[str],
    extra_where: str,
    extra_params: Sequence[Any],
    target_field_types: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    params: List[Any] = []
    select_parts: List[str] = ["COUNT(*) AS `total`"]
    target_field_types = target_field_types or {}
    for idx, spec in enumerate(specs):
        quoted = f"`{spec.field_name.replace('`', '``')}`"
        select_parts.append(
            f"SUM(CASE WHEN {quoted} IS NULL THEN 1 ELSE 0 END) AS `n_{idx}`"
        )
        effective_type = target_field_types.get(spec.field_name) or spec.data_type
        empty_condition = empty_condition_sql(quoted, effective_type)
        if empty_condition is None:
            select_parts.append(f"0 AS `e_{idx}`")
        else:
            select_parts.append(
                f"SUM(CASE WHEN {quoted} IS NOT NULL AND {empty_condition} "
                f"THEN 1 ELSE 0 END) AS `e_{idx}`"
            )
    sql = (
        "SELECT "
        + ", ".join(select_parts)
        + f" FROM {quote_identifier(target_table)} WHERE 1=1{_dt_clause(dt, params)}{extra_where}"
    )
    params.extend(extra_params)
    return fetch_one(conn, sql, params) or {}


def null_empty_rates_from_row(row: Dict[str, Any], specs: Sequence[UnionFieldSpec]) -> List[Dict[str, Any]]:
    total = int(row.get("total") or 0)
    rates: List[Dict[str, Any]] = []
    for idx, spec in enumerate(specs):
        null_count = int(row.get(f"n_{idx}") or 0)
        empty_count = int(row.get(f"e_{idx}") or 0)
        rates.append(
            {
                "field": spec.field_name,
                "total": total,
                "null_count": null_count,
                "empty_count": empty_count,
                "null_rate": null_count / total if total else 0.0,
                "empty_rate": empty_count / total if total else 0.0,
            }
        )
    return rates


def skipped_null_empty_rates(reason: str) -> List[Dict[str, Any]]:
    return [{"skipped": True, "reason": reason}]


def failed_null_empty_rates(exc: Exception) -> List[Dict[str, Any]]:
    return [
        {
            "skipped": True,
            "status": "failed",
            "reason": "null_empty_count_failed",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    ]


def validate_target_field_values(
    conn: Any,
    *,
    target_table: str,
    dt: Optional[str],
    limit: Optional[int],
) -> Dict[str, Any]:
    return {
        "checked": 0,
        "passed": 0,
        "failed": 0,
        "fail_rate": 0.0,
        "field_error_summary": {},
        "issues": [],
        "examples": {},
        "skipped": True,
        "reason": "field validator removed; union validation uses schema, coverage, null/empty rates, and source field mapping",
    }


REPORT_KEY_LABELS = {
    "status": "状态",
    "config_path": "配置文件",
    "mapping_csv": "映射文件",
    "paper_table": "论文源表",
    "ebook_table": "图书源表",
    "xinghe_table": "星河全文表",
    "target_table": "目标表",
    "dt": "目标表分区",
    "target_dt": "目标表分区",
    "paper_dt": "论文源表分区",
    "ebook_dt": "图书源表分区",
    "sample_size": "抽样数量",
    "coverage_mode": "覆盖统计模式",
    "null_empty_mode": "空值率统计模式",
    "missing_sample_mode": "缺失样例模式",
    "target_sample_mode": "目标表抽样模式",
    "schema_check": "Schema检查",
    "missing_fields": "缺失字段",
    "extra_fields": "多余字段",
    "expected_count": "预期字段数",
    "actual_count": "实际字段数",
    "coverage_counts": "覆盖统计",
    "paper_source": "论文去重表记录数",
    "ebook_source": "图书去重表记录数",
    "xinghe_only_paper_count": "星河表去重论文兜底数",
    "xinghe_only_ebook_count": "星河表去重图书兜底数",
    "expected_target_count": "理论全量表记录数",
    "actual_target_count": "实际全量表记录数",
    "target_count_diff": "全量表记录数差异",
    "source_field_mapping": "源字段映射校验",
    "checked": "已校验数",
    "passed": "通过数",
    "failed": "失败数",
    "skipped": "跳过数",
    "warning_count": "Warning数量",
    "field_quality": "字段质量校验",
    "fail_rate": "失败率",
    "field_error_summary": "字段错误汇总",
    "reason": "原因",
    "output_dir": "报告目录",
    "details": "明细",
    "null_empty_rates": "空值率统计",
    "top_null_empty_rates": "Top空值率统计",
    "field": "字段",
    "total": "总数",
    "null_count": "NULL数量",
    "empty_count": "空字符串/空集合数量",
    "null_rate": "NULL比例",
    "empty_rate": "空值比例",
    "null_empty_rate": "NULL和空值合计比例",
    "missing_target_samples": "缺失目标样例",
    "mismatches": "字段差异",
    "warnings": "Warning明细",
    "unique_id": "唯一ID",
    "metadata_type": "元数据类型",
    "expected": "预期值",
    "actual": "实际值",
    "report": "报告目录",
    "total_problem_rows": "问题记录数",
    "status_counts": "状态分布",
    "field_counts": "字段问题分布",
    "field_samples": "字段问题样例",
    "warning_samples": "Warning样例",
    "missing_target_sample_counts": "缺失目标样例数量",
    "sample_key": "样例key",
    "data_date": "数据日期",
    "sha256": "sha256",
    "origin_path": "原始路径",
    "error_type": "错误类型",
    "error": "错误信息",
}


FIELD_NAME_KEY_CONTAINERS = {
    "field_counts",
    "字段问题分布",
    "field_samples",
    "字段问题样例",
    "mismatches",
    "字段差异",
}


def localize_report_keys(value: Any, parent_key: Optional[str] = None) -> Any:
    if isinstance(value, dict):
        if parent_key in FIELD_NAME_KEY_CONTAINERS:
            return {
                str(key): localize_report_keys(val, str(key))
                for key, val in value.items()
            }
        return {
            REPORT_KEY_LABELS.get(str(key), str(key)): localize_report_keys(val, str(key))
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [localize_report_keys(item, parent_key) for item in value]
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(localize_report_keys(payload), f, ensure_ascii=False, indent=2, cls=JsonEncoder)


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(localize_report_keys(row), ensure_ascii=False, cls=JsonEncoder) + "\n")


def _json_inline(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, cls=JsonEncoder)


SAMPLES_PER_FIELD = 3


def top_null_empty_rates(rates: Sequence[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for row in rates:
        if row.get("skipped") or row.get("error"):
            continue
        total = int(row.get("total") or 0)
        null_count = int(row.get("null_count") or 0)
        empty_count = int(row.get("empty_count") or 0)
        total_rate = (null_count + empty_count) / total if total else 0.0
        rows.append({**row, "null_empty_rate": total_rate})
    rows.sort(
        key=lambda item: (
            float(item.get("null_empty_rate") or 0),
            int(item.get("null_count") or 0) + int(item.get("empty_count") or 0),
            str(item.get("field") or ""),
        ),
        reverse=True,
    )
    return rows[:limit]


def build_readable_report_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    details = result["details"]
    mismatch_rows = details["source_field_mapping"]["mismatches"]
    warnings = details["source_field_mapping"]["warnings"]
    status_counts: Dict[str, int] = {}
    field_counts: Dict[str, int] = {}
    field_samples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in mismatch_rows:
        status = str(row.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        mismatches = row.get("mismatches") or {}
        for field, diff in mismatches.items():
            field_counts[field] = field_counts.get(field, 0) + 1
            if len(field_samples[field]) >= SAMPLES_PER_FIELD:
                continue
            field_samples[field].append(
                {
                    "unique_id": row.get("unique_id") or row.get("唯一ID"),
                    "metadata_type": row.get("metadata_type") or row.get("元数据类型"),
                    "dt": row.get("dt") or row.get("目标表分区"),
                    "status": status,
                    "expected": diff.get("expected") if isinstance(diff, dict) else None,
                    "actual": diff.get("actual") if isinstance(diff, dict) else None,
                }
            )

    sorted_field_counts = dict(sorted(field_counts.items(), key=lambda item: (-item[1], item[0])))
    sorted_status_counts = dict(sorted(status_counts.items(), key=lambda item: (-item[1], item[0])))
    missing_samples = details.get("missing_target_samples") or {}
    if isinstance(missing_samples, dict) and missing_samples.get("skipped"):
        missing_sample_counts = {"skipped": 1}
    else:
        missing_sample_counts = {
            name: len(rows) if isinstance(rows, list) else 0
            for name, rows in missing_samples.items()
        }
    null_empty_rates = details.get("null_empty_rates") or []
    return {
        "status": result.get("status"),
        "report": result.get("output_dir"),
        "mapping_csv": result.get("mapping_csv"),
        "paper_table": result.get("paper_table"),
        "ebook_table": result.get("ebook_table"),
        "xinghe_table": result.get("xinghe_table"),
        "target_table": result.get("target_table"),
        "target_dt": result.get("target_dt") or result.get("dt"),
        "paper_dt": result.get("paper_dt"),
        "ebook_dt": result.get("ebook_dt"),
        "sample_size": result.get("sample_size"),
        "coverage_mode": result.get("coverage_mode"),
        "null_empty_mode": result.get("null_empty_mode"),
        "missing_sample_mode": result.get("missing_sample_mode"),
        "target_sample_mode": result.get("target_sample_mode"),
        "schema_check": result.get("schema_check"),
        "coverage_counts": result.get("coverage_counts"),
        "source_field_mapping": result.get("source_field_mapping"),
        "total_problem_rows": len(mismatch_rows),
        "status_counts": sorted_status_counts,
        "field_counts": sorted_field_counts,
        "field_count_total": len(sorted_field_counts),
        "field_samples": {
            field: field_samples[field]
            for field in sorted_field_counts
            if field in field_samples
        },
        "warning_count": len(warnings),
        "warning_samples": warnings[:5],
        "null_empty_rates": null_empty_rates,
        "top_null_empty_rates": top_null_empty_rates(null_empty_rates),
        "missing_target_sample_counts": missing_sample_counts,
        "field_quality": result.get("field_quality"),
    }


def _pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:.2f}%"
    except (TypeError, ValueError):
        return "N/A"


def _first_present(row: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row:
            return row.get(key)
    return None


def build_readable_report_markdown(summary: Dict[str, Any]) -> str:
    lines: List[str] = ["# 全量元数据 Union 校验报告摘要", ""]
    schema_check = summary.get("schema_check") or {}
    coverage_counts = summary.get("coverage_counts") or {}
    lines.extend(
        [
            f"- 目标分区: `{summary.get('target_dt')}`",
            f"- 源分区: paper=`{summary.get('paper_dt')}`, ebook=`{summary.get('ebook_dt')}`",
            f"- 抽样数量: `{summary.get('sample_size')}`",
            f"- 空值率统计: mode=`{summary.get('null_empty_mode')}`",
            f"- 字段不一致记录数: `{summary.get('total_problem_rows')}`",
            f"- 报告目录: `{summary.get('report')}`",
            "",
        ]
    )

    lines.append("## 重点结论")
    lines.append("")
    missing_fields = _first_present(schema_check, "missing_fields", "缺失字段") or []
    extra_fields = _first_present(schema_check, "extra_fields", "多余字段") or []
    lines.append(
        f"- Schema: 缺失 `{len(missing_fields)}` 个字段，"
        f"多余 `{len(extra_fields)}` 个字段"
    )
    expected_target_count = coverage_counts.get("expected_target_count")
    actual_target_count = coverage_counts.get("actual_target_count") or coverage_counts.get("target")
    target_count_diff = coverage_counts.get("target_count_diff")
    if expected_target_count is not None and actual_target_count is not None:
        lines.append(
            f"- 目标表数量: 理论 `{expected_target_count}`，"
            f"实际 `{actual_target_count}`，差异 `{target_count_diff}`"
        )
    top_fields = list((summary.get("field_counts") or {}).items())[:5]
    if top_fields:
        lines.append(
            "- Top字段问题: "
            + "；".join(f"`{field}`={count}" for field, count in top_fields)
        )
    else:
        lines.append("- Top字段问题: 无")
    lines.append("")

    lines.append("## Schema 对比")
    lines.append("")
    lines.append(f"- 预期字段数: `{_first_present(schema_check, 'expected_count', '预期字段数')}`")
    lines.append(f"- 实际字段数: `{_first_present(schema_check, 'actual_count', '实际字段数')}`")
    for field in missing_fields[:10]:
        lines.append(f"- missing: `{field}`")
    for field in extra_fields[:10]:
        lines.append(f"- extra: `{field}`")
    if len(extra_fields) > 10:
        lines.append(f"- extra 其余 `{len(extra_fields) - 10}` 个见 summary.json")
    lines.append("")

    lines.append("## 覆盖率统计")
    lines.append("")
    for key, value in coverage_counts.items():
        lines.append(f"- `{key}`: {value}")
    lines.append("")

    lines.append("## NULL/空值率统计")
    lines.append("")
    null_empty_rates = summary.get("null_empty_rates") or []
    if null_empty_rates and isinstance(null_empty_rates[0], dict) and null_empty_rates[0].get("skipped"):
        if null_empty_rates[0].get("status") == "failed":
            lines.append(f"- 统计失败: `{null_empty_rates[0].get('error_type')}`")
            lines.append(f"- 原因: `{null_empty_rates[0].get('error')}`")
        else:
            lines.append(f"- 未统计: `{null_empty_rates[0].get('reason')}`")
            lines.append("- 如需输出实际比例，运行时加 `--null-empty-mode exact`")
    else:
        rate_rows = []
        for row in null_empty_rates:
            if row.get("error") or row.get("错误"):
                continue
            total = int(_first_present(row, "total", "总数") or 0)
            null_count = int(_first_present(row, "null_count", "NULL数量") or 0)
            empty_count = int(_first_present(row, "empty_count", "空字符串/空集合数量") or 0)
            null_empty_rate = _first_present(row, "null_empty_rate", "NULL和空值合计比例")
            if null_empty_rate is None:
                null_empty_rate = (null_count + empty_count) / total if total else 0.0
            rate_rows.append(
                {
                    **row,
                    "field": _first_present(row, "field", "字段"),
                    "total": total,
                    "null_count": null_count,
                    "empty_count": empty_count,
                    "null_rate": _first_present(row, "null_rate", "NULL比例"),
                    "empty_rate": _first_present(row, "empty_rate", "空值比例"),
                    "null_empty_rate": null_empty_rate,
                }
            )
        rate_rows.sort(
            key=lambda row: (
                float(row.get("null_empty_rate") or 0),
                int(row.get("null_count") or 0) + int(row.get("empty_count") or 0),
                str(row.get("field") or ""),
            ),
            reverse=True,
        )
        for row in rate_rows:
            lines.append(
                f"- `{row.get('field')}`: NULL `{row.get('null_count')}` "
                f"({_pct(row.get('null_rate'))})，空值 `{row.get('empty_count')}` "
                f"({_pct(row.get('empty_rate'))})，合计 `{_pct(row.get('null_empty_rate'))}`"
            )
        if not rate_rows:
            lines.append("- 无或未统计")
    lines.append("")

    lines.append("## 状态分布")
    lines.append("")
    for status, count in (summary.get("status_counts") or {}).items():
        lines.append(f"- `{status}`: {count}")
    if not summary.get("status_counts"):
        lines.append("- 无")
    lines.append("")

    lines.append("## 字段问题分布")
    lines.append("")
    for field, count in (summary.get("field_counts") or {}).items():
        lines.append(f"- `{field}`: {count}")
    if not summary.get("field_counts"):
        lines.append("- 无")
    lines.append("")

    lines.append("## 字段问题样例")
    lines.append("")
    for field, samples in (summary.get("field_samples") or {}).items():
        count = (summary.get("field_counts") or {}).get(field, len(samples))
        lines.append(f"### {field} ({count})")
        lines.append("")
        for sample in samples:
            lines.append(
                f"- unique_id `{sample.get('unique_id')}`, metadata_type=`{sample.get('metadata_type')}`, "
                f"dt=`{sample.get('dt')}`, status=`{sample.get('status')}`"
            )
            lines.append(f"  - expected: `{_json_inline(sample.get('expected'))}`")
            lines.append(f"  - actual: `{_json_inline(sample.get('actual'))}`")
            lines.append("")

    if summary.get("warning_count"):
        lines.append("## Warning 样例")
        lines.append("")
        lines.append(f"- warning_count: `{summary.get('warning_count')}`")
        for warning in summary.get("warning_samples") or []:
            lines.append(f"- `{_json_inline(warning)}`")
        lines.append("")

    lines.append("## 缺失样例数量")
    lines.append("")
    for key, count in (summary.get("missing_target_sample_counts") or {}).items():
        lines.append(f"- `{key}`: {count}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_report(output_dir: Path, result: Dict[str, Any]) -> None:
    details = result["details"]
    write_jsonl(output_dir / "source_field_mismatch.jsonl", details["source_field_mapping"]["mismatches"])
    write_jsonl(output_dir / "source_field_warning.jsonl", details["source_field_mapping"]["warnings"])
    readable_summary = build_readable_report_summary(result)
    write_json(output_dir / "summary.json", readable_summary)
    with (output_dir / "readable_summary.md").open("w", encoding="utf-8") as f:
        f.write(build_readable_report_markdown(readable_summary))


def validate_db(
    *,
    config_path: Path,
    paper_table: str,
    ebook_table: str,
    xinghe_table: str,
    target_table: str,
    dt: Optional[str],
    paper_dt: Optional[str],
    ebook_dt: Optional[str],
    limit: Optional[int],
    output_dir: Optional[Path],
    mapping_csv: Path = DEFAULT_MAPPING_CSV,
    coverage_mode: str = "exact",
    null_empty_mode: str = "exact",
    missing_sample_mode: str = "skip",
    target_sample_mode: str = "natural",
) -> Dict[str, Any]:
    specs = load_union_specs(mapping_csv)
    cfg = load_config(config_path)
    mysql_cfg = cfg.get("mysql", {}) if isinstance(cfg.get("mysql"), dict) else {}
    catalog = mysql_cfg.get("catalog")
    paper_table = qualify_table_name(paper_table, catalog, "dws")
    ebook_table = qualify_table_name(ebook_table, catalog, "dws")
    xinghe_table = qualify_table_name(xinghe_table, catalog, "ads")
    target_table = qualify_table_name(target_table, catalog, "ads")
    reconnected_conn = None
    with connect_starrocks(config_path) as conn:
        try:
            with timed_step("schema 校验"):
                schema_check = validate_schema(conn, target_table=target_table, specs=specs)
            if coverage_mode == "exact":
                try:
                    with timed_step("coverage 总量统计"):
                        coverage_counts = source_coverage_counts(
                            conn,
                            paper_table=paper_table,
                            ebook_table=ebook_table,
                            xinghe_table=xinghe_table,
                            target_table=target_table,
                            target_dt=dt,
                            paper_dt=paper_dt,
                            ebook_dt=ebook_dt,
                        )
                except Exception as exc:
                    coverage_counts = failed_coverage_counts(exc)
                    log_step(
                        "coverage 总量统计失败，继续生成抽样报告："
                        f"{type(exc).__name__}: {exc}"
                    )
            else:
                coverage_counts = skipped_coverage_counts("coverage_mode=skip")
                log_step("coverage 总量统计已跳过（使用 --coverage-mode exact 开启）")
            with timed_step("source 字段映射抽样校验"):
                source_field_mapping = validate_source_field_mapping(
                    conn,
                    specs=specs,
                    paper_table=paper_table,
                    ebook_table=ebook_table,
                    xinghe_table=xinghe_table,
                    target_table=target_table,
                    target_dt=dt,
                    paper_dt=paper_dt,
                    ebook_dt=ebook_dt,
                    limit=limit,
                    target_sample_mode=target_sample_mode,
                )
            field_quality = validate_target_field_values(
                conn,
                target_table=target_table,
                dt=dt,
                limit=limit,
            )
            if null_empty_mode == "exact":
                try:
                    with timed_step("null/empty rates 统计"):
                        null_empty_rates = build_null_empty_rates(
                            conn,
                            target_table=target_table,
                            specs=specs,
                            dt=dt,
                        )
                except Exception as exc:
                    null_empty_rates = failed_null_empty_rates(exc)
                    log_step(
                        "null/empty rates 统计失败，继续生成报告："
                        f"{type(exc).__name__}: {exc}"
                    )
            else:
                null_empty_rates = skipped_null_empty_rates("null_empty_mode=skip")
                log_step("null/empty rates 统计已跳过（使用 --null-empty-mode exact 开启）")
            if missing_sample_mode == "sample":
                with timed_step("missing target 样例抽取"):
                    missing_target_samples = validate_missing_target_samples(
                        conn,
                        paper_table=paper_table,
                        ebook_table=ebook_table,
                        xinghe_table=xinghe_table,
                        target_table=target_table,
                        target_dt=dt,
                        paper_dt=paper_dt,
                        ebook_dt=ebook_dt,
                        limit=limit or 200,
                    )
            else:
                missing_target_samples = {"skipped": True, "reason": "missing_sample_mode=skip"}
                log_step("missing target 样例抽取已跳过")
        finally:
            if reconnected_conn is not None:
                try:
                    reconnected_conn.close()
                except Exception:
                    pass

    result = {
        "status": "ok",
        "config_path": str(config_path),
        "mapping_csv": str(mapping_csv),
        "paper_table": paper_table,
        "ebook_table": ebook_table,
        "xinghe_table": xinghe_table,
        "target_table": target_table,
        "dt": dt,
        "target_dt": dt,
        "paper_dt": paper_dt,
        "ebook_dt": ebook_dt,
        "sample_size": limit,
        "coverage_mode": coverage_mode,
        "null_empty_mode": null_empty_mode,
        "missing_sample_mode": missing_sample_mode,
        "target_sample_mode": target_sample_mode,
        "schema_check": schema_check,
        "coverage_counts": coverage_counts,
        "source_field_mapping": {
            "checked": source_field_mapping["checked"],
            "passed": source_field_mapping["passed"],
            "failed": source_field_mapping["failed"],
            "skipped": source_field_mapping["skipped"],
            "warning_count": len(source_field_mapping["warnings"]),
        },
        "field_quality": {
            "checked": field_quality["checked"],
            "passed": field_quality["passed"],
            "failed": field_quality["failed"],
            "fail_rate": field_quality["fail_rate"],
            "field_error_summary": field_quality["field_error_summary"],
            "skipped": field_quality.get("skipped", False),
            "reason": field_quality.get("reason"),
        },
        "output_dir": str(output_dir) if output_dir else None,
        "details": {
            "source_field_mapping": source_field_mapping,
            "field_quality": field_quality,
            "null_empty_rates": null_empty_rates,
            "missing_target_samples": missing_target_samples,
        },
    }
    if output_dir is not None:
        write_report(output_dir, result)
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, ensure_ascii=False, cls=JsonEncoder))
    return result


def cli() -> None:
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    config_args, _ = config_parser.parse_known_args()
    cfg = load_config(config_args.config) if config_args.config.exists() else {}
    union_cfg = cfg.get("union_unique_meta_data", {})

    default_csv = union_cfg.get("mapping_csv")
    if default_csv:
        default_csv = PROJECT_ROOT / default_csv
    else:
        default_csv = DEFAULT_MAPPING_CSV

    parser = argparse.ArgumentParser(
        description="Validate unified metadata target table against DB sources."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="shared settings JSON path")
    parser.add_argument("--mapping-csv", type=Path, default=default_csv, help="field mapping CSV")
    parser.add_argument("--paper-table", default=union_cfg.get("paper_table", DEFAULT_PAPER_TABLE))
    parser.add_argument("--ebook-table", default=union_cfg.get("ebook_table", DEFAULT_EBOOK_TABLE))
    parser.add_argument("--xinghe-table", default=union_cfg.get("xinghe_table", DEFAULT_XINGHE_TABLE))
    parser.add_argument("--target-table", default=union_cfg.get("target_table", DEFAULT_TARGET_TABLE))
    parser.add_argument("--dt", default=union_cfg.get("dt"), help="target table dt partition filter")
    parser.add_argument(
        "--paper-dt",
        default=union_cfg.get("paper_dt"),
        help="paper unique source dt partition filter; defaults to --dt when omitted",
    )
    parser.add_argument(
        "--ebook-dt",
        default=union_cfg.get("ebook_dt"),
        help="ebook unique source dt partition filter; defaults to --dt when omitted",
    )
    parser.add_argument("--limit", type=int, default=int(union_cfg.get("limit", 3000)), help="sample size")
    parser.add_argument("--full", action="store_true", help="validate all target rows for sampled checks")
    parser.add_argument("--output-dir", type=Path, default=union_cfg.get("output_dir"), help="report directory")
    parser.add_argument(
        "--coverage-mode",
        choices=("skip", "exact"),
        default=union_cfg.get("coverage_mode", "exact"),
        help="coverage count mode; exact runs full count and missing-target count SQL, then continues on timeout/error",
    )
    parser.add_argument(
        "--null-empty-mode",
        choices=("skip", "exact"),
        default=union_cfg.get("null_empty_mode", "exact"),
        help="null/empty rate mode; exact scans target fields",
    )
    parser.add_argument(
        "--missing-sample-mode",
        choices=("sample", "skip"),
        default=union_cfg.get("missing_sample_mode", "skip"),
        help="whether to collect source-has-target-missing samples",
    )
    parser.add_argument(
        "--target-sample-mode",
        choices=("natural", "hash"),
        default=union_cfg.get("target_sample_mode", "natural"),
        help="target sample mode; natural is fastest, hash adds CRC32 filter",
    )
    args = parser.parse_args()
    paper_dt = args.paper_dt or args.dt
    ebook_dt = args.ebook_dt or args.dt
    output_dir = Path(args.output_dir) if args.output_dir else default_output_dir(
        args.dt,
        paper_dt,
        ebook_dt,
        args.limit,
        args.full,
    )

    validate_db(
        config_path=args.config,
        paper_table=args.paper_table,
        ebook_table=args.ebook_table,
        xinghe_table=args.xinghe_table,
        target_table=args.target_table,
        dt=args.dt,
        paper_dt=paper_dt,
        ebook_dt=ebook_dt,
        limit=None if args.full else args.limit,
        output_dir=output_dir,
        mapping_csv=args.mapping_csv,
        coverage_mode=args.coverage_mode,
        null_empty_mode=args.null_empty_mode,
        missing_sample_mode=args.missing_sample_mode,
        target_sample_mode=args.target_sample_mode,
    )


from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule
from dingo.model.rule.scibase.report_utils import bool_param, int_param, write_temp_settings


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    ["sci_base_qa_test", "union_unique_meta_data"],
)
class RuleSciBaseUnionUniqueMetaDataReport(BaseRule):
    _metric_info = {
        "category": "Rule-Based Metadata Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleSciBaseUnionUniqueMetaDataReport",
        "description": "Run SciBase unified metadata DB validation and write reports.",
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
        dt = params.get("dt")
        paper_dt = params.get("paper_dt") or dt
        ebook_dt = params.get("ebook_dt") or dt
        output_dir = Path(str(params["output_dir"])) if params.get("output_dir") else default_output_dir(
            dt,
            paper_dt,
            ebook_dt,
            int_param(params, "limit", 3000),
            full,
        )

        config_path = write_temp_settings(params)
        result = validate_db(
            config_path=config_path,
            paper_table=str(params.get("paper_table") or DEFAULT_PAPER_TABLE),
            ebook_table=str(params.get("ebook_table") or DEFAULT_EBOOK_TABLE),
            xinghe_table=str(params.get("xinghe_table") or DEFAULT_XINGHE_TABLE),
            target_table=str(params.get("target_table") or DEFAULT_TARGET_TABLE),
            dt=dt,
            paper_dt=paper_dt,
            ebook_dt=ebook_dt,
            limit=None if full else int_param(params, "limit", 3000),
            output_dir=output_dir,
            mapping_csv=Path(str(params.get("mapping_csv") or DEFAULT_MAPPING_CSV)),
            coverage_mode=str(params.get("coverage_mode") or "exact"),
            null_empty_mode=str(params.get("null_empty_mode") or "exact"),
            missing_sample_mode=str(params.get("missing_sample_mode") or "skip"),
            target_sample_mode=str(params.get("target_sample_mode") or "natural"),
        )
        mapping_summary = result.get("source_field_mapping") or {}
        field_quality = result.get("field_quality") or {}
        schema_check = result.get("schema_check") or {}
        bad = bool(schema_check.get("missing_fields") or schema_check.get("type_mismatches"))
        bad = bad or int(mapping_summary.get("failed") or 0) > 0
        bad = bad or int(field_quality.get("failed") or 0) > 0
        reason = [
            str(output_dir),
            f"mapping_failed={mapping_summary.get('failed')}",
            f"field_failed={field_quality.get('failed')}",
        ]
        if bad:
            return EvalDetail(
                metric=cls.__name__,
                status=True,
                label=[f"{cls.metric_type}.{cls.__name__}"],
                reason=reason,
            )
        return EvalDetail(metric=cls.__name__, label=[QualityLabel.QUALITY_GOOD], reason=reason)


if __name__ == "__main__":
    cli()
