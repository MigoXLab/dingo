#!/usr/bin/env python3
"""Single-file verifier for S3 arxiv data loaded into the paper source table.

Generated from /Users/guhuaiyu/PycharmProjects/osi_test without modifying that source project.
This file validates S3 arxiv metadata against the paper source table.
Runtime dependencies: pymysql, duckdb, pyarrow, boto3.
"""
from __future__ import annotations


# ---- osi_verify/common.py ----


import json
from datetime import datetime
from typing import Any, Dict


def sql_literal(value: str) -> str:
    return value.replace("'", "''")


def json_loads_maybe(v: Any) -> Any:
    if v is None or isinstance(v, (dict, list)):
        return v
    if isinstance(v, (bytes, bytearray)):
        v = v.decode("utf-8", errors="replace")
    if isinstance(v, str):
        s = v.strip()
        if s and s[0] in "{[":
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass
    return v


def normalize_scalar(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    s = str(v).strip()
    return s if s else None


def get_first(row: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]
    return None


def as_bool_flag(v: Any) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return int(v) == 1
    return str(v).strip() in ("1", "true", "True", "yes", "Y")


def oa_flag_str(flag: bool) -> str:
    return "true" if flag else "false"


# ---- osi_verify/retry.py ----


import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional, TypeVar

T = TypeVar("T")

try:
    import pymysql
except ImportError:
    pymysql = None  # type: ignore

try:
    import duckdb
except ImportError:
    duckdb = None  # type: ignore

try:
    from botocore.exceptions import BotoCoreError, ClientError, ConnectionError as BotoConnectionError
except ImportError:
    BotoCoreError = ClientError = BotoConnectionError = ()  # type: ignore


@dataclass(frozen=True)
class RetryConfig:
    enabled: bool = True
    max_attempts: int = 3
    initial_delay_sec: float = 1.0
    backoff_factor: float = 2.0
    max_delay_sec: float = 30.0

    def __post_init__(self) -> None:
        max_attempts = max(1, int(self.max_attempts))
        initial_delay = max(0.0, float(self.initial_delay_sec))
        backoff = max(1.0, float(self.backoff_factor))
        max_delay = max(initial_delay, max(0.0, float(self.max_delay_sec)))
        object.__setattr__(self, "max_attempts", max_attempts)
        object.__setattr__(self, "initial_delay_sec", initial_delay)
        object.__setattr__(self, "backoff_factor", backoff)
        object.__setattr__(self, "max_delay_sec", max_delay)

    @classmethod
    def disabled(cls) -> "RetryConfig":
        return cls(enabled=False, max_attempts=1)

    def attempts(self) -> int:
        return max(1, self.max_attempts) if self.enabled else 1


def _positive_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, parsed)


def _non_negative_float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, parsed)


def _min_float(value: Any, default: float, minimum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, parsed)


def load_retry_config(settings: Dict[str, Any]) -> RetryConfig:
    raw = settings.get("retry")
    if not isinstance(raw, dict):
        return RetryConfig()
    return RetryConfig(
        enabled=bool(raw.get("enabled", True)),
        max_attempts=_positive_int(raw.get("max_attempts", 3), 3),
        initial_delay_sec=_non_negative_float(raw.get("initial_delay_sec", 1.0), 1.0),
        backoff_factor=_min_float(raw.get("backoff_factor", 2.0), 2.0, 1.0),
        max_delay_sec=_non_negative_float(raw.get("max_delay_sec", 30.0), 30.0),
    )


def _exc_message(exc: BaseException) -> str:
    return str(exc).lower()


def is_mysql_retryable(exc: BaseException) -> bool:
    if pymysql is None:
        return False
    if isinstance(exc, pymysql.err.OperationalError):
        code = exc.args[0] if exc.args else None
        if code in (2003, 2006, 2013):
            return True
    if isinstance(exc, pymysql.err.ProgrammingError):
        msg = _exc_message(exc)
        return any(
            token in msg
            for token in (
                "timeout",
                "timed out",
                "connection",
                "lost connection",
                "brpc",
                "host is down",
                "not connected",
                "could not determine master",
                "master from helpers",
                "no alive backend",
                "frontend",
            )
        )
    if isinstance(exc, (TimeoutError, ConnectionError, OSError)):
        return True
    return False


def is_s3_retryable(exc: BaseException) -> bool:
    if duckdb is not None and isinstance(exc, duckdb.IOException):
        msg = _exc_message(exc)
        return any(
            token in msg
            for token in (
                "connection",
                "failed to read",
                "timeout",
                "network",
                "io error",
            )
        )
    if isinstance(exc, (BotoConnectionError, TimeoutError, ConnectionError, OSError)):
        return True
    if isinstance(exc, ClientError):
        code = str(exc.response.get("Error", {}).get("Code", ""))
        status = int(exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode", 0) or 0)
        if status in (408, 429, 500, 502, 503, 504):
            return True
        return code in {
            "RequestTimeout",
            "RequestTimeoutException",
            "Throttling",
            "ThrottlingException",
            "SlowDown",
            "InternalError",
            "ServiceUnavailable",
        }
    if isinstance(exc, BotoCoreError):
        return True
    return False


def retry_call(
    fn: Callable[[], T],
    config: Optional[RetryConfig],
    *,
    label: str,
    retryable: Callable[[BaseException], bool],
) -> T:
    cfg = config or RetryConfig()
    attempts = cfg.attempts()
    delay = cfg.initial_delay_sec
    last_exc: Optional[BaseException] = None

    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts or not cfg.enabled or not retryable(exc):
                raise
            print(
                f"[retry] {label} 失败 ({type(exc).__name__}: {exc})，"
                f"{delay:.1f}s 后重试 ({attempt}/{attempts})",
                file=sys.stderr,
            )
            time.sleep(delay)
            delay = min(delay * cfg.backoff_factor, cfg.max_delay_sec)

    assert last_exc is not None
    raise last_exc


# ---- osi_verify/config.py ----


import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union

PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS_DIR = PROJECT_ROOT / "assets"
REPORT_ROOT = Path("report")
DEFAULT_ICEBERG_CATALOG = "lakehouse_iceberg"
DEFAULT_SETTINGS_JSON = Path("sci_base_qa_test_config.json")
DT_RE = re.compile(r"dt=([^/]+)")


@dataclass(frozen=True)
class TargetConfig:
    name: str
    kind: str
    description: str
    mapping_csv: Path
    database: str
    table: str
    catalog: Optional[str]
    origin_osi: str
    source_id_field: str
    transform: str
    mapping_target_column: str
    mapping_source_column: str
    s3_settings: Dict[str, Any]
    s3_subpath: Optional[str]
    s3_path: Optional[str]
    s3_format: Optional[str]


def resolve_project_path(value: Optional[Union[str, Path]]) -> Optional[Path]:
    if value is None:
        return None
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def load_settings(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_arxiv_target_config(settings: Dict[str, Any]) -> TargetConfig:
    arxiv_settings = settings.get("osi_arxiv", {}) if isinstance(settings.get("osi_arxiv"), dict) else {}
    table_settings = settings.get("table", {}) if isinstance(settings.get("table"), dict) else {}
    mapping_settings = settings.get("mapping", {}) if isinstance(settings.get("mapping"), dict) else {}
    s3_settings = arxiv_settings.get("s3", {}) if isinstance(arxiv_settings.get("s3"), dict) else {}
    for key in ("config_file", "path", "subpath", "format"):
        if key in arxiv_settings and arxiv_settings[key] not in (None, ""):
            s3_settings[key] = arxiv_settings[key]
    mapping_csv = resolve_project_path(
        arxiv_settings.get("mapping_csv")
        or table_settings.get("mapping_csv")
        or mapping_settings.get("csv")
        or str(ASSETS_DIR / "osi_arxiv_mapping.csv")
    )
    if mapping_csv is None:
        mapping_csv = ASSETS_DIR / "osi_arxiv_mapping.csv"
    return TargetConfig(
        name="osi_axiv",
        kind="osi_axiv",
        description="S3 arxiv 数据到论文源数据表校验",
        mapping_csv=mapping_csv,
        database=str(arxiv_settings.get("database") or table_settings.get("database") or "dws"),
        table=str(arxiv_settings.get("target_table") or arxiv_settings.get("table") or table_settings.get("table") or "dws_meta_paper_data_acc_d"),
        catalog=str(arxiv_settings.get("catalog") or table_settings.get("catalog") or DEFAULT_ICEBERG_CATALOG),
        origin_osi="arxiv",
        source_id_field="doc_id",
        transform="osi_arxiv",
        mapping_target_column=str(arxiv_settings.get("mapping_target_column") or mapping_settings.get("target_column") or "预期字段"),
        mapping_source_column=str(arxiv_settings.get("mapping_source_column") or mapping_settings.get("source_column") or "arxiv对应字段"),
        s3_settings=dict(s3_settings),
        s3_subpath=s3_settings.get("subpath"),
        s3_path=s3_settings.get("path"),
        s3_format=s3_settings.get("format"),
    )



def _merge_present(base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in overrides.items():
        if v is not None and v != "":
            out[k] = v
    return out


def _strip_endpoint_scheme(value: str) -> str:
    return value.removeprefix("https://").removeprefix("http://").rstrip("/")


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def parse_mysql_config(path: Path) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "：" not in line:
            continue
        key, val = line.split("：", 1)
        key, val = key.strip(), val.strip()
        if key in ("账号", "用户名", "user"):
            cfg["user"] = val
        elif key in ("密码", "password"):
            cfg["password"] = val
        elif key in ("地址", "host"):
            if ":" in val:
                host, port = val.rsplit(":", 1)
                cfg["host"] = host
                cfg["port"] = int(port)
            else:
                cfg["host"] = val
        elif key in ("catalog", "iceberg_catalog", "catalog名"):
            cfg["catalog"] = val
    if "port" not in cfg:
        cfg["port"] = 3306
    missing = [k for k in ("user", "password", "host") if k not in cfg]
    if missing:
        raise ValueError(f"MySQL 配置缺少字段: {missing}（文件: {path}）")
    return cfg


def load_mysql_config(path: Optional[Path], inline: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    if path and path.exists():
        cfg.update(parse_mysql_config(path))
    if inline:
        cfg = _merge_present(cfg, inline)
    host = cfg.get("host")
    if isinstance(host, str) and ":" in host:
        raise ValueError("MySQL host 请只配置主机名/IP，端口请通过 port 单独配置")
    if "port" not in cfg:
        cfg["port"] = 3306
    else:
        cfg["port"] = int(cfg["port"])
    missing = [k for k in ("user", "password", "host") if k not in cfg]
    if missing:
        source = path or "inline settings"
        raise ValueError(f"MySQL 配置缺少字段: {missing}（来源: {source}）")
    return cfg


def parse_s3_config(path: Path) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("s3://"):
            cfg["default_path"] = line if line.endswith("/") else line + "/"
            continue
        sep = "：" if "：" in line else (":" if ":" in line else None)
        if not sep:
            continue
        key, val = line.split(sep, 1)
        key, val = key.strip().upper(), val.strip()
        if key in ("AK", "ACCESS_KEY", "AWS_ACCESS_KEY_ID"):
            cfg["access_key"] = val
        elif key in ("SK", "SECRET_KEY", "AWS_SECRET_ACCESS_KEY"):
            cfg["secret_key"] = val
        elif key in ("ENDPOINT", "S3_ENDPOINT"):
            cfg["endpoint"] = _strip_endpoint_scheme(val)
        elif key in ("USE_SSL", "S3_USE_SSL"):
            cfg["use_ssl"] = _parse_bool(val)
        elif key in ("VERIFY_SSL", "S3_VERIFY_SSL"):
            cfg["verify_ssl"] = _parse_bool(val)
    missing = [k for k in ("access_key", "secret_key", "endpoint") if k not in cfg]
    if missing:
        raise ValueError(f"S3 配置缺少字段: {missing}（文件: {path}）")
    if "default_path" not in cfg:
        cfg["default_path"] = "s3://lakehouse-scibase/"
    return cfg


def load_s3_config(path: Optional[Path], inline: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    if path and path.exists():
        cfg.update(parse_s3_config(path))
    if inline:
        aliases = {
            "ak": "access_key",
            "sk": "secret_key",
            "bucket_path": "default_path",
            "path": "default_path",
        }
        normalized = {aliases.get(k, k): v for k, v in inline.items()}
        if "endpoint" in normalized and normalized["endpoint"]:
            normalized["endpoint"] = _strip_endpoint_scheme(str(normalized["endpoint"]))
        if "use_ssl" in normalized:
            normalized["use_ssl"] = _parse_bool(normalized["use_ssl"])
        if "verify_ssl" in normalized:
            normalized["verify_ssl"] = _parse_bool(normalized["verify_ssl"])
        cfg = _merge_present(cfg, normalized)
    missing = [k for k in ("access_key", "secret_key", "endpoint") if k not in cfg]
    if missing:
        source = path or "inline settings"
        raise ValueError(f"S3 配置缺少字段: {missing}（来源: {source}）")
    if "default_path" not in cfg:
        cfg["default_path"] = "s3://lakehouse-scibase/"
    return cfg


def resolve_s3_path(base: str, subpath: Optional[str]) -> str:
    base = base.rstrip("/")
    if not subpath:
        return base + "/"
    return base + "/" + subpath.strip("/") + "/"


def apply_s3_dt_to_path(s3_path: str, s3_dt: Optional[str]) -> str:
    if not s3_dt:
        return s3_path
    if "YYYY-MM-DD" in s3_path:
        return s3_path.replace("YYYY-MM-DD", s3_dt)
    if DT_RE.search(s3_path):
        return DT_RE.sub(f"dt={s3_dt}", s3_path, count=1)
    return s3_path


def extract_partition_dt(s3_subpath: Optional[str], override: Optional[str] = None) -> Optional[str]:
    if override:
        return override
    if not s3_subpath:
        return None
    m = DT_RE.search(s3_subpath)
    return m.group(1) if m else None


# ---- osi_verify/mapping.py ----


import csv
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence


CONTAINER_COMPARE_FIELDS = {"locations", "classifications"}
CONTAINER_CHILD_PREFIXES = tuple(f"{field}." for field in CONTAINER_COMPARE_FIELDS)
NON_COMPARE_MARKERS = ("后续处理",)
DEFAULT_EMPTY_SOURCE_MARKERS = {"无", "/"}


@dataclass(frozen=True)
class MappingRule:
    target_field: str
    source_note: str
    compare_field: str
    value_type: str = ""
    compare: bool = True


def canonical_field(field: str) -> str:
    return field.strip()


def should_compare(field: str, source_note: str) -> bool:
    if not field:
        return False
    if field.startswith(CONTAINER_CHILD_PREFIXES):
        return False
    if any(marker in source_note for marker in NON_COMPARE_MARKERS):
        return False
    if not source_note and field not in CONTAINER_COMPARE_FIELDS:
        return False
    return True


def load_mapping_rules(
    path: Path,
    *,
    target_column: str = "预期字段",
    source_column: str = "arxiv对应字段",
    type_column: str = "字段值数据类型",
) -> List[MappingRule]:
    rules: List[MappingRule] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or target_column not in reader.fieldnames:
            available = ", ".join(reader.fieldnames or [])
            raise ValueError(
                f"映射文件 {path} 缺少目标字段列 {target_column!r}"
                f"（可用列: {available}）"
            )
        for row in reader:
            target = (row.get(target_column) or "").strip()
            note = (row.get(source_column) or "").strip()
            value_type = (row.get(type_column) or "").strip()
            if not target:
                continue
            compare_field = canonical_field(target)
            rules.append(
                MappingRule(
                    target_field=target,
                    source_note=note,
                    compare_field=compare_field,
                    value_type=value_type,
                    compare=should_compare(target, note),
                )
            )
    return rules


def compare_fields_from_rules(rules: Sequence[MappingRule]) -> List[str]:
    fields: List[str] = []
    seen = set()
    for rule in rules:
        if not rule.compare:
            continue
        if rule.compare_field in seen:
            continue
        seen.add(rule.compare_field)
        fields.append(rule.compare_field)
    return fields


def default_empty_field_types_from_rules(rules: Sequence[MappingRule]) -> dict[str, str]:
    """映射来源为“无”的字段：按声明类型做默认空值校验。"""
    fields: dict[str, str] = {}
    for rule in rules:
        if not rule.compare or rule.source_note not in DEFAULT_EMPTY_SOURCE_MARKERS:
            continue
        if rule.compare_field in fields:
            continue
        fields[rule.compare_field] = rule.value_type
    return fields


# ---- osi_verify/transform.py ----


import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


ARXIV_ABS_RE = re.compile(
    r"^(?:https?://)?(?:arxiv\.org/abs/|export\.arxiv\.org/abs/)?",
    re.I,
)
ARXIV_DOI_PREFIX = "10.48550/arxiv."

# 校验字段名 -> 湖仓表实际列名（当二者不一致时）
DB_COLUMN_ALIASES: Dict[str, str] = {
    "s2FieldsOfStudy": "s2fieldsofstudy",
}


def strip_arxiv_id(paper_id: Optional[str]) -> Optional[str]:
    if not paper_id:
        return None
    s = ARXIV_ABS_RE.sub("", str(paper_id).strip())
    return s.strip("/") or None


def parse_datetime_value(updated: Any) -> Optional[datetime]:
    if updated is None:
        return None
    if isinstance(updated, datetime):
        return updated
    if hasattr(updated, "year") and hasattr(updated, "month") and hasattr(updated, "day"):
        return datetime(updated.year, updated.month, updated.day)
    s = str(updated).strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%a, %d %b %Y %H:%M:%S %Z",
    ):
        try:
            sample = s[:30] if "GMT" in s else s[:19]
            return datetime.strptime(sample, fmt)
        except ValueError:
            continue
    m = re.match(r"(\d{4})", s)
    return datetime(int(m.group(1)), 1, 1) if m else None


def parse_date_iso(updated: Any) -> Optional[str]:
    """将 GMT/各类日期字符串规范为 YYYY-MM-DD（与落库一致）。"""
    dt = parse_datetime_value(updated)
    return dt.strftime("%Y-%m-%d") if dt else None


def parse_year(updated: Any) -> Optional[int]:
    dt = parse_datetime_value(updated)
    return dt.year if dt else None


def _normalize_author_name(name: str) -> str:
    """去掉作者名前的 and（与落库一致，如 ', and Foo' 按逗号拆分后残留）。"""
    s = name.strip()
    if s.lower().startswith("and "):
        s = s[4:].strip()
    return s


def parse_authors(author: Any) -> List[str]:
    if author is None:
        return []
    if isinstance(author, list):
        return [
            n
            for a in author
            if (n := _normalize_author_name(str(a)))
        ]
    s = str(author).strip()
    if not s:
        return []
    return [
        n
        for p in re.split(r"[,;]\s*|\s+and\s+", s, flags=re.I)
        if p.strip() and (n := _normalize_author_name(p))
    ]


# 产品 license_url 可选值（2025.09.01）
LICENSE_ALLOWED: frozenset = frozenset(
    {
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
        "nonexclusive-distrib",
    }
)

# S3 license_url / 历史别名 -> 标准可选值
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
    "http://creativecommons.org/licenses/by-nc/4.0/": "cc-by-nc",
    "https://creativecommons.org/licenses/by-nc/4.0/": "cc-by-nc",
    "http://creativecommons.org/licenses/by-sa/4.0/": "cc-by-sa",
    "https://creativecommons.org/licenses/by-sa/4.0/": "cc-by-sa",
    "http://creativecommons.org/licenses/by-nd/4.0/": "cc-by-nd",
    "https://creativecommons.org/licenses/by-nd/4.0/": "cc-by-nd",
    "http://creativecommons.org/licenses/by-nc-sa/4.0/": "cc-by-nc-sa",
    "https://creativecommons.org/licenses/by-nc-sa/4.0/": "cc-by-nc-sa",
    "http://creativecommons.org/licenses/by-nc-nd/4.0/": "cc-by-nc-nd",
    "https://creativecommons.org/licenses/by-nc-nd/4.0/": "cc-by-nc-nd",
    "http://creativecommons.org/publicdomain/zero/1.0/": "cc0",
    "https://creativecommons.org/publicdomain/zero/1.0/": "cc0",
    "CC0-1.0": "cc0",
}

_CC_LICENSE_URL_RULES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"creativecommons\.org/licenses/by-nc-sa", re.I), "cc-by-nc-sa"),
    (re.compile(r"creativecommons\.org/licenses/by-nc-nd", re.I), "cc-by-nc-nd"),
    (re.compile(r"creativecommons\.org/licenses/by-nc(?:/|$)", re.I), "cc-by-nc"),
    (re.compile(r"creativecommons\.org/licenses/by-sa", re.I), "cc-by-sa"),
    (re.compile(r"creativecommons\.org/licenses/by-nd", re.I), "cc-by-nd"),
    (re.compile(r"creativecommons\.org/licenses/by(?:/|$)", re.I), "cc-by"),
    (re.compile(r"creativecommons\.org/publicdomain/zero", re.I), "cc0"),
    (re.compile(r"arxiv\.org/licenses/nonexclusive-distrib", re.I), "nonexclusive-distrib"),
]


def normalize_license_value(v: Any, license_map: Dict[str, str]) -> str:
    """将 S3 URL / 别名 / DB 值规范为 license_url 可选值。"""
    if v is None:
        return ""
    s = str(v).strip()
    if not s:
        return ""
    if s in license_map:
        return license_map[s]
    trimmed = s.rstrip("/")
    if trimmed in license_map:
        return license_map[trimmed]
    low = s.lower()
    if low in LICENSE_ALLOWED:
        return low
    for pat, canon in _CC_LICENSE_URL_RULES:
        if pat.search(s):
            return canon
    return low


def license_out_of_allowed_warning(value: str, *, source: str = "S3") -> Optional[str]:
    if value and value not in LICENSE_ALLOWED:
        allowed = ", ".join(sorted(LICENSE_ALLOWED - {""}))
        return (
            f"[WARN] license_url {source} 值 '{value}' 不在产品可选值内"
            f"（{allowed}），属上游数据，不判定为开发缺陷"
        )
    return None


def map_license_url(url: Any, license_map: Dict[str, str]) -> str:
    return normalize_license_value(url, license_map)





def build_doi(row: Dict[str, Any]) -> Optional[str]:
    """与落库一致：S3 有 doi 直接用；否则 10.48550/arxiv.{doc_id}。"""
    doi = get_first(row, "doi")
    if doi is not None and str(doi).strip():
        return str(doi).strip()
    doc_id = get_first(row, "doc_id")
    if doc_id is not None and str(doc_id).strip():
        return f"{ARXIV_DOI_PREFIX}{str(doc_id).strip()}"
    return None


def normalize_doi(v: Any) -> Optional[str]:
    """DOI 比对忽略大小写。"""
    v = normalize_scalar(v)
    if v is None:
        return None
    return str(v).strip().lower()


def normalize_indexed_in(v: Any) -> List[str]:
    """与落库一致：List[string]。"""
    v = json_loads_maybe(v)
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    s = str(v).strip()
    return [s] if s else []


def build_identifiers(row: Dict[str, Any]) -> Dict[str, str]:
    """
    与落库一致：map，oaiId <- oai_identifier，arxivId <- paper_id（去掉 https:// 等前缀）。
    """
    out: Dict[str, str] = {}
    oai = get_first(row, "oai_identifier")
    if oai:
        out["oaiId"] = str(oai).strip()
    aid = strip_arxiv_id(get_first(row, "paper_id"))
    if aid:
        out["arxivId"] = aid
    return out


def normalize_identifiers(v: Any) -> Dict[str, str]:
    """比对用：统一为 {oaiId, arxivId} map。"""
    v = json_loads_maybe(v)
    if v is None:
        return {}
    if isinstance(v, dict):
        out: Dict[str, str] = {}
        oai = v.get("oaiId") or v.get("oai_id")
        if oai:
            out["oaiId"] = str(oai).strip()
        arxiv = v.get("arxivId") or v.get("arxiv_id")
        if arxiv:
            aid = strip_arxiv_id(arxiv) or str(arxiv).strip()
            if aid:
                out["arxivId"] = aid
        return out
    if isinstance(v, list):
        out = {}
        for item in v:
            if not isinstance(item, dict):
                continue
            t = str(item.get("type", "")).lower()
            val = item.get("value")
            if not val:
                continue
            if t in ("oai_identifier", "oaiid", "oai_id"):
                out["oaiId"] = str(val).strip()
            elif t in ("arxiv_id", "arxivid"):
                aid = strip_arxiv_id(val) or str(val).strip()
                if aid:
                    out["arxivId"] = aid
        return out
    return {}


def build_locations(row: Dict[str, Any], license_map: Dict[str, str]) -> List[Dict[str, Any]]:
    locs: List[Dict[str, Any]] = []
    get_pdf = as_bool_flag(get_first(row, "get_pdf"))
    get_source = as_bool_flag(get_first(row, "get_source"))
    lic = map_license_url(get_first(row, "license_url"), license_map)
    pdf_url = get_first(row, "pdf_url")
    if pdf_url:
        locs.append(
            {
                "type": "download" if get_pdf else "",
                "url": str(pdf_url),
                "license": lic,
                "is_oa": oa_flag_str(get_pdf),
            }
        )
    source_url = get_first(row, "source_url")
    if source_url:
        locs.append(
            {
                "type": "download" if get_source else "",
                "url": str(source_url),
                "license": lic,
                "is_oa": oa_flag_str(get_source),
            }
        )
    return locs


def normalize_locations(v: Any, license_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """比对用：统一 locations，is_oa 为 string，license 为标准可选值。"""
    v = json_loads_maybe(v)
    if not isinstance(v, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in v:
        if not isinstance(item, dict):
            continue
        loc = dict(item)
        if "is_oa" in loc:
            loc["is_oa"] = oa_flag_str(as_bool_flag(loc["is_oa"]))
        if "license" in loc:
            loc["license"] = normalize_license_value(loc["license"], license_map)
        out.append(loc)
    return out


def _classification_field(row: Dict[str, Any], key: str) -> Any:
    """从 S3 行取 classifications 子字段；category -> arxiv_category。"""
    if key == "arxiv_category":
        raw = get_first(row, "category")
    else:
        raw = get_first(row, key)
    if raw is None:
        return None
    if isinstance(raw, str) and not raw.strip():
        return None
    if key == "arxiv_category":
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
        return [raw.strip()] if str(raw).strip() else None
    return raw


def build_classifications(row: Dict[str, Any]) -> Dict[str, Any]:
    """与落库一致：固定 Object，含 mesh / msc_class / acm_class / arxiv_category。"""
    return {
        "mesh": _classification_field(row, "mesh"),
        "msc_class": _classification_field(row, "msc_class"),
        "acm_class": _classification_field(row, "acm_class"),
        "arxiv_category": _classification_field(row, "arxiv_category"),
    }


def normalize_classifications(v: Any) -> Dict[str, Any]:
    """比对用：统一四类 key，空值归一为 null；category 别名 -> arxiv_category。"""
    v = json_loads_maybe(v)
    if not isinstance(v, dict):
        v = {}
    raw_cat = v.get("arxiv_category")
    if raw_cat is None and "category" in v:
        raw_cat = v.get("category")

    def norm_scalar(val: Any) -> Any:
        if val is None:
            return None
        if isinstance(val, str) and not val.strip():
            return None
        return val

    def norm_category(val: Any) -> Any:
        if val is None:
            return None
        if isinstance(val, list):
            items = [str(x).strip() for x in val if str(x).strip()]
            return items or None
        s = str(val).strip()
        return [s] if s else None

    return {
        "mesh": norm_scalar(v.get("mesh")),
        "msc_class": norm_scalar(v.get("msc_class")),
        "acm_class": norm_scalar(v.get("acm_class")),
        "arxiv_category": norm_category(raw_cat),
    }


def build_track_id(row: Dict[str, Any]) -> Optional[str]:
    """与落库一致：track_id = arxiv:{doc_id}。"""
    oid = get_first(row, "doc_id")
    if oid is None or not str(oid).strip():
        return None
    return f"arxiv:{str(oid).strip()}"


def arxiv_empty_field_defaults() -> Dict[str, Any]:
    """arxiv 源无对应字段时，落库表中的默认/空值（与湖仓表现一致）。"""
    return {
        "language": "",
        "type": [],
        "keywords": [],
        "fieldsOfStudy": [],
        "s2FieldsOfStudy": [],
        "primary_topic": {},
        "topics": [],
        "concepts": [],
        "subject": "",
        "major": "",
        "major_2": "",
        "major_3": "",
        "category": "",
        "area": "",
        "grade_class": "",
        "grade": "",
        "origin_db_source": "",
        "reference_count": None,
        "citation_count": None,
        "influential_citation_count": None,
        "fwci": None,
        "references": [],
        "related_works": [],
        "citation_normalized_percentile": {},
        "cited_by_percentile_year": {},
        "cited_by_api_url": "",
        "venue_name": "",
        "venue_type": "",
        "venue_issn": [],
        "venue_publisher": [],
        "venue.type": "",
        "venue.issn": [],
        "venue.publisher": [],
        "biblio_volume": "",
        "biblio_issue": "",
        "biblio_pages": "",
        "mesh": None,
        "msc_class": None,
        "acm_class": None,
        "arxiv_category": None,
    }


def transform_arxiv_row(row: Dict[str, Any], license_map: Dict[str, str]) -> Dict[str, Any]:
    updated = get_first(row, "updated")
    get_pdf = as_bool_flag(get_first(row, "get_pdf"))
    pdf_url = get_first(row, "pdf_url") or ""
    expected: Dict[str, Any] = arxiv_empty_field_defaults()
    expected.update({
        "track_id": build_track_id(row),
        "title": get_first(row, "title"),
        "abstract": get_first(row, "abstract"),
        "doi": build_doi(row),
        "author": parse_authors(get_first(row, "authors")),
        "identifiers": build_identifiers(row),
        "indexed_in": ["arxiv"],
        "published_date": parse_date_iso(updated),
        "published_year": parse_year(updated),
        "access_is_oa": "true",
        "access_oa_status": "",
        "access_oa_url": str(pdf_url) if get_pdf else "",
        "access_license": map_license_url(get_first(row, "license_url"), license_map),
        "origin_id": get_first(row, "doc_id"),
        "origin_osi": "arxiv",
        "locations": build_locations(row, license_map),
        "classifications": build_classifications(row),
        "mesh": _classification_field(row, "mesh"),
        "msc_class": _classification_field(row, "msc_class"),
        "acm_class": _classification_field(row, "acm_class"),
        "arxiv_category": _classification_field(row, "arxiv_category"),
    })
    return expected


# ---- osi_verify/transforms/registry.py ----


from typing import Any, Callable, Dict


TransformFn = Callable[[Dict[str, Any], Dict[str, str]], Dict[str, Any]]

TRANSFORMS: Dict[str, TransformFn] = {
    "osi_arxiv": transform_arxiv_row,
}


def transform_row(row: Dict[str, Any], license_map: Dict[str, str], transform: str) -> Dict[str, Any]:
    try:
        fn = TRANSFORMS[transform]
    except KeyError as e:
        raise ValueError(f"不支持的 transform: {transform}") from e
    return fn(row, license_map)


# ---- osi_verify/compare.py ----


import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple



def mysql_column_for_field(field: str, columns: Sequence[str]) -> Optional[str]:
    original = field
    if original in columns:
        return original
    field = DB_COLUMN_ALIASES.get(field, field)
    if field in columns:
        return field
    flat = original.replace(".", "_")
    if flat in columns:
        return flat
    flat = field.replace(".", "_")
    if flat in columns:
        return flat
    top = field.split(".")[0]
    return top if top in columns else None


def get_nested_value(obj: Any, path: str) -> Any:
    cur = obj
    for p in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def get_mysql_field_value(mysql_row: Dict[str, Any], field: str, columns: Sequence[str]) -> Any:
    col = mysql_column_for_field(field, columns)
    if not col:
        return None
    raw = mysql_row.get(col)
    parsed = json_loads_maybe(raw)
    if "." in field:
        if col == field.split(".")[0] and isinstance(parsed, dict):
            return get_nested_value(parsed, ".".join(field.split(".")[1:]))
        return get_nested_value(parsed if isinstance(parsed, dict) else mysql_row, field)
    return parsed


def normalize_scalar(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, datetime):
        return v.isoformat(sep=" ", timespec="seconds")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    s = str(v).strip()
    return s if s else None


def normalize_json(v: Any) -> Any:
    v = json_loads_maybe(v)
    if isinstance(v, dict):
        return {k: normalize_json(vv) for k, vv in sorted(v.items())}
    if isinstance(v, list):
        return [normalize_json(x) for x in v]
    return normalize_scalar(v)


def is_empty_value(v: Any) -> bool:
    v = normalize_json(v)
    if v is None:
        return True
    if isinstance(v, (list, dict)) and not v:
        return True
    if isinstance(v, str) and not v.strip():
        return True
    return False


def is_empty_value_for_type(v: Any, value_type: str) -> bool:
    v = json_loads_maybe(v)
    type_name = value_type.strip().lower()
    if v is None:
        return True
    if type_name.startswith("list"):
        return isinstance(v, list) and not v
    if type_name in {"object", "dict", "map"}:
        return isinstance(v, dict) and not v
    if type_name in {"string", "str"}:
        return isinstance(v, str) and not v.strip()
    if type_name in {"integer", "int", "float", "double", "number", "boolean", "bool"}:
        return v is None
    return is_empty_value(v)


def _format_diff_value(v: Any, max_len: int = 500) -> str:
    if v is None:
        return "null"
    if isinstance(v, (dict, list)):
        s = json.dumps(v, ensure_ascii=False, default=str)
    else:
        s = repr(v) if isinstance(v, str) else str(v)
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


@dataclass
class FieldMismatch:
    """单字段不一致：s3 为转换后的期望值，db 为 Iceberg/MySQL 实际值。"""

    field: str
    s3: Any
    db: Any

    def to_dict(self) -> Dict[str, Any]:
        return {"field": self.field, "s3": self.s3, "db": self.db}

    def __str__(self) -> str:
        return f"{self.field}: S3={_format_diff_value(self.s3)} | DB={_format_diff_value(self.db)}"


def values_equal(
    s3_val: Any,
    db_val: Any,
    field: str,
    license_map: Optional[Dict[str, str]] = None,
    empty_value_type: Optional[str] = None,
) -> Tuple[bool, Optional[FieldMismatch], Optional[str]]:
    license_map = license_map or DEFAULT_LICENSE_MAP
    s3_n = normalize_json(s3_val)
    db_n = normalize_json(db_val)
    if empty_value_type:
        s3_typed_empty = is_empty_value_for_type(s3_val, empty_value_type)
        db_typed_empty = is_empty_value_for_type(db_val, empty_value_type)
        if s3_typed_empty and db_typed_empty:
            return True, None, None
        if is_empty_value(s3_n) or is_empty_value(db_n):
            return False, FieldMismatch(field, s3_val, db_val), None
    if field == "doi":
        s3_n = normalize_doi(s3_val)
        db_n = normalize_doi(db_val)
        if s3_n == db_n:
            return True, None, None
        return False, FieldMismatch(field, s3_n, db_n), None
    if field == "identifiers":
        s3_n = normalize_identifiers(s3_val)
        db_n = normalize_identifiers(db_val)
        if s3_n == db_n:
            return True, None, None
        return False, FieldMismatch(field, s3_n, db_n), None
    if field == "indexed_in":
        s3_n = normalize_indexed_in(s3_val)
        db_n = normalize_indexed_in(db_val)
        if s3_n == db_n:
            return True, None, None
        return False, FieldMismatch(field, s3_n, db_n), None
    if field in ("published_date", "publication_published_date"):
        s3_n = parse_date_iso(s3_val)
        db_n = parse_date_iso(db_val)
        if s3_n == db_n:
            return True, None, None
        return False, FieldMismatch(field, s3_n, db_n), None
    if field == "access_license":
        s3_n = normalize_license_value(s3_val, license_map)
        db_n = normalize_license_value(db_val, license_map)
        warn = license_out_of_allowed_warning(s3_n, source="S3")
        if warn:
            return True, None, warn
        if s3_n == db_n:
            return True, None, None
        return False, FieldMismatch(field, s3_n, db_n), None
    if field == "locations":
        s3_n = normalize_locations(s3_val, license_map)
        db_n = normalize_locations(db_val, license_map)
        for i, loc in enumerate(s3_n):
            lic = loc.get("license", "")
            w = license_out_of_allowed_warning(lic, source=f"S3 locations[{i}]")
            if w:
                return True, None, w
        if s3_n == db_n:
            return True, None, None
        return False, FieldMismatch(field, s3_n, db_n), None
    if field == "classifications":
        s3_n = normalize_classifications(s3_val)
        db_n = normalize_classifications(db_val)
        if s3_n == db_n:
            return True, None, None
        return False, FieldMismatch(field, s3_n, db_n), None
    if field == "author":
        if s3_n == db_n:
            return True, None, None
        return False, FieldMismatch(field, s3_n, db_n), None
    if field == "access_is_oa":
        s3_s = oa_flag_str(as_bool_flag(s3_val))
        db_s = oa_flag_str(as_bool_flag(db_val))
        if s3_s == db_s:
            return True, None, None
        return False, FieldMismatch(field, s3_s, db_s), None
    if field in ("published_year", "publication_published_year"):
        try:
            if int(s3_n or 0) == int(db_n or 0):
                return True, None, None
        except (TypeError, ValueError):
            pass
        return False, FieldMismatch(field, s3_n, db_n), None
    if normalize_scalar(s3_n) == normalize_scalar(db_n):
        return True, None, None
    return False, FieldMismatch(field, s3_n, db_n), None


def compare_fields_for_table(
    columns: Sequence[str],
    mapping_rules: Sequence[Any],
) -> List[str]:
    """按当前 target 的 mapping CSV 生成字段清单，并仅保留目标表存在的列。"""
    requested = compare_fields_from_rules(mapping_rules)
    return [f for f in requested if mysql_column_for_field(f, columns)]


def check_track_id(
    expected_tid: Any,
    db_tid: Any,
    origin_id: Any,
    track_registry: Dict[str, str],
) -> List[FieldMismatch]:
    """track_id 非空、与期望值一致、本次校验批次内唯一。"""
    failures: List[FieldMismatch] = []
    exp = normalize_scalar(expected_tid)
    db = normalize_scalar(db_tid)
    if not db:
        failures.append(FieldMismatch("track_id", exp, db_tid))
        return failures
    if exp is not None and db != exp:
        failures.append(FieldMismatch("track_id", exp, db))
    tid = str(db)
    oid = str(origin_id) if origin_id is not None else ""
    prev = track_registry.get(tid)
    if prev is not None and prev != oid:
        failures.append(
            FieldMismatch(
                "track_id",
                exp,
                f"duplicate: also used by origin_id={prev}",
            )
        )
    else:
        track_registry[tid] = oid
    return failures


@dataclass
class RowResult:
    origin_id: Any
    ok: bool
    jsonl_file: str = ""
    missing_in_mysql: bool = False
    failures: List[FieldMismatch] = field(default_factory=list)
    passes: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.ok:
            return "PASS"
        return "MISSING" if self.missing_in_mysql else "FAIL"


def compare_row(
    s3_row: Dict[str, Any],
    mysql_row: Optional[Dict[str, Any]],
    license_map: Dict[str, str],
    *,
    track_registry: Optional[Dict[str, str]] = None,
    compare_fields: Optional[Sequence[str]] = None,
    default_empty_field_types: Optional[Dict[str, str]] = None,
    transform: str = "osi_arxiv",
) -> RowResult:
    expected = transform_row(s3_row, license_map, transform)
    origin_id = expected.get("origin_id")
    if mysql_row is None:
        return RowResult(origin_id=origin_id, ok=False, missing_in_mysql=True)
    columns = list(mysql_row.keys())
    if compare_fields is None:
        raise ValueError("compare_fields 不能为空；字段校验必须由当前 target 的 mapping CSV 生成")
    fields = list(compare_fields)
    empty_field_types = default_empty_field_types or {}
    failures, passes, warnings = [], [], []
    registry = track_registry if track_registry is not None else {}
    if "track_id" in fields:
        failures.extend(
            check_track_id(
                expected.get("track_id"),
                get_mysql_field_value(mysql_row, "track_id", columns),
                origin_id,
                registry,
            )
        )
        fields = [f for f in fields if f != "track_id"]
    for fld in fields:
        exp_val = expected.get(fld)
        ok, mismatch, warn = values_equal(
            exp_val,
            get_mysql_field_value(mysql_row, fld, columns),
            fld,
            license_map,
            empty_value_type=empty_field_types.get(fld),
        )
        if warn:
            warnings.append(warn)
        if ok:
            passes.append(fld)
        elif mismatch:
            failures.append(mismatch)
    return RowResult(
        origin_id=origin_id,
        ok=not failures,
        failures=failures,
        passes=passes,
        warnings=warnings,
    )


# ---- osi_verify/mysql_session.py ----


from typing import Any, Callable, Dict, Optional, TypeVar


try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:
    pymysql = None  # type: ignore
    DictCursor = None  # type: ignore

T = TypeVar("T")


class MySQLSession:
    """带重试的 MySQL/StarRocks 会话；连接断开时自动重连。"""

    def __init__(
        self,
        cfg: Dict[str, Any],
        database: Optional[str],
        *,
        catalog: Optional[str] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        self.cfg = cfg
        self.database = database
        self.catalog = catalog
        self.retry_config = retry_config or RetryConfig()
        self._conn: Any = None

    @property
    def conn(self) -> Any:
        if self._conn is None:
            self.connect()
        return self._conn

    def connect(self) -> Any:
        if pymysql is None:
            raise RuntimeError("请安装 pymysql: pip install pymysql")
        kwargs: Dict[str, Any] = dict(
            host=self.cfg["host"],
            port=self.cfg["port"],
            user=self.cfg["user"],
            password=self.cfg["password"],
            charset="utf8mb4",
            cursorclass=DictCursor,
            connect_timeout=30,
            read_timeout=300 if self.catalog else 60,
        )
        if not self.catalog and self.database:
            kwargs["database"] = self.database

        def _connect():
            return pymysql.connect(**kwargs)

        self._conn = retry_call(
            _connect,
            self.retry_config,
            label="MySQL 连接",
            retryable=is_mysql_retryable,
        )
        return self._conn

    def reconnect(self) -> None:
        self.close()
        self.connect()

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def run(self, fn: Callable[[Any], T], *, label: str) -> T:
        def attempt() -> T:
            try:
                return fn(self.conn)
            except Exception as exc:
                if is_mysql_retryable(exc):
                    self.close()
                raise

        return retry_call(
            attempt,
            self.retry_config,
            label=label,
            retryable=is_mysql_retryable,
        )

    def __enter__(self) -> "MySQLSession":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


# ---- osi_verify/s3_reader.py ----


import json
import random
import sys
from typing import Any, Dict, Generator, List, Optional, Tuple

try:
    import duckdb
except ImportError:
    duckdb = None  # type: ignore


RANGE_SAMPLE_CHUNK_BYTES = 1024 * 1024
RANGE_SAMPLE_MAX_ATTEMPT_FACTOR = 20
BOTOCORE_RETRY_ATTEMPTS = 2


def rows_from_cursor(cur) -> List[Dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def configure_duckdb_s3(con: "duckdb.DuckDBPyConnection", s3_cfg: Dict[str, Any]) -> None:
    con.execute("INSTALL httpfs; LOAD httpfs;")
    ep = sql_literal(s3_cfg["endpoint"])
    ak = sql_literal(s3_cfg["access_key"])
    sk = sql_literal(s3_cfg["secret_key"])
    use_ssl = bool(s3_cfg.get("use_ssl", True))
    con.execute(f"SET s3_endpoint='{ep}';")
    con.execute(f"SET s3_access_key_id='{ak}';")
    con.execute(f"SET s3_secret_access_key='{sk}';")
    con.execute(f"SET s3_use_ssl={'true' if use_ssl else 'false'};")
    con.execute("SET s3_url_style='path';")
    con.execute("SET s3_region='us-east-1';")


def _detect_s3_format(
    con: "duckdb.DuckDBPyConnection",
    s3_path: str,
    *,
    s3_cfg: Optional[Dict[str, Any]] = None,
    retry_config: Optional[RetryConfig] = None,
) -> str:
    if s3_cfg:
        if list_s3_files_boto3(s3_path, s3_cfg, ".jsonl", retry_config=retry_config):
            return "jsonl"
        if list_s3_files_boto3(s3_path, s3_cfg, ".parquet", retry_config=retry_config):
            return "parquet"
        raise FileNotFoundError(f"S3 路径下未找到 .jsonl 或 .parquet 文件: {s3_path}")

    base = sql_literal(s3_path.rstrip("/"))

    def _jsonl_count() -> int:
        return int(con.execute(f"SELECT count(*) FROM glob('{base}/*.jsonl')").fetchone()[0])

    def _parquet_count() -> int:
        return int(con.execute(f"SELECT count(*) FROM glob('{base}/**/*.parquet')").fetchone()[0])

    if retry_call(_jsonl_count, retry_config, label="S3 探测 jsonl", retryable=is_s3_retryable):
        return "jsonl"
    if retry_call(_parquet_count, retry_config, label="S3 探测 parquet", retryable=is_s3_retryable):
        return "parquet"
    raise FileNotFoundError(f"S3 路径下未找到 .jsonl 或 .parquet 文件: {s3_path}")


def open_duckdb_s3(s3_cfg: Optional[Dict[str, Any]]) -> "duckdb.DuckDBPyConnection":
    if duckdb is None:
        raise RuntimeError("请安装 duckdb: pip install duckdb pyarrow")
    con = duckdb.connect()
    if s3_cfg:
        configure_duckdb_s3(con, s3_cfg)
    return con


def jsonl_basename(s3_uri: str) -> str:
    return s3_uri.rsplit("/", 1)[-1]


def parse_s3_uri(uri: str) -> Tuple[str, str]:
    u = uri.replace("\\", "/")
    if not u.startswith("s3://"):
        raise ValueError(f"非 S3 URI: {uri}")
    rest = u[5:]
    bucket, _, key = rest.partition("/")
    if not bucket or not key:
        raise ValueError(f"无法解析 S3 URI: {uri}")
    return bucket, key


def _suppress_insecure_request_warning() -> None:
    """内网 Ceph 常使用自签证书，verify=False 时抑制 urllib3 重复告警。"""
    try:
        import urllib3
    except ImportError:
        return
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def s3_boto_client(s3_cfg: Dict[str, Any], *, retry_config: Optional[RetryConfig] = None):
    try:
        import boto3
        from botocore.config import Config
    except ImportError as e:
        raise RuntimeError("S3 流式/Range 抽样需要 boto3: pip install boto3") from e
    cfg = retry_config or RetryConfig()
    use_ssl = bool(s3_cfg.get("use_ssl", True))
    verify_ssl = bool(s3_cfg.get("verify_ssl", False))
    if use_ssl and not verify_ssl:
        _suppress_insecure_request_warning()
    scheme = "https" if use_ssl else "http"
    return boto3.client(
        "s3",
        endpoint_url=f"{scheme}://{s3_cfg['endpoint']}",
        aws_access_key_id=s3_cfg["access_key"],
        aws_secret_access_key=s3_cfg["secret_key"],
        region_name="us-east-1",
        config=Config(
            s3={"addressing_style": "path"},
            signature_version="s3v4",
            retries={
                "max_attempts": BOTOCORE_RETRY_ATTEMPTS if cfg.enabled else 1,
                "mode": "standard",
            },
        ),
        verify=verify_ssl,
    )


def list_s3_files_boto3(
    s3_path: str,
    s3_cfg: Dict[str, Any],
    suffix: str,
    *,
    retry_config: Optional[RetryConfig] = None,
) -> List[str]:
    bucket, prefix = parse_s3_uri(s3_path.rstrip("/") + "/")
    suffix_lc = suffix.lower()

    def _list() -> List[str]:
        client = s3_boto_client(s3_cfg, retry_config=retry_config)
        files: List[str] = []
        continuation_token: Optional[str] = None
        while True:
            kwargs: Dict[str, Any] = {"Bucket": bucket, "Prefix": prefix}
            if continuation_token:
                kwargs["ContinuationToken"] = continuation_token
            response = client.list_objects_v2(**kwargs)
            for item in response.get("Contents", []):
                key = item.get("Key")
                if key and str(key).lower().endswith(suffix_lc):
                    files.append(f"s3://{bucket}/{key}")
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
            if not continuation_token:
                break
        return sorted(files)

    return retry_call(
        _list,
        retry_config,
        label=f"S3 列出 {suffix}",
        retryable=is_s3_retryable,
    )


def sample_jsonl_rows_sequential_stream(
    s3_uri: str,
    s3_cfg: Dict[str, Any],
    sample_size: int,
    *,
    retry_config: Optional[RetryConfig] = None,
) -> List[Dict[str, Any]]:
    """流式读取 jsonl 前 N 条（不扫全文件）。"""
    if sample_size <= 0:
        return []
    bucket, key = parse_s3_uri(s3_uri)
    client = s3_boto_client(s3_cfg, retry_config=retry_config)

    def _read() -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        body = client.get_object(Bucket=bucket, Key=key)["Body"]
        for raw in body.iter_lines():
            if not raw or not raw.strip():
                continue
            rows.append(json.loads(raw))
            if len(rows) >= sample_size:
                break
        return rows

    return retry_call(_read, retry_config, label=f"S3 顺序读 {jsonl_basename(s3_uri)}", retryable=is_s3_retryable)


def _json_line_from_range(payload: bytes, *, offset: int, object_size: int) -> Optional[bytes]:
    if not payload:
        return None
    start = 0
    if offset > 0:
        first_newline = payload.find(b"\n")
        if first_newline < 0:
            return None
        start = first_newline + 1
    end = payload.find(b"\n", start)
    if end < 0:
        if offset + len(payload) >= object_size:
            end = len(payload)
        else:
            return None
    line = payload[start:end].strip()
    return line or None


def sample_jsonl_rows_s3_range(
    s3_uri: str,
    s3_cfg: Dict[str, Any],
    sample_size: int,
    *,
    retry_config: Optional[RetryConfig] = None,
) -> List[Dict[str, Any]]:
    """通过 S3 Range 近似随机抽样，不全量扫描大 JSONL 文件。"""
    if sample_size <= 0:
        return []
    bucket, key = parse_s3_uri(s3_uri)
    client = s3_boto_client(s3_cfg, retry_config=retry_config)

    def _head_size() -> int:
        return int(client.head_object(Bucket=bucket, Key=key)["ContentLength"])

    object_size = retry_call(_head_size, retry_config, label=f"S3 head {jsonl_basename(s3_uri)}", retryable=is_s3_retryable)
    if object_size <= 0:
        return []

    rows: List[Dict[str, Any]] = []
    seen = set()
    attempts = 0
    max_attempts = max(sample_size * RANGE_SAMPLE_MAX_ATTEMPT_FACTOR, sample_size)
    while len(rows) < sample_size and attempts < max_attempts:
        attempts += 1
        offset = random.randint(0, max(0, object_size - 1))
        end = min(object_size - 1, offset + RANGE_SAMPLE_CHUNK_BYTES - 1)

        def _read_range(off: int = offset, end_byte: int = end) -> bytes:
            return client.get_object(
                Bucket=bucket,
                Key=key,
                Range=f"bytes={off}-{end_byte}",
            )["Body"].read()

        body = retry_call(
            _read_range,
            retry_config,
            label=f"S3 Range 读 {jsonl_basename(s3_uri)}",
            retryable=is_s3_retryable,
        )
        raw_line = _json_line_from_range(body, offset=offset, object_size=object_size)
        if raw_line is None or raw_line in seen:
            continue
        try:
            row = json.loads(raw_line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        seen.add(raw_line)
        rows.append(row)
    return rows


def list_s3_jsonl_files(
    con: "duckdb.DuckDBPyConnection",
    s3_path: str,
    *,
    s3_cfg: Optional[Dict[str, Any]] = None,
    retry_config: Optional[RetryConfig] = None,
) -> List[str]:
    if s3_cfg:
        files = list_s3_files_boto3(s3_path, s3_cfg, ".jsonl", retry_config=retry_config)
        if not files:
            raise FileNotFoundError(f"未找到 jsonl: {s3_path}")
        return files

    base = sql_literal(s3_path.rstrip("/"))

    def _list() -> List[str]:
        return [
            r[0]
            for r in con.execute(
                f"SELECT file FROM glob('{base}/*.jsonl') ORDER BY file"
            ).fetchall()
        ]

    files = retry_call(_list, retry_config, label="S3 列出 jsonl", retryable=is_s3_retryable)
    if not files:
        raise FileNotFoundError(f"未找到 jsonl: {s3_path}")
    return files


def sample_jsonl_rows(
    con: "duckdb.DuckDBPyConnection",
    fpath: str,
    sample_size: int,
    *,
    sequential: bool = False,
    s3_cfg: Optional[Dict[str, Any]] = None,
    retry_config: Optional[RetryConfig] = None,
) -> List[Dict[str, Any]]:
    """从单个 jsonl 抽取最多 sample_size 行。"""
    if sample_size <= 0:
        return []
    if sequential and s3_cfg and fpath.startswith("s3://"):
        return sample_jsonl_rows_sequential_stream(
            fpath, s3_cfg, sample_size, retry_config=retry_config
        )
    if not sequential and s3_cfg and fpath.startswith("s3://"):
        return sample_jsonl_rows_s3_range(
            fpath, s3_cfg, sample_size, retry_config=retry_config
        )
    inner = f"SELECT * FROM read_json_auto('{sql_literal(fpath)}')"
    if sequential:
        sql = f"SELECT * FROM ({inner}) LIMIT {int(sample_size)}"
    else:
        sql = f"SELECT * FROM ({inner}) ORDER BY random() LIMIT {int(sample_size)}"

    def _sample() -> List[Dict[str, Any]]:
        return rows_from_cursor(con.execute(sql))

    return retry_call(
        _sample,
        retry_config,
        label=f"S3 DuckDB 抽样 {jsonl_basename(fpath)}",
        retryable=is_s3_retryable,
    )


def iter_s3_batches(
    *,
    parquet_glob: Optional[str],
    s3_path: Optional[str],
    s3_cfg: Optional[Dict[str, Any]],
    s3_format: str,
    full: bool,
    limit: int,
    batch_size: int,
    sequential: bool = False,
    retry_config: Optional[RetryConfig] = None,
) -> Generator[Tuple[str, List[Dict[str, Any]]], None, None]:
    """按批产出 (jsonl_s3_uri, rows)。"""
    con = open_duckdb_s3(s3_cfg)

    if s3_path:
        base = s3_path.rstrip("/")
        fmt = s3_format if s3_format != "auto" else _detect_s3_format(
            con,
            base,
            s3_cfg=s3_cfg,
            retry_config=retry_config,
        )
        if fmt == "jsonl":
            files = list_s3_jsonl_files(con, base, s3_cfg=s3_cfg, retry_config=retry_config)
            if full:
                print(
                    f"S3 数据格式: jsonl，全量 {len(files)} 个文件，batch_size={batch_size}",
                    file=sys.stderr,
                )
            else:
                mode = f"顺序前 {limit} 条" if sequential else f"随机 {limit} 条"
                print(
                    f"S3 数据格式: jsonl，抽样 {len(files)} 个文件，每文件{mode}",
                    file=sys.stderr,
                )
            for fpath in files:
                if full:
                    offset = 0
                    while True:
                        path_lit = sql_literal(fpath)
                        off = offset
                        bs = batch_size

                        def _read_batch() -> List[Dict[str, Any]]:
                            cur = con.execute(
                                f"SELECT * FROM read_json_auto('{path_lit}') "
                                f"LIMIT {int(bs)} OFFSET {int(off)}"
                            )
                            return rows_from_cursor(cur)

                        rows = retry_call(
                            _read_batch,
                            retry_config,
                            label=f"S3 DuckDB 全量批 {jsonl_basename(fpath)}",
                            retryable=is_s3_retryable,
                        )
                        if not rows:
                            break
                        yield fpath, rows
                        offset += len(rows)
                        if len(rows) < batch_size:
                            break
                else:
                    basename = jsonl_basename(fpath)
                    print(f"  [抽样] {basename} ...", file=sys.stderr, flush=True)
                    rows = sample_jsonl_rows(
                        con,
                        fpath,
                        limit,
                        sequential=sequential,
                        s3_cfg=s3_cfg,
                        retry_config=retry_config,
                    )
                    if rows:
                        print(
                            f"  [抽样] {basename}: {len(rows)} 条",
                            file=sys.stderr,
                        )
                        yield fpath, rows
            return

        path_expr = f"'{sql_literal(base)}/**/*.parquet'"
        sql = f"SELECT * FROM read_parquet({path_expr})"
        if not full and limit > 0:
            sql += f" ORDER BY random() LIMIT {int(limit)}"

        def _read_parquet() -> List[Dict[str, Any]]:
            return rows_from_cursor(con.execute(sql))

        rows = retry_call(_read_parquet, retry_config, label="S3 读 parquet", retryable=is_s3_retryable)
        yield "parquet", rows
        return

    if parquet_glob:
        reader = "read_json_auto" if parquet_glob.endswith(".jsonl") else "read_parquet"
        sql = f"SELECT * FROM {reader}('{sql_literal(parquet_glob)}')"
        if not full and limit > 0:
            sql += f" ORDER BY random() LIMIT {int(limit)}"

        def _read_glob() -> List[Dict[str, Any]]:
            return rows_from_cursor(con.execute(sql))

        rows = _read_glob()
        yield parquet_glob, rows
        return

    raise ValueError("请指定 --parquet-glob、--s3-path，或提供 s3 配置文件")


# ---- osi_verify/db.py ----


import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple



@dataclass(frozen=True)
class TableRef:
    """库表引用：Iceberg 经 StarRocks 时为 catalog.schema.table。"""

    catalog: Optional[str]
    schema: str
    table: str

    @property
    def sql_name(self) -> str:
        if self.catalog:
            return f"{self.catalog}.{self.schema}.{self.table}"
        return f"`{self.schema}`.`{self.table}`"

    @property
    def display_name(self) -> str:
        return self.sql_name


def resolve_table_ref(
    catalog: Optional[str], schema: str, table: str
) -> TableRef:
    return TableRef(catalog=catalog or None, schema=schema, table=table)


def discover_table(session: MySQLSession, table_ref: TableRef) -> TableRef:
    if table_ref.catalog:

        def _probe(conn) -> None:
            with conn.cursor() as cur:
                cur.execute(f"SELECT 1 FROM {table_ref.sql_name} LIMIT 1")

        session.run(_probe, label="MySQL 探活表")
        return table_ref
    if table_ref.table:
        return table_ref

    def _discover(conn) -> TableRef:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT TABLE_NAME, COUNT(*) AS cnt
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND COLUMN_NAME IN ('origin_id', 'origin_osi')
                GROUP BY TABLE_NAME
                HAVING cnt >= 2
                ORDER BY cnt DESC
                """
            )
            rows = cur.fetchall()
        if not rows:
            raise RuntimeError("未能自动发现含 origin_id/origin_osi 的表，请用 --table 指定")
        return TableRef(catalog=None, schema=table_ref.schema, table=rows[0]["TABLE_NAME"])

    return session.run(_discover, label="MySQL 发现表")



def fetch_mysql_rows_by_ids(
    session: MySQLSession,
    table_ref: TableRef,
    origin_ids: Sequence[Any],
    origin_osi: str = "arxiv",
    target_dt: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    ids = [str(i) for i in origin_ids if i is not None]
    if not ids:
        return {}

    def _fetch(conn) -> Dict[str, Dict[str, Any]]:
        placeholders = ",".join(["%s"] * len(ids))
        sql = (
            f"SELECT * FROM {table_ref.sql_name} "
            f"WHERE origin_osi = %s AND origin_id IN ({placeholders})"
        )
        params: List[Any] = [origin_osi, *ids]
        if target_dt:
            sql += " AND dt = %s"
            params.append(target_dt)
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return {str(r["origin_id"]): r for r in rows}

    return session.run(_fetch, label="MySQL 批量查询")


def count_s3_jsonl_lines_boto3(
    s3_uri: str,
    s3_cfg: Dict[str, Any],
    *,
    retry_config: Optional[RetryConfig] = None,
) -> int:
    """boto3 流式按换行符计数（不解析 JSON，适合大 jsonl）。"""
    bucket, key = parse_s3_uri(s3_uri)
    client = s3_boto_client(s3_cfg, retry_config=retry_config)

    def _count() -> int:
        n = 0
        body = client.get_object(Bucket=bucket, Key=key)["Body"]
        for chunk in body.iter_chunks(chunk_size=16 * 1024 * 1024):
            n += chunk.count(b"\n")
        return n

    return retry_call(_count, retry_config, label=f"S3 计数 {jsonl_basename(s3_uri)}", retryable=is_s3_retryable)


def count_s3_partition(
    con: "duckdb.DuckDBPyConnection",
    s3_path: str,
    files: Optional[List[str]] = None,
    *,
    s3_cfg: Optional[Dict[str, Any]] = None,
    retry_config: Optional[RetryConfig] = None,
) -> Tuple[int, Dict[str, int]]:
    """统计分区内 S3 行数（按 jsonl 文件）。有 s3_cfg 时用 boto3 流式计数。"""
    files = files or list_s3_jsonl_files(
        con,
        s3_path,
        s3_cfg=s3_cfg,
        retry_config=retry_config,
    )
    per_file: Dict[str, int] = {}
    total = 0
    use_boto = bool(s3_cfg)
    if use_boto:
        print("  [S3 计数] 使用 boto3 流式按行计数", file=sys.stderr)
    for fpath in files:
        if use_boto and fpath.startswith("s3://"):
            n = count_s3_jsonl_lines_boto3(fpath, s3_cfg, retry_config=retry_config)
        else:
            path_lit = sql_literal(fpath)

            def _duck_count() -> int:
                return int(
                    con.execute(
                        f"SELECT count(*) FROM read_json_auto('{path_lit}')"
                    ).fetchone()[0]
                )

            n = retry_call(
                _duck_count,
                retry_config,
                label=f"S3 DuckDB 计数 {jsonl_basename(fpath)}",
                retryable=is_s3_retryable,
            )
        name = jsonl_basename(fpath)
        per_file[name] = n
        total += n
        print(f"  [S3 计数] {name}: {n:,} 行", file=sys.stderr)
    return total, per_file


def table_columns(session: MySQLSession, table_ref: TableRef) -> List[str]:
    def _columns(conn) -> List[str]:
        with conn.cursor() as cur:
            if table_ref.catalog:
                cur.execute(f"DESCRIBE {table_ref.sql_name}")
                return [r["Field"] for r in cur.fetchall()]
            cur.execute(
                """
                SELECT COLUMN_NAME FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
                """,
                (table_ref.table,),
            )
            return [r["COLUMN_NAME"] for r in cur.fetchall()]

    return session.run(_columns, label="MySQL 读取表结构")


def count_mysql_origin(
    session: MySQLSession,
    table_ref: TableRef,
    partition_dt: Optional[str],
    origin_osi: str = "arxiv",
) -> Tuple[int, str]:
    """
    统计落库表中该分区指定 origin_osi 记录数。
    优先使用 dt / partition_dt / data_dt 等列；否则用 DATE(updated)=partition_dt。
    """
    cols = table_columns(session, table_ref)
    where = "origin_osi = %s"
    desc = f"origin_osi='{origin_osi}'"
    base_params: Tuple[Any, ...] = (origin_osi,)

    dt_cols = [c for c in ("dt", "partition_dt", "data_dt", "crawl_dt", "batch_dt") if c in cols]
    if partition_dt and dt_cols:
        c = dt_cols[0]
        where += f" AND `{c}` = %s"
        desc += f" AND {c}='{partition_dt}'"
        params: Tuple[Any, ...] = base_params + (partition_dt,)
    elif partition_dt and "updated" in cols:
        where += " AND DATE(`updated`) = %s"
        desc += f" AND DATE(updated)='{partition_dt}'"
        params = base_params + (partition_dt,)
    elif partition_dt and "published_date" in cols:
        where += " AND DATE(`published_date`) = %s"
        desc += f" AND DATE(published_date)='{partition_dt}'"
        params = base_params + (partition_dt,)
    elif partition_dt:
        print(
            f"[warn] 表 {table_ref.display_name} 无 dt/updated 等分区字段，仅按 origin_osi 统计总数",
            file=sys.stderr,
        )
        params = base_params
    else:
        params = base_params

    def _count(conn) -> int:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) AS n FROM {table_ref.sql_name} WHERE {where}", params)
            return int(cur.fetchone()["n"])

    n = session.run(_count, label="MySQL 统计行数")
    return n, desc


# ---- osi_verify/report.py ----


import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple



@dataclass
class ReportContext:
    target: str
    target_kind: str
    transform: str
    table_name: str
    origin_osi: str
    s3_path: str
    mapping_csv: str
    config_path: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "target": self.target,
            "target_kind": self.target_kind,
            "transform": self.transform,
            "table_name": self.table_name,
            "origin_osi": self.origin_osi,
            "s3_path": self.s3_path,
            "mapping_csv": self.mapping_csv,
            "config_path": self.config_path,
        }


@dataclass
class FileStats:
    total: int = 0
    pass_n: int = 0
    fail_n: int = 0
    miss_n: int = 0


@dataclass
class CountSummary:
    context: ReportContext
    s3_dt: Optional[str]
    target_dt: Optional[str]
    s3_path: str
    s3_total: int
    s3_per_file: Dict[str, int]
    mysql_total: int
    mysql_filter: str
    checked_rows: int = 0


def print_count_summary(cs: CountSummary) -> None:
    diff = cs.s3_total - cs.mysql_total
    print("\n" + "=" * 60)
    print("数据总量校验")
    print("=" * 60)
    print(f"Target            : {cs.context.target} ({cs.context.target_kind})")
    print(f"目标表            : {cs.context.table_name}")
    print(f"origin_osi        : {cs.context.origin_osi}")
    print(f"映射 CSV          : {cs.context.mapping_csv}")
    print(f"S3 分区 dt        : {cs.s3_dt or '(未解析)'}")
    print(f"目标表 dt         : {cs.target_dt or '(未指定)'}")
    print(f"S3 路径           : {cs.s3_path}")
    print(f"S3 jsonl 文件数   : {len(cs.s3_per_file)}")
    print(f"S3 总行数         : {cs.s3_total:,}")
    for name, n in sorted(cs.s3_per_file.items()):
        print(f"  - {name}: {n:,}")
    print(f"MySQL 过滤条件    : {cs.mysql_filter}")
    print(f"MySQL 行数        : {cs.mysql_total:,}")
    print(f"S3 - MySQL 差异   : {diff:+,}")
    if diff != 0:
        print("  >> 总量不一致，请检查落库任务是否漏跑/重复或分区字段过滤条件")
    else:
        print("  >> 总量一致")
    if cs.checked_rows and cs.checked_rows != cs.s3_total:
        print(
            f"  >> 本次仅校验抽样 {cs.checked_rows:,} 条，"
            f"字段级结果不代表全量（加 --full 做全量字段校验）"
        )


def print_anomaly_table(anomalies: List[RowResult], max_show: int = 50) -> None:
    print("\n" + "=" * 60)
    print(f"落库异常明细（共 {len(anomalies)} 条，展示前 {min(len(anomalies), max_show)} 条）")
    print("=" * 60)
    print(f"{'jsonl 文件':<32} {'origin_id':<16}  {'状态':<8}  异常摘要")
    print("-" * 60)
    for r in anomalies[:max_show]:
        brief = (str(r.failures[0])[:60] if r.failures else "数据库无该 origin_id 记录")
        print(
            f"{r.jsonl_file:<32} {str(r.origin_id):<16}  "
            f"{r.status:<8}  {brief}"
        )
    if len(anomalies) > max_show:
        print(f"... 另有 {len(anomalies) - max_show} 条，见 --report 文件")


SummaryKey = Tuple[str, str, str, str]


def _summary_value(v: Any, max_len: int = 500) -> str:
    if v is None:
        return "null"
    if isinstance(v, (dict, list)):
        text = json.dumps(v, ensure_ascii=False, default=str)
    else:
        text = repr(v) if isinstance(v, str) else str(v)
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


def _mismatch_key(mismatch: FieldMismatch) -> SummaryKey:
    return (
        "mismatch",
        mismatch.field,
        _summary_value(mismatch.s3),
        _summary_value(mismatch.db),
    )


def _print_summary_key(count: int, key: SummaryKey) -> None:
    kind, label, s3_val, db_val = key
    if kind == "mismatch":
        print(f"{count:>8}  {label}:")
        print(f"{'':>8}    S3: {s3_val}")
        print(f"{'':>8}    DB: {db_val}")
        return
    print(f"{count:>8}  {label}")


def print_anomaly_summary(anomalies: List[RowResult], max_examples: int = 3) -> None:
    print("\n" + "=" * 60)
    print(f"落库异常/Warning 类型汇总（共 {len(anomalies)} 条记录）")
    print("=" * 60)
    if not anomalies:
        print("无异常")
        return

    type_counts: Counter[SummaryKey] = Counter()
    examples: Dict[SummaryKey, List[str]] = defaultdict(list)

    for r in anomalies:
        if r.missing_in_mysql:
            key = ("message", "MySQL 缺失: 数据库无该 origin_id 记录", "", "")
            type_counts[key] += 1
            if len(examples[key]) < max_examples:
                examples[key].append(f"{r.jsonl_file} origin_id={r.origin_id}")

        for w in r.warnings:
            key = ("message", f"Warning: {w}", "", "")
            type_counts[key] += 1
            if len(examples[key]) < max_examples:
                examples[key].append(f"{r.jsonl_file} origin_id={r.origin_id}")

        for m in r.failures:
            key = _mismatch_key(m)
            type_counts[key] += 1
            if len(examples[key]) < max_examples:
                examples[key].append(f"{r.jsonl_file} origin_id={r.origin_id}")

    print(f"{'次数':>8}  错误类型")
    print("-" * 60)
    for key, count in type_counts.most_common():
        _print_summary_key(count, key)
        if max_examples > 0 and examples.get(key):
            print(f"{'':>8}  样例: {', '.join(examples[key])}")
    print("\n完整逐条明细请查看 --report 输出的 JSONL 文件")


def print_file_stats(stats: Dict[str, FileStats]) -> None:
    print("\n" + "=" * 60)
    print("按 jsonl 文件统计（本次已校验行）")
    print("=" * 60)
    print(f"{'jsonl 文件':<36} {'校验':>8} {'通过':>8} {'失败':>8} {'缺失':>8}")
    print("-" * 60)
    for name in sorted(stats):
        s = stats[name]
        print(f"{name:<36} {s.total:>8} {s.pass_n:>8} {s.fail_n:>8} {s.miss_n:>8}")


def print_run_context(ctx: ReportContext) -> None:
    print("\n" + "=" * 60)
    print("校验上下文")
    print("=" * 60)
    print(f"Target      : {ctx.target} ({ctx.target_kind})")
    print(f"Transform   : {ctx.transform}")
    print(f"目标表      : {ctx.table_name}")
    print(f"origin_osi  : {ctx.origin_osi}")
    print(f"S3 路径     : {ctx.s3_path or '(local/parquet-glob)'}")
    print(f"映射 CSV    : {ctx.mapping_csv}")
    print(f"配置文件    : {ctx.config_path}")


def safe_filename_token(value: Any) -> str:
    text = "unknown" if value in (None, "") else str(value)
    return re.sub(r"[^0-9A-Za-z_-]+", "_", text).strip("_") or "unknown"


def default_osi_report_path(target: str, s3_dt: Optional[str], target_dt: Optional[str]) -> Path:
    dt_tag = f"s3_{safe_filename_token(s3_dt)}_target_{safe_filename_token(target_dt)}"
    report_dir = REPORT_ROOT / f"meta_paper_data_{safe_filename_token(target)}_{dt_tag}"
    return report_dir / "source_field_mismatch.jsonl"


def summary_paths(report_path: Path) -> Tuple[Path, Path]:
    return report_path.parent / "summary.json", report_path.parent / "readable_summary.md"


REPORT_KEY_LABELS = {
    "report": "报告路径",
    "context": "校验上下文",
    "target": "目标名称",
    "target_kind": "目标类型",
    "transform": "转换逻辑",
    "table_name": "目标表",
    "origin_osi": "来源标识",
    "s3_path": "S3路径",
    "mapping_csv": "映射文件",
    "config_path": "配置文件",
    "s3_dt": "S3分区",
    "target_dt": "目标表分区",
    "partition_dt": "目标表分区",
    "checked": "已校验数",
    "passed": "通过数",
    "failed": "失败数",
    "missing": "目标表缺失数",
    "warnings": "Warning数量",
    "count_summary": "Count校验",
    "s3_total": "S3总行数",
    "mysql_total": "目标表行数",
    "diff": "数量差异",
    "mysql_filter": "目标表过滤条件",
    "checked_rows": "已校验行数",
    "s3_file_count": "S3文件数",
    "file_stats": "文件统计",
    "status_counts": "状态分布",
    "field_counts": "字段问题分布",
    "field_samples": "字段问题样例",
    "warning_counts": "Warning分布",
    "warning_samples": "Warning样例",
    "jsonl_file": "JSONL文件",
    "jsonl_s3_uri": "JSONL S3路径",
    "origin_id": "来源ID",
    "status": "状态",
    "field_diffs": "字段差异",
    "field": "字段",
    "s3": "S3值",
    "db": "目标表值",
    "expected": "预期值",
    "actual": "实际值",
    "missing_in_mysql": "目标表缺失",
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


def build_osi_report_summary(
    *,
    report_path: Optional[Path],
    context: ReportContext,
    s3_dt: Optional[str],
    target_dt: Optional[str],
    total: int,
    ok_n: int,
    fail_n: int,
    miss_n: int,
    warn_n: int,
    count_summary: Optional[CountSummary],
    per_file: Dict[str, FileStats],
    notable_results: List[RowResult],
) -> Dict[str, Any]:
    status_counts = Counter()
    field_counts = Counter()
    warning_counts = Counter()
    field_samples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    warning_samples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in notable_results:
        status_counts[row.status if not row.ok else "WARN"] += 1
        for warning in row.warnings:
            warning_counts[warning] += 1
            samples = warning_samples[warning]
            if len(samples) < SAMPLES_PER_FIELD:
                samples.append({"jsonl_file": row.jsonl_file, "origin_id": row.origin_id})
        if row.missing_in_mysql:
            field_counts["missing_in_mysql"] += 1
            samples = field_samples["missing_in_mysql"]
            if len(samples) < SAMPLES_PER_FIELD:
                samples.append({"jsonl_file": row.jsonl_file, "origin_id": row.origin_id})
        for mismatch in row.failures:
            field_counts[mismatch.field] += 1
            samples = field_samples[mismatch.field]
            if len(samples) < SAMPLES_PER_FIELD:
                samples.append(
                    {
                        "jsonl_file": row.jsonl_file,
                        "origin_id": row.origin_id,
                        "s3": mismatch.s3,
                        "db": mismatch.db,
                    }
                )

    count_payload = None
    if count_summary:
        count_payload = {
            "s3_dt": count_summary.s3_dt,
            "target_dt": count_summary.target_dt,
            "s3_total": count_summary.s3_total,
            "mysql_total": count_summary.mysql_total,
            "diff": count_summary.s3_total - count_summary.mysql_total,
            "mysql_filter": count_summary.mysql_filter,
            "checked_rows": count_summary.checked_rows,
            "s3_file_count": len(count_summary.s3_per_file),
        }

    sorted_field_counts = dict(field_counts.most_common())
    sorted_warning_counts = dict(warning_counts.most_common())
    top_sample_fields = set(list(sorted_field_counts)[:TOP_SAMPLE_FIELD_LIMIT])
    top_sample_warnings = set(list(sorted_warning_counts)[:TOP_SAMPLE_FIELD_LIMIT])
    return {
        "report": str(report_path) if report_path else None,
        "context": context.to_dict(),
        "s3_dt": s3_dt,
        "target_dt": target_dt,
        "partition_dt": target_dt,
        "checked": total,
        "passed": ok_n,
        "failed": fail_n,
        "missing": miss_n,
        "warnings": warn_n,
        "count_summary": count_payload,
        "file_stats": {
            name: {
                "total": stats.total,
                "passed": stats.pass_n,
                "failed": stats.fail_n,
                "missing": stats.miss_n,
            }
            for name, stats in sorted(per_file.items())
        },
        "status_counts": dict(status_counts.most_common()),
        "field_counts": sorted_field_counts,
        "field_count_total": len(sorted_field_counts),
        "field_samples": {
            field: field_samples[field]
            for field in sorted_field_counts
            if field in top_sample_fields
        },
        "warning_counts": sorted_warning_counts,
        "warning_type_total": len(sorted_warning_counts),
        "warning_samples": {
            warning: warning_samples[warning]
            for warning in sorted_warning_counts
            if warning in top_sample_warnings
        },
    }


def write_osi_report_summary(report_path: Path, summary: Dict[str, Any]) -> None:
    summary_json_path, summary_md_path = summary_paths(report_path)
    summary_json_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_json_path.open("w", encoding="utf-8") as f:
        json.dump(localize_report_keys(summary), f, ensure_ascii=False, indent=2, default=str)

    count_summary = summary.get("count_summary") or {}
    lines = [
        "# S3 数据到论文源数据表校验报告摘要",
        "",
        f"- 目标表: `{summary.get('context', {}).get('table_name')}`",
        f"- 分区: S3=`{summary.get('s3_dt')}`, 目标表=`{summary.get('target_dt')}`",
        f"- 结果: 已校验 `{summary.get('checked')}`，通过 `{summary.get('passed')}`，失败 `{summary.get('failed')}`，缺失 `{summary.get('missing')}`",
        f"- Warning: `{summary.get('warnings')}`",
        f"- 明细报告: `{summary.get('report')}`",
        f"- 报告目录: `{Path(str(summary.get('report'))).parent if summary.get('report') else None}`",
        "",
        "## Count 校验",
        "",
    ]
    if count_summary:
        lines.extend(
            [
                f"- s3_total: `{count_summary.get('s3_total')}`",
                f"- mysql_total: `{count_summary.get('mysql_total')}`",
                f"- diff: `{count_summary.get('diff')}`",
                f"- checked_rows: `{count_summary.get('checked_rows')}`",
                f"- mysql_filter: `{count_summary.get('mysql_filter')}`",
            ]
        )
    else:
        lines.append("- 未执行或已跳过")
    lines.extend(["", "## 状态分布", ""])
    for status, count in (summary.get("status_counts") or {}).items():
        lines.append(f"- `{status}`: {count}")
    if not summary.get("status_counts"):
        lines.append("- 无")
    lines.extend(["", "## 字段问题分布", ""])
    for field, count in (summary.get("field_counts") or {}).items():
        lines.append(f"- `{field}`: {count}")
    if not summary.get("field_counts"):
        lines.append("- 无")
    lines.extend(["", "## 字段问题样例", ""])
    for field, samples in (summary.get("field_samples") or {}).items():
        count = (summary.get("field_counts") or {}).get(field, len(samples))
        lines.append(f"### {field} ({count})")
        lines.append("")
        for sample in samples:
            lines.append(
                f"- origin_id `{sample.get('origin_id')}`, jsonl_file=`{sample.get('jsonl_file')}`"
            )
            if "s3" in sample or "db" in sample:
                lines.append(f"  - s3: `{json.dumps(sample.get('s3'), ensure_ascii=False, default=str)}`")
                lines.append(f"  - db: `{json.dumps(sample.get('db'), ensure_ascii=False, default=str)}`")
            lines.append("")

    if summary.get("warnings"):
        lines.extend(["", "## Warning 分布", ""])
        for warning, count in (summary.get("warning_counts") or {}).items():
            lines.append(f"- `{warning}`: {count}")
        if not summary.get("warning_counts"):
            lines.append("- 无")
        lines.extend(["", "## Warning 样例", ""])
        for warning, samples in (summary.get("warning_samples") or {}).items():
            count = (summary.get("warning_counts") or {}).get(warning, len(samples))
            lines.append(f"### {warning} ({count})")
            lines.append("")
            for sample in samples:
                lines.append(
                    f"- origin_id `{sample.get('origin_id')}`, jsonl_file=`{sample.get('jsonl_file')}`"
                )
            lines.append("")
    with summary_md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


# ---- osi_verify/runner.py ----


import json
import sys
from argparse import Namespace
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence



def run_verification(
    *,
    args: Namespace,
    target_config: TargetConfig,
    mysql_settings: Dict[str, Any],
    s3_settings: Dict[str, Any],
    mapping_rules: Sequence[MappingRule],
    requested_compare_fields: Sequence[str],
    license_map: Dict[str, str],
    retry_config: Optional[RetryConfig] = None,
) -> int:
    s3_cfg, s3_path = None, args.s3_path
    if args.parquet_glob:
        s3_path = None
    elif args.s3_config.exists() or s3_settings:
        inline_s3 = {
            k: v
            for k, v in s3_settings.items()
            if k not in {"config_file", "subpath", "format", "path"}
        }
        if args.s3_path:
            inline_s3["default_path"] = args.s3_path
        s3_cfg = load_s3_config(args.s3_config, inline_s3)
        s3_path = resolve_s3_path(s3_path or s3_cfg["default_path"], args.s3_subpath)
        s3_path = apply_s3_dt_to_path(s3_path, args.s3_dt or args.partition_dt)
        print(f"S3: endpoint={s3_cfg['endpoint']} path={s3_path}", file=sys.stderr)
    elif not s3_path:
        print("请指定 --parquet-glob、--s3-path，或提供 s3 配置文件", file=sys.stderr)
        return 2
    else:
        s3_path = apply_s3_dt_to_path(s3_path, args.s3_dt or args.partition_dt)

    row_limit = 0 if args.full else (max(args.limit, 1000) if args.origin_id else args.limit)
    origin_filter = set(args.origin_id) if args.origin_id else None
    source_id_field = target_config.source_id_field

    def align_filtered(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not origin_filter:
            return rows
        return [r for r in rows if str(get_first(r, source_id_field)) in origin_filter]

    s3_dt = extract_partition_dt(args.s3_subpath or s3_path, args.s3_dt or args.partition_dt)
    target_dt = args.target_dt or args.partition_dt or s3_dt

    def batch_kwargs() -> Dict[str, Any]:
        return {
            "parquet_glob": args.parquet_glob,
            "s3_path": s3_path,
            "s3_cfg": s3_cfg,
            "s3_format": args.s3_format,
            "full": args.full,
            "limit": row_limit,
            "batch_size": args.batch_size,
            "sequential": args.sequential,
            "retry_config": retry_config,
        }

    dry_run_context = ReportContext(
        target=target_config.name,
        target_kind=target_config.kind,
        transform=target_config.transform,
        table_name=resolve_table_ref(
            args.catalog if args.catalog else None,
            args.database,
            args.table,
        ).display_name,
        origin_osi=target_config.origin_osi,
        s3_path=s3_path or args.parquet_glob or "",
        mapping_csv=str(args.mapping_csv),
        config_path=str(args.config),
    )

    if args.dry_run:
        print_run_context(dry_run_context)
        shown = 0
        for src, batch in iter_s3_batches(**batch_kwargs()):
            batch = align_filtered(batch)
            if not batch:
                continue
            for row in batch:
                exp = transform_row(row, license_map, target_config.transform)
                print(
                    f"\n--- [{shown}] {jsonl_basename(src)} "
                    f"origin_id={exp.get('origin_id')} ---"
                )
                print(json.dumps(exp, ensure_ascii=False, indent=2, default=str))
                shown += 1
        print(f"共展示 {shown} 条", file=sys.stderr)
        return 0

    inline_mysql = {
        k: v
        for k, v in mysql_settings.items()
        if k not in {"config_file", "database", "table"}
    }
    mysql_cfg = load_mysql_config(args.mysql_config, inline_mysql)
    catalog = (args.catalog or mysql_cfg.get("catalog") or "").strip() or None
    table_ref = resolve_table_ref(catalog, args.database, args.table)
    if retry_config and retry_config.enabled:
        print(
            f"[info] 连接重试已启用: max_attempts={retry_config.max_attempts}, "
            f"initial_delay={retry_config.initial_delay_sec}s, "
            f"backoff={retry_config.backoff_factor}x",
            file=sys.stderr,
        )
    mysql_session = MySQLSession(
        mysql_cfg,
        args.database,
        catalog=catalog,
        retry_config=retry_config,
    )
    report_context = ReportContext(
        target=target_config.name,
        target_kind=target_config.kind,
        transform=target_config.transform,
        table_name=table_ref.display_name,
        origin_osi=target_config.origin_osi,
        s3_path=s3_path or args.parquet_glob or "",
        mapping_csv=str(args.mapping_csv),
        config_path=str(args.config),
    )
    report_path = args.report
    if report_path is None:
        report_path = default_osi_report_path(target_config.name, s3_dt, target_dt)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    warning_report_path = report_path.parent / "source_field_warning.jsonl"
    report_fp = report_path.open("w", encoding="utf-8")
    warning_report_fp = warning_report_path.open("w", encoding="utf-8")
    ok_n = miss_n = fail_n = warn_n = total = 0
    anomalies: List[RowResult] = []
    notable_results: List[RowResult] = []
    per_file: Dict[str, FileStats] = {}
    count_summary: Optional[CountSummary] = None
    track_registry: Dict[str, str] = {}
    active_compare_fields: Optional[List[str]] = None
    active_default_empty_field_types = default_empty_field_types_from_rules(mapping_rules)

    try:
        mysql_session.connect()
        table_ref = discover_table(mysql_session, table_ref)
        report_context.table_name = table_ref.display_name
        mode = f"StarRocks Iceberg catalog={catalog}" if catalog else "MySQL"
        print(f"使用表 ({mode}): {table_ref.display_name}")
        print_run_context(report_context)

        if s3_path and not args.skip_count:
            print("\n正在统计 S3 分区行数（可能较慢）...", file=sys.stderr)
            con = open_duckdb_s3(s3_cfg)
            jsonl_files = list_s3_jsonl_files(
                con,
                s3_path,
                s3_cfg=s3_cfg,
                retry_config=retry_config,
            )
            s3_total, s3_per_file = count_s3_partition(
                con,
                s3_path,
                jsonl_files,
                s3_cfg=s3_cfg,
                retry_config=retry_config,
            )
            mysql_total, mysql_filter = count_mysql_origin(
                mysql_session,
                table_ref,
                target_dt,
                origin_osi=target_config.origin_osi,
            )
            count_summary = CountSummary(
                context=report_context,
                s3_dt=s3_dt,
                target_dt=target_dt,
                s3_path=s3_path,
                s3_total=s3_total,
                s3_per_file=s3_per_file,
                mysql_total=mysql_total,
                mysql_filter=mysql_filter,
            )
            print_count_summary(count_summary)

        if args.count_only:
            if count_summary:
                write_osi_report_summary(
                    report_path,
                    build_osi_report_summary(
                        report_path=report_path,
                        context=report_context,
                        s3_dt=s3_dt,
                        target_dt=target_dt,
                        total=0,
                        ok_n=0,
                        fail_n=0,
                        miss_n=0,
                        warn_n=0,
                        count_summary=count_summary,
                        per_file=per_file,
                        notable_results=notable_results,
                    ),
                )
                print(f"\n汇总报告: {summary_paths(report_path)[0]}")
            return 0 if count_summary and count_summary.s3_total == count_summary.mysql_total else 1

        for src, batch in iter_s3_batches(**batch_kwargs()):
            batch = align_filtered(batch)
            if not batch:
                continue
            fname = jsonl_basename(src)
            if fname not in per_file:
                per_file[fname] = FileStats()
            ids = [get_first(r, source_id_field) for r in batch]
            mysql_map = fetch_mysql_rows_by_ids(
                mysql_session,
                table_ref,
                ids,
                origin_osi=target_config.origin_osi,
                target_dt=target_dt,
            )
            if mysql_map and active_compare_fields is None:
                active_compare_fields = compare_fields_for_table(
                    list(next(iter(mysql_map.values())).keys()),
                    mapping_rules,
                )
                skipped = [
                    f for f in requested_compare_fields
                    if f not in active_compare_fields
                ]
                print(
                    f"[info] 字段比对共 {len(active_compare_fields)} 列"
                    + (f"，表无列跳过: {', '.join(skipped)}" if skipped else ""),
                    file=sys.stderr,
                )
            for row in batch:
                oid = str(get_first(row, source_id_field))
                result = compare_row(
                    row,
                    mysql_map.get(oid),
                    license_map,
                    track_registry=track_registry,
                    compare_fields=active_compare_fields,
                    default_empty_field_types=active_default_empty_field_types,
                    transform=target_config.transform,
                )
                result.jsonl_file = fname
                total += 1
                fs = per_file[fname]
                fs.total += 1
                if result.warnings:
                    warn_n += len(result.warnings)
                    notable_results.append(result)
                if result.ok:
                    ok_n += 1
                    fs.pass_n += 1
                elif result.missing_in_mysql:
                    miss_n += 1
                    fs.miss_n += 1
                    anomalies.append(result)
                    if not result.warnings:
                        notable_results.append(result)
                else:
                    fail_n += 1
                    fs.fail_n += 1
                    anomalies.append(result)
                    if not result.warnings:
                        notable_results.append(result)
                if report_fp and not result.ok:
                    payload: Dict[str, Any] = {
                        "status": result.status,
                        "context": report_context.to_dict(),
                        "s3_dt": s3_dt,
                        "target_dt": target_dt,
                        "partition_dt": target_dt,
                        "jsonl_file": fname,
                        "jsonl_s3_uri": src,
                        "origin_id": result.origin_id,
                    }
                    if result.failures:
                        payload["field_diffs"] = [m.to_dict() for m in result.failures]
                    report_fp.write(json.dumps(localize_report_keys(payload), ensure_ascii=False) + "\n")
                if warning_report_fp and result.warnings:
                    warning_payload: Dict[str, Any] = {
                        "status": "warning",
                        "context": report_context.to_dict(),
                        "s3_dt": s3_dt,
                        "target_dt": target_dt,
                        "partition_dt": target_dt,
                        "jsonl_file": fname,
                        "jsonl_s3_uri": src,
                        "origin_id": result.origin_id,
                        "warnings": result.warnings,
                    }
                    warning_report_fp.write(
                        json.dumps(localize_report_keys(warning_payload), ensure_ascii=False) + "\n"
                    )
                if args.verbose_failures and (not result.ok or result.warnings):
                    tag = result.status if not result.ok else "WARN"
                    print(
                        f"\n[{tag}] {fname} origin_id={result.origin_id}"
                    )
                    for w in result.warnings:
                        print(f"  ! {w}")
                    for m in result.failures:
                        print(f"  - {m}")
            print(
                f"[进度] 已校验 {total} 条（通过 {ok_n} / 失败 {fail_n} / 缺失 {miss_n}"
                f" / warning {warn_n}）  当前: {fname}",
                file=sys.stderr,
            )

        if count_summary:
            count_summary.checked_rows = total
            print_count_summary(count_summary)

        print("\n" + "=" * 60)
        print("字段校验汇总")
        print("=" * 60)
        print(f"已校验行数 : {total:,}")
        print(f"通过       : {ok_n:,}")
        print(f"字段不一致 : {fail_n:,}")
        print(f"MySQL 缺失 : {miss_n:,}")
        print(f"Warning     : {warn_n:,}（license 超出可选值，不记为缺陷）")

        print_file_stats(per_file)
        print_anomaly_summary(notable_results, max_examples=args.max_show)

        if report_fp:
            print(f"\n完整异常报告: {report_path}")
        write_osi_report_summary(
            report_path,
            build_osi_report_summary(
                report_path=report_path,
                context=report_context,
                s3_dt=s3_dt,
                target_dt=target_dt,
                total=total,
                ok_n=ok_n,
                fail_n=fail_n,
                miss_n=miss_n,
                warn_n=warn_n,
                count_summary=count_summary,
                per_file=per_file,
                notable_results=notable_results,
            ),
        )
        print(f"汇总报告: {summary_paths(report_path)[0]}")
        count_ok = not count_summary or count_summary.s3_total == count_summary.mysql_total
        return 0 if fail_n == 0 and miss_n == 0 and count_ok else 1
    finally:
        mysql_session.close()
        if report_fp:
            report_fp.close()
        if warning_report_fp:
            warning_report_fp.close()


# ---- osi_verify/cli.py ----


import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence



def _nested(settings: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur: Any = settings
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _bool_default(settings: Dict[str, Any], *keys: str, default: bool = False) -> bool:
    return bool(_nested(settings, *keys, default=default))


def _merge_target_s3_settings(
    global_s3_settings: Dict[str, Any],
    target_s3_settings: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict(global_s3_settings)
    for key, value in target_s3_settings.items():
        if value is not None and value != "":
            merged[key] = value
    return merged


def _section_dict(settings: Dict[str, Any], key: str) -> Dict[str, Any]:
    value = settings.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _merged_arxiv_options(
    settings: Dict[str, Any],
    section: str,
    flat_keys: Sequence[str],
) -> Dict[str, Any]:
    arxiv_settings = _section_dict(settings, "osi_arxiv")
    merged = _section_dict(settings, section)
    merged.update(_section_dict(arxiv_settings, section))
    for key in flat_keys:
        if key in arxiv_settings and arxiv_settings[key] is not None:
            merged[key] = arxiv_settings[key]
    return merged


def main(argv: Optional[Sequence[str]] = None) -> int:
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument("--config", type=Path, default=DEFAULT_SETTINGS_JSON)
    config_args, remaining_argv = config_parser.parse_known_args(argv)
    settings = load_settings(config_args.config)
    target_config = load_arxiv_target_config(settings)
    mysql_settings = settings.get("mysql", {}) if isinstance(settings.get("mysql", {}), dict) else {}
    global_s3_settings = settings.get("s3", {}) if isinstance(settings.get("s3", {}), dict) else {}
    s3_settings = _merge_target_s3_settings(global_s3_settings, target_config.s3_settings)
    run_settings = _merged_arxiv_options(
        settings,
        "run",
        (
            "limit",
            "sequential",
            "full",
            "batch_size",
            "dry_run",
            "origin_ids",
            "partition_dt",
            "s3_dt",
            "target_dt",
            "skip_count",
            "count_only",
            "parquet_glob",
            "s3_path",
        ),
    )
    report_settings = _merged_arxiv_options(
        settings,
        "report",
        ("report_path", "summary_only", "verbose_failures", "max_show"),
    )
    retry_config = load_retry_config(settings)

    parser = argparse.ArgumentParser(description="校验 S3 arxiv 数据到论文源数据表的一致性")
    parser.add_argument("--config", type=Path, default=config_args.config, help="可选自动化配置文件")
    parser.add_argument("--mysql-config", type=Path, default=resolve_project_path(mysql_settings.get("config_file")) or PROJECT_ROOT / "mysql")
    parser.add_argument("--mapping-csv", type=Path, default=target_config.mapping_csv)
    parser.add_argument(
        "--database",
        default=target_config.database,
        help="库名（Iceberg 模式下为 schema，如 dws）",
    )
    parser.add_argument("--table", default=target_config.table)
    parser.add_argument(
        "--catalog",
        default=target_config.catalog if target_config.catalog is not None else mysql_settings.get("catalog", DEFAULT_ICEBERG_CATALOG),
        help="StarRocks Iceberg catalog（默认 lakehouse_iceberg）；传空字符串则用原生库连接",
    )
    parser.add_argument("--s3-config", type=Path, default=resolve_project_path(s3_settings.get("config_file")) or PROJECT_ROOT / "s3")
    parser.add_argument("--parquet-glob", default=run_settings.get("parquet_glob"))
    parser.add_argument("--s3-path", default=target_config.s3_path or s3_settings.get("path") or run_settings.get("s3_path"))
    parser.add_argument("--s3-subpath", default=target_config.s3_subpath or s3_settings.get("subpath"))
    parser.add_argument("--s3-format", choices=("auto", "jsonl", "parquet"), default=target_config.s3_format or s3_settings.get("format", "auto"))
    parser.add_argument(
        "--limit",
        type=int,
        default=int(run_settings.get("limit", 200)),
        help="抽样模式：每个 jsonl 随机抽查条数（默认 200）；与 --full 互斥",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        default=bool(run_settings.get("sequential", False)),
        help="顺序抽取：每个 jsonl 取文件开头前 N 条（配合 --limit，比随机抽样快）",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        default=bool(run_settings.get("full", False)),
        help="全量：读取分区内全部 jsonl 文件、全部行（分批处理）",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=int(run_settings.get("batch_size", 500)),
        help="全量模式每批处理条数（默认 500）",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=resolve_project_path(report_settings.get("path") or report_settings.get("report_path")) if (report_settings.get("path") or report_settings.get("report_path")) else None,
        help="将 FAIL/MISSING 记录写入 JSONL 报告文件",
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        default=bool(report_settings.get("summary_only", False)),
        help="兼容旧参数：当前默认仅打印汇总，不逐条打印失败详情",
    )
    parser.add_argument(
        "--verbose-failures",
        action="store_true",
        default=bool(report_settings.get("verbose_failures", False)),
        help="逐条打印 FAIL/WARN 明细；默认只打印错误类型汇总",
    )
    parser.add_argument("--license-map", type=Path, default=resolve_project_path(settings.get("license_map")) if settings.get("license_map") else None)
    parser.add_argument("--dry-run", action="store_true", default=bool(run_settings.get("dry_run", False)))
    parser.add_argument("--origin-id", action="append", default=run_settings.get("origin_ids"))
    parser.add_argument(
        "--partition-dt",
        default=run_settings.get("partition_dt"),
        help="兼容旧参数：同时作为 S3 分区和目标表分区默认值；建议改用 --s3-dt / --target-dt",
    )
    parser.add_argument(
        "--s3-dt",
        default=run_settings.get("s3_dt"),
        help="S3 数据分区日期；默认从 S3 path 中的 dt= 解析",
    )
    parser.add_argument(
        "--target-dt",
        default=run_settings.get("target_dt"),
        help="论文源数据表 dt；默认沿用 --partition-dt，未指定时再沿用 S3 dt",
    )
    parser.add_argument(
        "--skip-count",
        action="store_true",
        default=bool(run_settings.get("skip_count", False)),
        help="跳过 S3/MySQL 总量统计（大分区计数较慢）",
    )
    parser.add_argument(
        "--count-only",
        action="store_true",
        default=bool(run_settings.get("count_only", False)),
        help="仅做总量统计，不做字段级校验",
    )
    parser.add_argument(
        "--max-show",
        type=int,
        default=int(report_settings.get("max_show", 3)),
        help="错误类型汇总中每类最多展示多少个样例 origin_id",
    )
    parser.add_argument(
        "--retry-max-attempts",
        type=int,
        default=retry_config.max_attempts,
        help="连接/查询失败时的最大重试次数（含首次，默认 3）",
    )
    parser.add_argument(
        "--retry-initial-delay",
        type=float,
        default=retry_config.initial_delay_sec,
        help="重试初始等待秒数（默认 1.0）",
    )
    parser.add_argument(
        "--no-retry",
        action="store_true",
        help="禁用数据库与 S3 连接重试",
    )
    args = parser.parse_args(remaining_argv)
    if args.summary_only and "--verbose-failures" not in remaining_argv:
        args.verbose_failures = False
    if args.full:
        print("[info] 全量模式：读取分区内全部 jsonl，忽略 --limit", file=sys.stderr)
    if args.full and args.dry_run:
        print("[warn] 全量 dry-run 可能极慢，建议加 --summary-only", file=sys.stderr)

    if not args.mapping_csv.exists():
        print(f"映射文件不存在: {args.mapping_csv}", file=sys.stderr)
        return 2

    try:
        mapping_rules = load_mapping_rules(
            args.mapping_csv,
            target_column=target_config.mapping_target_column,
            source_column=target_config.mapping_source_column,
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    requested_compare_fields = compare_fields_from_rules(mapping_rules)
    print(
        f"目标 target={target_config.name} kind={target_config.kind} "
        f"transform={target_config.transform}"
    )
    print(
        f"已加载映射规则 {len(mapping_rules)} 条，启用字段校验 {len(requested_compare_fields)} 列"
    )
    license_map = dict(DEFAULT_LICENSE_MAP)
    if args.license_map:
        license_map.update(json.loads(args.license_map.read_text(encoding="utf-8")))
    effective_retry = RetryConfig(
        enabled=not args.no_retry and retry_config.enabled,
        max_attempts=args.retry_max_attempts,
        initial_delay_sec=args.retry_initial_delay,
        backoff_factor=retry_config.backoff_factor,
        max_delay_sec=retry_config.max_delay_sec,
    )
    try:
        return run_verification(
            args=args,
            target_config=target_config,
            mysql_settings=mysql_settings,
            s3_settings=s3_settings,
            mapping_rules=mapping_rules,
            requested_compare_fields=requested_compare_fields,
            license_map=license_map,
            retry_config=effective_retry,
        )
    except Exception as exc:
        if is_s3_retryable(exc):
            print(
                f"\n[S3 ERROR] {type(exc).__name__}: {exc}\n"
                "S3 连接重试已耗尽。若是内网 Ceph HTTPS 偶发断连，可重跑；"
                "抽样校验建议加 --sequential --skip-count 减少 HEAD/Range 请求。"
                "如果 endpoint 支持 HTTP，可在 evaluator parameters 中设置 use_ssl=false。",
                file=sys.stderr,
            )
            return 2
        raise



def init_config(path: Path) -> int:
    target = path.expanduser()
    if not target.is_absolute():
        target = Path.cwd() / target
    target.parent.mkdir(parents=True, exist_ok=True)
    source = PROJECT_ROOT / "config" / "settings.template.json"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"created config template: {target}")
    return 0


def arxiv_entry(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--init-config" in args:
        idx = args.index("--init-config")
        if idx + 1 < len(args) and not args[idx + 1].startswith("-"):
            return init_config(Path(args[idx + 1]))
        return init_config(DEFAULT_SETTINGS_JSON)
    return main(args)


from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule
from dingo.model.rule.scibase.report_utils import (
    bool_param,
    int_param,
    s3_path_from_dingo,
    write_temp_settings,
)


def _dingo_append_cli_option(argv: list[str], flag: str, value: Any) -> None:
    if value is not None and value != "":
        argv.extend([flag, str(value)])


def _dingo_append_cli_flag(argv: list[str], flag: str, enabled: bool) -> None:
    if enabled:
        argv.append(flag)


def _dingo_append_origin_ids(argv: list[str], value: Any) -> None:
    if value is None or value == "":
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _dingo_append_cli_option(argv, "--origin-id", item)
        return
    _dingo_append_cli_option(argv, "--origin-id", value)


@Model.rule_register(
    "QUALITY_BAD_EFFECTIVENESS",
    ["sci_base_qa_test", "meta_paper_data"],
)
class RuleSciBaseMetaPaperDataReport(BaseRule):
    _metric_info = {
        "category": "Rule-Based Metadata Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleSciBaseMetaPaperDataReport",
        "description": "Run SciBase S3 paper source-data validation and write reports.",
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
        config_path = write_temp_settings(params, include_s3=True)
        report_path = Path(params["report_path"]) if params.get("report_path") else None
        if report_path is None and params.get("output_dir"):
            report_path = Path(str(params["output_dir"])) / "source_field_mismatch.jsonl"

        s3_path = s3_path_from_dingo(params)
        parquet_glob = params.get("parquet_glob")
        if not s3_path and not parquet_glob:
            raise RuntimeError(
                "S3 path is required for RuleSciBaseMetaPaperDataReport. "
                "Set evaluator config parameters.s3_path, or run with dataset.source=s3 "
                "so input_path and dataset.s3_config.s3_bucket can be combined."
            )

        argv = [
            "--config",
            str(config_path),
            "--mapping-csv",
            str(params.get("mapping_csv") or ASSETS_DIR / "osi_arxiv_mapping.csv"),
            "--database",
            str(params.get("database") or "dws"),
            "--table",
            str(params.get("target_table") or params.get("table") or "dws_meta_paper_data_acc_d"),
        ]
        catalog = params.get("catalog", DEFAULT_ICEBERG_CATALOG)
        _dingo_append_cli_option(argv, "--catalog", catalog)
        _dingo_append_cli_option(argv, "--s3-path", s3_path)
        _dingo_append_cli_option(argv, "--s3-subpath", params.get("s3_subpath"))
        _dingo_append_cli_option(argv, "--s3-format", params.get("s3_format"))
        _dingo_append_cli_option(argv, "--parquet-glob", parquet_glob)
        _dingo_append_cli_option(argv, "--partition-dt", params.get("partition_dt"))
        _dingo_append_cli_option(argv, "--s3-dt", params.get("s3_dt"))
        _dingo_append_cli_option(argv, "--target-dt", params.get("target_dt"))
        _dingo_append_cli_option(argv, "--limit", int_param(params, "limit", 200))
        _dingo_append_cli_option(argv, "--batch-size", int_param(params, "batch_size", 500))
        _dingo_append_cli_option(argv, "--max-show", int_param(params, "max_show", 3))
        _dingo_append_cli_option(argv, "--report", report_path)
        _dingo_append_cli_option(argv, "--license-map", params.get("license_map"))
        _dingo_append_cli_option(argv, "--retry-max-attempts", params.get("retry_max_attempts"))
        _dingo_append_cli_option(argv, "--retry-initial-delay", params.get("retry_initial_delay"))
        _dingo_append_origin_ids(argv, params.get("origin_id") or params.get("origin_ids"))

        _dingo_append_cli_flag(argv, "--sequential", bool_param(params, "sequential", False))
        _dingo_append_cli_flag(argv, "--full", bool_param(params, "full", False))
        _dingo_append_cli_flag(argv, "--dry-run", bool_param(params, "dry_run", False))
        _dingo_append_cli_flag(argv, "--skip-count", bool_param(params, "skip_count", False))
        _dingo_append_cli_flag(argv, "--count-only", bool_param(params, "count_only", False))
        _dingo_append_cli_flag(argv, "--summary-only", bool_param(params, "summary_only", False))
        _dingo_append_cli_flag(argv, "--verbose-failures", bool_param(params, "verbose_failures", False))
        _dingo_append_cli_flag(argv, "--no-retry", bool_param(params, "no_retry", False))

        exit_code = main(argv)
        reason = [
            f"exit_code={exit_code}",
            str(report_path.parent if report_path else REPORT_ROOT),
        ]
        if exit_code != 0:
            return EvalDetail(
                metric=cls.__name__,
                status=True,
                label=[f"{cls.metric_type}.{cls.__name__}"],
                reason=reason,
            )
        return EvalDetail(metric=cls.__name__, label=[QualityLabel.QUALITY_GOOD], reason=reason)


if __name__ == "__main__":
    raise SystemExit(arxiv_entry())
