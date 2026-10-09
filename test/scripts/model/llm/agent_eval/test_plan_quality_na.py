from dingo.model.llm.agent_eval.llm_agent_plan_quality import LLMAgentPlanQuality


def test_no_planning_sentinel_is_na_not_full_score():
    res = LLMAgentPlanQuality.process_response('{"score": -1, "reason": "no plan"}')
    # 模型自述"无计划"不再强转满分 pass（spec §15.2 #3），改记 N/A
    assert res.applicable is False
    assert res.score is None
    assert res.effective_verdict == "n/a"
    assert res.status is False
