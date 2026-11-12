import json
from pathlib import Path

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
