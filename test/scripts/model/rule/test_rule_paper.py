import json
from pathlib import Path

import pytest

from dingo.io.input import Data
from dingo.model.model import Model
from dingo.model.rule.scibase import base_check_paper, rule_paper, rule_quanliang
from dingo.model.rule.scibase.base_field_validation import BaseFieldValidation


def test_paper_reuses_checks_with_independent_mapping_and_config():
    paper = rule_paper.RulePaperFieldValidation
    quanliang = rule_quanliang.RuleQuanliangFieldValidation
    assert Model.get_rule_by_name(paper.__name__) is paper
    assert paper.__bases__ == (BaseFieldValidation,)
    assert quanliang.__bases__ == (BaseFieldValidation,)
    assert paper.eval is quanliang.eval
    assert paper.eval is BaseFieldValidation.eval
    assert paper.normalize_record.__func__ is BaseFieldValidation.normalize_record.__func__
    assert quanliang.normalize_record.__func__ is BaseFieldValidation.normalize_record.__func__
    assert paper.field_validators is not quanliang.field_validators
    assert paper.dynamic_config is not quanliang.dynamic_config
    assert paper.dynamic_config.key_list is not quanliang.dynamic_config.key_list
    assert paper.dynamic_config.key_list == list(paper.field_validators)
    assert quanliang.dynamic_config.key_list == list(quanliang.field_validators)
    for module in (rule_paper, rule_quanliang):
        for name, check in vars(module).items():
            if name.startswith("check_"):
                if module is rule_paper and name in {"check_access_is_oa", "check_access_oa_status"}:
                    assert check is not getattr(base_check_paper, name)
                    assert check.__module__ == rule_paper.__name__
                    continue
                assert check is getattr(base_check_paper, name)
                assert check.__module__ == base_check_paper.__name__

    data_path = Path(__file__).parents[3] / "data/scibase/rule_quanliang_cases.jsonl"
    for line in data_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        model = paper()
        model.dynamic_config = model.dynamic_config.model_copy(deep=True)
        model.dynamic_config.key_list = row["key_list"]
        result = model.eval(Data(**row["input"]))
        assert result.metric == "RulePaperFieldValidation"
        assert result.status is row["expected_status"], row["case"]
        assert result.label == row["expected_labels"], row["case"]
        assert (result.reason or []) == row["expected_reasons"], row["case"]


@pytest.mark.parametrize(
    "record, expected_label",
    [
        ({}, "missing_field"),
        ({"access_is_oa": None}, "null"),
        ({"access_is_oa": True}, "wrong_type"),
        ({"access_is_oa": False}, "wrong_type"),
        ({"access_is_oa": 1}, "wrong_type"),
        ({"access_is_oa": []}, "wrong_type"),
        ({"access_is_oa": {}}, "wrong_type"),
        ({"access_is_oa": ""}, "empty"),
        ({"access_is_oa": "True"}, "unsupported_value"),
        ({"access_is_oa": " true "}, "unsupported_value"),
        ({"access_is_oa": " "}, "unsupported_value"),
        ({"access_is_oa": "invalid"}, "unsupported_value"),
        ({"access_is_oa": "true"}, None),
        ({"access_is_oa": "false"}, None),
        ({"access_is_oa": "unknown"}, None),
    ],
)
@pytest.mark.parametrize(
    "metadata",
    [{}, {"metadata_type": "paper"}, {"metadata_type": "ebook"}, {"metadata_type": []}],
)
def test_paper_access_is_oa_basic_validation(record, expected_label, metadata):
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["access_is_oa"]
    result = model.eval(Data(**metadata, **record))
    assert result.status is (expected_label is not None)
    assert result.label == (
        [f"access_is_oa.{expected_label}"] if expected_label else ["QUALITY_GOOD"]
    )
    if expected_label:
        assert len(result.reason) == 1


@pytest.mark.parametrize("oa_flag", ["true", "false", "unknown"])
def test_paper_access_is_oa_is_independent_of_related_fields(oa_flag):
    record = {
        "metadata_type": "paper",
        "access_is_oa": oa_flag,
        "access_oa_status": "closed" if oa_flag == "true" else "gold",
        "access_oa_url": [] if oa_flag == "true" else ["https://example.com/paper.pdf"],
        "access_license": "cc-by",
    }
    assert rule_paper.RulePaperFieldValidation.field_validators["access_is_oa"](record) == (False, [], [])
    assert rule_quanliang.RuleQuanliangFieldValidation.field_validators["access_is_oa"](record)[0] is True


@pytest.mark.parametrize(
    "record, expected_label",
    [
        ({}, "missing_field"),
        ({"access_oa_status": None}, "null"),
        ({"access_oa_status": True}, "wrong_type"),
        ({"access_oa_status": 1}, "wrong_type"),
        ({"access_oa_status": []}, "wrong_type"),
        ({"access_oa_status": {}}, "wrong_type"),
        ({"access_oa_status": "Gold"}, "unsupported_value"),
        ({"access_oa_status": " gold "}, "unsupported_value"),
        ({"access_oa_status": " "}, "unsupported_value"),
        ({"access_oa_status": "unknown"}, "unsupported_value"),
    ],
)
def test_paper_access_oa_status_basic_validation(record, expected_label):
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["access_oa_status"]
    result = model.eval(Data(access_is_oa="false", **record))
    assert result.status is True
    assert result.label == [f"access_oa_status.{expected_label}"]
    assert len(result.reason) == 1


@pytest.mark.parametrize("status", ["diamond", "gold", "green", "hybrid", "bronze", "closed", ""])
@pytest.mark.parametrize("oa_flag", ["true", "false", "unknown", None, True, False, "invalid", []])
def test_paper_access_oa_status_consistency(status, oa_flag):
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["access_oa_status"]
    result = model.eval(Data(access_oa_status=status, access_is_oa=oa_flag))
    mismatch = (oa_flag == "false" and status != "closed") or (oa_flag == "true" and status == "closed")
    assert result.status is mismatch
    assert result.label == (
        ["access_oa_status.oa_status_mismatch"] if mismatch else ["QUALITY_GOOD"]
    )
    # Quanliang retains its independent basic status validator.
    assert rule_quanliang.RuleQuanliangFieldValidation.field_validators["access_oa_status"](
        {"access_oa_status": status, "access_is_oa": oa_flag}
    ) == (False, [], [])


def test_paper_check_can_be_replaced_independently(monkeypatch):
    assert rule_paper.check_title is rule_quanliang.check_title
    monkeypatch.setattr(
        rule_paper, "check_title",
        lambda value: (True, ["paper_specific"], ["paper title rejected"]),
    )
    model = rule_paper.RulePaperFieldValidation()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["title"]
    result = model.eval(Data(title="A clean title"))
    assert result.label == ["title.paper_specific"]
    assert result.reason == ["title: paper title rejected"]
    assert rule_quanliang.RuleQuanliangFieldValidation.field_validators["title"](
        {"title": "A clean title"}
    )[0] is False


def test_paper_class_mapping_can_be_replaced_independently(monkeypatch):
    paper = rule_paper.RulePaperFieldValidation
    quanliang = rule_quanliang.RuleQuanliangFieldValidation
    monkeypatch.setitem(
        paper.field_validators, "paper_field",
        lambda record: (True, ["invalid"], ["paper field rejected"]),
    )
    model = paper()
    model.dynamic_config = model.dynamic_config.model_copy(deep=True)
    model.dynamic_config.key_list = ["paper_field"]
    result = model.eval(Data(paper_field="value"))
    assert result.label == ["paper_field.invalid"]
    assert result.reason == ["paper_field: paper field rejected"]
    assert "paper_field" not in quanliang.field_validators
