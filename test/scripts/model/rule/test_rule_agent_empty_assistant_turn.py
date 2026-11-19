"""Native-message empty-turn detection scans every assistant without loss filtering."""

import json
from copy import deepcopy
from pathlib import Path
from test.scripts.ms_swift_test_utils import standard_ms_swift_record

import pytest

from dingo.config import InputArgs
from dingo.exec import LocalExecutor
from dingo.io import Data
from dingo.io.output.eval_detail import QualityLabel
from dingo.model import Model
from dingo.model.rule.agent_trace.rule_ms_swift import RuleMsSwiftSchema
from dingo.model.rule.rule_agent import RuleAgentTraceEmptyAssistantTurn

LABEL = "AGENT_TRACE_QUALITY.RuleAgentTraceEmptyAssistantTurn"
SAMPLE_PATH = Path(__file__).resolve().parents[4] / "test" / "data" / "agent" / "empty_assistant_turn.jsonl"


def _assistant(content="", reasoning="", **extra):
    return {"role": "assistant", "content": content, "reasoning_content": reasoning, **extra}


def _call():
    return {"type": "function", "id": "read_1", "function": {
        "name": "Read", "arguments": {"path": "settings.json"},
    }}


def _eval(messages):
    return RuleAgentTraceEmptyAssistantTurn.eval(Data(messages=messages))


def _sample_records():
    return [json.loads(line) for line in SAMPLE_PATH.read_text(encoding="utf-8").splitlines()]


def test_complete_scan_counts_empty_turns_at_start_middle_and_end():
    messages = [
        _assistant(), _assistant("5"), _assistant(),
        _assistant(reasoning="先读配置"), _assistant(tool_calls=[_call()]), _assistant(),
    ]
    result = _eval(messages)
    assert result.status is True
    assert result.label == [LABEL]
    assert result.applicable is True
    assert result.score is None
    assert result.reason == [
        "共检查 6 条 assistant 消息，发现 3 条 content、reasoning_content 均为空且无工具调用的空回合。"
    ]


@pytest.mark.parametrize("loss", [True, False, None, 0, 1, "true", "false", "0", "1"])
def test_loss_flag_does_not_change_which_messages_are_checked(loss):
    result = _eval([_assistant(loss=loss)])
    assert result.status is True
    assert "发现 1 条" in result.reason[0]


@pytest.mark.parametrize("content,reasoning,calls,empty", [
    ("", "", [], True), (" \t", "\n", [], True),
    ("5", "", [], False), ("", "先读取配置", [], False),
    ("", "", [_call()], False), ("", "读文件", [_call()], False),
    ("正在读取", "", [_call()], False), ("正在读取", "读文件", [_call()], False),
])
def test_signal_combinations(content, reasoning, calls, empty):
    result = _eval([_assistant(content, reasoning, tool_calls=calls)])
    assert result.status is empty
    assert result.label == ([LABEL] if empty else [QualityLabel.QUALITY_GOOD])


@pytest.mark.parametrize("content", ["ok", "5", "...", "…", "<|im_end|>"])
def test_nonempty_text_is_not_classified_by_semantics_or_stop_marker_patterns(content):
    result = _eval([_assistant(content)])
    assert result.status is False
    assert result.reason == [
        "共检查 1 条 assistant 消息，未发现 content、reasoning_content 均为空且无工具调用的空回合。"
    ]


def test_current_messages_only_and_input_is_not_modified():
    messages = [
        {"role": "system", "content": ""}, {"role": "user", "content": ""},
        _assistant("完成"), {"role": "tool", "content": ""},
    ]
    original = deepcopy(messages)
    result = RuleAgentTraceEmptyAssistantTurn.eval(Data(
        messages=messages, total_rounds=999,
        sub_agent_trajectory={"child": {"messages": [_assistant()]}},
    ))
    assert result.status is False
    assert "共检查 1 条" in result.reason[0]
    assert messages == original


@pytest.mark.parametrize("messages", [
    None, {}, "[]", [None], [{"content": ""}], [{"role": 1}],
    [{"role": "assistant", "reasoning_content": ""}],
    [{"role": "assistant", "content": ""}],
    [_assistant(content=None)], [_assistant(content=0)],
    [_assistant(reasoning=None)], [_assistant(reasoning=False)],
    [_assistant(tool_calls=None)], [_assistant(tool_calls=False)],
    [_assistant(tool_calls={})], [_assistant(tool_calls=[None])],
    [_assistant(tool_calls=[{}])],
    [_assistant(tool_calls=[{"type": "function", "id": "read_1", "function": {}}])],
    [_assistant(), _assistant(reasoning=None)],
])
def test_malformed_input_is_na_even_after_an_earlier_empty_turn(messages):
    result = _eval(messages)
    assert result.applicable is False
    assert result.not_applicable_kind == "structural"
    assert result.not_applicable_code == "invalid_messages"
    assert result.status is False
    assert result.label == []
    assert result.score is None
    assert result.effective_verdict == "n/a"


def test_all_malformed_messages_are_scanned_and_counted():
    result = _eval([_assistant(), None, _assistant(reasoning=None), _assistant()])
    assert result.applicable is False
    assert result.reason == [
        "messages 中有 2 条消息的必要结构无法读取，无法完成空 assistant 回合检查。"
    ]


@pytest.mark.parametrize("change", [
    {"type": "other"}, {"id": False}, {"function": None},
    {"function": {"name": "", "arguments": {}}},
    {"function": {"name": "Read"}},
])
def test_malformed_tool_calls_are_not_treated_as_valid_action_signals(change):
    call = _call()
    call.update(change)
    assert _eval([_assistant(tool_calls=[call])]).applicable is False


@pytest.mark.parametrize("arguments", [None, {}, [], "raw", 0, False])
def test_tool_arguments_are_not_reinterpreted_by_the_empty_turn_rule(arguments):
    call = _call()
    call["function"]["arguments"] = arguments
    result = _eval([_assistant(tool_calls=[call])])
    assert result.applicable is True
    assert result.status is False


@pytest.mark.parametrize("messages", [[], [{"role": "user", "content": "hello"}]])
def test_no_assistant_is_not_a_pass(messages):
    result = _eval(messages)
    assert result.applicable is False
    assert result.not_applicable_code == "no_assistant_messages"
    assert result.status is False
    assert result.label == []


def test_registration_metadata_and_missing_messages():
    rule = RuleAgentTraceEmptyAssistantTurn
    assert Model.rule_name_map[rule.__name__] is rule
    assert rule in Model.rule_groups["agent_trace_basic"]
    assert rule.metric_type == "AGENT_TRACE_QUALITY"
    assert rule._required_fields == []
    assert rule._metric_info["metric_name"] == rule.__name__
    assert rule.eval(Data()).not_applicable_code == "invalid_messages"


def test_bundled_samples_have_valid_full_schemas_and_expected_counts():
    records = _sample_records()
    assert len(records) == 2
    for index, record in enumerate(records):
        schema = RuleMsSwiftSchema.eval(Data(**record))
        assert schema.status is False, schema.reason
        assert _eval(record["messages"]).status is (index == 0)
    assert "共检查 6 条 assistant 消息，发现 3 条" in _eval(records[0]["messages"]).reason[0]


@pytest.mark.parametrize("dataset_format", ["jsonl", "ms_swift"])
def test_local_pipeline_reads_native_messages_and_saves_issue_pass_and_na(tmp_path, monkeypatch, dataset_format):
    monkeypatch.setenv("LOCAL_DEPLOYMENT_MODE", "true")
    records = _sample_records()
    no_assistant = standard_ms_swift_record(
        messages=[{"role": "user", "content": "hello"}],
        completeness_tag="incomplete_main_no_sub",
    )
    no_assistant["completeness"]["no_final_assistant_turn"] = True
    records.append(no_assistant)
    input_path = tmp_path / "traces.jsonl"
    input_path.write_text("\n".join(json.dumps(row) for row in records), encoding="utf-8")
    output_path = tmp_path / "results"
    executor = LocalExecutor(InputArgs(
        input_path=str(input_path), output_path=str(output_path),
        dataset={"source": "local", "format": dataset_format},
        executor={"max_workers": 2, "result_save": {
            "bad": True, "good": True, "raw": True, "all_labels": True, "merge": True,
        }},
        evaluator=[{
            "fields": {"messages": "messages"},
            "evals": [{"name": "RuleAgentTraceEmptyAssistantTurn"}],
        }],
    ))
    converted = list(executor.load_data())
    assert all(not row._derived_fields for row in converted)
    assert [row.messages for row in converted] == [row["messages"] for row in records]
    summary = executor.execute()
    assert summary.total == 3
    assert summary.num_bad == 1
    assert summary.type_count["messages"][LABEL] == 1
    saved = [json.loads(line) for line in (output_path / "all_results.jsonl").read_text(encoding="utf-8").splitlines()]
    details = [row["dingo_result"]["eval_details"]["messages"][0] for row in saved]
    assert [item["status"] for item in details] == [True, False, False]
    assert [item["applicable"] for item in details] == [True, True, False]
    assert [item["label"] for item in details] == [[LABEL], [QualityLabel.QUALITY_GOOD], []]
    assert "发现 3 条" in details[0]["reason"][0]
