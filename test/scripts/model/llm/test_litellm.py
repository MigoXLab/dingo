"""Unit tests for BaseLiteLLM provider."""
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

pytest.importorskip("litellm", reason="litellm is not installed")

from dingo.config.input_args import EvaluatorLLMArgs  # noqa: E402
from dingo.model.llm.base_litellm import BaseLiteLLM  # noqa: E402
from dingo.utils.exception import ExceedMaxTokens  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(**cfg_kwargs) -> type:
    """Return a fresh BaseLiteLLM subclass with an isolated dynamic_config."""

    class _Provider(BaseLiteLLM):
        prompt = "Evaluate: "
        dynamic_config = EvaluatorLLMArgs(**cfg_kwargs)

    return _Provider


def _stub_response(content='{"score": 1, "reason": "ok"}', finish_reason="stop"):
    choice = SimpleNamespace(
        finish_reason=finish_reason,
        message=SimpleNamespace(content=content),
    )
    return SimpleNamespace(choices=[choice])


# ---------------------------------------------------------------------------
# create_client
# ---------------------------------------------------------------------------

class TestCreateClient:
    def test_raises_without_model(self):
        P = _make_provider()
        with pytest.raises(ValueError, match="model cannot be empty"):
            P.create_client()

    def test_sets_sentinel_on_success(self):
        P = _make_provider(model="anthropic/claude-haiku-4-5")
        P.create_client()
        assert P.client is True

    def test_raises_import_error_when_litellm_missing(self, monkeypatch):
        P = _make_provider(model="anthropic/claude-haiku-4-5")
        monkeypatch.setitem(sys.modules, "litellm", None)  # type: ignore[arg-type]
        with pytest.raises((ImportError, TypeError)):
            P.create_client()


# ---------------------------------------------------------------------------
# send_messages
# ---------------------------------------------------------------------------

class TestSendMessages:
    def test_dispatches_to_litellm(self):
        P = _make_provider(model="anthropic/claude-haiku-4-5")
        msgs = [{"role": "user", "content": "hello"}]
        with mock.patch("litellm.completion", return_value=_stub_response()) as m:
            P.send_messages(msgs)
        m.assert_called_once()
        assert m.call_args.kwargs["model"] == "anthropic/claude-haiku-4-5"
        assert m.call_args.kwargs["messages"] == msgs

    def test_drop_params_always_true(self):
        P = _make_provider(model="gpt-4o")
        with mock.patch("litellm.completion", return_value=_stub_response()) as m:
            P.send_messages([{"role": "user", "content": "hi"}])
        assert m.call_args.kwargs.get("drop_params") is True

    def test_api_key_forwarded(self):
        P = _make_provider(model="gpt-4o", key="sk-test-123")
        with mock.patch("litellm.completion", return_value=_stub_response()) as m:
            P.send_messages([{"role": "user", "content": "hi"}])
        assert m.call_args.kwargs.get("api_key") == "sk-test-123"

    def test_api_base_forwarded_when_url_set(self):
        P = _make_provider(model="gpt-4o", api_url="https://my-proxy.example.com/v1")
        with mock.patch("litellm.completion", return_value=_stub_response()) as m:
            P.send_messages([{"role": "user", "content": "hi"}])
        assert m.call_args.kwargs.get("api_base") == "https://my-proxy.example.com/v1"

    def test_no_api_key_when_key_not_set(self):
        P = _make_provider(model="anthropic/claude-haiku-4-5")
        with mock.patch("litellm.completion", return_value=_stub_response()) as m:
            P.send_messages([{"role": "user", "content": "hi"}])
        assert "api_key" not in m.call_args.kwargs

    def test_no_api_base_when_url_not_set(self):
        P = _make_provider(model="gpt-4o")
        with mock.patch("litellm.completion", return_value=_stub_response()) as m:
            P.send_messages([{"role": "user", "content": "hi"}])
        assert "api_base" not in m.call_args.kwargs

    def test_extra_params_forwarded(self):
        P = _make_provider(model="gpt-4o", temperature=0.3, max_tokens=500)
        with mock.patch("litellm.completion", return_value=_stub_response()) as m:
            P.send_messages([{"role": "user", "content": "hi"}])
        kw = m.call_args.kwargs
        assert kw.get("temperature") == 0.3
        assert kw.get("max_tokens") == 500

    def test_raises_on_length_finish_reason(self):
        P = _make_provider(model="gpt-4o", max_tokens=10)
        length_resp = _stub_response(finish_reason="length")
        with mock.patch("litellm.completion", return_value=length_resp):
            with pytest.raises(ExceedMaxTokens):
                P.send_messages([{"role": "user", "content": "hi"}])

    def test_raises_on_empty_choices(self):
        P = _make_provider(model="gpt-4o")
        empty_resp = SimpleNamespace(choices=[])
        with mock.patch("litellm.completion", return_value=empty_resp):
            with pytest.raises(ValueError, match="empty response choices"):
                P.send_messages([{"role": "user", "content": "hi"}])

    def test_none_content_returns_empty_string(self):
        P = _make_provider(model="gpt-4o")
        none_resp = _stub_response(content=None)
        with mock.patch("litellm.completion", return_value=none_resp):
            result = P.send_messages([{"role": "user", "content": "hi"}])
        assert result == ""


# ---------------------------------------------------------------------------
# process_response (inherited from BaseOpenAI)
# ---------------------------------------------------------------------------

class TestProcessResponse:
    def test_parses_good_score(self):
        import json
        response = json.dumps({"score": 1, "reason": "looks fine"})
        result = BaseLiteLLM.process_response(response)
        assert result.status is False
        assert result.label == ["QUALITY_GOOD"]

    def test_parses_bad_score(self):
        import json
        response = json.dumps({"score": 0, "reason": "bad content"})
        result = BaseLiteLLM.process_response(response)
        assert result.status is True
        assert "BaseLiteLLM" in result.label[0]
