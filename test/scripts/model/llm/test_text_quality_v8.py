import json

from dingo.model import Model
from dingo.model.llm.text_quality.llm_text_quality_v8 import LLMTextQualityV8


def test_v8_is_registered_with_garbled_character_guardrails():
    prompt = LLMTextQualityV8.prompt

    assert Model.get_llm_name_map()["LLMTextQualityV8"] is LLMTextQualityV8
    assert "strictly greater than 1%" in prompt
    assert "garbled_character_rate" in prompt
    assert "numerator, denominator, and percentage" in prompt
    assert "Awkward Wording Is Not Garbled" in prompt
    assert "Intact Web Extraction Noise" in prompt


def test_v8_response_uses_v8_metric_name():
    response = json.dumps([
        {
            "score": 0,
            "type": "Effectiveness",
            "name": "Garbled_Characters",
            "reason": "Confirmed corruption exceeds the threshold",
        }
    ])

    result = LLMTextQualityV8.process_response(response)

    assert result.metric == "LLMTextQualityV8"
    assert result.status is True
    assert result.label == ["Effectiveness.Garbled_Characters"]
