"""Unit tests for the deterministic agent-trace rules in ``rule_agent.py``.

Covers the three trace-level rules and, importantly, the malformed-input edge
cases (JSON ``null`` values, non-dict items) that previously raised
``TypeError`` / ``AttributeError`` — plus the ``dynamic_config`` /
``input_data_type`` contract the dingo-saas orchestrator depends on.
"""

import json
from test.scripts.ms_swift_test_utils import standard_ms_swift_record

import pytest

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io import Data
from dingo.io.output.eval_detail import QualityLabel
from dingo.model.model import Model
from dingo.model.rule.agent_trace.rule_ms_swift import RuleMsSwiftSchema
from dingo.model.rule.rule_agent import RuleAgentTextToolCallValidity, RuleAgentTraceLatencyAnomaly, RuleAgentTraceLoopDetection, RuleAgentTraceTokenBudget


def _data(content: str) -> Data:
    return Data(data_id="t", content=content)


class TestRuleAgentTraceLoopDetection:
    """Single- and multi-tool interaction repetition, including short traces."""

    @staticmethod
    def call(name="a", result="observed", **extra):
        return {"tool_name": name, "args": {"target": name}, "result": result, **extra}

    def evaluate(self, calls, **config):
        model = RuleAgentTraceLoopDetection()
        Model.set_config_rule(model, EvaluatorRuleArgs(**config))
        return model.eval(_data(json.dumps({"tool_calls": calls})))

    @pytest.mark.parametrize("sequence,expected,period,count", [
        ("", False, None, None), ("A", False, None, None),
        ("AA", False, None, None), ("AAA", True, 1, 3),
        ("AAAA", True, 1, 4), ("AAAAA", True, 1, 5),
        ("AAAAAA", True, 1, 6), ("ABAB", False, None, None),
        ("ABABAB", True, 2, 3), ("ABCABCABC", True, 3, 3),
    ])
    def test_pattern_lengths_and_short_traces(self, sequence, expected, period, count):
        res = self.evaluate([self.call(name) for name in sequence])
        assert res.status is expected
        assert res.applicable is True
        assert res.verdict is None
        assert res.score is None
        detail = json.loads(res.reason[1])
        if expected:
            assert res.label == ["AGENT_TRACE_QUALITY.RuleAgentTraceLoopDetection"]
            assert detail["pattern_length"] == period
            assert detail["repeat_count"] == count
        else:
            assert res.label == [QualityLabel.QUALITY_GOOD]

    def test_distinct_arguments_do_not_match(self):
        calls = [self.call("search", args={"query": f"topic {i}"}) for i in range(6)]
        assert self.evaluate(calls).status is False

    def test_argument_order_is_canonical_but_array_order_and_types_are_not(self):
        calls = [self.call(args=args) for args in (
            {"a": 1, "b": 2}, {"b": 2, "a": 1}, {"a": 1, "b": 2},
        )]
        assert self.evaluate(calls).status
        for args in ([1, 2], [2, 1], True, 1, None, {}, []):
            mixed = [self.call(args=args), self.call(args="different"), self.call(args=args)]
            assert not self.evaluate(mixed).status

    def test_missing_arguments_are_not_known_empty_arguments(self):
        calls = [self.call() for _ in range(3)]
        calls[1].pop("args")
        assert not self.evaluate(calls).status
        assert self.evaluate([self.call(args={}) for _ in range(3)]).status

    def test_changing_results_prevents_a_match(self):
        assert not self.evaluate([self.call(result=str(i)) for i in range(6)]).status

    def test_failed_first_candidate_does_not_hide_later_repetition(self):
        calls = [self.call(result="first")] + [self.call(result="second") for _ in range(4)]
        res = self.evaluate(calls)
        assert res.status
        detail = json.loads(res.reason[1])
        assert detail["call_indices"] == [1, 2, 3, 4]
        assert detail["repeat_count"] == 4

    def test_later_multitool_pattern_is_checked(self):
        calls = [self.call("A", "old"), self.call("B", "old")]
        calls += [self.call(name, "new") for name in "ABABAB"]
        res = self.evaluate(calls)
        assert res.status
        assert json.loads(res.reason[1])["call_indices"] == list(range(2, 8))

    def test_all_round_pairs_must_match_not_just_neighbors_or_first(self):
        for texts in (["aaaaabbbbb", "aaaabbbbbb", "aaabbbbbbb"],
                      ["aaaaabbbbb", "aaaaaabbbb", "aaaabbbbbb"]):
            res = self.evaluate([self.call(result=t) for t in texts],
                                threshold=0.8, result_ngram_size=1)
            assert not res.status

    def test_one_different_pattern_position_cannot_be_averaged_away(self):
        calls = [self.call(name, result) for name, result in (
            ("A", "same"), ("B", "one"), ("A", "same"),
            ("B", "two"), ("A", "same"), ("B", "three"),
        )]
        assert not self.evaluate(calls).status

    def test_empty_return_is_comparable_but_missing_return_is_not(self):
        assert self.evaluate([self.call(result="") for _ in range(3)]).status
        calls = [self.call(result="") for _ in range(4)]
        calls[2]["result_present"] = False
        assert not self.evaluate(calls).status
        for call in calls:
            call.pop("result")
        assert not self.evaluate(calls).status

    def test_invalid_items_are_barriers_not_removed(self):
        calls = [self.call(), self.call(), None, self.call()]
        assert not self.evaluate(calls).status

    def test_user_segments_are_not_joined(self):
        calls = [self.call(segment_id=segment) for segment in (0, 0, 1)]
        assert not self.evaluate(calls).status

    def test_headers_and_call_ids_do_not_affect_similarity(self):
        calls = [self.call(call_id=str(i), result_headers=f"Wall time: {i}\n")
                 for i in range(3)]
        assert self.evaluate(calls).status

    def test_short_legacy_input_is_false_with_missing_evidence_reason(self):
        res = self.evaluate([{"tool_name": "read", "args": {}} for _ in range(4)])
        assert res.status is False
        assert res.applicable is True
        assert "no complete" in res.reason[0]

    def test_exact_mode_is_distinct_from_identical_ngram_counts(self):
        calls = [self.call(result=text) for text in ("ab", "ba", "ab")]
        assert self.evaluate(calls, result_ngram_size=1, threshold=1).status
        assert not self.evaluate(calls, result_match_mode="exact").status

    def test_similarity_threshold_includes_equality(self):
        calls = [self.call(result=t) for t in ("abcdef", "abcdeg")]
        assert self.evaluate(calls, min_repeats=2, threshold=1 / 3).status
        assert not self.evaluate(calls, min_repeats=2, threshold=1 / 3 + 1e-6).status

    def test_results_after_completed_repetition_do_not_cancel_the_hit(self):
        calls = [self.call() for _ in range(3)] + [self.call(result="changed")]
        assert json.loads(self.evaluate(calls).reason[1])["repeat_count"] == 3

    @pytest.mark.parametrize("content", [
        '{"tool_calls": null}', '["a", null, {"name":"x"}]', "free text",
        '{"tool_calls": [], "steps": [{"name":"x"}]}',
    ])
    def test_malformed_or_empty_containers_are_binary_false(self, content):
        res = RuleAgentTraceLoopDetection.eval(_data(content))
        assert not res.status
        assert res.applicable

    @pytest.mark.parametrize("config", [
        {"threshold": 0}, {"threshold": 1.1}, {"threshold": float("nan")},
        {"min_repeats": True}, {"min_repeats": 1}, {"min_repeats": 3.5},
        {"result_ngram_size": False}, {"result_ngram_size": 0},
        {"result_match_mode": "unknown"},
    ])
    def test_invalid_config_raises_instead_of_returning_a_quality_result(self, config):
        with pytest.raises(ValueError):
            self.evaluate([self.call()] * 3, **config)

    def test_instance_configuration_does_not_leak_to_later_runs_or_class_sdk(self):
        calls = [self.call(result=t) for t in ("ab", "ba", "ab")]
        assert self.evaluate(calls, result_ngram_size=1, threshold=1).status
        assert not self.evaluate(calls).status
        assert RuleAgentTraceLoopDetection.dynamic_config.threshold == 0.95
        assert RuleAgentTraceLoopDetection.eval(
            _data(json.dumps([self.call()] * 3))
        ).status


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
        assert res.applicable is False
        # Says what the trace does not carry, rather than claiming this run's
        # spending is unknown to us: the first is why the check does not apply,
        # the second is a gap in the run — a different verdict with a different
        # meaning downstream.
        assert "no token usage" in res.reason[0].lower()

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


class TestRuleMsSwiftSchema:
    def test_complete_record_passes(self):
        result = RuleMsSwiftSchema.eval(Data(**standard_ms_swift_record()))

        assert result.status is False
        assert result.label == [QualityLabel.QUALITY_GOOD]
        assert "matches" in result.reason[0]

    def test_missing_field_is_flagged_with_path(self):
        record = standard_ms_swift_record()
        record["tool_call_check"]["mismatches"] = [{
            "tool": "read",
            "tool_call_id": "call-1",
            "message_index": 0,
            "reasons": ["type_mismatch"],
            "extra_args": [],
            "missing_required": [],
        }]

        result = RuleMsSwiftSchema.eval(Data(**record))

        assert result.status is True
        assert result.label == ["AGENT_TRACE_QUALITY.RuleMsSwiftSchema"]
        assert "tool_call_check.mismatches[0]" in result.reason[0]
        assert "type_mismatch" in result.reason[0]

    def test_wrong_field_type_is_flagged(self):
        record = standard_ms_swift_record()
        record["messages"] = None

        result = RuleMsSwiftSchema.eval(Data(**record))

        assert result.status is True
        assert "ms_swift.messages must be a list" in result.reason[0]

    def test_converter_derived_fields_do_not_affect_schema_result(self):
        record = standard_ms_swift_record()
        record["RuleAgentTraceLoopDetection_content"] = '{"tool_calls": []}'

        result = RuleMsSwiftSchema.eval(Data(**record))

        assert result.status is False

    def test_rule_is_registered_without_field_requirements(self):
        assert Model.rule_name_map["RuleMsSwiftSchema"] is RuleMsSwiftSchema
        assert RuleMsSwiftSchema._required_fields == []
        assert not hasattr(RuleMsSwiftSchema, "eval_layer")
        assert not hasattr(RuleMsSwiftSchema, "input_data_type")


_TOOLS = [{"name": "get_weather", "parameters": {
    "type": "object", "properties": {"city": {"type": "string"}}, "required": ["city"],
}}]


def _traj(assistant_contents, tools):
    import json as _json
    msgs = [{"role": "user", "content": "do it"}] + [
        {"role": "assistant", "content": c} for c in assistant_contents
    ]
    return Data(data_id="1", content=_json.dumps({"messages": msgs, "tools": tools}))


class TestRuleAgentTextToolCallValidity:
    def test_no_calls_passes(self):
        assert RuleAgentTextToolCallValidity.eval(_traj(["Which city?"], _TOOLS)).status is False

    def test_valid_xml_call_passes(self):
        call = "<function=get_weather>\n<parameter=city>Paris</parameter>\n</function>"
        assert RuleAgentTextToolCallValidity.eval(_traj([call], _TOOLS)).status is False

    def test_valid_tool_call_tag_passes(self):
        call = '<tool_call>\n{"name": "get_weather", "arguments": {"city": "Paris"}}\n</tool_call>'
        assert RuleAgentTextToolCallValidity.eval(_traj([call], _TOOLS)).status is False

    def test_openai_style_tool_definition(self):
        tools = [{"type": "function", "function": _TOOLS[0]}]
        call = '<tool_call>{"name": "get_weather", "arguments": "{\\"city\\": \\"Paris\\"}"}</tool_call>'
        assert RuleAgentTextToolCallValidity.eval(_traj([call], tools)).status is False

    def test_undefined_tool(self):
        call = '<tool_call>{"name": "book_flight", "arguments": {}}</tool_call>'
        res = RuleAgentTextToolCallValidity.eval(_traj([call], _TOOLS))
        assert res.status is True
        assert res.label == ["QUALITY_BAD_EFFECTIVENESS.RuleAgentTextToolCallValidity"]
        assert "undefined tools" in res.reason[0]

    def test_unknown_and_missing_arguments(self):
        call = "<function=get_weather>\n<parameter=town>Paris</parameter>\n</function>"
        res = RuleAgentTextToolCallValidity.eval(_traj([call], _TOOLS))
        assert res.status is True
        assert any("not declared" in r for r in res.reason)
        assert any("Missing required" in r for r in res.reason)

    def test_empty_properties_schema_skips_argument_check(self):
        tools = [{"name": "lookup", "parameters": {"type": "dict", "properties": {}, "required": []}}]
        call = "<function=lookup>\n<parameter=ip>1.1.1.1</parameter>\n</function>"
        assert RuleAgentTextToolCallValidity.eval(_traj([call], tools)).status is False

    def test_malformed_tool_call(self):
        res = RuleAgentTextToolCallValidity.eval(_traj(["<tool_call>{broken</tool_call>"], _TOOLS))
        assert res.status is True
        assert "malformed" in res.reason[0]

    def test_invalid_trajectory_json(self):
        res = RuleAgentTextToolCallValidity.eval(Data(data_id="1", content="not json"))
        assert res.status is True
        assert "not valid JSON" in res.reason[0]
