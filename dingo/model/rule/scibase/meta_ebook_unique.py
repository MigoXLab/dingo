#!/usr/bin/env python3
"""Self-contained meta_ebook unique DB validator.

Field aggregation rules are driven by ../doc/ebook_unique_mapping.csv.
"""
from __future__ import annotations

import csv
import re
import argparse
import json
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

SKIP_COMPARE_STRATEGIES = frozenset({"random_pick_cls"})
ORDER_INSENSITIVE_COMPARE_STRATEGIES = frozenset({"dedup_array", "isbn_normalize"})
StrategyHandler = Callable[[List[Dict[str, Any]], "FieldRule", Dict[str, Any]], Any]


@dataclass
class FieldRule:
    field_name: str
    data_type: str
    strategy: str
    params: Dict[str, Any]
    source_field: str
    description: str

    @property
    def effective_source(self) -> str:
        return self.source_field or self.field_name


def _parse_params(raw: str) -> Dict[str, Any]:
    if not raw:
        return {}
    params: Dict[str, Any] = {}
    for pair in raw.split(";"):
        pair = pair.strip()
        if "=" not in pair:
            continue
        key, val = pair.split("=", 1)
        key, val = key.strip(), val.strip()
        if val.lower() == "true":
            params[key] = True
        elif val.lower() == "false":
            params[key] = False
        elif val.lstrip("-").isdigit():
            params[key] = int(val)
        else:
            params[key] = val
    return params


def load_field_rules(
    path: Path,
    *,
    field_column: str = "字段名",
    type_column: str = "数据类型",
    strategy_column: str = "聚合策略",
    params_column: str = "策略参数",
    source_column: str = "源字段名",
    desc_column: str = "去重 / 聚合处理逻辑",
) -> List[FieldRule]:
    rules: List[FieldRule] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or field_column not in reader.fieldnames:
            available = ", ".join(fn for fn in (reader.fieldnames or []) if fn.strip())
            raise ValueError(
                f"映射文件 {path} 缺少字段列 {field_column!r}（可用列: {available}）"
            )
        for row in reader:
            name = (row.get(field_column) or "").strip()
            if not name:
                continue
            rules.append(FieldRule(
                field_name=name,
                data_type=(row.get(type_column) or "").strip(),
                strategy=(row.get(strategy_column) or "").strip(),
                params=_parse_params((row.get(params_column) or "").strip()),
                source_field=(row.get(source_column) or "").strip(),
                description=(row.get(desc_column) or "").strip(),
            ))
    return rules


def output_fields_from_rules(rules: Sequence[FieldRule]) -> List[str]:
    return [r.field_name for r in rules if r.strategy not in SKIP_COMPARE_STRATEGIES]


def order_insensitive_fields_from_rules(rules: Sequence[FieldRule]) -> set:
    return {
        r.field_name
        for r in rules
        if r.strategy in ORDER_INSENSITIVE_COMPARE_STRATEGIES
    }


def aggregate_by_rules(
    records: List[Dict[str, Any]],
    rules: Sequence[FieldRule],
    handlers: Dict[str, StrategyHandler],
) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for rule in rules:
        handler = handlers.get(rule.strategy)
        if handler is None:
            raise ValueError(
                f"Unknown aggregation strategy {rule.strategy!r} "
                f"for field {rule.field_name!r}"
            )
        result[rule.field_name] = handler(records, rule, result)
    return result

try:
    import pymysql
except ImportError:  # pragma: no cover - runtime dependency check
    pymysql = None  # type: ignore


CURRENT_YEAR = datetime.now().year
PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
DEFAULT_CONFIG_PATH = Path("sci_base_qa_test_config.json")
TEMPLATE_CONFIG_PATH = ASSETS_DIR / "settings.template.json"
DEFAULT_MAPPING_CSV = ASSETS_DIR / "ebook_unique_mapping.csv"
REPORT_ROOT = Path("report")
DEFAULT_SOURCE_TABLE = "dws_meta_ebook_data_acc_d"
DEFAULT_TARGET_TABLE = "dws_meta_ebook_isbn_unique_acc_d"


def safe_filename_token(value: Optional[Any]) -> str:
    text = "all" if value in (None, "") else str(value)
    return re.sub(r"[^0-9A-Za-z_-]+", "_", text).strip("_") or "all"


def default_report_path(dt: Optional[str], sample_mode: str, full: bool) -> Path:
    mode = "full" if full else sample_mode
    report_dir = REPORT_ROOT / f"meta_ebook_unique_dt_{safe_filename_token(dt)}_{safe_filename_token(mode)}"
    return report_dir / "source_field_mismatch.jsonl"


def _json_inline(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, cls=JsonEncoder)


def summary_paths(report_path: Path) -> Tuple[Path, Path]:
    return report_path.parent / "summary.json", report_path.parent / "readable_summary.md"


REPORT_KEY_LABELS = {
    "report": "报告路径",
    "total_problem_rows": "问题记录数",
    "result": "校验结果",
    "status_counts": "状态分布",
    "field_counts": "字段问题分布",
    "field_samples": "字段问题样例",
    "key": "键值",
    "expected_key": "预期键值",
    "dt": "分区日期",
    "source_count": "源表记录数",
    "status": "状态",
    "expected": "预期值",
    "actual": "实际值",
    "kind": "校验类型",
    "source_table": "源表",
    "target_table": "目标表",
    "key_field": "去重键字段",
    "validated_partitions": "已校验分区",
    "sample_mode": "抽样模式",
    "sample_size": "抽样数量",
    "dt_check": "分区检查",
    "checked": "已校验数",
    "passed": "通过数",
    "failed": "失败数",
    "missing_source": "源表缺失数",
    "missing_target": "目标表缺失数",
    "source_count_buckets": "源表记录数分桶",
    "missing_samples": "缺失样例",
    "source_records": "源表记录",
    "target_records": "目标表记录",
    "expected_record": "预期记录",
    "report_path": "报告路径",
    "sample_mismatches": "问题样例",
    "mismatches": "字段差异",
    "source_dt_count": "源表分区数",
    "target_dt_count": "目标表分区数",
    "missing_in_target": "目标表缺失分区",
    "extra_in_target": "目标表多余分区",
    "count_mismatches": "数量不一致明细",
    "source_distinct_skipped": "源表去重计数已跳过",
}


def localize_report_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            REPORT_KEY_LABELS.get(str(key), str(key)): localize_report_keys(val)
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [localize_report_keys(item) for item in value]
    return value


TOP_FIELD_LIMIT = 20
TOP_SAMPLE_FIELD_LIMIT = 5
SAMPLES_PER_FIELD = 3


def compact_record_for_report(record: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "track_id",
        "isbn13",
        "isbns",
        "origin_osi",
        "origin_id",
        "title",
        "type",
        "author",
        "contributors",
        "published_year",
        "published_date",
        "publisher",
        "dt",
    )
    return {
        key: record.get(key)
        for key in keys
        if record.get(key) not in (None, "", [], {})
    }


def compact_records_for_report(records: Any) -> Any:
    if isinstance(records, dict):
        return compact_record_for_report(records)
    if not isinstance(records, list):
        return records
    return [
        compact_record_for_report(record)
        for record in records
        if isinstance(record, dict)
    ]


def build_report_summary(
    report_path: Path,
    result: Dict[str, Any],
    mismatch_rows: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    status_counts = Counter(str(row.get("status") or "unknown") for row in mismatch_rows)
    field_counts: Counter = Counter()
    field_samples: Dict[str, List[Dict[str, Any]]] = {}
    missing_samples: List[Dict[str, Any]] = []
    for row in mismatch_rows:
        if row.get("status") in ("missing_target", "missing_source") and len(missing_samples) < SAMPLES_PER_FIELD:
            missing_samples.append(
                {
                    "key": row.get("key"),
                    "expected_key": row.get("expected_key"),
                    "dt": row.get("dt"),
                    "source_count": row.get("source_count"),
                    "status": row.get("status"),
                    "source_records": compact_records_for_report(row.get("source_records")),
                    "target_records": compact_records_for_report(row.get("target_records")),
                    "expected_record": compact_records_for_report(row.get("expected_record")),
                }
            )
        for field, diff in (row.get("mismatches") or {}).items():
            field_counts[field] += 1
            samples = field_samples.setdefault(field, [])
            if len(samples) < SAMPLES_PER_FIELD:
                samples.append(
                    {
                        "key": row.get("key"),
                        "expected_key": row.get("expected_key"),
                        "dt": row.get("dt"),
                        "source_count": row.get("source_count"),
                        "status": row.get("status"),
                        "expected": diff.get("expected") if isinstance(diff, dict) else None,
                        "actual": diff.get("actual") if isinstance(diff, dict) else None,
                    }
                )
    sorted_field_counts = dict(field_counts.most_common())
    top_sample_fields = set(list(sorted_field_counts)[:TOP_SAMPLE_FIELD_LIMIT])
    return {
        "report": str(report_path),
        "total_problem_rows": len(mismatch_rows),
        "result": {k: v for k, v in result.items() if k != "sample_mismatches"},
        "status_counts": dict(status_counts.most_common()),
        "field_counts": sorted_field_counts,
        "field_count_total": len(sorted_field_counts),
        "field_samples": {
            field: field_samples[field]
            for field in sorted_field_counts
            if field in top_sample_fields and field in field_samples
        },
        "missing_samples": missing_samples,
    }


def write_report_summary(report_path: Path, result: Dict[str, Any], mismatch_rows: Sequence[Dict[str, Any]]) -> None:
    summary_json_path, summary_md_path = summary_paths(report_path)
    summary = build_report_summary(report_path, result, mismatch_rows)
    with summary_json_path.open("w", encoding="utf-8") as f:
        json.dump(localize_report_keys(summary), f, ensure_ascii=False, indent=2, cls=JsonEncoder)

    lines = [
        "# Ebook 去重校验报告摘要",
        "",
        f"- 分区: `{result.get('dt')}`",
        f"- 抽样: `{result.get('sample_mode')}`, 数量 `{result.get('sample_size')}`",
        f"- 结果: 已校验 `{result.get('checked')}`，通过 `{result.get('passed')}`，失败 `{result.get('failed')}`",
        f"- 缺失: 源表 `{result.get('missing_source')}`，目标表 `{result.get('missing_target')}`",
        f"- 明细报告: `{report_path}`",
        f"- 报告目录: `{report_path.parent}`",
        f"- 源表记录数分桶: `{_json_inline(result.get('source_count_buckets'))}`",
        "",
        "## Count 校验",
        "",
        f"- source_distinct_skipped: `{(result.get('dt_check') or {}).get('source_distinct_skipped')}`",
        f"- count_mismatches: `{len((result.get('dt_check') or {}).get('count_mismatches') or [])}`",
        "",
        "## 状态分布",
        "",
    ]
    for status, count in summary["status_counts"].items():
        lines.append(f"- `{status}`: {count}")
    if not summary["status_counts"]:
        lines.append("- 无")
    lines.extend(["", "## 字段问题分布", ""])
    for field, count in summary["field_counts"].items():
        lines.append(f"- `{field}`: {count}")
    if not summary["field_counts"]:
        lines.append("- 无")
    if summary.get("missing_samples"):
        lines.extend(["", "## 缺失样例", ""])
        for sample in summary["missing_samples"]:
            lines.append(
                f"- ISBN13 `{sample.get('key')}`, expected_key=`{sample.get('expected_key')}`, "
                f"source_count={sample.get('source_count')}, status=`{sample.get('status')}`"
            )
            for name in ("source_records", "target_records", "expected_record"):
                if sample.get(name) is not None:
                    lines.append(f"  - {name}: `{_json_inline(sample.get(name))}`")
    lines.extend(["", "## 字段问题样例", ""])
    for field, samples in summary["field_samples"].items():
        lines.append(f"### {field} ({summary['field_counts'].get(field)})")
        lines.append("")
        for sample in samples:
            lines.append(
                f"- ISBN13 `{sample.get('key')}`, expected_key=`{sample.get('expected_key')}`, "
                f"source_count={sample.get('source_count')}, status=`{sample.get('status')}`"
            )
            lines.append(f"  - expected: `{_json_inline(sample.get('expected'))}`")
            lines.append(f"  - actual: `{_json_inline(sample.get('actual'))}`")
            lines.append("")
    with summary_md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


class JsonEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            if obj == obj.to_integral_value():
                return int(obj)
            return float(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


# ---- common scalar/array helpers ----


def is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def choose_freq_then_lex_max(values: Iterable[str]) -> str:
    vals = [v for v in values if isinstance(v, str) and v != ""]
    if not vals:
        return ""
    cnt = Counter(vals)
    max_freq = max(cnt.values())
    candidates = [k for k, v in cnt.items() if v == max_freq]
    return max(candidates)


def choose_freq_then_max_int(values: Iterable[int]) -> Optional[int]:
    vals = [v for v in values if isinstance(v, int)]
    if not vals:
        return None
    cnt = Counter(vals)
    max_freq = max(cnt.values())
    candidates = [k for k, v in cnt.items() if v == max_freq]
    return max(candidates)


def dedup_str_array(values: Iterable[Any], lower: bool = False) -> List[str]:
    out = set()
    for item in values:
        if isinstance(item, list):
            for v in item:
                if v is None:
                    continue
                s = str(v)
                if s == "":
                    continue
                out.add(s.lower() if lower else s)
        elif item is not None:
            s = str(item)
            if s != "":
                out.add(s.lower() if lower else s)
    return sorted(out)


def merge_identifiers(values: Iterable[Any]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        for k, v in item.items():
            if v is None:
                continue
            sv = str(v)
            if k not in merged or sv > merged[k]:
                merged[k] = sv
    return merged


def parse_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    txt = str(value).strip()
    if txt == "":
        return None
    try:
        return int(txt)
    except ValueError:
        return None


# ---- ebook-specific normalization helpers ----


def normalize_isbn_to_13(raw: Any) -> Optional[str]:
    """10 位 ISBN 前面加 978 转为 13 位，13 位保留，其他长度丢弃。"""
    if raw is None:
        return None
    s = str(raw).strip().replace("-", "")
    if not s:
        return None
    if len(s) == 13 and s.isdigit():
        return s
    if len(s) == 10 and s[:9].isdigit() and (s[9].isdigit() or s[9].upper() == "X"):
        return "978" + s
    return None


def extract_year(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, int):
        year = value
    else:
        txt = str(value).strip()
        m = re.search(r"(1\d{3}|20\d{2})", txt)
        if not m:
            return None
        year = int(m.group(1))
    if year < 1000 or year > CURRENT_YEAR:
        return None
    return year


# ---- strategy handlers ----


def _handle_freq_lex_max(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> Any:
    src = rule.effective_source
    min_len = rule.params.get("min_len")
    max_len = rule.params.get("max_len")
    vals: List[str] = []
    for r in records:
        v = r.get(src)
        if not is_non_empty(v):
            continue
        s = str(v)
        if min_len is not None and len(s) < min_len:
            continue
        if max_len is not None and len(s) > max_len:
            continue
        vals.append(s)
    return choose_freq_then_lex_max(vals)


def _handle_freq_int_max(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> Any:
    src = rule.effective_source
    min_val = rule.params.get("min_val")
    max_val = rule.params.get("max_val")
    if isinstance(max_val, str) and max_val == "CURRENT_YEAR":
        max_val = CURRENT_YEAR
    use_extract = rule.params.get("extract_year", False)
    vals: List[int] = []
    for r in records:
        v = extract_year(r.get(src)) if use_extract else parse_int(r.get(src))
        if v is None:
            continue
        if min_val is not None and v < min_val:
            continue
        if max_val is not None and v > max_val:
            continue
        vals.append(v)
    return choose_freq_then_max_int(vals)


def _handle_dedup_array(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> List[str]:
    return dedup_str_array(
        [r.get(rule.effective_source, []) for r in records],
        lower=rule.params.get("lower", False),
    )


def _handle_merge_map(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> Dict[str, str]:
    return merge_identifiers([r.get(rule.effective_source, {}) for r in records])


def _handle_max_int(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> Optional[int]:
    vals = [v for r in records for v in [parse_int(r.get(rule.effective_source))] if v is not None]
    return max(vals) if vals else None


def _handle_latest_dt(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> str:
    src = rule.effective_source
    vals = [str(r.get(src, "")) for r in records if is_non_empty(r.get(src))]
    return max(vals) if vals else ""


def _handle_isbn_normalize(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> List[str]:
    raw = dedup_str_array([r.get(rule.effective_source, []) for r in records])
    normalized = [v for v in (normalize_isbn_to_13(s) for s in raw) if v is not None]
    return sorted(set(normalized))


def _handle_isbn_min(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> str:
    isbns = result.get("isbns", [])
    if isbns:
        return isbns[0]
    return str(records[0].get("isbn13", "")) if records else ""


STRATEGY_HANDLERS: Dict[str, StrategyHandler] = {
    "freq_lex_max": _handle_freq_lex_max,
    "freq_int_max": _handle_freq_int_max,
    "dedup_array": _handle_dedup_array,
    "merge_map": _handle_merge_map,
    "max_int": _handle_max_int,
    "latest_dt": _handle_latest_dt,
    "isbn_normalize": _handle_isbn_normalize,
    "isbn_min": _handle_isbn_min,
}


# ---- aggregation ----


def aggregate_group(records: List[Dict[str, Any]], rules: Sequence[FieldRule]) -> Dict[str, Any]:
    return aggregate_by_rules(records, rules, STRATEGY_HANDLERS)


# ---- DB validation helpers ----


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

    def _is_retryable_connect_error(exc: Exception) -> bool:
        if pymysql is None:
            return False
        if isinstance(exc, pymysql.err.OperationalError):
            code = exc.args[0] if exc.args else None
            if code in (2003, 2006, 2013):
                return True
        msg = str(exc).lower()
        return any(token in msg for token in ("lost connection", "can't connect", "timed out", "timeout"))

    for attempt in range(1, max_attempts + 1):
        try:
            # Do not pass database= on connect: this StarRocks endpoint drops
            # auth when a default schema is selected; use fully-qualified table names in SQL.
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
            if attempt >= max_attempts or not _is_retryable_connect_error(exc):
                raise
            print(
                f"[retry] MySQL 连接失败 ({type(exc).__name__}: {exc})，"
                f"{delay:.1f}s 后重试 ({attempt}/{max_attempts})"
            )
            time.sleep(delay)
            delay *= backoff

    raise RuntimeError("MySQL connection retry exhausted unexpectedly")


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


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def comparable_record(record: Dict[str, Any], fields: Iterable[str]) -> Dict[str, Any]:
    return {field: canonicalize(record.get(field)) for field in fields}


def _dt_clause(dt: Optional[str], params: List[Any]) -> str:
    if dt is not None:
        params.append(dt)
        return " AND `dt` = %s"
    return ""


def _limit_clause(limit: Optional[int]) -> str:
    return "" if limit is None else f" LIMIT {int(limit)}"


def source_canonical_isbn13_expr(array_field: str = "`isbns`") -> str:
    """SQL expression matching normalize_isbn_to_13 + min per source row."""
    cleaned = "regexp_replace(trim(x), '-', '')"
    normalized = (
        "CASE "
        f"WHEN {cleaned} REGEXP '^[0-9]{{13}}$' THEN {cleaned} "
        f"WHEN {cleaned} REGEXP '^[0-9]{{9}}[0-9Xx]$' THEN concat('978', {cleaned}) "
        "ELSE NULL END"
    )
    return (
        "array_min(array_distinct(array_filter("
        f"array_map(x -> {normalized}, {array_field}), "
        "x -> x IS NOT NULL AND x != ''"
        ")))"
    )


def _key_not_null_clause(key_expr: str) -> str:
    return f" AND {key_expr} IS NOT NULL AND {key_expr} != ''"


def _hash_sample_predicate(
    mod_base: Optional[int],
    mod_max: Optional[int],
    *,
    key_expr: str = "`isbn13`",
) -> str:
    if not mod_base or not mod_max or mod_max <= 0:
        return ""
    return f" AND (ABS(CRC32({key_expr})) MOD {int(mod_base)}) < {int(mod_max)}"


def _sample_order_clause(*, high_first: bool = False, key_expr: str = "sample_key") -> str:
    if high_first:
        return f"source_count DESC, CRC32({key_expr})"
    return f"CRC32({key_expr})"


def build_target_key_query(
    table: str,
    dt: Optional[str],
    limit: Optional[int],
    *,
    hash_mod_base: Optional[int] = None,
    hash_mod_max: Optional[int] = None,
) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    sql = (
        f"SELECT `isbn13` AS sample_key FROM {quote_identifier(table)} "
        "WHERE 1=1"
        f"{_key_not_null_clause('`isbn13`')}"
        f"{_dt_clause(dt, params)}"
        f"{_hash_sample_predicate(hash_mod_base, hash_mod_max, key_expr='`isbn13`')}"
        f" ORDER BY {_sample_order_clause(key_expr='`isbn13`')}{_limit_clause(limit)}"
    )
    return sql, params


def build_target_first_key_query(
    table: str,
    dt: Optional[str],
    limit: Optional[int],
) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    sql = (
        f"SELECT `isbn13` AS sample_key FROM {quote_identifier(table)} "
        "WHERE 1=1"
        f"{_key_not_null_clause('`isbn13`')}"
        f"{_dt_clause(dt, params)}"
        f"{_limit_clause(limit)}"
    )
    return sql, params


def build_random_key_query(
    table: str,
    dt: Optional[str],
    limit: Optional[int],
    *,
    hash_mod_base: Optional[int] = None,
    hash_mod_max: Optional[int] = None,
) -> Tuple[str, List[Any]]:
    return build_target_key_query(
        table,
        dt,
        limit,
        hash_mod_base=hash_mod_base,
        hash_mod_max=hash_mod_max,
    )


def build_duplicate_key_query(
    table: str,
    dt: Optional[str],
    limit: Optional[int],
    *,
    high_first: bool,
    hash_mod_base: Optional[int] = None,
    hash_mod_max: Optional[int] = None,
) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    key_expr = source_canonical_isbn13_expr()
    sql = (
        "SELECT sample_key, COUNT(*) AS source_count FROM ("
        f"SELECT {key_expr} AS sample_key FROM {quote_identifier(table)} WHERE 1=1"
        f"{_dt_clause(dt, params)}"
        ") keyed WHERE 1=1"
        f"{_key_not_null_clause('sample_key')}"
        f"{_hash_sample_predicate(hash_mod_base, hash_mod_max, key_expr='sample_key')}"
        " GROUP BY sample_key HAVING COUNT(*) > 1 "
        f"ORDER BY {_sample_order_clause(high_first=high_first)}{_limit_clause(limit)}"
    )
    return sql, params


def build_field_conflict_key_query(
    table: str,
    dt: Optional[str],
    limit: Optional[int],
    *,
    hash_mod_base: Optional[int] = None,
    hash_mod_max: Optional[int] = None,
) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    key_expr = source_canonical_isbn13_expr()
    conflict_checks = [
        "COUNT(DISTINCT `title`) > 1",
        "COUNT(DISTINCT `abstract`) > 1",
        "COUNT(DISTINCT `language`) > 1",
        "COUNT(DISTINCT `published_year`) > 1",
        "COUNT(DISTINCT `pages`) > 1",
        "COUNT(DISTINCT `category`) > 1",
    ]
    sql = (
        "SELECT sample_key, COUNT(*) AS source_count FROM ("
        f"SELECT {key_expr} AS sample_key, `title`, `abstract`, `language`, "
        f"`published_year`, `pages`, `category` FROM {quote_identifier(table)} WHERE 1=1"
        f"{_dt_clause(dt, params)}"
        ") keyed WHERE 1=1"
        f"{_key_not_null_clause('sample_key')}"
        f"{_hash_sample_predicate(hash_mod_base, hash_mod_max, key_expr='sample_key')}"
        " GROUP BY sample_key HAVING COUNT(*) > 1 AND "
        f"({' OR '.join(conflict_checks)}) "
        f"ORDER BY {_sample_order_clause(high_first=True)}{_limit_clause(limit)}"
    )
    return sql, params


def build_count_bucket_key_query(
    table: str,
    dt: Optional[str],
    limit: Optional[int],
    *,
    bucket: str,
    hash_mod_base: Optional[int] = None,
    hash_mod_max: Optional[int] = None,
) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    key_expr = source_canonical_isbn13_expr()
    if bucket == "one":
        having = "COUNT(*) = 1"
    elif bucket == "two":
        having = "COUNT(*) = 2"
    elif bucket == "multi":
        having = "COUNT(*) > 2"
    else:
        raise ValueError(f"Unsupported count bucket: {bucket}")
    sql = (
        "SELECT sample_key, COUNT(*) AS source_count FROM ("
        f"SELECT {key_expr} AS sample_key FROM {quote_identifier(table)} WHERE 1=1"
        f"{_dt_clause(dt, params)}"
        ") keyed WHERE 1=1"
        f"{_key_not_null_clause('sample_key')}"
        f"{_hash_sample_predicate(hash_mod_base, hash_mod_max, key_expr='sample_key')}"
        f" GROUP BY sample_key HAVING {having} "
        f"ORDER BY {_sample_order_clause()}{_limit_clause(limit)}"
    )
    return sql, params


def _append_sample_key(
    keys: List[str],
    seen: set,
    key: str,
    *,
    sample_size: Optional[int],
) -> bool:
    if not key or key in seen:
        return False
    seen.add(key)
    keys.append(key)
    return sample_size is not None and len(keys) >= sample_size


def fetch_sample_keys(
    conn: Any,
    *,
    source_table: str,
    target_table: str,
    dt: Optional[str],
    sample_mode: str,
    sample_size: Optional[int],
    hash_mod_base: Optional[int] = None,
    hash_mod_max: Optional[int] = None,
) -> List[str]:
    hash_kw = {"hash_mod_base": hash_mod_base, "hash_mod_max": hash_mod_max}

    if sample_mode == "target-first":
        sql, params = build_target_first_key_query(target_table, dt, sample_size)
        query_plan: List[Tuple[str, Tuple[str, List[Any]]]] = [("target-first", (sql, params))]
    elif sample_mode == "target-random":
        sql, params = build_target_key_query(target_table, dt, sample_size, **hash_kw)
        query_plan: List[Tuple[str, Tuple[str, List[Any]]]] = [("target-random", (sql, params))]
    elif sample_mode == "count-buckets":
        per_bucket = None if sample_size is None else max(1, sample_size // 3)
        query_plan = [
            ("count=1", build_count_bucket_key_query(source_table, dt, per_bucket, bucket="one", **hash_kw)),
            ("count=2", build_count_bucket_key_query(source_table, dt, per_bucket, bucket="two", **hash_kw)),
            ("count>2", build_count_bucket_key_query(source_table, dt, per_bucket, bucket="multi", **hash_kw)),
        ]
    elif sample_mode == "mixed":
        per_bucket = None if sample_size is None else max(1, sample_size // 6)
        query_plan = [
            ("count=1", build_count_bucket_key_query(source_table, dt, per_bucket, bucket="one", **hash_kw)),
            ("count=2", build_count_bucket_key_query(source_table, dt, per_bucket, bucket="two", **hash_kw)),
            ("count>2", build_count_bucket_key_query(source_table, dt, per_bucket, bucket="multi", **hash_kw)),
            ("field-conflict", build_field_conflict_key_query(source_table, dt, per_bucket, **hash_kw)),
            ("high-duplicate", build_duplicate_key_query(source_table, dt, per_bucket, high_first=True, **hash_kw)),
            ("target-random", build_random_key_query(target_table, dt, per_bucket, **hash_kw)),
        ]
    else:
        raise ValueError(f"Unsupported sample_mode: {sample_mode}")

    keys: List[str] = []
    seen: set = set()

    for idx, (label, (sql, params)) in enumerate(query_plan, start=1):
        _log(
            f"[info] 抽样 SQL {idx}/{len(query_plan)} [{label}] 开始执行"
            f"（dt={dt!r}, mode={sample_mode}）…"
        )
        t0 = time.monotonic()
        rows = fetch_records(conn, sql, params)
        for row in rows:
            if _append_sample_key(keys, seen, str(row.get("sample_key") or ""), sample_size=sample_size):
                _log(
                    f"[info] 抽样 SQL {idx}/{len(query_plan)} [{label}] 完成，"
                    f"耗时 {time.monotonic() - t0:.1f}s，已收集 {len(keys)} 个 key"
                )
                return keys
        _log(
            f"[info] 抽样 SQL {idx}/{len(query_plan)} [{label}] 完成，"
            f"耗时 {time.monotonic() - t0:.1f}s，当前共 {len(keys)} 个 key"
        )
    return keys


def build_target_record_query(table: str, isbn13: Any, dt: Optional[str]) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    if dt is not None:
        params.append(dt)
    params.append(str(isbn13))
    dt_sql = " AND `dt` = %s" if dt is not None else ""
    sql = (
        f"SELECT * FROM {quote_identifier(table)} WHERE 1=1"
        f"{dt_sql} AND `isbn13` = %s LIMIT 1"
    )
    return sql, params


def build_source_query(table: str, isbn13: Any, dt: Optional[str]) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    key_expr = source_canonical_isbn13_expr()
    if dt is not None:
        params.append(dt)
    params.append(str(isbn13))
    dt_sql = " AND `dt` = %s" if dt is not None else ""
    return (
        "SELECT * FROM ("
        f"SELECT *, {key_expr} AS sample_key FROM {quote_identifier(table)} WHERE 1=1{dt_sql}"
        ") keyed WHERE sample_key = %s",
        params,
    )


def build_source_batch_query(
    table: str,
    sample_keys: Sequence[str],
    dt: Optional[str],
) -> Tuple[str, List[Any]]:
    if not sample_keys:
        raise ValueError("sample_keys must not be empty")

    key_expr = source_canonical_isbn13_expr()
    sample_key_sql = " UNION ALL ".join("SELECT %s AS sample_key" for _ in sample_keys)
    params: List[Any] = [str(key) for key in sample_keys]
    if dt is not None:
        params.append(dt)
    dt_sql = " AND `dt` = %s" if dt is not None else ""

    sql = (
        f"WITH sample_keys AS ({sample_key_sql}), "
        "source_keyed AS ("
        f"SELECT *, {key_expr} AS sample_key FROM {quote_identifier(table)} WHERE 1=1{dt_sql}"
        ") "
        "SELECT source_keyed.* FROM source_keyed "
        "JOIN sample_keys ON source_keyed.sample_key = sample_keys.sample_key"
    )
    return sql, params


def group_source_rows_by_sample_key(
    rows: Sequence[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = str(row.get("sample_key") or "")
        if not key:
            continue
        grouped.setdefault(key, []).append(row)
    return grouped


def normalize_order_insensitive_value(value: Any) -> Any:
    value = canonicalize(value)
    if isinstance(value, list):
        dedup_map: Dict[str, Any] = {}
        for item in value:
            if item is None or item == "":
                continue
            dedup_map[canonical_json(item)] = item
        return [dedup_map[key] for key in sorted(dedup_map)]
    return value


def normalize_empty_for_compare(value: Any, data_type: str) -> Any:
    type_text = (data_type or "").strip().lower()
    if value is None:
        return None
    if type_text in ("string", "varchar", "char", "text"):
        return None if isinstance(value, str) and value.strip() == "" else value
    if type_text.startswith("array"):
        if value == []:
            return None
        if isinstance(value, str) and value.strip() in ("", "[]"):
            return None
    return value


def compare_records(
    expected: Dict[str, Any],
    actual: Dict[str, Any],
    order_insensitive_fields: Optional[set] = None,
    field_types: Optional[Dict[str, str]] = None,
) -> Dict[str, Dict[str, Any]]:
    mismatches: Dict[str, Dict[str, Any]] = {}
    order_insensitive_fields = order_insensitive_fields or set()
    field_types = field_types or {}
    for field, expected_value in expected.items():
        if field in order_insensitive_fields:
            expected_value = normalize_order_insensitive_value(expected_value)
            actual_value = normalize_order_insensitive_value(actual.get(field))
        else:
            actual_value = canonicalize(actual.get(field))
        expected_value = normalize_empty_for_compare(expected_value, field_types.get(field, ""))
        actual_value = normalize_empty_for_compare(actual_value, field_types.get(field, ""))
        if expected_value != actual_value:
            mismatches[field] = {"expected": expected_value, "actual": actual_value}
    return mismatches


def validate_dt_partitions(
    conn: Any,
    source_table: str,
    target_table: str,
    dt: Optional[str],
    *,
    skip_source_distinct: bool = False,
) -> Dict[str, Any]:
    """Check dt partition coverage and key counts between source and target."""
    params: List[Any] = []
    dt_filter = _dt_clause(dt, params)

    src_map: Dict[str, int] = {}
    if not skip_source_distinct:
        key_expr = source_canonical_isbn13_expr()
        src_sql = (
            "SELECT `dt`, COUNT(DISTINCT sample_key) AS key_count FROM ("
            f"SELECT `dt`, {key_expr} AS sample_key FROM {quote_identifier(source_table)}"
            f" WHERE 1=1{dt_filter}"
            ") keyed WHERE 1=1"
            f"{_key_not_null_clause('sample_key')}"
            " GROUP BY `dt` ORDER BY `dt`"
        )
        src_rows = fetch_records(conn, src_sql, params)
        src_map = {str(r["dt"]): int(r["key_count"]) for r in src_rows}

    tgt_sql = (
        f"SELECT `dt`, COUNT(*) AS row_count"
        f" FROM {quote_identifier(target_table)}"
        f" WHERE 1=1{dt_filter} GROUP BY `dt` ORDER BY `dt`"
    )
    tgt_rows = fetch_records(conn, tgt_sql, params)
    tgt_map = {str(r["dt"]): int(r["row_count"]) for r in tgt_rows}
    all_dts = sorted(set(src_map) | set(tgt_map))

    mismatches: List[Dict[str, Any]] = []
    for d in all_dts:
        src_cnt = src_map.get(d)
        tgt_cnt = tgt_map.get(d)
        if src_cnt != tgt_cnt:
            mismatches.append({
                "dt": d,
                "source_key_count": src_cnt,
                "target_row_count": tgt_cnt,
            })

    return {
        "source_dt_count": len(src_map),
        "target_dt_count": len(tgt_map),
        "missing_in_target": sorted(set(src_map) - set(tgt_map)),
        "extra_in_target": sorted(set(tgt_map) - set(src_map)),
        "count_mismatches": mismatches,
        "source_distinct_skipped": skip_source_distinct,
    }


def discover_dt_values(conn: Any, table: str) -> List[str]:
    sql = (
        f"SELECT DISTINCT `dt` FROM {quote_identifier(table)} "
        "WHERE `dt` IS NOT NULL AND `dt` != '' ORDER BY `dt`"
    )
    return [str(r["dt"]) for r in fetch_records(conn, sql)]


def validate_db(
    *,
    config_path: Path,
    source_table: str,
    target_table: str,
    dt: Optional[str],
    limit: Optional[int],
    sample_mode: str,
    report_path: Optional[Path],
    mapping_csv: Path = DEFAULT_MAPPING_CSV,
    skip_dt_check: bool = False,
    skip_source_distinct: bool = False,
    hash_mod_base: Optional[int] = 100,
    hash_mod_max: Optional[int] = 2,
) -> Dict[str, Any]:
    rules = load_field_rules(mapping_csv)
    output_fields = output_fields_from_rules(rules)
    order_insensitive_fields = order_insensitive_fields_from_rules(rules)
    field_types = {rule.field_name: rule.data_type for rule in rules}
    cfg = load_config(config_path)
    mysql_cfg = cfg.get("mysql", {}) if isinstance(cfg.get("mysql"), dict) else {}
    catalog = mysql_cfg.get("catalog")
    database = str(mysql_cfg.get("database") or "dws")
    source_table = qualify_table_name(source_table, catalog, database)
    target_table = qualify_table_name(target_table, catalog, database)
    hash_enabled = bool(hash_mod_base and hash_mod_max and hash_mod_max > 0)
    _log(
        f"[info] 图书去重校验开始：dt={dt!r}, limit={limit}, sample_mode={sample_mode}, "
        f"hash_sample={'on' if hash_enabled else 'off'}, "
        f"skip_dt_check={skip_dt_check}, source={source_table}, target={target_table}"
    )
    with connect_starrocks(config_path) as conn:
        _log("[info] StarRocks 连接成功")
        if dt is not None:
            dt_list = [dt]
        else:
            _log("[info] 正在发现源表 dt 分区…")
            dt_list = discover_dt_values(conn, source_table)
            _log(f"[info] 自动发现 {len(dt_list)} 个 dt 分区，逐分区验证")

        if skip_dt_check:
            dt_check = {"skipped": True}
            _log("[info] 跳过分区行数统计（--skip-dt-check）")
        else:
            _log("[info] 正在统计目标/源分区行数（源表 DISTINCT 可较慢，可用 --skip-source-distinct 跳过）…")
            t0 = time.monotonic()
            dt_check = validate_dt_partitions(
                conn,
                source_table,
                target_table,
                dt,
                skip_source_distinct=skip_source_distinct,
            )
            _log(f"[info] 分区统计完成，耗时 {time.monotonic() - t0:.1f}s")

        checked = passed = failed = missing_source = missing_target = 0
        source_count_buckets = {"one": 0, "two": 0, "multi": 0}
        mismatch_rows: List[Dict[str, Any]] = []

        for partition_dt in dt_list:
            _log(f"[info] 分区 {partition_dt}：开始抽样 key…")
            sample_keys = fetch_sample_keys(
                conn,
                source_table=source_table,
                target_table=target_table,
                dt=partition_dt,
                sample_mode=sample_mode,
                sample_size=limit,
                hash_mod_base=hash_mod_base if hash_enabled else None,
                hash_mod_max=hash_mod_max if hash_enabled else None,
            )
            _log(f"[info] 分区 {partition_dt}：抽到 {len(sample_keys)} 个 ISBN13，开始批量拉取源记录…")
            t0 = time.monotonic()
            source_rows_by_key: Dict[str, List[Dict[str, Any]]] = {}
            if sample_keys:
                source_sql, source_params = build_source_batch_query(source_table, sample_keys, partition_dt)
                source_rows_by_key = group_source_rows_by_sample_key(
                    fetch_records(conn, source_sql, source_params)
                )
            _log(
                f"[info] 分区 {partition_dt}：源记录批量拉取完成，耗时 "
                f"{time.monotonic() - t0:.1f}s，命中 {len(source_rows_by_key)}/{len(sample_keys)} 个 key"
            )
            _log(f"[info] 分区 {partition_dt}：开始逐条比对…")

            for isbn13 in sample_keys:
                source_rows = source_rows_by_key.get(isbn13, [])
                checked += 1
                if checked == 1 or checked % 20 == 0:
                    _log(f"[info] 分区 {partition_dt}：已比对 {checked}/{len(sample_keys)} 条")

                if not source_rows:
                    missing_source += 1
                    mismatch_rows.append({
                        "key": isbn13,
                        "dt": partition_dt,
                        "status": "missing_source",
                        "source_count": 0,
                        "mismatches": {},
                    })
                    continue

                if len(source_rows) == 1:
                    source_count_buckets["one"] += 1
                elif len(source_rows) == 2:
                    source_count_buckets["two"] += 1
                else:
                    source_count_buckets["multi"] += 1
                normalized_source = [{key: normalize_json_like(value) for key, value in row.items()} for row in source_rows]
                aggregated = aggregate_group(normalized_source, rules)
                expected = comparable_record(aggregated, output_fields)
                expected_isbn13 = str(expected.get("isbn13") or isbn13)
                target_sql, target_params = build_target_record_query(target_table, expected_isbn13, partition_dt)
                target_rows = fetch_records(conn, target_sql, target_params)
                if not target_rows:
                    missing_target += 1
                    mismatch_rows.append({
                        "key": isbn13,
                        "expected_key": expected_isbn13,
                        "dt": partition_dt,
                        "status": "missing_target",
                        "source_count": len(source_rows),
                        "source_records": normalized_source,
                        "expected_record": expected,
                        "mismatches": {},
                    })
                    continue

                target_row = target_rows[0]
                actual = comparable_record(target_row, output_fields)
                mismatches = compare_records(expected, actual, order_insensitive_fields, field_types)
                if mismatches:
                    failed += 1
                    mismatch_rows.append(
                        {
                            "key": isbn13,
                            "expected_key": expected_isbn13,
                            "dt": partition_dt,
                            "status": "field_mismatch",
                            "source_count": len(source_rows),
                            "mismatches": mismatches,
                        }
                    )
                else:
                    passed += 1

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as f:
            for row in mismatch_rows:
                f.write(json.dumps(localize_report_keys(row), ensure_ascii=False, cls=JsonEncoder) + "\n")
        (report_path.parent / "source_field_warning.jsonl").write_text("", encoding="utf-8")

    result = {
        "status": "ok",
        "kind": "ebook",
        "source_table": source_table,
        "target_table": target_table,
        "key_field": "isbn13",
        "dt": dt,
        "validated_partitions": dt_list,
        "sample_mode": sample_mode,
        "sample_size": limit,
        "dt_check": dt_check,
        "checked": checked,
        "passed": passed,
        "failed": failed,
        "missing_source": missing_source,
        "missing_target": missing_target,
        "source_count_buckets": source_count_buckets,
        "report_path": str(report_path) if report_path is not None else None,
        "sample_mismatches": mismatch_rows[:5],
    }
    if report_path is not None:
        write_report_summary(report_path, result, mismatch_rows)
    print(json.dumps(result, ensure_ascii=False, cls=JsonEncoder))
    return result


# ---- CLI ----


def cli() -> None:
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    config_args, _ = config_parser.parse_known_args()
    cfg = load_config(config_args.config) if config_args.config.exists() else {}
    ebook_cfg = cfg.get("unique_ebook", {})

    default_csv = ebook_cfg.get("mapping_csv")
    if default_csv:
        default_csv = PROJECT_ROOT / default_csv
    else:
        default_csv = DEFAULT_MAPPING_CSV

    parser = argparse.ArgumentParser(description="Validate meta_ebook unique DB table by ISBN13.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="shared settings JSON path")
    parser.add_argument("--mapping-csv", type=Path, default=default_csv, help="field mapping CSV")
    parser.add_argument("--source-table", default=ebook_cfg.get("source_table", DEFAULT_SOURCE_TABLE))
    parser.add_argument("--target-table", default=ebook_cfg.get("target_table", DEFAULT_TARGET_TABLE))
    parser.add_argument("--dt", default=ebook_cfg.get("dt"), help="dt partition filter")
    parser.add_argument("--limit", type=int, default=int(ebook_cfg.get("limit", 600)))
    parser.add_argument(
        "--sample-mode",
        choices=("count-buckets", "mixed", "target-random", "target-first"),
        default=ebook_cfg.get("sample_mode", "count-buckets"),
        help="count-buckets: 1/2/N 源行分桶；mixed: 加深抽样；target-random: 目标表稳定排序抽样；target-first: 目标表 LIMIT 抽样（smoke 最快）",
    )
    parser.add_argument("--full", action="store_true", help="validate all target rows")
    parser.add_argument("--skip-dt-check", action="store_true", default=bool(ebook_cfg.get("skip_dt_check")))
    parser.add_argument(
        "--skip-source-distinct",
        action="store_true",
        default=bool(ebook_cfg.get("skip_source_distinct")),
        help="dt 统计时跳过源表 COUNT(DISTINCT canonical_isbn13)",
    )
    parser.add_argument(
        "--no-sample-hash",
        action="store_true",
        help="关闭 CRC32 哈希预过滤（默认 mod 100 取 2，约 2%% 子集）",
    )
    parser.add_argument(
        "--sample-hash-mod-base",
        type=int,
        default=int(ebook_cfg.get("sample_hash_mod_base", 100)),
    )
    parser.add_argument(
        "--sample-hash-mod-max",
        type=int,
        default=int(ebook_cfg.get("sample_hash_mod_max", 2)),
    )
    parser.add_argument("--report", type=Path, default=ebook_cfg.get("report_path"), help="JSONL report path")
    args = parser.parse_args()

    hash_mod_base = None if args.no_sample_hash else args.sample_hash_mod_base
    hash_mod_max = None if args.no_sample_hash else args.sample_hash_mod_max
    report_path = Path(args.report) if args.report else default_report_path(
        args.dt,
        "count-buckets" if args.full else args.sample_mode,
        args.full,
    )

    validate_db(
        config_path=args.config,
        source_table=args.source_table,
        target_table=args.target_table,
        dt=args.dt,
        limit=None if args.full else args.limit,
        sample_mode="count-buckets" if args.full else args.sample_mode,
        report_path=report_path,
        mapping_csv=args.mapping_csv,
        skip_dt_check=args.skip_dt_check,
        skip_source_distinct=args.skip_source_distinct,
        hash_mod_base=hash_mod_base,
        hash_mod_max=hash_mod_max,
    )


from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule
from dingo.model.rule.scibase.report_utils import bool_param, int_param, write_temp_settings


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    ["sci_base_qa_test", "meta_ebook_unique"],
)
class RuleSciBaseMetaEbookUniqueReport(BaseRule):
    _metric_info = {
        "category": "Rule-Based Metadata Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleSciBaseMetaEbookUniqueReport",
        "description": "Run SciBase ebook ISBN unique DB validation and write reports.",
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
        sample_mode = str(params.get("sample_mode") or "count-buckets")
        dt = params.get("dt")
        report_path = Path(params["report_path"]) if params.get("report_path") else None
        if report_path is None and params.get("output_dir"):
            report_path = Path(str(params["output_dir"])) / "source_field_mismatch.jsonl"
        if report_path is None:
            report_path = default_report_path(dt, "count-buckets" if full else sample_mode, full)

        config_path = write_temp_settings(params)
        result = validate_db(
            config_path=config_path,
            source_table=str(params.get("source_table") or DEFAULT_SOURCE_TABLE),
            target_table=str(params.get("target_table") or DEFAULT_TARGET_TABLE),
            dt=dt,
            limit=None if full else int_param(params, "limit", 600),
            sample_mode="count-buckets" if full else sample_mode,
            report_path=report_path,
            mapping_csv=Path(str(params.get("mapping_csv") or DEFAULT_MAPPING_CSV)),
            skip_dt_check=bool_param(params, "skip_dt_check", False),
            skip_source_distinct=bool_param(params, "skip_source_distinct", False),
            hash_mod_base=None if bool_param(params, "no_sample_hash", False) else int_param(params, "sample_hash_mod_base", 100),
            hash_mod_max=None if bool_param(params, "no_sample_hash", False) else int_param(params, "sample_hash_mod_max", 2),
        )
        bad = any(
            int(result.get(key) or 0) > 0
            for key in ("failed", "missing_source", "missing_target")
        )
        count_mismatches = ((result.get("dt_check") or {}).get("count_mismatches") or [])
        bad = bad or bool(count_mismatches)
        reason = [str(report_path.parent), f"checked={result.get('checked')}", f"failed={result.get('failed')}"]
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
