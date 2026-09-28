import json
import re
from typing import Any, List

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io.input import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule

MAX_CLAIMS_LENGTH = 1_000_000
IPC_CODE_RE = re.compile(
    r"^(?P<section>[A-H])"
    r"(?P<class>0[1-9]|[1-9][0-9])"
    r"(?P<subclass>[A-Z]) "
    r"(?P<main_group>[1-9][0-9]{0,2})/"
    r"(?P<subgroup>[0-9]{2,6})$"
)
ValidationResult = tuple[bool, List[str], List[str]]


def check_claims(claims: Any) -> ValidationResult:
    claims_length = len(str(claims))
    if claims_length > MAX_CLAIMS_LENGTH:
        return (
            True,
            ["too_long"],
            [
                f"string length {claims_length} exceeds the maximum "
                f"of {MAX_CLAIMS_LENGTH}"
            ],
        )
    return False, [], []


def check_ipc_unified(ipc_unified: Any) -> ValidationResult:
    if ipc_unified is None:
        return True, ["null"], ["value is null"]

    if isinstance(ipc_unified, str):
        try:
            ipc_unified = json.loads(ipc_unified, strict=False)
        except json.JSONDecodeError:
            return True, ["invalid_json"], ["value must be a JSON array"]

    if not isinstance(ipc_unified, list):
        return True, ["wrong_type"], ["value must be a list"]

    error_labels: List[str] = []
    reasons: List[str] = []

    for index, ipc_code in enumerate(ipc_unified):
        if not isinstance(ipc_code, str):
            if "wrong_type" not in error_labels:
                error_labels.append("wrong_type")
            reasons.append(f"item[{index}] must be a string")
            continue

        match = IPC_CODE_RE.fullmatch(ipc_code)
        if match is None:
            if "invalid_format" not in error_labels:
                error_labels.append("invalid_format")
            reasons.append(
                f"item[{index}] value {ipc_code!r} must match IPC format "
                "'<A-H><01-99><A-Z> <1-999>/<2-6 digits>'"
            )
            continue

        subgroup = match.group("subgroup")
        if subgroup != "00" and int(subgroup) == 0:
            if "invalid_format" not in error_labels:
                error_labels.append("invalid_format")
            reasons.append(
                f"item[{index}] value {ipc_code!r} subgroup may be zero only "
                "when written as '00'"
            )

    return bool(error_labels), error_labels, reasons


FIELD_VALIDATORS = {
    "claims": lambda record: check_claims(record.get("claims")),
    "ipc_unified": lambda record: check_ipc_unified(record.get("ipc_unified")),
}


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["xinghe", "quanliang"])
class RulePatentFieldValidation(BaseRule):
    _metric_info = {
        "category": "Rule-Based Metadata Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RulePatentFieldValidation",
        "description": "Validate patent metadata fields and report invalid fields",
        "paper_title": "",
        "paper_url": "",
        "paper_authors": "",
        "evaluation_results": "",
    }

    _required_fields = []
    dynamic_config = EvaluatorRuleArgs(key_list=list(FIELD_VALIDATORS.keys()))

    def eval(self, input_data: Data) -> EvalDetail:
        res = EvalDetail(metric=self.__class__.__name__)
        record = input_data.to_dict()
        selected_fields = self.dynamic_config.key_list or []
        bad_fields: List[str] = []
        reasons: List[str] = []

        for field in selected_fields:
            if field not in FIELD_VALIDATORS:
                bad_fields.append(f"{field}.unsupported_field")
                reasons.append(f"{field}: unsupported field")
                continue
            if field not in record:
                bad_fields.append(f"{field}.missing_field")
                reasons.append(f"{field}: missing field")
                continue
            invalid, error_labels, detail_reasons = FIELD_VALIDATORS[field](record)
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
