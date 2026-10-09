from dingo.io.input import Data
from dingo.model.llm.agent_eval.llm_agent_error_recovery import LLMAgentErrorRecovery


def test_no_error_events_is_na_not_full_score():
    res = LLMAgentErrorRecovery.eval(Data(data_id="t", prompt="p", content='{"error_events": []}'))
    # 无错误事件不该给满分抬高聚合分（spec §15.2 #2），应记 N/A 剔除分母
    assert res.applicable is False
    assert res.score is None
    assert res.effective_verdict == "n/a"
    assert res.status is False   # 仍非 issue
