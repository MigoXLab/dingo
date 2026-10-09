import json

import pytest

from dingo.model.llm.text_quality.llm_text_quality_v7 import LLMTextQualityV7


def test_multiple_defects_are_aggregated():
    response = json.dumps([
        {"score": 0, "type": "Effectiveness", "name": "Words_Stuck", "reason": "Missing word boundaries"},
        {"score": 0, "type": "Similarity", "name": "Duplication", "reason": "Sentence repeats 6 times"},
    ])

    result = LLMTextQualityV7.process_response(response)

    assert result.status is True
    assert result.score == 0
    assert result.label == ["Effectiveness.Words_Stuck", "Similarity.Duplication"]
    assert result.reason == ["Missing word boundaries", "Sentence repeats 6 times"]


def test_good_response_is_a_single_item_list():
    response = '```json\n[{"score": 1, "type": "Good", "name": "None", "reason": "Clear text"}]\n```'

    result = LLMTextQualityV7.process_response(response)

    assert result.status is False
    assert result.score == 1
    assert result.label == ["QUALITY_GOOD"]
    assert result.reason == ["Clear text"]


def test_structured_response_includes_statistics():
    response = json.dumps({
        "statistics": {
            "formula_count": 2,
            "table_count": 1,
            "code_count": 3,
        },
        "findings": [
            {
                "score": 1,
                "type": "Good",
                "name": "None",
                "reason": "All structures are intact",
            }
        ],
    })

    result = LLMTextQualityV7.process_response(response)

    assert result.statistics == {
        "formula_count": 2,
        "table_count": 1,
        "code_count": 3,
    }


@pytest.mark.parametrize("invalid_count", [-1, 1.5, True, "1"])
def test_structured_response_rejects_invalid_statistics(invalid_count):
    response = json.dumps({
        "statistics": {
            "formula_count": invalid_count,
            "table_count": 0,
            "code_count": 0,
        },
        "findings": [
            {
                "score": 1,
                "type": "Good",
                "name": "None",
                "reason": "Clear text",
            }
        ],
    })

    with pytest.raises(ValueError):
        LLMTextQualityV7.process_response(response)


def test_structured_response_rejects_non_structure_statistics():
    response = json.dumps({
        "statistics": {
            "formula_count": 0,
            "table_count": 0,
            "code_count": 0,
            "Words_Stuck": 1,
        },
        "findings": [
            {
                "score": 0,
                "type": "Effectiveness",
                "name": "Words_Stuck",
                "reason": "Missing word boundaries",
            }
        ],
    })

    with pytest.raises(ValueError, match="unsupported fields: Words_Stuck"):
        LLMTextQualityV7.process_response(response)


@pytest.mark.parametrize("response", [
    "[]",
    '{"score": 1, "type": "Good", "name": "None", "reason": "Clear text"}',
    '[{"score": 1, "type": "Good", "name": "None", "reason": "Clear"},'
    ' {"score": 0, "type": "Similarity", "name": "Duplication", "reason": "Repeated"}]',
    '[{"score": 0, "type": "Similarity", "name": "Duplication", "reason": "Repeated"},'
    ' {"score": 0, "type": "Similarity", "name": "Duplication", "reason": "Repeated again"}]',
])
def test_invalid_multi_label_shapes_are_rejected(response):
    with pytest.raises(ValueError):
        LLMTextQualityV7.process_response(response)
