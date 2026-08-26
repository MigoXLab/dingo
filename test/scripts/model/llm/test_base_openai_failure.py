from dingo.io.input import Data
from dingo.io.output.eval_detail import QualityLabel
from dingo.model.llm.agent_eval.llm_agent_task_completion import LLMAgentTaskCompletion


def _always_raise(cls, messages):
    raise ConnectionError("boom")


def test_retry_exhaustion_is_not_faked_as_issue(monkeypatch):
    monkeypatch.setattr(LLMAgentTaskCompletion, "send_messages", classmethod(_always_raise))
    monkeypatch.setattr(LLMAgentTaskCompletion, "create_client", classmethod(lambda cls: None))
    monkeypatch.setattr(LLMAgentTaskCompletion, "client", object())

    res = LLMAgentTaskCompletion.eval(Data(data_id="t", prompt="p", content="c"))

    # 基础设施错误绝不能伪装成阻塞性 finding（spec §9.3）
    assert res.status is False
    assert res.label is not None
    assert res.label[0].startswith(QualityLabel.REVIEW_EXECUTION_ERROR_PREFIX)
    assert "boom" in res.reason[0]
    assert res.score is None
    # 执行失败必须在判定层体现为 n/a，而不是伪装成真正的 pass（final-review #2）
    assert res.applicable is False
    assert res.effective_verdict == "n/a"


def test_retry_exhaustion_says_which_kind_of_not_applicable(monkeypatch):
    """applicable=False 有三种成因，此前只有两种说得出名字。

    下游拿到 applicable=False 却无从分辨"评测器自己挂了"和"这项检查在这类运行
    上不适用"，于是把前者渲染成后者——一句在讲用户的运行，可它讲的其实只是
    评测器。做出决定的分支才知道答案，所以名字在那里给。
    """
    monkeypatch.setattr(LLMAgentTaskCompletion, "send_messages", classmethod(_always_raise))
    monkeypatch.setattr(LLMAgentTaskCompletion, "create_client", classmethod(lambda cls: None))
    monkeypatch.setattr(LLMAgentTaskCompletion, "client", object())

    res = LLMAgentTaskCompletion.eval(Data(data_id="t", prompt="p", content="c"))

    assert res.not_applicable_kind == "execution_error"
    # 与另外两种互斥：它们描述这次运行，这一种只描述评测器。
    assert res.not_applicable_kind not in ("declined", "structural")
