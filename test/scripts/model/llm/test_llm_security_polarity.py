import json

from dingo.model.llm.repository_code_quality.common.llm_repository_security_review import LLMRepositorySecurityPolitics, LLMRepositorySecurityProhibition
from dingo.model.llm.security.llm_security import LLMSecurity
from dingo.model.llm.security.llm_security_politics import LLMSecurityPolitics
from dingo.model.llm.security.llm_security_prohibition import LLMSecurityProhibition


class ExtendedPolitics(LLMSecurityPolitics):
    """A politics scenario registered under its own name."""


class ExtendedProhibition(LLMSecurityProhibition):
    """A prohibition scenario registered under its own name."""


def test_polarity_is_resolved_per_scenario():
    assert LLMSecurity.hit_values() == ("pos",)
    assert LLMSecurityProhibition.hit_values() == ("pos",)
    assert LLMSecurityPolitics.hit_values() == ("neg",)


def test_polarity_is_inherited_by_subclasses():
    assert ExtendedPolitics.hit_values() == ("neg",)
    assert ExtendedProhibition.hit_values() == ("pos",)
    assert LLMRepositorySecurityPolitics.hit_values() == ("neg",)
    assert LLMRepositorySecurityProhibition.hit_values() == ("pos",)


def test_politics_negative_stance_is_hit():
    result = LLMSecurityPolitics.process_response(json.dumps({"terrorism_and_extremism": "neg"}))
    assert result.status is True
    assert result.reason == ["terrorism_and_extremism"]
    assert result.label == ["Security.LLMSecurityPolitics"]


def test_politics_positive_and_none_stance_are_not_hits():
    for answer in ("pos", "none"):
        result = LLMSecurityPolitics.process_response(json.dumps({"terrorism_and_extremism": answer}))
        assert result.status is False
        assert result.reason == []


def test_politics_reports_only_negative_aspects():
    response = json.dumps({
        "terrorism_and_extremism": "none",
        "ethnic_hate_and_discrimination": "neg",
        "hurt_china_unity_stability": "pos",
    })
    result = LLMSecurityPolitics.process_response(response)
    assert result.status is True
    assert result.reason == ["ethnic_hate_and_discrimination"]


def test_politics_subclass_uses_the_inherited_polarity():
    result = ExtendedPolitics.process_response(json.dumps({"terrorism_and_extremism": "neg"}))
    assert result.status is True
    assert result.reason == ["terrorism_and_extremism"]


def test_politics_accepts_markdown_fenced_response():
    response = "```json\n" + json.dumps({"terrorism_and_extremism": "neg"}) + "\n```"
    result = LLMSecurityPolitics.process_response(response)
    assert result.status is True
    assert result.reason == ["terrorism_and_extremism"]


def test_prohibition_positive_stays_a_hit():
    result = LLMSecurityProhibition.process_response(json.dumps({"porn": "pos"}))
    assert result.status is True
    assert result.reason == ["porn"]
    assert result.label == ["Security.LLMSecurityProhibition"]


def test_prohibition_negative_stays_clean():
    result = LLMSecurityProhibition.process_response(json.dumps({"porn": "neg"}))
    assert result.status is False
    assert result.reason == []


def test_prohibition_subclass_keeps_positive_polarity():
    response = json.dumps({"porn": "neg", "gamble": "pos"})
    result = ExtendedProhibition.process_response(response)
    assert result.status is True
    assert result.reason == ["gamble"]


def test_repository_politics_adapter_keeps_negative_polarity():
    response = json.dumps({
        "hurt_socialist_regime_system": "none",
        "hurt_china_interests_image": "neg",
        "hurt_china_unity_stability": "none",
        "terrorism_and_extremism": "none",
        "ethnic_hate_and_discrimination": "none",
    })
    result = LLMRepositorySecurityPolitics.process_response(response)
    assert result.status is True
    assert result.score == 0
    assert result.label == ["Security.Politics"]
    assert result.reason == ["hurt_china_interests_image"]


def test_repository_prohibition_adapter_keeps_positive_polarity():
    result = LLMRepositorySecurityProhibition.process_response(json.dumps({"porn": "pos", "gamble": "neg", "drug": "neg"}))
    assert result.status is True
    assert result.label == ["Security.Porn"]
