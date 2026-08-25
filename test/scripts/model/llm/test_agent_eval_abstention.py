"""A judge that cannot answer must be able to say so.

Without an abstention it had only the score, so "the record cannot confirm or
contradict this" and "the agent failed" came out as the same low number under
the same "critical" label — measured on two live traces whose attached file was
never returned by any call (0.2/critical) beside two in the identical
evidentiary position (0.6-0.7).
"""

import json

from dingo.io.output.eval_detail import QualityLabel
from dingo.model.llm.agent_eval.llm_agent_task_completion import LLMAgentTaskCompletion


class TestAJudgeMayDecline:
    def test_declining_reaches_no_verdict(self):
        res = LLMAgentTaskCompletion.process_response(json.dumps({
            "not_applicable": True,
            "reason": "The attached file was never returned by any call",
        }))

        assert res.applicable is False
        assert res.score is None
        assert res.status is False
        assert res.label != [QualityLabel.QUALITY_GOOD]
        assert res.reason == ["The attached file was never returned by any call"]

    def test_an_ordinary_verdict_is_unaffected(self):
        res = LLMAgentTaskCompletion.process_response(json.dumps({
            "score": 8, "reason": "done", "goal_achievement": 4,
        }))

        assert res.applicable is True
        assert res.score == 0.8
        assert json.loads(res.reason[1]) == {"goal_achievement": 4}

    def test_a_low_score_is_still_a_verdict(self):
        """Declining and failing must stay distinguishable — that is the point."""
        res = LLMAgentTaskCompletion.process_response(json.dumps({
            "score": 2, "reason": "the agent did not do it",
        }))

        assert res.applicable is True
        assert res.score == 0.2

    def test_not_applicable_false_is_not_a_decline(self):
        res = LLMAgentTaskCompletion.process_response(json.dumps({
            "not_applicable": False, "score": 7, "reason": "ok",
        }))

        assert res.applicable is True
        assert res.score == 0.7


class TestEveryJudgeGetsTheSameEvidenceRules:
    """Pasted by hand into three prompts, the block drifted inside the very
    commit that introduced it. A judge holding a stale copy applies a different
    evidence standard from its neighbours while both verdicts are on screen."""

    def test_the_shared_rules_reach_all_three_judges(self):
        from dingo.model.llm.agent_eval.llm_agent_plan_quality import LLMAgentPlanQuality
        from dingo.model.llm.agent_eval.llm_agent_step_efficiency import LLMAgentStepEfficiency

        shared = "An agent's own statement is not evidence that the statement is true"
        for cls in (LLMAgentTaskCompletion, LLMAgentStepEfficiency, LLMAgentPlanQuality):
            assert shared in cls.prompt, cls.__name__
            assert '"not_applicable": true' in cls.prompt, cls.__name__

    def test_the_per_judge_bullet_still_differs(self):
        from dingo.model.llm.agent_eval.llm_agent_plan_quality import LLMAgentPlanQuality

        assert "A plan step the record shows never happened" in LLMAgentPlanQuality.prompt
        assert "A plan step the record shows never happened" not in LLMAgentTaskCompletion.prompt
