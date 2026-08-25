"""Unit tests for the deterministic agent-trace rules in ``rule_agent.py``.

Covers the three trace-level rules and, importantly, the malformed-input edge
cases (JSON ``null`` values, non-dict items) that previously raised
``TypeError`` / ``AttributeError`` — plus the ``dynamic_config`` /
``input_data_type`` contract the dingo-saas orchestrator depends on.
"""

import json

import pytest

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.io.output.eval_detail import QualityLabel
from dingo.model.model import Model
from dingo.model.rule.rule_agent import RuleAgentTraceLatencyAnomaly, RuleAgentTraceLoopDetection, RuleAgentTraceTokenBudget


def _data(content: str) -> Data:
    return Data(data_id="t", content=content)


class TestRuleAgentTraceLoopDetection:
    """Loop detection via n-gram repetition on the tool-name sequence."""

    def test_repeating_pattern_is_flagged(self):
        # [search, click] repeated 4 times → pattern len 2 repeats ≥ 3.
        content = json.dumps([{"tool_name": "search"}, {"tool_name": "click"}] * 4)
        res = RuleAgentTraceLoopDetection.eval(_data(content))
        assert res.status is True
        assert res.label == ["AGENT_TRACE_QUALITY.RuleAgentTraceLoopDetection"]
        assert res.reason is not None and "Loop detected" in res.reason[0]

    def test_dict_form_with_tool_calls_key(self):
        content = json.dumps(
            {"tool_calls": [{"tool_name": "a"}, {"tool_name": "b"}, {"tool_name": "c"}] * 3}
        )
        res = RuleAgentTraceLoopDetection.eval(_data(content))
        assert res.status is True

    def test_distinct_sequence_passes(self):
        content = json.dumps([{"tool_name": f"tool_{i}"} for i in range(8)])
        res = RuleAgentTraceLoopDetection.eval(_data(content))
        assert res.status is False
        assert res.label == [QualityLabel.QUALITY_GOOD]

    def test_same_tool_with_distinct_arguments_is_not_a_loop(self):
        # A research fan-out: one tool, eight different queries. Comparing tool
        # names alone reads this as ['WebSearch','WebSearch'] repeating 4 times.
        content = json.dumps(
            {
                "tool_calls": [
                    {"tool_name": "WebSearch", "args": {"query": f"topic {i}"}}
                    for i in range(8)
                ]
            }
        )
        res = RuleAgentTraceLoopDetection.eval(_data(content))
        assert res.status is False
        assert res.label == [QualityLabel.QUALITY_GOOD]

    def test_same_tool_with_identical_arguments_is_flagged(self):
        # Same tool, same arguments, over and over — a real stuck loop.
        content = json.dumps(
            {
                "tool_calls": [
                    {"tool_name": "WebSearch", "args": {"query": "same question"}}
                    for _ in range(6)
                ]
            }
        )
        res = RuleAgentTraceLoopDetection.eval(_data(content))
        assert res.status is True
        assert res.reason is not None and "Loop detected" in res.reason[0]

    def test_three_identical_calls_are_a_loop(self):
        # Pattern search starts at length 2, so one call repeated verbatim was
        # never a "pattern" and went unreported — the plainest loop there is.
        # Observed live: a research agent asked the same calculation 3 times.
        content = json.dumps(
            {
                "tool_calls": [
                    {"tool_name": "mathematics", "args": {"expr": "hc/610nm"}}
                    for _ in range(3)
                ]
                + [
                    {"tool_name": "browse_tools", "args": {"q": str(i)}}
                    for i in range(5)
                ]
            }
        )
        res = RuleAgentTraceLoopDetection.eval(_data(content))
        assert res.status is True
        assert "mathematics" in res.reason[0]

    def test_three_repeats_without_arguments_are_not_claimed_as_a_loop(self):
        # With no arguments recorded, three consecutive calls to one tool are as
        # likely three different files as one repeat. The single-call branch
        # must stay silent; only the pre-existing pattern search may speak.
        content = json.dumps(
            {
                "tool_calls": [{"tool_name": "read_file"} for _ in range(3)]
                + [{"tool_name": f"other_{i}", "args": {"i": i}} for i in range(5)]
            }
        )
        res = RuleAgentTraceLoopDetection.eval(_data(content))
        assert res.status is False

    def test_loop_reason_names_the_repeated_tool_not_its_signature(self):
        content = json.dumps(
            {
                "tool_calls": [
                    {"tool_name": "read_file", "args": {"path": "a.md"}}
                    for _ in range(6)
                ]
            }
        )
        res = RuleAgentTraceLoopDetection.eval(_data(content))
        assert res.status is True
        # The reported pattern stays human-readable: tool names, not the
        # internal argument fingerprint used for comparison.
        assert "read_file" in res.reason[0]
        assert "path" not in res.reason[0]

    def test_short_sequence_is_unanalysable_not_clean(self):
        # Fewer than 6 tool names → the test never ran. Reporting that as a
        # pass told a reader the trace had been checked for repetition.
        content = json.dumps([{"tool_name": "a"}, {"tool_name": "b"}])
        res = RuleAgentTraceLoopDetection.eval(_data(content))
        assert res.status is False
        assert res.applicable is False
        assert res.label != [QualityLabel.QUALITY_GOOD]

    def test_null_tool_calls_does_not_crash(self):
        # JSON null for a present key previously broke iteration (TypeError).
        res = RuleAgentTraceLoopDetection.eval(_data('{"tool_calls": null}'))
        assert res.status is False
        assert res.applicable is False

    def test_non_dict_items_do_not_crash(self):
        # Operator-precedence bug previously raised AttributeError on "a"/null.
        res = RuleAgentTraceLoopDetection.eval(_data('["a", null, {"name": "x"}]'))
        assert res.status is False
        assert res.applicable is False

    def test_non_json_text_passes(self):
        # Plain text content (not JSON) must be tolerated, not raise.
        res = RuleAgentTraceLoopDetection.eval(_data("just some free text"))
        assert res.status is False
        assert res.applicable is False


class TestRuleAgentTraceTokenBudget:
    """Token-budget rule with a default-but-overridable 500k threshold."""

    def test_default_threshold_is_500k(self):
        assert isinstance(RuleAgentTraceTokenBudget.dynamic_config, EvaluatorRuleArgs)
        assert RuleAgentTraceTokenBudget.dynamic_config.threshold == 500_000

    def test_under_budget_passes_and_reports_the_usage(self):
        res = RuleAgentTraceTokenBudget.eval(_data('{"total_tokens": 1000}'))
        assert res.status is False
        assert res.label == [QualityLabel.QUALITY_GOOD]
        assert "1,000 of budget 500,000" in res.reason[0]

    def test_being_under_budget_is_not_a_score(self):
        """A budget is a threshold. Scoring everything under it 1.0 graded a run
        at 0.2% of budget and one at 99% alike, and put a constant into the
        efficiency mean — 16 of 16 scores were exactly 1.0 on one live import."""
        frugal = RuleAgentTraceTokenBudget.eval(_data('{"total_tokens": 1000}'))
        nearly_over = RuleAgentTraceTokenBudget.eval(_data('{"total_tokens": 499000}'))

        assert frugal.score is None
        assert nearly_over.score is None
        assert frugal.status is nearly_over.status is False

    def test_an_overage_still_scores_by_how_far_over(self):
        res = RuleAgentTraceTokenBudget.eval(_data('{"total_tokens": 1000000}'))
        assert res.score == 0.5

    def test_over_budget_is_flagged(self):
        res = RuleAgentTraceTokenBudget.eval(_data('{"total_tokens": 600000}'))
        assert res.status is True
        assert res.label == ["AGENT_TRACE_QUALITY.RuleAgentTraceTokenBudget"]
        assert res.reason is not None and "exceeds budget" in res.reason[0]

    def test_missing_tokens_reaches_no_verdict(self):
        """The reason said the budget was not checked while the label said the
        trace was good. A source that exports no token counts is not a source
        reporting frugal ones."""
        res = RuleAgentTraceTokenBudget.eval(_data('{"other_field": 1}'))
        assert res.applicable is False
        assert res.status is False
        assert res.label != [QualityLabel.QUALITY_GOOD]

    def test_threshold_override_via_dynamic_config(self):
        original = RuleAgentTraceTokenBudget.dynamic_config.threshold
        try:
            RuleAgentTraceTokenBudget.dynamic_config.threshold = 100
            res = RuleAgentTraceTokenBudget.eval(_data('{"total_tokens": 200}'))
            assert res.status is True
        finally:
            RuleAgentTraceTokenBudget.dynamic_config.threshold = original


class TestRuleAgentTraceLatencyAnomaly:
    """Latency anomaly via mean + 3·stddev outlier detection."""

    def test_outlier_is_flagged(self):
        steps = [{"name": f"s{i}", "duration": 1.0} for i in range(15)]
        steps.append({"name": "slow", "duration": 40.0})
        res = RuleAgentTraceLatencyAnomaly.eval(_data(json.dumps({"steps": steps})))
        assert res.status is True
        assert res.label == ["AGENT_TRACE_QUALITY.RuleAgentTraceLatencyAnomaly"]
        assert res.reason is not None and "slow" in res.reason[0]

    def test_uniform_durations_pass(self):
        steps = [{"name": f"s{i}", "duration": 1.0} for i in range(5)]
        res = RuleAgentTraceLatencyAnomaly.eval(_data(json.dumps({"steps": steps})))
        assert res.status is False
        assert res.label == [QualityLabel.QUALITY_GOOD]

    def test_few_steps_is_uncomparable_not_clean(self):
        # Fewer than 3 valid durations → nothing to compare against. "No
        # outlier stood out" and "there was nothing to stand out from" are
        # different answers, and only the first is a pass.
        steps = [{"name": "a", "duration": 1.0}, {"name": "b", "duration": 99.0}]
        res = RuleAgentTraceLatencyAnomaly.eval(_data(json.dumps({"steps": steps})))
        assert res.status is False
        assert res.applicable is False
        assert res.label != [QualityLabel.QUALITY_GOOD]

    def test_duration_seconds_alias(self):
        steps = [{"name": f"s{i}", "duration_seconds": 1.0} for i in range(15)]
        steps.append({"name": "slow", "duration_seconds": 40.0})
        res = RuleAgentTraceLatencyAnomaly.eval(_data(json.dumps({"steps": steps})))
        assert res.status is True

    def test_null_steps_does_not_crash(self):
        res = RuleAgentTraceLatencyAnomaly.eval(_data('{"steps": null}'))
        assert res.status is False
        assert res.applicable is False

    # -- peer grouping -------------------------------------------------

    def test_fast_and_slow_step_kinds_are_compared_separately(self):
        """A normal long inference must not be flagged just because tool calls are fast.

        Without grouping the 18 sub-second tool steps drag the mean to ~4s and
        the final generation trips mean+3σ — the bimodal-pooling failure.
        """
        steps = [
            {"name": "tool", "duration": 0.15, "group": "tool"} for _ in range(18)
        ] + [
            {"name": "LLM Inference", "duration": d, "group": "llm"}
            for d in (4.46, 9.73, 5.87, 6.01, 11.79, 57.97)
        ]
        res = RuleAgentTraceLatencyAnomaly.eval(_data(json.dumps({"steps": steps})))
        assert res.status is False
        assert res.label == [QualityLabel.QUALITY_GOOD]

    def test_pooled_input_still_flags_the_same_outlier(self):
        """The same steps without groups keep the old (pooled) verdict."""
        steps = [{"name": "tool", "duration": 0.15} for _ in range(18)] + [
            {"name": "LLM Inference", "duration": d}
            for d in (4.46, 9.73, 5.87, 6.01, 11.79, 57.97)
        ]
        res = RuleAgentTraceLatencyAnomaly.eval(_data(json.dumps({"steps": steps})))
        assert res.status is True

    def test_outlier_within_its_own_group_is_flagged(self):
        """Grouping must not mute real anomalies — a stuck tool call is now visible
        against its peers instead of hiding under the inference threshold."""
        steps = [
            {"name": "read", "duration": 0.15, "group": "tool"} for _ in range(10)
        ] + [
            {"name": "stuck_tool", "duration": 9.0, "group": "tool"},
            {"name": "gen", "duration": 30.0, "group": "llm"},
            {"name": "gen", "duration": 32.0, "group": "llm"},
            {"name": "gen", "duration": 31.0, "group": "llm"},
        ]
        res = RuleAgentTraceLatencyAnomaly.eval(_data(json.dumps({"steps": steps})))
        assert res.status is True
        assert "stuck_tool" in res.reason[0]
        # The group is named so a reader knows what the step was compared against.
        assert "tool threshold" in res.reason[0]

    def test_group_with_too_few_samples_is_skipped(self):
        """Two samples cannot establish a threshold — that group is not judged."""
        steps = [{"name": f"s{i}", "duration": 1.0, "group": "a"} for i in range(5)] + [
            {"name": "lonely", "duration": 999.0, "group": "b"},
            {"name": "lonely2", "duration": 1.0, "group": "b"},
        ]
        res = RuleAgentTraceLatencyAnomaly.eval(_data(json.dumps({"steps": steps})))
        assert res.status is False

    @pytest.mark.parametrize("key", ["group", "type"])
    def test_group_alias_keys(self, key):
        # 15 baseline samples keep stdev small enough that the outlier clears
        # mean+3σ; with too few, a lone outlier inflates σ and masks itself.
        steps = [{"name": "t", "duration": 0.1, key: "tool"} for _ in range(15)] + [
            {"name": "slow", "duration": 9.0, key: "tool"}
        ]
        res = RuleAgentTraceLatencyAnomaly.eval(_data(json.dumps({"steps": steps})))
        assert res.status is True


class TestRuleAgentRegistration:
    """The saas orchestrator keys off rule_name_map + the agent attributes."""

    @pytest.mark.parametrize(
        "name",
        [
            "RuleAgentTraceLoopDetection",
            "RuleAgentTraceTokenBudget",
            "RuleAgentTraceLatencyAnomaly",
        ],
    )
    def test_registered_in_name_map(self, name):
        assert name in Model.rule_name_map

    @pytest.mark.parametrize(
        "rule_cls",
        [
            RuleAgentTraceLoopDetection,
            RuleAgentTraceTokenBudget,
            RuleAgentTraceLatencyAnomaly,
        ],
    )
    def test_declares_agent_eval_attributes(self, rule_cls):
        # input_data_type + eval_layer are what dingo-saas' _is_agent_evaluator
        # checks to route these as trace-level (not span-level) evaluators.
        assert rule_cls.input_data_type == "agent_trace_json"
        assert rule_cls.eval_layer


class TestPassingVerdictsExplainThemselves:
    """A pass with no reason is indistinguishable from a rule that never ran."""

    def test_loop_pass_says_what_was_checked(self):
        content = json.dumps(
            {"tool_calls": [{"tool_name": f"t{i}", "args": {"i": i}} for i in range(8)]}
        )
        res = RuleAgentTraceLoopDetection.eval(_data(content))
        assert res.status is False
        assert "8 tool calls checked" in res.reason[0]

    def test_loop_pass_below_threshold_says_it_did_not_analyse(self):
        content = json.dumps({"tool_calls": [{"tool_name": "a"}, {"tool_name": "b"}]})
        res = RuleAgentTraceLoopDetection.eval(_data(content))
        assert res.status is False
        assert "too few to analyse" in res.reason[0]

    def test_token_pass_reports_usage_against_budget(self):
        res = RuleAgentTraceTokenBudget.eval(_data(json.dumps({"total_tokens": 25_000})))
        assert res.status is False
        assert "25,000" in res.reason[0] and "500,000" in res.reason[0]

    def test_token_pass_without_usage_does_not_claim_a_check(self):
        res = RuleAgentTraceTokenBudget.eval(_data(json.dumps({"steps": []})))
        assert res.status is False
        assert "not checked" in res.reason[0]

    def test_latency_pass_reports_what_it_compared(self):
        content = json.dumps(
            {"steps": [{"name": f"s{i}", "duration": 1.0 + i * 0.01, "group": "tool"}
                       for i in range(5)]}
        )
        res = RuleAgentTraceLatencyAnomaly.eval(_data(content))
        assert res.status is False
        assert "5 timed steps" in res.reason[0]

    def test_latency_pass_with_too_few_samples_says_so(self):
        content = json.dumps({"steps": [{"name": "s", "duration": 1.0, "group": "tool"}]})
        res = RuleAgentTraceLatencyAnomaly.eval(_data(content))
        assert res.status is False
        assert "Too few timed steps" in res.reason[0]
