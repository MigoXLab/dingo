import json
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl


def load_scibase_parameters(params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(params or {})


def datasource_note() -> Dict[str, str]:
    return {
        "source": "dingo dataset datasource",
        "connection_config": "dataset.sql_config or dataset.s3_config",
        "input_config": "input_path",
    }


def table_params(params: Dict[str, Any], defaults: Dict[str, str]) -> Dict[str, Any]:
    result = dict(defaults)
    for key in (
        "dt",
        "s3_dt",
        "target_dt",
        "paper_dt",
        "ebook_dt",
        "source_table",
        "target_table",
        "paper_table",
        "ebook_table",
        "xinghe_table",
    ):
        if params.get(key) is not None:
            result[key] = params[key]
    return result


def dingo_sql_config(params: Dict[str, Any]) -> Dict[str, Any]:
    config = dict(params.get("_dingo_dataset_sql_config") or params.get("sql_config") or {})
    if not config.get("host") or not config.get("username"):
        raise RuntimeError(
            "SQL config is required for this SciBase validator. "
            "Set dataset.sql_config in the Dingo input config."
        )
    return config


def dingo_s3_config(params: Dict[str, Any]) -> Dict[str, Any]:
    config = dict(params.get("_dingo_dataset_s3_config") or params.get("s3_config") or {})
    return config


def s3_path_from_dingo(params: Dict[str, Any]) -> Optional[str]:
    explicit_path = params.get("s3_path")
    if explicit_path:
        return str(explicit_path)

    s3_config = dingo_s3_config(params)
    input_path = params.get("_dingo_input_path")
    if input_path:
        input_path_str = str(input_path).strip()
        if input_path_str.startswith("s3://"):
            return input_path_str
        if params.get("_dingo_dataset_source") == "s3":
            bucket = str(s3_config.get("s3_bucket") or "").strip().strip("/")
            if bucket:
                return f"s3://{bucket}/{input_path_str.lstrip('/')}"

    bucket = str(s3_config.get("s3_bucket") or "").strip().strip("/")
    if bucket and params.get("s3_subpath"):
        return f"s3://{bucket}/"
    return None


def _connect_args_dict(raw: Any) -> Dict[str, str]:
    if not raw:
        return {}
    text = str(raw)
    if text.startswith("?"):
        text = text[1:]
    return dict(parse_qsl(text, keep_blank_values=True))


def mysql_settings_from_dingo(params: Dict[str, Any]) -> Dict[str, Any]:
    sql_config = dingo_sql_config(params)
    connect_args = _connect_args_dict(sql_config.get("connect_args"))
    settings = {
        "host": sql_config.get("host"),
        "port": int(sql_config.get("port") or 0),
        "user": sql_config.get("username"),
        "password": sql_config.get("password"),
        "database": sql_config.get("database") or "dws",
        "charset": connect_args.get("charset", "utf8mb4"),
    }
    for key in ("catalog", "connect_timeout", "read_timeout", "read_timeout_sec"):
        if params.get(key) is not None:
            settings[key] = params[key]
    return settings


def s3_settings_from_dingo(params: Dict[str, Any]) -> Dict[str, Any]:
    s3_config = dingo_s3_config(params)
    endpoint = str(s3_config.get("s3_endpoint_url") or "").rstrip("/")
    if endpoint.startswith("https://"):
        endpoint = endpoint[len("https://"):]
    elif endpoint.startswith("http://"):
        endpoint = endpoint[len("http://"):]
    settings = {
        "endpoint": endpoint,
        "access_key": s3_config.get("s3_ak"),
        "secret_key": s3_config.get("s3_sk"),
        "path": s3_path_from_dingo(params),
        "format": params.get("s3_format", "auto"),
    }
    if params.get("s3_subpath") is not None:
        settings["subpath"] = params["s3_subpath"]
    for key in ("use_ssl", "verify_ssl"):
        if params.get(key) is not None:
            settings[key] = params[key]
        elif s3_config.get(key) is not None:
            settings[key] = s3_config[key]
    return settings


def write_temp_settings(params: Dict[str, Any], *, include_s3: bool = False) -> Path:
    payload: Dict[str, Any] = {
        "mysql": mysql_settings_from_dingo(params),
        "retry": params.get("retry", {}),
    }
    if include_s3:
        payload["s3"] = s3_settings_from_dingo(params)
        payload["osi_arxiv"] = {
            "s3": payload["s3"],
            "mapping_csv": params.get("mapping_csv"),
            "target_table": params.get("target_table"),
            "database": params.get("database"),
            "catalog": params.get("catalog"),
        }
    temp = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        suffix=".json",
        prefix="dingo_scibase_",
        delete=False,
    )
    with temp:
        json.dump(payload, temp, ensure_ascii=False, indent=2)
    return Path(temp.name)


def int_param(params: Dict[str, Any], key: str, default: int) -> int:
    value = params.get(key, default)
    return default if value is None else int(value)


def bool_param(params: Dict[str, Any], key: str, default: bool = False) -> bool:
    value = params.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)
