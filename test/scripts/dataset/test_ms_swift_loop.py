"""Lossless loop inputs and deterministic text-similarity regression tests."""

import copy
import json
from test.scripts.ms_swift_test_utils import standard_ms_swift_record

import pytest

from dingo.config import InputArgs
from dingo.data.converter import converters
from dingo.data.converter.agent_trace_utils import split_tool_result
from dingo.io import Data
from dingo.model.rule.rule_agent import RuleAgentTraceLoopDetection
from dingo.model.rule.utils.agent_trace_similarity import (
    LoopSettings, ResultSimilarity, canonical_args, extract_calls,
)


def envelope(body, newline="\n", chunk="c1"):
    return newline.join([
        f"Chunk ID: {chunk}", "Wall time: 30.0014 seconds",
        "Process running with session ID 4868", "Original token count: 12",
        "Output:", "",
    ]) + body


def convert(record):
    args = InputArgs(
        dataset={"source": "local", "format": "ms_swift"},
        evaluator=[{"fields": {"content": "RuleAgentTraceLoopDetection_content"},
                    "evals": [{"name": "RuleAgentTraceLoopDetection"}]}],
    )
    data = converters["ms_swift"].convertor(args)(record)
    return data, json.loads(data.RuleAgentTraceLoopDetection_content)


def record_for(results):
    messages = []
    for i, result in enumerate(results):
        messages.append({
            "role": "assistant", "content": "", "reasoning_content": "",
            "tool_calls": [{"id": f"c{i}", "type": "function", "function": {
                "name": "example", "arguments": {"target": 1},
            }}],
        })
        if result is not None:
            messages.append({"role": "tool", "name": "example",
                             "tool_call_id": f"c{i}", "content": result})
    return standard_ms_swift_record(messages=messages)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("body", ["", "  indented\nOutput:\nmore\n", '{"ok":true}', "\rprogress\r"])
def test_split_preserves_every_character(newline, body):
    raw = envelope(body, newline)
    headers, result = split_tool_result(raw)
    assert result == body
    assert headers + result == raw
    assert headers.endswith("Output:" + newline)


@pytest.mark.parametrize("raw", [
    "", "Output:\nordinary output", '{"Output":"json string"}',
    "docs\nChunk ID: c\nWall time: 1 seconds\nOutput:\nexample",
    "Chunk ID: c\nWall time: 1 seconds\nunknown header\nOutput:\nbody",
    "Chunk ID: c\nOutput:\nmissing wall time",
    "Chunk ID: c\nWall time: 1 seconds\nincomplete",
])
def test_unrecognized_wrappers_remain_complete_bodies(raw):
    assert split_tool_result(raw) == ("", raw)


def test_output_marker_at_end_without_newline():
    raw = "Chunk ID: c\nWall time: 1 seconds\nOutput:"
    assert split_tool_result(raw) == (raw, "")


def test_converter_pairs_by_id_and_preserves_source():
    record = record_for([envelope("one"), envelope("two")])
    record["messages"][1], record["messages"][3] = record["messages"][3], record["messages"][1]
    original = copy.deepcopy(record)
    data, payload = convert(record)
    calls = payload["tool_calls"]
    assert list(payload) == ["tool_calls"]
    assert [c["result"] for c in calls] == ["one", "two"]
    assert [c["result_message_index"] for c in calls] == [3, 1]
    assert [c["call_id"] for c in calls] == ["c0", "c1"]
    assert [c["call_index"] for c in calls] == [0, 1]
    assert [c["message_index"] for c in calls] == [0, 2]
    assert all(c["result_present"] for c in calls)
    assert record == original
    assert data.messages == original["messages"]


def test_missing_and_empty_results_are_different():
    _, payload = convert(record_for([None, ""]))
    a, b = payload["tool_calls"]
    assert a["result_present"] is False
    assert a["result_message_index"] is None
    assert a["result_headers"] == a["result"] == ""
    assert b["result_present"] is True
    assert b["result"] == ""


@pytest.mark.parametrize("duplicate_result", [False, True])
def test_duplicate_ids_empty_only_loop_metric_input(duplicate_result):
    record = record_for(["a", "b"])
    if duplicate_result:
        record["messages"][3]["tool_call_id"] = "c0"
    else:
        record["messages"][2]["tool_calls"][0]["id"] = "c0"
    args = InputArgs(
        dataset={"source": "local", "format": "ms_swift"},
        evaluator=[{"evals": [{"name": n}]} for n in (
            "RuleAgentTraceLoopDetection", "RuleAgentTraceTokenBudget",
        )],
    )
    data = converters["ms_swift"].convertor(args)(record)
    assert data.RuleAgentTraceLoopDetection_content == ""
    assert data.RuleAgentTraceTokenBudget_content == "{}"


def test_no_tool_exemptions_and_headers_do_not_prevent_repetition():
    for tool in ("write_stdin", "search", "unseen_custom_tool"):
        record = record_for([envelope("running", chunk=str(i)) for i in range(3)])
        for message in record["messages"]:
            for call in message.get("tool_calls", []):
                call["function"]["name"] = tool
        data, payload = convert(record)
        assert len({c["result_headers"] for c in payload["tool_calls"]}) == 3
        assert RuleAgentTraceLoopDetection.eval(
            Data(content=data.RuleAgentTraceLoopDetection_content)
        ).status


def test_segments_and_current_node_scope():
    record = record_for(["same", "same", "same"])
    record["messages"].insert(4, {"role": "user", "content": "new request"})
    record["sub_agent_trajectory"] = {"c0": record_for(["nested"])}
    record["server_tool_calls"] = [{"name": "server", "id": "server"}]
    data, payload = convert(record)
    assert [c["segment_id"] for c in payload["tool_calls"]] == [0, 0, 1]
    assert len(payload["tool_calls"]) == 3
    assert not RuleAgentTraceLoopDetection.eval(
        Data(content=data.RuleAgentTraceLoopDetection_content)
    ).status


def test_counter_jaccard_known_value_and_cache_eviction():
    items = [{"tool_name": "a", "args": {}, "result": text}
             for text in ("abcdef", "abcdeg", "zzzzzz", "", "")]
    calls = extract_calls(items)
    settings = LoopSettings()
    for size in (0, 1, 4096):
        sim = ResultSimilarity(settings, cache_size=size)
        assert sim(calls[0], calls[1]) == pytest.approx(1 / 3)
        assert sim(calls[1], calls[0]) == pytest.approx(1 / 3)
        assert sim(calls[0], calls[2]) == 0
        assert sim(calls[3], calls[4]) == 1
        assert sim(calls[0], calls[1]) == pytest.approx(1 / 3)
        assert len(sim.pairs) <= size


def test_ngrams_count_frequency_not_just_presence():
    calls = extract_calls([{"name": "a", "args": {}, "result": t}
                           for t in ("aaaaaaaaaa", "aaaaaaaaaaaaaaa")])
    assert ResultSimilarity(LoopSettings())(*calls) == pytest.approx(6 / 11)


def test_canonical_arguments_preserve_types_and_array_order():
    assert canonical_args({"a": 1, "b": 2}) == canonical_args({"b": 2, "a": 1})
    assert canonical_args(True) != canonical_args(1)
    assert canonical_args([1, 2]) != canonical_args([2, 1])
    assert canonical_args(None) != canonical_args({})
