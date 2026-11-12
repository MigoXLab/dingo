"""Shared execution and result helpers for field-based metadata validation."""

import json
import re
from typing import Any, Callable

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io.input import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.rule.base import BaseRule

# (是否无效, 错误标签列表, 错误原因列表)。False 表示校验通过；
# 标签和原因由字段检查函数返回，eval() 再统一添加字段名前缀。
ValidationResult = tuple[bool, list[str], list[str]]


class BaseFieldValidation(BaseRule):
    # 子类提供字段映射，并根据映射创建独立的 dynamic_config。
    field_validators: dict[str, Callable[[dict[str, Any]], ValidationResult]]

    _required_fields = []
    dynamic_config: EvaluatorRuleArgs

    @staticmethod
    def _ok() -> ValidationResult:
        return False, [], []

    @staticmethod
    def _fail(error_label: str, reason: str) -> ValidationResult:
        return True, [error_label], [reason]

    @staticmethod
    def _normalize_json_like_field(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            return value
        if stripped[0] not in ("[", "{"):
            return value
        try:
            return json.loads(stripped)
        except (TypeError, ValueError, json.JSONDecodeError):
            cleaned = stripped.replace("\r", " ").replace("\n", " ").replace("\t", " ")
            cleaned = "".join(ch if ord(ch) >= 32 else " " for ch in cleaned)
            invalid_escape_re = re.compile(r'\\(?!["\\/bfnrtu])')
            for _ in range(10):
                next_cleaned = invalid_escape_re.sub(r"\\\\", cleaned)
                if next_cleaned == cleaned:
                    break
                cleaned = next_cleaned
            try:
                return json.loads(cleaned)
            except (TypeError, ValueError, json.JSONDecodeError):
                return value

    @staticmethod
    def _normalize_bool_field(value: Any) -> Any:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            if value in (0, 1):
                return bool(value)
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("1", "true"):
                return True
            if lowered in ("0", "false"):
                return False
        return value

    @classmethod
    def normalize_record(cls, record: dict[str, Any]) -> dict[str, Any]:
        """复制记录并归一化 JSON、布尔值；子类可重写以提供特殊处理。"""
        json_list_fields = {
            "isbns", "author", "contributors", "locations", "access_oa_url",
            "publication_venue_issn", "references", "related_works", "citations",
            "supplementary_material",
        }
        json_object_fields = {"primary_location", "best_oa_location"}
        normalized = dict(record)
        for field in json_list_fields | json_object_fields:
            if field in normalized:
                normalized[field] = cls._normalize_json_like_field(normalized.get(field))
        normalized["access_xinghe_repository_has_fulltext"] = cls._normalize_bool_field(
            normalized.get("access_xinghe_repository_has_fulltext")
        )
        return normalized

    def eval(self, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=self.__class__.__name__)
        normalized = self.normalize_record(input_data.to_dict())
        selected_fields = self.dynamic_config.key_list or []
        bad_fields: list[str] = []
        reasons: list[str] = []
        for field in selected_fields:
            if field not in self.field_validators:
                bad_fields.append(f"{field}.unsupported_field")
                reasons.append(f"{field}: unsupported field")
                continue
            if field not in normalized:
                bad_fields.append(f"{field}.missing_field")
                reasons.append(f"{field}: missing field")
                continue
            invalid, error_labels, detail_reasons = self.field_validators[field](normalized)
            if invalid:
                bad_fields.extend(f"{field}.{error_label}" for error_label in error_labels)
                reasons.extend(f"{field}: {reason}" for reason in detail_reasons)

        if bad_fields:
            res.status = True
            res.label = bad_fields
            res.reason = reasons
        else:
            res.label = [QualityLabel.QUALITY_GOOD]
        return res
