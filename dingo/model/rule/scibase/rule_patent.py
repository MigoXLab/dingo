from typing import Any, List

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io.input import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule


MAX_CLAIMS_LENGTH = 1_000
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


FIELD_VALIDATORS = {
    "claims": lambda record: check_claims(record.get("claims")),
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
