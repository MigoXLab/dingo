"""评估器自己的配置键不能被当成请求参数发给模型服务。

为什么见 ``base_openai.LOCAL_ONLY_CONFIG_KEYS`` 的说明。这里钉住的是行为：
放行按 SDK 签名、本地键不外发、没登记的键丢弃但告警。
"""

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.model.llm.agent_eval.llm_agent_step_efficiency import LLMAgentStepEfficiency
from dingo.model.llm.base_openai import DEFAULT_MAX_RETRIES, DEFAULT_REQUEST_TIMEOUT, LOCAL_ONLY_CONFIG_KEYS, BaseOpenAI


class _Recorder:
    """记下发给 provider 的参数，不联网。"""

    def __init__(self):
        self.kwargs = {}

        class _Completions:
            @staticmethod
            def create(**kw):
                self.kwargs = kw
                raise _Captured

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


class _Captured(Exception):
    pass


class _FakeOpenAI:
    """记下构造客户端时用了哪些参数。"""

    built: dict = {}

    def __init__(self, **kwargs):
        type(self).built = kwargs


def _send(cls, **config):
    cls.dynamic_config = EvaluatorLLMArgs(
        model="m", key="k", api_url="http://example.invalid", **config
    )
    recorder = _Recorder()
    cls.client = recorder
    try:
        cls.send_messages([{"role": "user", "content": "hi"}])
    except _Captured:
        pass
    return recorder.kwargs


def test_threshold_is_not_forwarded_to_the_provider():
    sent = _send(LLMAgentStepEfficiency, threshold=0.4)

    assert "threshold" not in sent, (
        "threshold 是判定阈值，不是请求参数；转发出去会让 SDK 抛 TypeError"
    )
    # 仍然要能被评估器自己读到，否则这个配置项就等于没了
    assert LLMAgentStepEfficiency._get_threshold() == 0.4


def test_request_timeout_steers_the_call_but_is_not_a_body_param():
    sent = _send(LLMAgentStepEfficiency, request_timeout=180)

    assert sent["timeout"] == 180
    assert "request_timeout" not in sent


def test_default_timeout_applies_when_unconfigured():
    sent = _send(LLMAgentStepEfficiency)

    assert sent["timeout"] == DEFAULT_REQUEST_TIMEOUT


def test_real_request_params_still_reach_the_provider():
    """过滤只针对本地键。把真正的请求参数一起挡掉，是另一种同样糟的失败。"""
    sent = _send(LLMAgentStepEfficiency, temperature=0.2, max_tokens=1000)

    assert sent["temperature"] == 0.2
    assert sent["max_tokens"] == 1000


def test_every_local_key_is_filtered():
    """名单里的每一个键都要真的被挡住。

    逐个验证而不是只测一个：漏登记一个键的症状是「配上就崩」，而这条断言是
    唯一会提前发现它的地方。
    """
    sent = _send(LLMAgentStepEfficiency, **{k: 1 for k in LOCAL_ONLY_CONFIG_KEYS})

    leaked = LOCAL_ONLY_CONFIG_KEYS & set(sent)
    assert not leaked, f"这些本地配置键漏给了 provider：{sorted(leaked)}"


def test_an_unregistered_local_key_is_dropped_not_forwarded(caplog):
    """没登记过的配置键也不能发出去，但要出声。

    这是把黑名单换成白名单的理由：``strictness``、``agent_config`` 都曾经漏登记，
    而漏一个的症状是该评估器每次调用必崩。现在判据是 SDK 签名，登记表只决定
    要不要告警。
    """
    sent = _send(LLMAgentStepEfficiency, strictness=5, definitely_not_a_param=1)

    assert "strictness" not in sent
    assert "definitely_not_a_param" not in sent
    # 登记过的不吵，没登记的要提示——拼错键名不该悄悄不生效
    assert "definitely_not_a_param" in caplog.text
    assert "strictness" not in caplog.text


def test_filter_lives_on_the_shared_accessor():
    """过滤必须在取参数那一处，否则下一个调用点会忘掉它。"""
    BaseOpenAI.dynamic_config = EvaluatorLLMArgs(threshold=1, temperature=0.5)
    try:
        assert BaseOpenAI.get_request_extra_params() == {"temperature": 0.5}
        assert BaseOpenAI.get_local_config_value("threshold") == 1
    finally:
        BaseOpenAI.dynamic_config = EvaluatorLLMArgs()


def test_max_retries_reaches_the_client_not_the_request(monkeypatch):
    """重试次数是构造客户端时的参数，配错地方就会变成请求体里的未知字段。"""
    monkeypatch.setattr("openai.OpenAI", _FakeOpenAI)
    LLMAgentStepEfficiency.dynamic_config = EvaluatorLLMArgs(
        model="m", key="k", api_url="http://example.invalid", max_retries=1
    )
    LLMAgentStepEfficiency.create_client()

    assert _FakeOpenAI.built["max_retries"] == 1
    assert "max_retries" not in _send(LLMAgentStepEfficiency, max_retries=1)


def test_max_retries_defaults_to_the_sdk_value(monkeypatch):
    """不配就得是原来的行为，否则这次改动会悄悄改掉所有调用方的重试次数。"""
    monkeypatch.setattr("openai.OpenAI", _FakeOpenAI)
    LLMAgentStepEfficiency.dynamic_config = EvaluatorLLMArgs(
        model="m", key="k", api_url="http://example.invalid"
    )
    LLMAgentStepEfficiency.create_client()

    assert _FakeOpenAI.built["max_retries"] == DEFAULT_MAX_RETRIES
