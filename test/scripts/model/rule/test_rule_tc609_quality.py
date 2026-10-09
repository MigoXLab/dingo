import pytest

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.io.input import RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.guobiao import rule_tc609_quality, rule_tc609_quality_base
from dingo.model.rule.guobiao.rule_tc609_quality import (Rule_TC609_0201_FormatCompliance, Rule_TC609_0202_SafetyCompliance, Rule_TC609_0203_AnnotationCompliance,
                                                         Rule_TC609_0204_StructuralCompleteness, Rule_TC609_0205_ContentAuthenticity, Rule_TC609_0206_ContentConsistency,
                                                         Rule_TC609_0208_ContentCleanliness, Rule_TC609_0301_ContentDiversity)
from dingo.model.rule.rule_common import RuleWatermark


def test_format_compliance_accepts_matching_record(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0201_FormatCompliance,
        "dynamic_config",
        EvaluatorRuleArgs(
            field_schema={
                "data_id": "str",
                "content": "str",
                "type": "str",
                "dt": "str",
            }
        ),
    )

    result = Rule_TC609_0201_FormatCompliance.eval(
        Data(
            data_id="demo-001",
            content="example",
            type="medical",
            dt="2026-07-20 09:00:00",
        )
    )

    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]


def test_format_compliance_default_schema_matches_tc609_metadata():
    assert Rule_TC609_0201_FormatCompliance.dynamic_config.field_schema == {
        "id": "str",
        "rid": "Optional[list]",
        "data_content": "list",
        "annotation": "Optional[dict]",
        "original_time": "str",
        "last_modified_time": "str",
        "version": "str",
        "license": "str",
        "source": "str",
        "source_details": "str",
        "generated_data_indicator": "int",
    }

    result = Rule_TC609_0201_FormatCompliance.eval(
        Data(
            id="d6c9a4d5e57597df8fe30f09ae44c985",
            rid=None,
            data_content=[
                {
                    "media_type": "image",
                    "content": "../data/images/streetscape.jpg",
                }
            ],
            annotation=None,
            original_time="2025-1-1",
            last_modified_time="2025-1-1",
            version="1.0.0-alpha",
            license="其他",
            source="互联网",
            source_details="https://example.com/image.jpg",
            generated_data_indicator=0,
        )
    )

    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]


def test_format_compliance_default_schema_requires_mandatory_fields():
    result = Rule_TC609_0201_FormatCompliance.eval(
        Data(
            id="dataset-id",
            data_content={},
        )
    )

    assert result.status is True
    assert "data_content: expected list, got dict" in result.reason
    assert "rid: required field is missing" in result.reason
    assert "annotation: required field is missing" in result.reason
    assert "original_time: required field is missing" in result.reason


def test_format_compliance_reports_missing_and_wrong_type(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0201_FormatCompliance,
        "dynamic_config",
        EvaluatorRuleArgs(
            field_schema={
                "data_id": "str",
                "content": "str",
                "dt": "str",
            }
        ),
    )

    result = Rule_TC609_0201_FormatCompliance.eval(
        Data(data_id=1, content="example")
    )

    assert result.status is True
    assert result.label == [
        "QUALITY_BAD.Rule_TC609_0201_FormatCompliance"
    ]
    assert result.reason == [
        "data_id: expected str, got int",
        "dt: required field is missing",
    ]


def test_format_compliance_reports_unexpected_fields(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0201_FormatCompliance,
        "dynamic_config",
        EvaluatorRuleArgs(
            field_schema={"content": "str"},
            allow_extra=False,
        ),
    )

    result = Rule_TC609_0201_FormatCompliance.eval(
        Data(content="example", source="demo")
    )

    assert result.status is True
    assert result.reason == ["source: unexpected field"]


def test_format_compliance_allows_unexpected_fields_by_default(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0201_FormatCompliance,
        "dynamic_config",
        EvaluatorRuleArgs(field_schema={"content": "str"}),
    )

    result = Rule_TC609_0201_FormatCompliance.eval(
        Data(content="example", source="demo")
    )

    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]


@pytest.mark.parametrize(
    "value, type_name",
    [
        (None, "Optional[str]"),
        ("text", "Optional[str]"),
        (None, "Optional[int]"),
        (1, "Optional[int]"),
        (None, "Optional[float]"),
        (1.5, "Optional[float]"),
        (None, "Optional[bool]"),
        (True, "Optional[bool]"),
        (None, "Optional[list]"),
        ([], "Optional[list]"),
        (None, "Optional[dict]"),
        ({}, "Optional[dict]"),
    ],
)
def test_format_compliance_accepts_optional_types(
    monkeypatch, value, type_name
):
    monkeypatch.setattr(
        Rule_TC609_0201_FormatCompliance,
        "dynamic_config",
        EvaluatorRuleArgs(field_schema={"value": type_name}),
    )

    result = Rule_TC609_0201_FormatCompliance.eval(Data(value=value))

    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]


def test_format_compliance_still_requires_optional_field(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0201_FormatCompliance,
        "dynamic_config",
        EvaluatorRuleArgs(field_schema={"value": "Optional[str]"}),
    )

    result = Rule_TC609_0201_FormatCompliance.eval(Data())

    assert result.status is True
    assert result.reason == ["value: required field is missing"]


@pytest.mark.parametrize(
    "schema, error",
    [
        (None, "requires a non-empty dynamic_config.field_schema"),
        ({}, "requires a non-empty dynamic_config.field_schema"),
        ({"content": "string"}, "Unsupported schema type"),
        ({"content": {"type": "str"}}, "Unsupported schema type"),
        ({"content": "optional_string"}, "Unsupported schema type"),
        ({"content": "optional_str"}, "Unsupported schema type"),
        ({"content": "optional[str]"}, "Unsupported schema type"),
        ({"content": "typing.Optional[str]"}, "Unsupported schema type"),
        ({"content": "optianal[str]"}, "Unsupported schema type"),
    ],
)
def test_format_compliance_rejects_invalid_schema(monkeypatch, schema, error):
    monkeypatch.setattr(
        Rule_TC609_0201_FormatCompliance,
        "dynamic_config",
        EvaluatorRuleArgs(field_schema=schema),
    )

    with pytest.raises(ValueError, match=error):
        Rule_TC609_0201_FormatCompliance.eval(Data(content="example"))


def test_safety_compliance_passes_words_config_to_unsafe_rule(monkeypatch):
    class UnsafeWordsRule:
        dynamic_config = EvaluatorRuleArgs()
        _unsafe_words_list = None
        _unsafe_words_automaton = None

        @classmethod
        def eval(cls, input_data):
            if "unsafe" in cls.dynamic_config.key_list:
                return EvalDetail(
                    metric=cls.__name__,
                    status=True,
                    label=["QUALITY_BAD_SECURITY.UnsafeWordsRule"],
                    reason=["unsafe"],
                )
            return EvalDetail(
                metric=cls.__name__,
                label=[QualityLabel.QUALITY_GOOD],
            )

    class PassingRule:
        @classmethod
        def eval(cls, input_data):
            return EvalDetail(
                metric=cls.__name__,
                label=[QualityLabel.QUALITY_GOOD],
            )

    component_map = {
        Rule_TC609_0202_SafetyCompliance.component_rules[0]: UnsafeWordsRule,
        Rule_TC609_0202_SafetyCompliance.component_rules[1]: PassingRule,
        Rule_TC609_0202_SafetyCompliance.component_rules[2]: PassingRule,
    }
    monkeypatch.setattr(
        Rule_TC609_0202_SafetyCompliance,
        "_resolve_rule",
        classmethod(lambda cls, path: component_map[path]),
    )
    monkeypatch.setattr(
        Rule_TC609_0202_SafetyCompliance,
        "dynamic_config",
        EvaluatorRuleArgs(key_list=["unsafe"], refer_path=[]),
    )

    result = Rule_TC609_0202_SafetyCompliance.eval(
        Data(
            data_content=[
                {"media_type": "text", "content": "safe"},
                {"media_type": "image", "content": "unsafe"},
                {"media_type": "text", "content": "unsafe"},
            ]
        )
    )

    assert UnsafeWordsRule.dynamic_config.key_list == ["unsafe"]
    assert result.status is True
    assert result.reason == ["UnsafeWordsRule: unsafe"]


def test_safety_compliance_has_usable_default_words(monkeypatch):
    from dingo.model.rule.rule_common import RuleUnsafeWords

    assert Rule_TC609_0202_SafetyCompliance.dynamic_config.key_list
    monkeypatch.setattr(RuleUnsafeWords, "_unsafe_words_list", None)
    monkeypatch.setattr(RuleUnsafeWords, "_unsafe_words_automaton", None)

    result = Rule_TC609_0202_SafetyCompliance.eval(
        Data(
            data_content=[
                {
                    "media_type": "text",
                    "content": "该内容提供制作炸弹的具体步骤",
                }
            ]
        )
    )

    assert result.status is True
    assert "RuleUnsafeWords: 制作炸弹" in result.reason


def test_safety_compliance_requires_text_content():
    result = Rule_TC609_0202_SafetyCompliance.eval(
        Data(
            data_content=[
                {"media_type": "image", "content": "制作炸弹"}
            ]
        )
    )

    assert result.status is True
    assert result.reason == [
        "data_content: at least one text item is required"
    ]


def test_safety_compliance_declares_data_content():
    assert Rule_TC609_0202_SafetyCompliance._required_fields == [
        RequiredField.DATA_CONTENT
    ]


def test_annotation_compliance_accepts_valid_metadata():
    result = Rule_TC609_0203_AnnotationCompliance.eval(
        Data(
            annotation={
                "label": [
                    {
                        "iscrowd": 0,
                        "bbox": [20, 20, 20, 20],
                        "category": "human",
                    }
                ],
                "annotation_method": "人工标注",
                "annotator": "普通标注员",
            }
        )
    )

    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]


def test_annotation_compliance_accepts_none_for_unannotated_data():
    result = Rule_TC609_0203_AnnotationCompliance.eval(
        Data(annotation=None)
    )

    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]


def test_annotation_compliance_declares_required_field():
    assert Rule_TC609_0203_AnnotationCompliance._required_fields == [
        RequiredField.ANNOTATION
    ]


def test_annotation_compliance_reports_invalid_nested_metadata():
    result = Rule_TC609_0203_AnnotationCompliance.eval(
        Data(
            annotation={
                "label": [],
                "annotation_method": "众包标注",
                "annotator": 1,
            }
        )
    )

    assert result.status is True
    assert result.reason == [
        "annotation.label: empty value is not allowed",
        (
            "annotation.annotation_method: unsupported value '众包标注'; "
            "allowed values: 人工标注, 其他, 半自动标注, 自动标注"
        ),
        "annotation.annotator: expected str or None, got int",
    ]


def test_annotation_compliance_requires_all_nested_fields():
    result = Rule_TC609_0203_AnnotationCompliance.eval(
        Data(annotation={})
    )

    assert result.status is True
    assert result.reason == [
        "annotation.label: required field is missing",
        "annotation.annotation_method: required field is missing",
        "annotation.annotator: required field is missing",
    ]


def test_content_cleanliness_propagates_empty_watermark_config(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0208_ContentCleanliness,
        "dynamic_config",
        EvaluatorRuleArgs(key_list=[]),
    )

    with pytest.raises(
        ValueError,
        match="RuleWatermark requires non-empty dynamic_config.key_list",
    ):
        Rule_TC609_0208_ContentCleanliness.eval(
            Data(
                data_content=[
                    {"media_type": "text", "content": "safe text"}
                ]
            )
        )


def test_content_cleanliness_passes_key_list_to_watermark(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0208_ContentCleanliness,
        "dynamic_config",
        EvaluatorRuleArgs(key_list=["DINGO-WATERMARK"]),
    )
    monkeypatch.setattr(
        RuleWatermark,
        "dynamic_config",
        EvaluatorRuleArgs(key_list=["stale-value"]),
    )

    result = Rule_TC609_0208_ContentCleanliness.eval(
        Data(
            data_content=[
                {"media_type": "text", "content": "text with"},
                {"media_type": "image", "content": "DINGO-WATERMARK"},
                {"media_type": "text", "content": "DINGO-WATERMARK"},
            ]
        )
    )

    assert RuleWatermark.dynamic_config.key_list == ["DINGO-WATERMARK"]
    assert result.status is True
    assert result.reason == ["RuleWatermark: DINGO-WATERMARK"]


def test_content_cleanliness_returns_good_without_watermark(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0208_ContentCleanliness,
        "dynamic_config",
        EvaluatorRuleArgs(key_list=["DINGO-WATERMARK"]),
    )

    result = Rule_TC609_0208_ContentCleanliness.eval(
        Data(
            data_content=[
                {"media_type": "text", "content": "ordinary"},
                {"media_type": "text", "content": "clean text"},
                {"media_type": "image", "content": "DINGO-WATERMARK"},
            ]
        )
    )

    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]


def test_content_cleanliness_has_usable_default_watermarks(monkeypatch):
    assert Rule_TC609_0208_ContentCleanliness.dynamic_config.key_list

    result = Rule_TC609_0208_ContentCleanliness.eval(
        Data(
            data_content=[
                {
                    "media_type": "text",
                    "content": "本文版权所有，未经授权不得转载。",
                }
            ]
        )
    )

    assert result.status is True
    assert "RuleWatermark: 版权所有" in result.reason


def test_content_cleanliness_requires_text_content():
    result = Rule_TC609_0208_ContentCleanliness.eval(
        Data(
            data_content=[
                {"media_type": "image", "content": "image.png"}
            ]
        )
    )

    assert result.status is True
    assert result.reason == [
        "data_content: at least one text item is required"
    ]


def test_structural_completeness_accepts_present_values(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0204_StructuralCompleteness,
        "dynamic_config",
        EvaluatorRuleArgs(
            key_list=["content", "labels", "metadata"],
            allow_none=False,
            allow_empty=False,
        ),
    )

    result = Rule_TC609_0204_StructuralCompleteness.eval(
        Data(content="example", labels=["valid"], metadata={"source": "demo"})
    )

    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]


def test_structural_completeness_has_tc609_required_fields_by_default():
    assert Rule_TC609_0204_StructuralCompleteness.dynamic_config.key_list == [
        "id",
        "data_content",
        "original_time",
        "last_modified_time",
        "version",
        "license",
        "source",
        "source_details",
        "generated_data_indicator",
    ]

    result = Rule_TC609_0204_StructuralCompleteness.eval(
        Data(
            id="dataset-id",
            data_content=[{"media_type": "text", "content": "example"}],
            original_time="2025-01-01",
            last_modified_time="2025-01-01",
            version="1.0.0",
            license="其他",
            source="互联网",
            source_details="https://example.com/data",
            generated_data_indicator=0,
        )
    )

    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]


def test_structural_completeness_reports_missing_none_and_empty(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0204_StructuralCompleteness,
        "dynamic_config",
        EvaluatorRuleArgs(
            key_list=["missing", "nullable", "text", "items", "metadata"],
            allow_none=False,
            allow_empty=False,
        ),
    )

    result = Rule_TC609_0204_StructuralCompleteness.eval(
        Data(nullable=None, text="", items=[], metadata={})
    )

    assert result.status is True
    assert result.reason == [
        "missing: required field is missing",
        "nullable: None is not allowed",
        "text: empty value is not allowed",
        "items: empty value is not allowed",
        "metadata: empty value is not allowed",
    ]


def test_structural_completeness_allows_none_and_empty(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0204_StructuralCompleteness,
        "dynamic_config",
        EvaluatorRuleArgs(
            key_list=["nullable", "text", "items", "metadata"],
            allow_none=True,
            allow_empty=True,
        ),
    )

    result = Rule_TC609_0204_StructuralCompleteness.eval(
        Data(nullable=None, text="", items=[], metadata={})
    )

    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]


def test_structural_completeness_requires_key_list(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0204_StructuralCompleteness,
        "dynamic_config",
        EvaluatorRuleArgs(
            key_list=[],
            allow_none=False,
            allow_empty=False,
        ),
    )

    with pytest.raises(ValueError, match="non-empty dynamic_config.key_list"):
        Rule_TC609_0204_StructuralCompleteness.eval(Data(content="example"))


@pytest.mark.parametrize(
    "source_details",
    [
        "https://example.com/data/1",
        "http://localhost:8080/record?id=1",
    ],
)
def test_content_authenticity_accepts_valid_internet_url(source_details):
    result = Rule_TC609_0205_ContentAuthenticity.eval(
        Data(source="互联网", source_details=source_details)
    )

    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]


def test_content_authenticity_accepts_non_url_source_details():
    result = Rule_TC609_0205_ContentAuthenticity.eval(
        Data(
            source="图书",
            source_details="ISBN 978-7-121-15535-2，第 10 页",
        )
    )

    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]


@pytest.mark.parametrize(
    "source, source_details, reason",
    [
        (None, "detail", "source: expected a non-empty string"),
        ("", "detail", "source: expected a non-empty string"),
        ("图书", None, "source_details: expected a non-empty string"),
        ("图书", "", "source_details: expected a non-empty string"),
    ],
)
def test_content_authenticity_rejects_empty_source_metadata(
    source, source_details, reason
):
    result = Rule_TC609_0205_ContentAuthenticity.eval(
        Data(source=source, source_details=source_details)
    )

    assert result.status is True
    assert result.reason == [reason]


@pytest.mark.parametrize(
    "source, source_details",
    [
        ("互联网", "example.com/data/1"),
        ("互联网", "ftp://example.com/data/1"),
        ("互联网", "https://"),
        ("互联网", "https://exa mple.com/data/1"),
        ("互联网", "https://example.com:invalid/data/1"),
    ],
)
def test_content_authenticity_rejects_invalid_url(source, source_details):
    result = Rule_TC609_0205_ContentAuthenticity.eval(
        Data(source=source, source_details=source_details)
    )

    assert result.status is True
    assert result.reason == [
        "source_details: expected a valid HTTP or HTTPS URL"
    ]


def test_content_authenticity_declares_required_fields():
    assert Rule_TC609_0205_ContentAuthenticity._required_fields == [
        RequiredField.SOURCE,
        RequiredField.SOURCE_DETAILS,
    ]


def test_content_consistency_accepts_consistent_text_items(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0206_ContentConsistency,
        "dynamic_config",
        EvaluatorRuleArgs(
            threshold=0.5,
            model="test-model",
            device=-1,
        ),
    )
    monkeypatch.setattr(
        rule_tc609_quality,
        "calculate_text_consistency",
        lambda **kwargs: {
            "score": 0.85,
            "is_consistent": True,
            "item_scores": [0.9, 0.85, 0.8],
            "outlier_indexes": [],
        },
    )

    result = Rule_TC609_0206_ContentConsistency.eval(
        Data(
            data_content=[
                {"media_type": "text", "content": "海底管道砂袋防护"},
                {"media_type": "image", "content": "pipeline.jpg"},
                {"media_type": "text", "content": "砂袋用于保护海底管道"},
                {"media_type": "text", "content": "模拟砂袋周围流场"},
            ]
        )
    )

    assert result.status is False
    assert result.score == 0.85
    assert result.label == [QualityLabel.QUALITY_GOOD]


def test_content_consistency_rejects_inconsistent_text_items(monkeypatch):
    monkeypatch.setattr(
        Rule_TC609_0206_ContentConsistency,
        "dynamic_config",
        EvaluatorRuleArgs(
            threshold=0.5,
            model="test-model",
            device=-1,
        ),
    )
    monkeypatch.setattr(
        rule_tc609_quality,
        "calculate_text_consistency",
        lambda **kwargs: {
            "score": 0.2,
            "is_consistent": False,
            "item_scores": [0.9, 0.2],
            "outlier_indexes": [1],
        },
    )

    result = Rule_TC609_0206_ContentConsistency.eval(
        Data(
            data_content=[
                {"media_type": "text", "content": "健康知识"},
                {"media_type": "image", "content": "health.jpg"},
                {"media_type": "text", "content": "金融市场"},
            ]
        )
    )

    assert result.status is True
    assert result.score == 0.2
    assert result.reason == [
        "Text items in data_content are inconsistent "
        "(score: 0.2000, threshold: 0.5000, outlier indexes: [2])"
    ]


def test_content_consistency_skips_comparison_for_one_text_item():
    result = Rule_TC609_0206_ContentConsistency.eval(
        Data(
            data_content=[
                {"media_type": "text", "content": "文本内容"},
                {"media_type": "image", "content": "image.jpg"},
            ]
        )
    )

    assert result.status is False
    assert result.score is None
    assert result.label == [QualityLabel.QUALITY_GOOD]


@pytest.mark.parametrize(
    "data, reason",
    [
        (
            Data(data_content=[]),
            "data_content: expected a non-empty list",
        ),
        (
            Data(data_content=["text"]),
            "data_content[0]: expected dict, got str",
        ),
        (
            Data(data_content=[{"media_type": ["text"], "content": "文本"}]),
            "data_content[0].media_type: expected a non-empty string",
        ),
        (
            Data(data_content=[{"media_type": "text", "content": ""}]),
            (
                "data_content[0].content: "
                "expected a non-empty string for text media"
            ),
        ),
    ],
)
def test_content_consistency_rejects_invalid_data_content(data, reason):
    result = Rule_TC609_0206_ContentConsistency.eval(data)

    assert result.status is True
    assert result.reason == [reason]


def test_calculate_text_consistency_compares_two_texts_directly(monkeypatch):
    torch = pytest.importorskip("torch")

    monkeypatch.setattr(
        rule_tc609_quality_base,
        "_encode_texts",
        lambda *args, **kwargs: torch.tensor(
            [[1.0, 0.0], [0.8, 0.6]]
        ),
    )

    result = rule_tc609_quality_base.calculate_text_consistency(
        ["标题", "摘要"],
        model_name="test-model",
        threshold=0.75,
    )

    assert result["score"] == pytest.approx(0.8)
    assert result["is_consistent"] is True
    assert result["outlier_indexes"] == []


def test_calculate_text_consistency_uses_robust_center(monkeypatch):
    torch = pytest.importorskip("torch")

    encoded = torch.tensor(
        [
            [1.0, 0.0],
            [0.99, 0.1],
            [0.98, -0.1],
            [0.97, 0.05],
            [0.0, 1.0],
        ]
    )
    encoded = torch.nn.functional.normalize(encoded, p=2, dim=1)
    monkeypatch.setattr(
        rule_tc609_quality_base,
        "_encode_texts",
        lambda *args, **kwargs: encoded,
    )

    result = rule_tc609_quality_base.calculate_text_consistency(
        ["文本1", "文本2", "文本3", "文本4", "离群文本"],
        model_name="test-model",
        threshold=0.5,
        consensus_keep_ratio=0.8,
    )

    assert result["score"] < 0.5
    assert result["is_consistent"] is False
    assert result["outlier_indexes"] == [4]


def test_content_consistency_declares_data_content_required():
    assert Rule_TC609_0206_ContentConsistency._required_fields == [
        RequiredField.DATA_CONTENT
    ]


def test_uncovered_rule_is_explicit_placeholder():
    assert Rule_TC609_0301_ContentDiversity.group == []
    with pytest.raises(NotImplementedError, match="placeholder"):
        Rule_TC609_0301_ContentDiversity.eval(
            Data(data_id="diversity", content="test")
        )
