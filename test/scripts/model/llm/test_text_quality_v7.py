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
