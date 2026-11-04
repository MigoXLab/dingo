import json

from dingo.io import Data
from dingo.io.output.eval_detail import QualityLabel
from dingo.model.llm.llm_text_advertisement import LLMTextAdvertisement


def test_advertisement_response_is_bad():
    response = json.dumps({
        "score": 0,
        "type": "Effectiveness",
        "name": "Advertisement",
        "reason": "Click the yellow cart for the anniversary dump price.",
    })
    result = LLMTextAdvertisement.process_response(response)
    assert result.status is True
    assert result.label == ["Effectiveness.Advertisement"]
    assert "yellow cart" in result.reason[0]


def test_non_ad_response_is_good():
    result = LLMTextAdvertisement.process_response(
        '{"score": 1, "type": "Good", "name": "None", "reason": "Personal travel diary"}'
    )
    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]


def test_build_messages_includes_title_and_content():
    messages = LLMTextAdvertisement.build_messages(
        Data(prompt="周年庆抄底价", content="点击视频下方链接薅羊毛")
    )
    assert len(messages) == 1
    user = messages[0]["content"]
    assert "周年庆抄底价" in user
    assert "点击视频下方链接薅羊毛" in user
    assert "Default to Good" in user
    assert "Do NOT flag" in user


def test_process_response_strips_trailing_junk():
    response = (
        '{"score": 1, "type": "Good", "name": "None", "reason": "Personal review"}`\n'
    )
    result = LLMTextAdvertisement.process_response(response)
    assert result.status is False
    assert result.label == [QualityLabel.QUALITY_GOOD]
