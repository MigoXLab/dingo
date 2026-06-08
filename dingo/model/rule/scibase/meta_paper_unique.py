#!/usr/bin/env python3
"""Self-contained meta_paper unique DB validator.

Field aggregation rules are driven by ../doc/paper_unique_mapping.csv.
"""
from __future__ import annotations

import csv
import argparse
import html
import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple, Union

SKIP_COMPARE_STRATEGIES = frozenset({"random_pick_cls"})
ORDER_INSENSITIVE_COMPARE_STRATEGIES = frozenset(
    {"dedup_array", "dedup_map", "dedup_struct", "dedup_locations"}
)
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
DEFAULT_MAPPING_CSV = ASSETS_DIR / "paper_unique_mapping.csv"
REPORT_ROOT = Path("report")
DEFAULT_SOURCE_TABLE = "dws_meta_paper_data_acc_d"
DEFAULT_TARGET_TABLE = "dws_meta_paper_doi_unique_acc_d"
DOI_KEY_SQL_PATTERN = r'(10\.[^[:space:]<>"&;]+|[^[:space:]<>"&;]+)'


def safe_filename_token(value: Optional[Any]) -> str:
    text = "all" if value in (None, "") else str(value)
    return re.sub(r"[^0-9A-Za-z_-]+", "_", text).strip("_") or "all"


def default_report_path(dt: Optional[str], sample_mode: str, full: bool) -> Path:
    mode = "full" if full else sample_mode
    report_dir = REPORT_ROOT / f"meta_paper_unique_dt_{safe_filename_token(dt)}_{safe_filename_token(mode)}"
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
    "report_path": "报告路径",
    "sample_mismatches": "问题样例",
    "mismatches": "字段差异",
    "source_count_mode": "源表计数模式",
    "source_failed_buckets": "源表计数失败分桶",
    "count_mismatches": "数量不一致明细",
    "count_check": "数量校验",
    "mismatch_count": "数量不一致数",
    "failed_bucket_count": "计数失败分桶数",
    "difference": "目标表多出记录数",
    "source_dt_count": "源表分区数",
    "target_dt_count": "目标表分区数",
    "missing_in_target": "目标表缺失分区",
    "extra_in_target": "目标表多余分区",
    "source_distinct_skipped": "源表去重计数已跳过",
    "matched_key_count": "源表目标表共同 DOI 数",
    "source_missing_in_target_key_count": "元数据有目标无",
    "target_extra_key_count": "目标有元数据无",
    "key_gap_failed": "key 覆盖统计失败",
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
        "origin_osi",
        "origin_id",
        "title",
        "published_year",
        "published_date",
        "venue_name",
    )
    return {
        key: record.get(key)
        for key in keys
        if record.get(key) not in (None, "", [], {})
    }


def compact_records_for_report(records: Any) -> Any:
    if not isinstance(records, list):
        return records
    compacted = []
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        compact = compact_record_for_report(record)
        marker = json.dumps(compact, ensure_ascii=False, sort_keys=True, cls=JsonEncoder)
        if marker in seen:
            continue
        seen.add(marker)
        compacted.append(compact)
    return compacted


def compact_dt_check(dt_check: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    dt_check = dt_check or {}
    mismatches = []
    for item in dt_check.get("count_mismatches") or []:
        source_count = item.get("source_key_count")
        target_count = item.get("target_row_count")
        difference = None
        if source_count is not None and target_count is not None:
            difference = int(target_count) - int(source_count)
        mismatches.append(
            {
                "dt": item.get("dt"),
                "source_key_count": source_count,
                "target_row_count": target_count,
                "difference": difference,
            }
        )
    failed_buckets = dt_check.get("source_failed_buckets") or []
    compact = {
        "source_count_mode": dt_check.get("source_count_mode"),
        "source_distinct_skipped": dt_check.get("source_distinct_skipped"),
        "failed_bucket_count": len(failed_buckets),
        "mismatch_count": len(mismatches),
        "count_mismatches": mismatches,
        "missing_in_target": dt_check.get("missing_in_target") or [],
        "extra_in_target": dt_check.get("extra_in_target") or [],
    }
    for key in (
        "matched_key_count",
        "source_missing_in_target_key_count",
        "target_extra_key_count",
        "key_gap_failed",
    ):
        if key in dt_check:
            compact[key] = dt_check.get(key)
    return compact


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
                    "dt": row.get("dt"),
                    "source_count": row.get("source_count"),
                    "status": row.get("status"),
                    "source_records": compact_records_for_report(row.get("source_records")),
                    "target_records": compact_records_for_report(row.get("target_records")),
                }
            )
        for field, diff in (row.get("mismatches") or {}).items():
            field_counts[field] += 1
            samples = field_samples.setdefault(field, [])
            if len(samples) < SAMPLES_PER_FIELD:
                samples.append(
                    {
                        "key": row.get("key"),
                        "dt": row.get("dt"),
                        "source_count": row.get("source_count"),
                        "status": row.get("status"),
                        "expected": diff.get("expected") if isinstance(diff, dict) else None,
                        "actual": diff.get("actual") if isinstance(diff, dict) else None,
                    }
                )
    sorted_field_counts = dict(field_counts.most_common())
    top_sample_fields = set(list(sorted_field_counts)[:TOP_SAMPLE_FIELD_LIMIT])
    compact_result = {k: v for k, v in result.items() if k not in ("sample_mismatches", "dt_check")}
    count_check = compact_dt_check(result.get("dt_check"))
    return {
        "report": str(report_path),
        "total_problem_rows": len(mismatch_rows),
        "result": compact_result,
        "count_check": count_check,
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
        "# Paper 去重校验报告摘要",
        "",
        f"- 分区: `{result.get('dt')}`",
        f"- 抽样: `{result.get('sample_mode')}`, 数量 `{result.get('sample_size')}`",
        f"- 结果: 已校验 `{result.get('checked')}`，通过 `{result.get('passed')}`，失败 `{result.get('failed')}`",
        f"- 缺失: 源表 `{result.get('missing_source')}`，目标表 `{result.get('missing_target')}`",
        f"- 明细报告: `{report_path}`",
        f"- 报告目录: `{report_path.parent}`",
        f"- 源表记录数分桶: `{_json_inline(result.get('source_count_buckets'))}`",
        "",
        "## 数量校验",
        "",
        f"- 源表计数模式: `{summary['count_check'].get('source_count_mode')}`",
        f"- 计数失败分桶数: `{summary['count_check'].get('failed_bucket_count')}`",
        f"- 数量不一致数: `{summary['count_check'].get('mismatch_count')}`",
    ]
    if "source_missing_in_target_key_count" in summary["count_check"]:
        lines.append(
            f"- 元数据有目标无: `{summary['count_check'].get('source_missing_in_target_key_count')}`"
        )
    if "target_extra_key_count" in summary["count_check"]:
        lines.append(
            f"- 目标有元数据无: `{summary['count_check'].get('target_extra_key_count')}`"
        )
    for item in summary["count_check"].get("count_mismatches") or []:
        lines.append(
            "- 分区 `{}`: source_key_count `{}`，target_row_count `{}`，difference `{}`".format(
                item.get("dt"),
                item.get("source_key_count"),
                item.get("target_row_count"),
                item.get("difference"),
            ),
        )
    lines.extend(["", "## 状态分布", ""])
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
                f"- DOI `{sample.get('key')}`, source_count={sample.get('source_count')}, "
                f"status=`{sample.get('status')}`"
            )
            source_records = sample.get("source_records")
            target_records = sample.get("target_records")
            if source_records is not None:
                lines.append(f"  - source_records: `{_json_inline(source_records)}`")
            if target_records is not None:
                lines.append(f"  - target_records: `{_json_inline(target_records)}`")
    lines.extend(["", "## 字段问题样例", ""])
    for field, samples in summary["field_samples"].items():
        lines.append(f"### {field} ({summary['field_counts'].get(field)})")
        lines.append("")
        for sample in samples:
            lines.append(
                f"- DOI `{sample.get('key')}`, source_count={sample.get('source_count')}, "
                f"status=`{sample.get('status')}`"
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
        return value not in ("", "{}")
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def choose_freq_then_lex_max(values: Iterable[str]) -> str:
    vals = [v for v in values if v not in ("", "{}")]
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


def choose_freq_then_max_decimal(values: Iterable[Decimal]) -> Optional[Decimal]:
    vals = [v for v in values if isinstance(v, Decimal)]
    if not vals:
        return None
    cnt = Counter(vals)
    max_freq = max(cnt.values())
    candidates = [k for k, v in cnt.items() if v == max_freq]
    return max(candidates)


def normalize_doi(doi: Any) -> str:
    if doi is None:
        return ""
    s = html.unescape(str(doi).strip().lower())
    if s in ("", "{}"):
        return ""
    start = s.find("10.")
    if start >= 0:
        s = s[start:]
    s = re.split(r"[\s<>\"&;]", s, maxsplit=1)[0].strip()
    if s in ("", "{}"):
        return ""
    return s


def parse_int(value: Any) -> Optional[int]:
    if value is None or (isinstance(value, str) and value in ("", "{}")):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except ValueError:
        return None


def parse_decimal(value: Any) -> Optional[Decimal]:
    if value is None or (isinstance(value, str) and value in ("", "{}")):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def decimal_to_json_number(value: Decimal) -> Union[int, float]:
    if value == value.to_integral_value():
        return int(value)
    return float(value)


def year_from_date_str(s: str) -> Optional[int]:
    if len(s) < 4:
        return None
    year_txt = s[:4]
    if not year_txt.isdigit():
        return None
    year = int(year_txt)
    if year < 1000 or year > CURRENT_YEAR:
        return None
    return year


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def dedup_str_array(values: Iterable[Any], lower: bool = False) -> List[str]:
    out = set()

    def add_value(raw: Any) -> None:
        if raw is None:
            return
        s = str(raw)
        if s in ("", "{}", "[]"):
            return
        out.add(s.lower() if lower else s)

    for item in values:
        if isinstance(item, list):
            for v in item:
                if isinstance(v, str):
                    try:
                        parsed = json.loads(v)
                    except json.JSONDecodeError:
                        parsed = None
                    if isinstance(parsed, list):
                        for elem in parsed:
                            add_value(elem)
                        continue
                add_value(v)
        elif item is not None:
            if isinstance(item, str):
                try:
                    parsed = json.loads(item)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    for elem in parsed:
                        add_value(elem)
                    continue
            add_value(item)
    return sorted(out)


# ---- paper-specific complex value helpers ----


def dedup_complex_to_string(values: Iterable[Any]) -> List[str]:
    out = set()
    for item in values:
        if isinstance(item, list):
            for v in item:
                if v is None or (isinstance(v, str) and v in ("", "{}")):
                    continue
                out.add(canonical_json(v) if not isinstance(v, str) else v)
        elif item is not None and not (isinstance(item, str) and item in ("", "{}")):
            out.add(canonical_json(item) if not isinstance(item, str) else item)
    return sorted(v for v in out if v not in ("", "{}"))


def dedup_locations_struct(values: Iterable[Any]) -> List[Dict[str, str]]:
    dedup_map: Dict[str, Dict[str, str]] = {}
    for item in values:
        candidates = item if isinstance(item, list) else [item]
        for candidate in candidates:
            if candidate is None or (isinstance(candidate, str) and candidate in ("", "{}")):
                continue

            obj: Optional[Dict[str, Any]] = None
            if isinstance(candidate, dict):
                obj = candidate
            elif isinstance(candidate, str):
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    obj = parsed

            if obj is None:
                continue

            normalized = {
                "type": "" if obj.get("type") is None or str(obj.get("type")) == "{}" else str(obj.get("type")),
                "url": "" if obj.get("url") is None or str(obj.get("url")) == "{}" else str(obj.get("url")),
                "license": ""
                if obj.get("license") is None or str(obj.get("license")) == "{}"
                else str(obj.get("license")),
                "is_oa": "" if obj.get("is_oa") is None or str(obj.get("is_oa")) == "{}" else str(obj.get("is_oa")),
            }
            dedup_map[canonical_json(normalized)] = normalized

    return [dedup_map[k] for k in sorted(dedup_map.keys())]


def dedup_map_array(values: Iterable[Any]) -> List[Dict[str, str]]:
    dedup_map: Dict[str, Dict[str, str]] = {}
    for item in values:
        candidates = item if isinstance(item, list) else [item]
        for candidate in candidates:
            if candidate is None or (isinstance(candidate, str) and candidate in ("", "{}")):
                continue

            objects: List[Dict[str, Any]] = []
            if isinstance(candidate, dict):
                objects = [candidate]
            elif isinstance(candidate, list):
                objects = [obj for obj in candidate if isinstance(obj, dict)]
            elif isinstance(candidate, str):
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    objects = [parsed]
                elif isinstance(parsed, list):
                    objects = [obj for obj in parsed if isinstance(obj, dict)]

            if not objects:
                continue

            for obj in objects:
                normalized = {
                    str(k): ""
                    if v is None or (isinstance(v, str) and v == "{}")
                    else stringify_map_value(v)
                    for k, v in obj.items()
                }
                dedup_map[canonical_json(normalized)] = normalized

    return [dedup_map[k] for k in sorted(dedup_map.keys())]


def choose_freq_then_lex_max_struct(values: Iterable[Any]) -> Dict[str, Any]:
    candidates: List[str] = []
    for value in values:
        obj: Optional[Dict[str, Any]] = None
        if isinstance(value, dict):
            obj = value
        elif isinstance(value, str):
            if value in ("", "{}"):
                continue
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and parsed:
                obj = parsed

        if isinstance(obj, dict) and obj:
            candidates.append(canonical_json(obj))

    if not candidates:
        return {}

    best = choose_freq_then_lex_max(candidates)
    try:
        parsed_best = json.loads(best)
    except json.JSONDecodeError:
        return {}
    return parsed_best if isinstance(parsed_best, dict) else {}


def _parse_struct_obj(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        if value in ("", "{}"):
            return None
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


def _normalize_topic_node(value: Any) -> Optional[Dict[str, Any]]:
    obj = _parse_struct_obj(value)
    if obj is None:
        return None
    normalized = {
        "id": canonicalize(obj.get("id")),
        "display_name": canonicalize(obj.get("display_name")),
    }
    if not any(is_non_empty(v) for v in normalized.values()):
        return None
    return normalized


def empty_primary_topic_struct() -> Dict[str, Any]:
    return {
        "id": None,
        "display_name": None,
        "score": None,
        "subfield": None,
        "field": None,
        "domain": None,
    }


def normalize_primary_topic_struct(value: Any) -> Dict[str, Any]:
    obj = _parse_struct_obj(value)
    if obj is None:
        return empty_primary_topic_struct()
    score = parse_decimal(obj.get("score"))
    return {
        "id": canonicalize(obj.get("id")),
        "display_name": canonicalize(obj.get("display_name")),
        "score": decimal_to_json_number(score) if score is not None else None,
        "subfield": _normalize_topic_node(obj.get("subfield")),
        "field": _normalize_topic_node(obj.get("field")),
        "domain": _normalize_topic_node(obj.get("domain")),
    }


def choose_freq_then_lex_max_primary_topic(values: Iterable[Any]) -> Dict[str, Any]:
    candidates: List[str] = []
    for value in values:
        obj = _parse_struct_obj(value)
        if not obj:
            continue
        normalized = normalize_primary_topic_struct(obj)
        if any(is_non_empty(v) for v in normalized.values()):
            candidates.append(canonical_json(normalized))

    if not candidates:
        return empty_primary_topic_struct()

    best = choose_freq_then_lex_max(candidates)
    parsed_best = json.loads(best)
    return parsed_best if isinstance(parsed_best, dict) else empty_primary_topic_struct()


def dedup_struct_array(values: Iterable[Any]) -> List[Dict[str, Any]]:
    def parse_to_dict_list(value: Any) -> List[Dict[str, Any]]:
        if value is None:
            return []

        def parse_str(raw: str) -> Any:
            if raw in ("", "{}", "[]"):
                return None
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return None

        def collect_from_list(items: List[Any]) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            for elem in items:
                if isinstance(elem, dict):
                    if elem:
                        out.append(elem)
                    continue
                if isinstance(elem, str):
                    parsed_elem = parse_str(elem)
                    if isinstance(parsed_elem, dict) and parsed_elem:
                        out.append(parsed_elem)
                    elif isinstance(parsed_elem, list):
                        out.extend(collect_from_list(parsed_elem))
            return out

        if isinstance(value, dict):
            return [value] if value else []
        if isinstance(value, list):
            return collect_from_list(value)
        if isinstance(value, str):
            parsed = parse_str(value)
            if isinstance(parsed, dict):
                return [parsed] if parsed else []
            if isinstance(parsed, list):
                return collect_from_list(parsed)
        return []

    merged_topics: List[Dict[str, Any]] = []
    for item in values:
        merged_topics.extend(parse_to_dict_list(item))

    dedup_map: Dict[str, Dict[str, Any]] = {}
    for topic in merged_topics:
        dedup_map[canonical_json(topic)] = topic

    return [dedup_map[k] for k in sorted(dedup_map.keys())]


def normalize_origin_osi(value: Any) -> str:
    if value is None:
        return ""
    origin = str(value).strip().lower()
    if origin in ("", "{}"):
        return ""
    if origin.startswith("semantic"):
        return "semantic"
    return origin


def stringify_map_value(value: Any) -> str:
    return stringify_map_value_with_style(value, compact=True)


def stringify_map_value_with_style(value: Any, compact: Optional[bool]) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        if compact is True:
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def detect_json_compact_style(raw: str) -> bool:
    in_string = False
    escaped = False
    length = len(raw)

    for idx, ch in enumerate(raw):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch in {":", ","}:
            if idx + 1 < length and raw[idx + 1].isspace():
                return False

    return True


def merge_string_map(values: Iterable[Any]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for item in values:
        if isinstance(item, str):
            try:
                parsed = json.loads(item)
            except json.JSONDecodeError:
                parsed = None
            item = parsed
        if not isinstance(item, dict):
            continue
        for k, v in item.items():
            if k is None or v is None:
                continue
            key = str(k)
            val = stringify_map_value(v)
            if key in ("", "{}"):
                continue
            if val == "{}":
                val = ""
            if key not in merged or val > merged[key]:
                merged[key] = val
    return merged


def merge_identifiers(values: Iterable[Any], origin_osi_values: Iterable[Any]) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for item, origin_osi in zip(values, origin_osi_values):
        if isinstance(item, str):
            try:
                parsed = json.loads(item)
            except json.JSONDecodeError:
                parsed = None
            item = parsed
        if not isinstance(item, dict):
            continue
        normalized_origin = normalize_origin_osi(origin_osi)
        for k, v in item.items():
            if k is None or v is None:
                continue
            key = str(k)
            if key in ("", "{}"):
                continue
            lowered_key = key.lower()
            if lowered_key in {"doi", "mag"} and normalized_origin:
                key = f"{normalized_origin}_{lowered_key}"
            sv = str(v)
            if sv == "{}":
                sv = ""
            if key not in merged or sv > merged[key]:
                merged[key] = sv
    return merged


# ---- strategy handlers ----


def _handle_key_lower(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> str:
    src = rule.effective_source
    vals = [normalize_doi(r.get(src, "")) for r in records if normalize_doi(r.get(src, ""))]
    return vals[0] if vals else ""


def _handle_freq_lex_max(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> str:
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
        if rule.field_name == "access_is_oa" and s.lower() == "unknown":
            continue
        vals.append(s)
    return choose_freq_then_lex_max(vals)


def _handle_freq_int_max(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> Optional[int]:
    src = rule.effective_source
    min_val = rule.params.get("min_val")
    max_val = rule.params.get("max_val")
    if isinstance(max_val, str) and max_val == "CURRENT_YEAR":
        max_val = CURRENT_YEAR
    vals: List[int] = []
    for r in records:
        v = parse_int(r.get(src))
        if v is None:
            continue
        if min_val is not None and v < min_val:
            continue
        if max_val is not None and v > max_val:
            continue
        vals.append(v)
    return choose_freq_then_max_int(vals)


def _handle_freq_decimal_max(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> Any:
    src = rule.effective_source
    vals = [d for r in records for d in [parse_decimal(r.get(src))] if d is not None]
    best = choose_freq_then_max_decimal(vals)
    return decimal_to_json_number(best) if best is not None else None


def _handle_freq_date(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> str:
    src = rule.effective_source
    vals: List[str] = []
    for r in records:
        d = r.get(src)
        if isinstance(d, str) and d and year_from_date_str(d) is not None:
            vals.append(d)
    return choose_freq_then_lex_max(vals)


def _handle_freq_struct(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> Dict[str, Any]:
    if rule.field_name == "primary_topic":
        return choose_freq_then_lex_max_primary_topic(
            [r.get(rule.effective_source) for r in records]
        )
    return choose_freq_then_lex_max_struct([r.get(rule.effective_source) for r in records])


def _handle_dedup_array(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> List[str]:
    return dedup_str_array(
        [r.get(rule.effective_source, []) for r in records],
        lower=rule.params.get("lower", False),
    )


def _handle_dedup_map(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> List[Dict[str, str]]:
    return dedup_map_array([r.get(rule.effective_source, []) for r in records])


def _handle_dedup_struct(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return dedup_struct_array([r.get(rule.effective_source, []) for r in records])


def _handle_dedup_locations(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> List[Dict[str, str]]:
    return dedup_locations_struct([r.get(rule.effective_source, []) for r in records])


def _handle_merge_map(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> Dict[str, str]:
    return merge_string_map([r.get(rule.effective_source) for r in records])


def _handle_merge_identifiers(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> Dict[str, str]:
    src = rule.effective_source
    return merge_identifiers(
        [r.get(src) for r in records],
        [r.get("origin_osi") for r in records],
    )


def _handle_latest_dt(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> str:
    src = rule.effective_source
    vals = [str(r.get(src, "")) for r in records if is_non_empty(r.get(src, ""))]
    return max(vals) if vals else ""


def _handle_random_pick_cls(
    records: List[Dict[str, Any]], rule: FieldRule, result: Dict[str, Any],
) -> None:
    return None


STRATEGY_HANDLERS: Dict[str, StrategyHandler] = {
    "key_lower": _handle_key_lower,
    "freq_lex_max": _handle_freq_lex_max,
    "freq_int_max": _handle_freq_int_max,
    "freq_decimal_max": _handle_freq_decimal_max,
    "freq_date": _handle_freq_date,
    "freq_struct": _handle_freq_struct,
    "dedup_array": _handle_dedup_array,
    "dedup_map": _handle_dedup_map,
    "dedup_struct": _handle_dedup_struct,
    "dedup_locations": _handle_dedup_locations,
    "merge_map": _handle_merge_map,
    "merge_identifiers": _handle_merge_identifiers,
    "latest_dt": _handle_latest_dt,
    "random_pick_cls": _handle_random_pick_cls,
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


def comparable_record(record: Dict[str, Any], fields: Iterable[str]) -> Dict[str, Any]:
    return {field: canonicalize(record.get(field)) for field in fields}


def _dt_clause(dt: Optional[str], params: List[Any]) -> str:
    if dt is not None:
        params.append(dt)
        return " AND `dt` = %s"
    return ""


def _limit_clause(limit: Optional[int]) -> str:
    return "" if limit is None else f" LIMIT {int(limit)}"


def _doi_not_null_clause() -> str:
    return " AND `doi` IS NOT NULL AND `doi` != ''"


def doi_key_expr(alias: Optional[str] = None) -> str:
    prefix = f"{alias}." if alias else ""
    return f"REGEXP_EXTRACT(LOWER(TRIM({prefix}`doi`)), '{DOI_KEY_SQL_PATTERN}', 1)"


def _doi_key_not_null_clause(alias: Optional[str] = None) -> str:
    expr = doi_key_expr(alias)
    return (
        f" AND {expr} IS NOT NULL"
        f" AND {expr} != ''"
        f" AND {expr} != '{{}}'"
    )


def _hash_sample_predicate(mod_base: Optional[int], mod_max: Optional[int]) -> str:
    """Narrow scan on Iceberg dt partitions by cleaned DOI key."""
    if not mod_base or not mod_max or mod_max <= 0:
        return ""
    return f" AND (ABS(CRC32({doi_key_expr()})) MOD {int(mod_base)}) < {int(mod_max)}"


def _sample_order_clause(*, high_first: bool = False) -> str:
    if high_first:
        return f"source_count DESC, CRC32({doi_key_expr()})"
    return f"CRC32({doi_key_expr()})"


def build_target_key_query(
    table: str,
    dt: Optional[str],
    limit: Optional[int],
    *,
    hash_mod_base: Optional[int] = None,
    hash_mod_max: Optional[int] = None,
) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    key_expr = doi_key_expr()
    sql = (
        f"SELECT {key_expr} AS sample_key FROM {quote_identifier(table)} "
        "WHERE 1=1"
        f"{_doi_key_not_null_clause()}"
        f"{_dt_clause(dt, params)}"
        f"{_hash_sample_predicate(hash_mod_base, hash_mod_max)}"
        f" ORDER BY {_sample_order_clause()}{_limit_clause(limit)}"
    )
    return sql, params


def build_target_first_key_query(
    table: str,
    dt: Optional[str],
    limit: Optional[int],
) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    key_expr = doi_key_expr()
    sql = (
        f"SELECT {key_expr} AS sample_key FROM {quote_identifier(table)} "
        "WHERE 1=1"
        f"{_doi_key_not_null_clause()}"
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
    key_expr = doi_key_expr()
    sql = (
        f"SELECT {key_expr} AS sample_key, COUNT(*) AS source_count FROM {quote_identifier(table)} "
        "WHERE 1=1"
        f"{_doi_key_not_null_clause()}"
        f"{_dt_clause(dt, params)}"
        f"{_hash_sample_predicate(hash_mod_base, hash_mod_max)}"
        f" GROUP BY {key_expr} HAVING COUNT(*) > 1 "
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
    conflict_checks = [
        "COUNT(DISTINCT `title`) > 1",
        "COUNT(DISTINCT `abstract`) > 1",
        "COUNT(DISTINCT `language`) > 1",
        "COUNT(DISTINCT `published_year`) > 1",
        "COUNT(DISTINCT `published_date`) > 1",
        "COUNT(DISTINCT `venue_name`) > 1",
        "COUNT(DISTINCT `venue_type`) > 1",
        "COUNT(DISTINCT `access_is_oa`) > 1",
        "COUNT(DISTINCT `access_oa_status`) > 1",
        "COUNT(DISTINCT `citation_count`) > 1",
        "COUNT(DISTINCT `reference_count`) > 1",
        "COUNT(DISTINCT `fwci`) > 1",
    ]
    key_expr = doi_key_expr()
    sql = (
        f"SELECT {key_expr} AS sample_key, COUNT(*) AS source_count FROM {quote_identifier(table)} "
        "WHERE 1=1"
        f"{_doi_key_not_null_clause()}"
        f"{_dt_clause(dt, params)}"
        f"{_hash_sample_predicate(hash_mod_base, hash_mod_max)}"
        f" GROUP BY {key_expr} HAVING COUNT(*) > 1 AND "
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
    if bucket == "one":
        having = "COUNT(*) = 1"
    elif bucket == "two":
        having = "COUNT(*) = 2"
    elif bucket == "multi":
        having = "COUNT(*) > 2"
    else:
        raise ValueError(f"Unsupported count bucket: {bucket}")
    key_expr = doi_key_expr()
    sql = (
        f"SELECT {key_expr} AS sample_key, COUNT(*) AS source_count FROM {quote_identifier(table)} "
        "WHERE 1=1"
        f"{_doi_key_not_null_clause()}"
        f"{_dt_clause(dt, params)}"
        f"{_hash_sample_predicate(hash_mod_base, hash_mod_max)}"
        f" GROUP BY {key_expr} HAVING {having} "
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
        sql, params = build_target_key_query(
            target_table,
            dt,
            sample_size,
            **hash_kw,
        )
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
            (
                "field-conflict",
                build_field_conflict_key_query(source_table, dt, per_bucket, **hash_kw),
            ),
            (
                "high-duplicate",
                build_duplicate_key_query(
                    source_table,
                    dt,
                    per_bucket,
                    high_first=True,
                    **hash_kw,
                ),
            ),
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
            if _append_sample_key(keys, seen, normalize_doi(row.get("sample_key")), sample_size=sample_size):
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


def build_target_record_query(table: str, doi: Any, dt: Optional[str]) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    if dt is not None:
        params.append(dt)
    params.append(normalize_doi(doi))
    dt_sql = " AND `dt` = %s" if dt is not None else ""
    sql = (
        f"SELECT * FROM {quote_identifier(table)} WHERE 1=1"
        f"{dt_sql} AND {doi_key_expr()} = %s LIMIT 1"
    )
    return sql, params


def build_source_query(table: str, doi: Any, dt: Optional[str]) -> Tuple[str, List[Any]]:
    params: List[Any] = []
    if dt is not None:
        params.append(dt)
    params.append(normalize_doi(doi))
    dt_sql = " AND `dt` = %s" if dt is not None else ""
    return (
        f"SELECT * FROM {quote_identifier(table)} WHERE 1=1{dt_sql} AND {doi_key_expr()} = %s",
        params,
    )


def build_source_batch_query(
    table: str,
    sample_keys: Sequence[str],
    dt: Optional[str],
) -> Tuple[str, List[Any]]:
    if not sample_keys:
        raise ValueError("sample_keys must not be empty")

    sample_key_sql = " UNION ALL ".join("SELECT %s AS sample_key" for _ in sample_keys)
    params: List[Any] = [normalize_doi(key) for key in sample_keys]
    if dt is not None:
        params.append(dt)
    dt_sql = " AND s.`dt` = %s" if dt is not None else ""

    sql = (
        f"WITH sample_keys AS ({sample_key_sql}) "
        f"SELECT s.* FROM {quote_identifier(table)} s "
        f"JOIN sample_keys k ON {doi_key_expr('s')} = k.sample_key "
        f"WHERE 1=1{dt_sql}"
    )
    return sql, params


def build_target_batch_query(
    table: str,
    sample_keys: Sequence[str],
    dt: Optional[str],
) -> Tuple[str, List[Any]]:
    if not sample_keys:
        raise ValueError("sample_keys must not be empty")

    sample_key_sql = " UNION ALL ".join("SELECT %s AS sample_key" for _ in sample_keys)
    params: List[Any] = [normalize_doi(key) for key in sample_keys]
    if dt is not None:
        params.append(dt)
    dt_sql = " AND t.`dt` = %s" if dt is not None else ""

    sql = (
        f"WITH sample_keys AS ({sample_key_sql}) "
        f"SELECT t.* FROM {quote_identifier(table)} t "
        f"JOIN sample_keys k ON {doi_key_expr('t')} = k.sample_key "
        f"WHERE 1=1{dt_sql}"
    )
    return sql, params


def group_rows_by_doi(rows: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        key = normalize_doi(row.get("doi"))
        if not key:
            continue
        grouped.setdefault(key, []).append(row)
    return grouped


def _parse_classifications(raw: Any) -> Optional[Dict[str, Any]]:
    if raw is None:
        return None
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
        return None
    if isinstance(raw, dict):
        return raw
    return None


def validate_classifications(
    source_records: List[Dict[str, Any]],
    target_row: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Validate classifications field with random-pick semantics.

    CSV rules:
    - classifications.mesh: randomly pick one non-empty classifications.mesh value; null if all empty
    - msc_class, acm_class, arxiv_category: pick from arxiv records only
    """
    actual_cls = _parse_classifications(normalize_json_like(target_row.get("classifications")))
    mismatches: Dict[str, Dict[str, Any]] = {}

    mesh_candidates: List[str] = []
    arxiv_sub_candidates: Dict[str, List[str]] = {
        "msc_class": [], "acm_class": [], "arxiv_category": [],
    }

    def candidate_expectation(candidates: Iterable[str]) -> Any:
        values: List[Any] = []
        for raw in sorted(set(candidates)):
            try:
                values.append(json.loads(raw))
            except json.JSONDecodeError:
                values.append(raw)
        if len(values) == 1:
            return values[0]
        return {"any_of": values}

    for r in source_records:
        c = _parse_classifications(r.get("classifications"))
        if c is not None and is_non_empty(c.get("mesh")):
            mesh_candidates.append(canonical_json(canonicalize(c["mesh"])))
        origin = normalize_origin_osi(r.get("origin_osi"))
        if origin == "arxiv":
            if c is None:
                continue
            for sub in arxiv_sub_candidates:
                if is_non_empty(c.get(sub)):
                    arxiv_sub_candidates[sub].append(canonical_json(canonicalize(c[sub])))

    if actual_cls is None:
        has_any_cls = any(_parse_classifications(r.get("classifications")) is not None for r in source_records)
        if has_any_cls:
            mismatches["classifications"] = {"expected": "non-null struct", "actual": None}
        return mismatches

    actual_mesh = actual_cls.get("mesh")
    if mesh_candidates:
        expected_mesh = candidate_expectation(mesh_candidates)
        if not is_non_empty(actual_mesh):
            mismatches["classifications.mesh"] = {
                "expected": expected_mesh,
                "actual": actual_mesh,
            }
        elif canonical_json(canonicalize(actual_mesh)) not in set(mesh_candidates):
            mismatches["classifications.mesh"] = {
                "expected": expected_mesh,
                "actual": actual_mesh,
            }
    else:
        if is_non_empty(actual_mesh):
            mismatches["classifications.mesh"] = {"expected": None, "actual": actual_mesh}

    for sub, candidates in arxiv_sub_candidates.items():
        actual_sub = actual_cls.get(sub)
        unique_candidates = set(candidates)
        if unique_candidates:
            expected_sub = candidate_expectation(unique_candidates)
            if not is_non_empty(actual_sub):
                mismatches[f"classifications.{sub}"] = {
                    "expected": expected_sub,
                    "actual": actual_sub,
                }
            elif canonical_json(canonicalize(actual_sub)) not in unique_candidates:
                mismatches[f"classifications.{sub}"] = {
                    "expected": expected_sub,
                    "actual": actual_sub,
                }
        else:
            if is_non_empty(actual_sub):
                mismatches[f"classifications.{sub}"] = {
                    "expected": "empty (no arxiv source)",
                    "actual": actual_sub,
                }

    return mismatches


def normalize_order_insensitive_value(value: Any) -> Any:
    value = canonicalize(value)
    if isinstance(value, list):
        return sorted(value, key=canonical_json)
    return value


def normalize_mesh_empty_values(value: Any) -> Any:
    value = canonicalize(value)
    if isinstance(value, dict):
        return {
            key: normalize_mesh_empty_values(None if val == "" else val)
            for key, val in value.items()
        }
    if isinstance(value, list):
        return [normalize_mesh_empty_values(item) for item in value]
    return None if value == "" else value


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
        if field == "mesh":
            expected_value = normalize_mesh_empty_values(expected_value)
            actual_value = normalize_mesh_empty_values(actual_value)
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
    count_mode: str = "hash-buckets",
    count_buckets: int = 100,
) -> Dict[str, Any]:
    """Check dt partition coverage and key counts between source and target."""
    params: List[Any] = []
    dt_filter = _dt_clause(dt, params)

    src_map: Dict[str, int] = {}
    bucket_counts: Dict[str, List[Dict[str, Any]]] = {}
    failed_buckets: List[Dict[str, Any]] = []
    matched_key_count: Optional[int] = None
    key_gap_failed = False
    if skip_source_distinct:
        count_mode = "skip"

    if count_mode == "exact":
        key_expr = doi_key_expr()
        src_sql = (
            f"SELECT `dt`, COUNT(DISTINCT {key_expr}) AS key_count"
            f" FROM {quote_identifier(source_table)}"
            f" WHERE 1=1{_doi_key_not_null_clause()}{dt_filter} GROUP BY `dt` ORDER BY `dt`"
        )
        src_rows = fetch_records(conn, src_sql, params)
        src_map = {str(r["dt"]): int(r["key_count"]) for r in src_rows}
    elif count_mode == "hash-buckets":
        if dt is None:
            raise ValueError("--count-mode hash-buckets requires --dt")
        if count_buckets <= 0:
            raise ValueError("--count-buckets must be positive")
        src_map[str(dt)] = 0
        matched_key_count = 0
        bucket_counts[str(dt)] = []
        source_key_expr = doi_key_expr()
        target_key_expr_t = doi_key_expr("t")
        for bucket in range(count_buckets):
            bucket_params: List[Any] = [dt, bucket]
            bucket_sql = (
                f"SELECT COUNT(DISTINCT {source_key_expr}) AS key_count"
                f" FROM {quote_identifier(source_table)}"
                " WHERE 1=1"
                f"{_doi_key_not_null_clause()}"
                " AND `dt` = %s"
                f" AND (ABS(CRC32({source_key_expr})) MOD {int(count_buckets)}) = %s"
            )
            _log(
                f"[info] source distinct hash bucket {bucket + 1}/{count_buckets} "
                f"开始执行（dt={dt!r}）…"
            )
            t0 = time.monotonic()
            try:
                rows = fetch_records(conn, bucket_sql, bucket_params)
                row = rows[0] if rows else None
                key_count = int(row.get("key_count") or 0) if row else 0
                src_map[str(dt)] += key_count
                bucket_counts[str(dt)].append({"bucket": bucket, "key_count": key_count})
                _log(
                    f"[info] source distinct hash bucket {bucket + 1}/{count_buckets} "
                    f"完成，耗时 {time.monotonic() - t0:.1f}s，key_count={key_count}"
                )
                join_sql = (
                    "SELECT COUNT(*) AS key_count"
                    " FROM ("
                    f" SELECT DISTINCT {source_key_expr} AS doi_key"
                    f" FROM {quote_identifier(source_table)}"
                    " WHERE 1=1"
                    f"{_doi_key_not_null_clause()}"
                    " AND `dt` = %s"
                    f" AND (ABS(CRC32({source_key_expr})) MOD {int(count_buckets)}) = %s"
                    " ) s"
                    f" JOIN {quote_identifier(target_table)} t"
                    f" ON t.`dt` = %s AND {target_key_expr_t} = s.doi_key"
                )
                join_t0 = time.monotonic()
                join_rows = fetch_records(conn, join_sql, [dt, bucket, dt])
                join_row = join_rows[0] if join_rows else None
                joined_count = int(join_row.get("key_count") or 0) if join_row else 0
                matched_key_count += joined_count
                _log(
                    f"[info] matched key hash bucket {bucket + 1}/{count_buckets} "
                    f"完成，耗时 {time.monotonic() - join_t0:.1f}s，key_count={joined_count}"
                )
            except Exception as exc:
                key_gap_failed = True
                failed_buckets.append({"dt": str(dt), "bucket": bucket, "error": str(exc)})
                _log(
                    f"[warn] source distinct hash bucket {bucket + 1}/{count_buckets} "
                    f"失败，耗时 {time.monotonic() - t0:.1f}s：{exc}"
                )
    elif count_mode == "skip":
        pass
    else:
        raise ValueError(f"Unsupported count_mode: {count_mode}")

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

    result = {
        "source_dt_count": len(src_map),
        "target_dt_count": len(tgt_map),
        "missing_in_target": sorted(set(src_map) - set(tgt_map)),
        "extra_in_target": sorted(set(tgt_map) - set(src_map)),
        "count_mismatches": mismatches,
        "source_distinct_skipped": count_mode == "skip",
        "source_count_mode": count_mode,
        "source_count_buckets": count_buckets if count_mode == "hash-buckets" else None,
        "source_bucket_counts": bucket_counts,
        "source_failed_buckets": failed_buckets,
    }
    if count_mode == "hash-buckets" and dt is not None and matched_key_count is not None:
        target_count = tgt_map.get(str(dt))
        source_count = src_map.get(str(dt))
        result["matched_key_count"] = matched_key_count
        result["key_gap_failed"] = key_gap_failed
        if not key_gap_failed and source_count is not None and target_count is not None:
            result["source_missing_in_target_key_count"] = max(source_count - matched_key_count, 0)
            result["target_extra_key_count"] = max(target_count - matched_key_count, 0)
    return result


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
    count_mode: str = "hash-buckets",
    count_buckets: int = 100,
    hash_mod_base: Optional[int] = 100,
    hash_mod_max: Optional[int] = 2,
) -> Dict[str, Any]:
    rules = load_field_rules(mapping_csv)
    output_fields = output_fields_from_rules(rules)
    order_insensitive_fields = order_insensitive_fields_from_rules(rules)
    field_types = {rule.field_name: rule.data_type for rule in rules}
    has_cls = any(r.strategy == "random_pick_cls" for r in rules)
    cfg = load_config(config_path)
    mysql_cfg = cfg.get("mysql", {}) if isinstance(cfg.get("mysql"), dict) else {}
    catalog = mysql_cfg.get("catalog")
    database = str(mysql_cfg.get("database") or "dws")
    source_table = qualify_table_name(source_table, catalog, database)
    target_table = qualify_table_name(target_table, catalog, database)
    hash_enabled = bool(hash_mod_base and hash_mod_max and hash_mod_max > 0)
    _log(
        f"[info] 论文去重校验开始：dt={dt!r}, limit={limit}, sample_mode={sample_mode}, "
        f"hash_sample={'on' if hash_enabled else 'off'}, "
        f"skip_dt_check={skip_dt_check}, count_mode={count_mode}, "
        f"source={source_table}, target={target_table}"
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
            _log("[info] 正在统计目标分区行数（源表 DISTINCT 可较慢，可用 --skip-source-distinct 跳过）…")
            t0 = time.monotonic()
            dt_check = validate_dt_partitions(
                conn,
                source_table,
                target_table,
                dt,
                skip_source_distinct=skip_source_distinct,
                count_mode=count_mode,
                count_buckets=count_buckets,
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
            _log(f"[info] 分区 {partition_dt}：抽到 {len(sample_keys)} 个 DOI，开始批量拉取源/目标记录…")
            t0 = time.monotonic()
            source_rows_by_key: Dict[str, List[Dict[str, Any]]] = {}
            target_rows_by_key: Dict[str, List[Dict[str, Any]]] = {}
            if sample_keys:
                source_sql, source_params = build_source_batch_query(source_table, sample_keys, partition_dt)
                source_rows_by_key = group_rows_by_doi(fetch_records(conn, source_sql, source_params))
                target_sql, target_params = build_target_batch_query(target_table, sample_keys, partition_dt)
                target_rows_by_key = group_rows_by_doi(fetch_records(conn, target_sql, target_params))
            _log(
                f"[info] 分区 {partition_dt}：批量拉取完成，耗时 {time.monotonic() - t0:.1f}s，"
                f"源命中 {len(source_rows_by_key)}/{len(sample_keys)}，"
                f"目标命中 {len(target_rows_by_key)}/{len(sample_keys)}"
            )
            _log(f"[info] 分区 {partition_dt}：开始逐条比对…")

            for doi in sample_keys:
                sample_key = normalize_doi(doi)
                target_rows = target_rows_by_key.get(sample_key, [])
                source_rows = source_rows_by_key.get(sample_key, [])
                checked += 1
                if checked == 1 or checked % 20 == 0:
                    _log(f"[info] 分区 {partition_dt}：已比对 {checked}/{len(sample_keys)} 条")

                if len(source_rows) == 1:
                    source_count_buckets["one"] += 1
                elif len(source_rows) == 2:
                    source_count_buckets["two"] += 1
                elif len(source_rows) > 2:
                    source_count_buckets["multi"] += 1

                if not target_rows:
                    missing_target += 1
                    mismatch_rows.append({
                        "key": doi,
                        "dt": partition_dt,
                        "status": "missing_target",
                        "source_count": len(source_rows),
                        "source_records": [
                            {key: normalize_json_like(value) for key, value in row.items()}
                            for row in source_rows
                        ],
                        "mismatches": {},
                    })
                    continue
                if not source_rows:
                    missing_source += 1
                    mismatch_rows.append({
                        "key": doi,
                        "dt": partition_dt,
                        "status": "missing_source",
                        "source_count": 0,
                        "target_records": [
                            {key: normalize_json_like(value) for key, value in row.items()}
                            for row in target_rows
                        ],
                        "mismatches": {},
                    })
                    continue

                target_row = target_rows[0]
                normalized_source = [{key: normalize_json_like(value) for key, value in row.items()} for row in source_rows]
                aggregated = aggregate_group(normalized_source, rules)
                expected = comparable_record(aggregated, output_fields)
                actual = comparable_record(target_row, output_fields)
                mismatches = compare_records(expected, actual, order_insensitive_fields, field_types)
                if has_cls:
                    cls_mismatches = validate_classifications(normalized_source, target_row)
                    mismatches.update(cls_mismatches)
                if mismatches:
                    failed += 1
                    mismatch_rows.append(
                        {
                            "key": doi,
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
        "kind": "paper",
        "source_table": source_table,
        "target_table": target_table,
        "key_field": "doi",
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
    paper_cfg = cfg.get("unique_paper", {})

    default_csv = paper_cfg.get("mapping_csv")
    if default_csv:
        default_csv = PROJECT_ROOT / default_csv
    else:
        default_csv = DEFAULT_MAPPING_CSV

    parser = argparse.ArgumentParser(description="Validate meta_paper unique DB table by DOI.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH, help="shared settings JSON path")
    parser.add_argument("--mapping-csv", type=Path, default=default_csv, help="field mapping CSV")
    parser.add_argument("--source-table", default=paper_cfg.get("source_table", DEFAULT_SOURCE_TABLE))
    parser.add_argument("--target-table", default=paper_cfg.get("target_table", DEFAULT_TARGET_TABLE))
    parser.add_argument("--dt", default=paper_cfg.get("dt"), help="dt partition filter")
    parser.add_argument("--limit", type=int, default=int(paper_cfg.get("limit", 600)))
    parser.add_argument(
        "--sample-mode",
        choices=("count-buckets", "mixed", "target-random", "target-first"),
        default=paper_cfg.get("sample_mode", "count-buckets"),
        help="count-buckets: 1/2/N 源行分桶；mixed: 加深抽样；target-random: 目标表稳定排序抽样；target-first: 目标表 LIMIT 抽样（smoke 最快）",
    )
    parser.add_argument("--full", action="store_true", help="validate all target rows")
    parser.add_argument("--skip-dt-check", action="store_true", default=bool(paper_cfg.get("skip_dt_check")))
    parser.add_argument(
        "--skip-source-distinct",
        action="store_true",
        default=bool(paper_cfg.get("skip_source_distinct")),
        help="dt 统计时跳过源表 COUNT(DISTINCT doi)，等价于 --count-mode skip",
    )
    parser.add_argument(
        "--count-mode",
        choices=("exact", "skip", "hash-buckets"),
        default=paper_cfg.get("count_mode", "hash-buckets"),
        help="源表 distinct DOI 计数模式：exact 单条 COUNT(DISTINCT)，hash-buckets 分桶精确统计，skip 跳过",
    )
    parser.add_argument(
        "--count-buckets",
        type=int,
        default=int(paper_cfg.get("count_buckets", 100)),
        help="--count-mode hash-buckets 时的 hash 分桶数",
    )
    parser.add_argument(
        "--no-sample-hash",
        action="store_true",
        help="关闭 CRC32 哈希预过滤（默认 mod 100 取 2，约 2%% 子集）",
    )
    parser.add_argument(
        "--sample-hash-mod-base",
        type=int,
        default=int(paper_cfg.get("sample_hash_mod_base", 100)),
    )
    parser.add_argument(
        "--sample-hash-mod-max",
        type=int,
        default=int(paper_cfg.get("sample_hash_mod_max", 2)),
    )
    parser.add_argument("--report", type=Path, default=paper_cfg.get("report_path"), help="JSONL report path")
    args = parser.parse_args()

    hash_mod_base = None if args.no_sample_hash else args.sample_hash_mod_base
    hash_mod_max = None if args.no_sample_hash else args.sample_hash_mod_max
    count_mode = "skip" if args.skip_source_distinct else args.count_mode
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
        count_mode=count_mode,
        count_buckets=args.count_buckets,
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
    ["sci_base_qa_test", "meta_paper_unique"],
)
class RuleSciBaseMetaPaperUniqueReport(BaseRule):
    _metric_info = {
        "category": "Rule-Based Metadata Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleSciBaseMetaPaperUniqueReport",
        "description": "Run SciBase paper DOI unique DB validation and write reports.",
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
        count_mode = "skip" if bool_param(params, "skip_source_distinct", False) else str(params.get("count_mode") or "hash-buckets")
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
            count_mode=count_mode,
            count_buckets=int_param(params, "count_buckets", 100),
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
