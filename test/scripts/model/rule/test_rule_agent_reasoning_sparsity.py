"""Reasoning sparsity is a per-trajectory feature, never a quality failure."""

import json
from pathlib import Path
from test.scripts.ms_swift_test_utils import standard_ms_swift_record

import pytest

from dingo.config import InputArgs
from dingo.config.input_args import EvaluatorRuleArgs
from dingo.exec import LocalExecutor
from dingo.io import Data
from dingo.model import Model
from dingo.model.rule.agent_trace.rule_ms_swift import RuleMsSwiftSchema
from dingo.model.rule.rule_agent import RuleAgentTraceReasoningSparsity

LABEL = "AGENT_TRACE_QUALITY.RuleAgentTraceReasoningSparsity"


def _assistant(reasoning="", **extra):
    return {"role": "assistant", "content": "回答", "reasoning_content": reasoning, **extra}


def _rule(**config):
    rule = RuleAgentTraceReasoningSparsity()
    Model.set_config_rule(rule, EvaluatorRuleArgs(**config))
    return rule


@pytest.mark.parametrize("empty,matched", [(0, False), (6, False), (7, False), (8, True), (10, True)])
def test_default_threshold_is_strictly_greater(empty, matched):
    messages = [_assistant()] * empty + [_assistant("检查配置")] * (10 - empty)
    result = _rule().eval(Data(messages=messages))
    assert result.label == ([LABEL] if matched else [])
    assert result.status is False
    assert result.effective_verdict == "pass"
    assert result.score is None
    assert result.applicable is True
    assert result.reason == [
        f"共 10 条 assistant 消息，其中 {empty} 条 reasoning_content 为空，占比 {empty / 10:.2%}；"
        + ("超过" if matched else "未超过")
        + "阈值 70.00%，" + ("命中" if matched else "未命中") + " reasoning 稀疏特征。"
    ]


def test_only_current_assistant_messages_count_including_tool_calls():
    data = Data(
        messages=[
            {"role": "system", "content": "指令"},
            {"role": "user", "content": "读取配置"},
            _assistant(" \t\n", content="", tool_calls=[{
                "type": "function", "id": "read-1",
                "function": {"name": "Read", "arguments": {"path": "config.json"}},
            }]),
            {"role": "tool", "content": "{}", "name": "Read", "tool_call_id": "read-1"},
            _assistant("配置已确认"),
        ],
        total_rounds=999,
        sub_agent_trajectory={"child": {"messages": [_assistant()] * 100}},
    )
    result = _rule().eval(data)
    assert result.label == []
    assert "共 2 条 assistant 消息，其中 1 条" in result.reason[0]
    assert "50.00%" in result.reason[0]


def test_thresholds_are_instance_local_and_endpoints_are_supported():
    data = Data(messages=[_assistant()])
    lower = _rule(threshold=0)
    upper = _rule(threshold=1)
    assert lower.eval(data).label == [LABEL]
    assert upper.eval(data).label == []
    assert RuleAgentTraceReasoningSparsity.dynamic_config.threshold == 0.7


def test_comparison_does_not_use_rounded_percentage():
    data = Data(messages=[_assistant()] * 7 + [_assistant("思考")] * 3)
    assert _rule(threshold=0.699999).eval(data).label == [LABEL]
    assert _rule(threshold=0.7).eval(data).label == []


@pytest.mark.parametrize("threshold", [-0.1, 1.1, float("nan"), float("inf")])
def test_invalid_threshold_is_configuration_error(threshold):
    with pytest.raises(ValueError, match=r"threshold must be in \[0, 1\]"):
        _rule(threshold=threshold).eval(Data(messages=[_assistant()]))


@pytest.mark.parametrize("messages,code", [
    (None, "invalid_messages"),
    ({}, "invalid_messages"),
    ([None], "invalid_messages"),
    ([{"content": "no role"}], "invalid_messages"),
    ([{"role": "assistant"}], "invalid_reasoning_content"),
    ([_assistant(None)], "invalid_reasoning_content"),
    ([_assistant(0)], "invalid_reasoning_content"),
    ([_assistant(False)], "invalid_reasoning_content"),
    ([], "no_assistant_messages"),
    ([{"role": "user", "content": "hi"}], "no_assistant_messages"),
])
def test_unmeasurable_inputs_are_not_silently_counted_as_empty(messages, code):
    result = _rule().eval(Data(messages=messages))
    assert result.applicable is False
    assert result.not_applicable_kind == "structural"
    assert result.not_applicable_code == code
    assert result.label == []
    assert result.status is False
    assert result.score is None


def test_missing_messages_and_registration():
    assert _rule().eval(Data()).not_applicable_code == "invalid_messages"
    assert Model.rule_name_map["RuleAgentTraceReasoningSparsity"] is RuleAgentTraceReasoningSparsity
    assert RuleAgentTraceReasoningSparsity in Model.rule_groups["agent_trace_basic"]


def test_bundled_examples_are_complete_standardized_records():
    repo_root = Path(__file__).resolve().parents[4]
    sample_path = repo_root / "test" / "data" / "agent" / "reasoning_sparsity.jsonl"
    records = [json.loads(line) for line in sample_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    for index, record in enumerate(records):
        schema = RuleMsSwiftSchema.eval(Data(**record))
        assert schema.status is False, schema.reason
        result = _rule().eval(Data(messages=record["messages"]))
        assert result.label == ([LABEL] if index == 0 else [])


@pytest.mark.parametrize("dataset_format", ["jsonl", "ms_swift"])
def test_local_pipeline_preserves_feature_results_without_marking_samples_bad(
    tmp_path, monkeypatch, dataset_format,
):
    monkeypatch.setenv("LOCAL_DEPLOYMENT_MODE", "true")
    records = [
        standard_ms_swift_record(messages=[_assistant()]),
        standard_ms_swift_record(messages=[_assistant()] * 7 + [_assistant("思考")] * 3),
        standard_ms_swift_record(messages=[{"role": "user", "content": "hi"}]),
    ]
    input_path = tmp_path / "traces.jsonl"
    input_path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")
    output_path = tmp_path / "results"
    executor = LocalExecutor(InputArgs(
        input_path=str(input_path), output_path=str(output_path),
        dataset={"source": "local", "format": dataset_format},
        executor={"max_workers": 2, "result_save": {
            "bad": True, "good": True, "all_labels": True, "merge": True,
        }},
        evaluator=[{
            "fields": {"messages": "messages"},
            "evals": [{"name": "RuleAgentTraceReasoningSparsity", "config": {"threshold": 0.7}}],
        }],
    ))
    converted = list(executor.load_data())
    assert all(not item._derived_fields for item in converted)
    summary = executor.execute()
    assert summary.total == 3
    assert summary.num_bad == 0
    assert summary.type_count["messages"][LABEL] == 1
    results = [json.loads(line) for line in (output_path / "all_results.jsonl").read_text(encoding="utf-8").splitlines()]
    details = [item["dingo_result"]["eval_details"]["messages"][0] for item in results]
    assert [item["label"] for item in details] == [[LABEL], [], []]
    assert details[2]["applicable"] is False
    assert all(item["dingo_result"]["eval_status"] is False for item in results)
    assert all(item["messages"] == record["messages"] for item, record in zip(results, records))
