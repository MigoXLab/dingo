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


def _completion_family_judges():
    """The three judges that read the trace summary, for tests that assert all
    of them answer alike. Was copied verbatim into two adjacent classes."""
    from dingo.model.llm.agent_eval.llm_agent_step_efficiency import LLMAgentStepEfficiency
    from dingo.model.llm.agent_eval.llm_agent_tool_correctness import LLMAgentToolCorrectness

    return (LLMAgentTaskCompletion, LLMAgentToolCorrectness, LLMAgentStepEfficiency)


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


class TestEveryJudgeOfATraceAnswersInOneLanguage:
    """Reading `prompt + content` made the answer depend on the view: the
    tool-call view of a Chinese run is full of Chinese arguments while its trace
    summary is mostly English step names, so one trace came back with task
    completion in English and tool correctness in Chinese, side by side on the
    same card."""

    def _judges(self):
        return _completion_family_judges()

    def test_the_task_decides_it_not_the_view(self):
        from dingo.io import Data

        chinese_task = Data(data_id="t", prompt="帮我编辑这个文件，让它更简洁", content="")
        english_view = Data(data_id="t", prompt="帮我编辑这个文件，让它更简洁",
                            content="Execution (3 steps): read, write, final_answer")
        hints = {cls.language_hint_for(chinese_task) for cls in self._judges()}
        hints |= {cls.language_hint_for(english_view) for cls in self._judges()}

        assert len(hints) == 1, "one trace, one language, whatever each judge is shown"
        assert "中文" in hints.pop()

    def test_an_english_task_stays_english(self):
        from dingo.io import Data

        # …even when the calls it made are full of Chinese arguments.
        data = Data(data_id="t", prompt="Summarise this repository",
                    content='{"args": {"path": "文档/说明.md"}}' * 20)
        hints = {cls.language_hint_for(data) for cls in self._judges()}

        assert len(hints) == 1
        # Said out loud rather than left blank. Silence is what let a leftover
        # "follow the input content" line in the template decide instead, and
        # the input content here is Chinese.
        assert "English" in hints.pop()


class TestTheCallerCanDecideTheLanguageForTheWholeTrace:
    """The mechanism the platform actually uses, which the test above does not
    reach: it builds `Data` with only prompt and content, so it exercises the
    fallback and never the attribute the fix added. A trace whose task is
    "1+1=？" carries no CJK at all, and every judge was back to choosing for
    itself — Step Efficiency answered in English beside four dimensions in
    Chinese, on the same card.
    """

    def _judges(self):
        return _completion_family_judges()

    def test_a_sample_from_the_caller_outranks_a_task_too_short_to_tell(self):
        from dingo.io import Data

        data = Data(
            data_id="t",
            prompt="1+1=？",
            content="Execution (3 steps): FileContext.Load, qwen3.7-plus, final_answer",
            language_sample="1+1=？\n答案是 2。这是一个简单的算术问题，代理直接给出了正确结果。",
        )
        hints = {cls.language_hint_for(data) for cls in self._judges()}

        assert len(hints) == 1, "one trace, one language, for every judge"
        assert "中文" in hints.pop()

    def test_without_a_sample_it_still_falls_back_to_the_task(self):
        from dingo.io import Data

        data = Data(data_id="t", prompt="帮我编辑这个文件，让它更简洁", content="")

        assert "中文" in LLMAgentTaskCompletion.language_hint_for(data)

    def test_the_instruction_is_never_silent(self):
        """An empty hint is what let a leftover "follow the input content" line
        in the template win — a judge given no instruction obeys whichever one
        is left."""
        from dingo.io import Data

        english = Data(data_id="t", prompt="Summarise this repository", content="")

        assert LLMAgentTaskCompletion.language_hint_for(english).strip()

    def test_no_judge_carries_a_second_language_instruction(self):
        """The one this test class exists because of: a template line saying to
        follow "the input content" is a different answer for every judge, since
        each is shown a different slice."""
        from dingo.model.llm.agent_eval.llm_agent_argument_correctness import LLMAgentArgumentCorrectness
        from dingo.model.llm.agent_eval.llm_agent_error_recovery import LLMAgentErrorRecovery
        from dingo.model.llm.agent_eval.llm_agent_plan_adherence import LLMAgentPlanAdherence
        from dingo.model.llm.agent_eval.llm_agent_plan_quality import LLMAgentPlanQuality

        for cls in (*self._judges(), LLMAgentPlanQuality, LLMAgentPlanAdherence,
                    LLMAgentErrorRecovery, LLMAgentArgumentCorrectness):
            assert "same language as the input content" not in cls.prompt, cls.__name__
            assert "same language as the Task Objective" not in cls.prompt, cls.__name__
