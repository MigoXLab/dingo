from types import SimpleNamespace

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io import ResultInfo
from dingo.io.input import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model.llm.base import LLMCallResult
from dingo.model.llm.base_openai import BaseOpenAI


def _completion(
    content='{"score": 1, "reason": "ok"}',
    usage=None,
    finish_reason="stop",
):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(content=content),
            )
        ],
        usage=usage,
    )


def test_extract_token_usage_from_openai_response_object():
    usage = SimpleNamespace(
        prompt_tokens=11,
        completion_tokens=7,
        total_tokens=18,
        prompt_tokens_details=SimpleNamespace(cached_tokens=3),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=2),
    )

    result = BaseOpenAI._extract_token_usage(
        _completion(usage=usage),
        model_name="gpt-test",
        provider="openai",
    )

    assert result.prompt_tokens == 11
    assert result.completion_tokens == 7
    assert result.total_tokens == 18
    assert result.cached_tokens == 3
    assert result.reasoning_tokens == 2
    assert result.model == "gpt-test"
    assert not hasattr(result, "provider")
    assert result.calls == 1


def test_base_openai_eval_attaches_token_usage():
    class UsageLLM(BaseOpenAI):
        prompt = ""
        dynamic_config = EvaluatorLLMArgs()
        client = True

        @classmethod
        def send_messages(cls, messages):
            return LLMCallResult(
                content='{"score": 1, "reason": "ok"}',
                usage=BaseOpenAI._extract_token_usage(
                    _completion(
                        usage={
                            "prompt_tokens": 5,
                            "completion_tokens": 2,
                            "total_tokens": 7,
                        }
                    ),
                    model_name="gpt-test",
                ),
            )

    result = UsageLLM.eval(Data(content="sample"))

    assert result.status is False
    assert result.usage is not None
    assert result.usage.prompt_tokens == 5
    assert result.usage.completion_tokens == 2
    assert result.usage.total_tokens == 7


def test_base_openai_error_result_keeps_token_usage():
    class ParseErrorLLM(BaseOpenAI):
        prompt = ""
        dynamic_config = EvaluatorLLMArgs()
        client = True

        @classmethod
        def send_messages(cls, messages):
            return LLMCallResult(
                content="not json",
                usage=BaseOpenAI._extract_token_usage(
                    _completion(
                        usage={
                            "prompt_tokens": 3,
                            "completion_tokens": 1,
                            "total_tokens": 4,
                        }
                    ),
                    model_name="gpt-test",
                ),
            )

    result = ParseErrorLLM.eval(Data(content="sample"))

    assert result.status is False
    assert result.label == ["REVIEW_EXECUTION_ERROR.ConvertJsonError"]
    assert result.usage is not None
    assert result.usage.total_tokens == 4


def test_base_openai_eval_still_accepts_legacy_string_send_messages():
    class LegacyLLM(BaseOpenAI):
        prompt = ""
        dynamic_config = EvaluatorLLMArgs()
        client = True

        @classmethod
        def send_messages(cls, messages):
            return '{"score": 1, "reason": "ok"}'

    result = LegacyLLM.eval(Data(content="sample"))

    assert result.status is False
    assert result.usage is None


def test_result_info_only_serializes_usage_when_present():
    with_usage = ResultInfo(
        dingo_id="1",
        eval_details={
            "content": [
                EvalDetail(
                    metric="LLMMetric",
                    usage=BaseOpenAI._extract_token_usage(
                        _completion(
                            usage={
                                "prompt_tokens": 1,
                                "completion_tokens": 2,
                                "total_tokens": 3,
                            }
                        ),
                        model_name="gpt-test",
                    ),
                )
            ]
        },
    ).to_dict()
    without_usage = ResultInfo(
        dingo_id="2",
        eval_details={"content": [EvalDetail(metric="RuleMetric")]},
    ).to_dict()

    assert with_usage["eval_details"]["content"][0]["usage"]["total_tokens"] == 3
    assert "provider" not in with_usage["eval_details"]["content"][0]["usage"]
    assert "usage" not in without_usage["eval_details"]["content"][0]
