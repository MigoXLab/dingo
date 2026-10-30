import copy
from test.scripts.ms_swift_test_utils import standard_ms_swift_record

import pytest

from dingo.config import InputArgs
from dingo.data.converter import converters
from dingo.io import Data
from dingo.model.rule.agent_trace.rule_ms_swift import RuleMsSwiftSchema

REQUIRED_TOP_LEVEL_FIELDS = (
    "messages", "tools", "termination", "source", "harness", "model",
    "total_rounds", "total_tool_calls", "tool_counts", "reasoning_total_tokens",
    "tool_defs_tag", "missing_tool_defs", "tool_call_tag", "tool_call_check",
    "server_tool_calls", "metadata", "completeness_tag", "completeness",
)


def convert(record, names=()):
    args = InputArgs(
        dataset={"source": "local", "format": "ms_swift"},
        evaluator=[{"evals": [{"name": name}]} for name in names],
    )
    return converters["ms_swift"].convertor(args)(record)


def validate_ms_swift_record(record):
    """Exercise schema validation through its evaluator, not the converter."""
    result = RuleMsSwiftSchema.eval(Data(**record))
    if result.status:
        raise ValueError(result.reason[0])
    return result


@pytest.mark.parametrize("field", REQUIRED_TOP_LEVEL_FIELDS)
def test_every_required_top_level_field_must_exist(field):
    record = standard_ms_swift_record()
    record.pop(field)
    with pytest.raises(ValueError, match=rf"missing required field.*{field}"):
        validate_ms_swift_record(record)


def test_optional_top_level_fields_may_be_absent():
    record = standard_ms_swift_record()
    assert "sub_agent_trajectory" not in record
    assert "sub_agent_relay_mounts" not in record
    validate_ms_swift_record(record)


def test_explicit_empty_values_are_preserved_and_valid():
    record = standard_ms_swift_record(messages=[{
        "role": "assistant", "content": "", "reasoning_content": "", "tool_calls": [],
    }])
    validate_ms_swift_record(record)


def test_developer_message_role_is_valid():
    record = standard_ms_swift_record(messages=[{
        "role": "developer", "content": "Follow the application policy.",
    }])
    converted = convert(record, ("LLMAgentTaskCompletion",))
    assert '"role": "developer"' in converted.LLMAgentTaskCompletion_content


def test_converter_does_not_run_schema_validation_before_preparer(monkeypatch):
    import dingo.data.converter.ms_swift as module

    calls = []

    def prepare(_record):
        calls.append("called")
        return {"RuleAgentTraceLoopDetection_content": "{}"}

    monkeypatch.setitem(module._PREPARERS, "RuleAgentTraceLoopDetection", prepare)
    record = standard_ms_swift_record()
    record.pop("tools")
    converted = convert(record, ("RuleAgentTraceLoopDetection",))
    assert calls == ["called"]
    assert converted.RuleAgentTraceLoopDetection_content == "{}"


@pytest.mark.parametrize("message, missing", [
    ({"content": "x"}, "role"),
    ({"role": "user"}, "content"),
    ({"role": "assistant", "content": "x"}, "reasoning_content"),
    ({"role": "tool", "content": "x", "name": "read"}, "tool_call_id"),
    ({"role": "tool", "content": "x", "tool_call_id": "a"}, "name"),
])
def test_required_message_fields_must_exist(message, missing):
    record = standard_ms_swift_record(messages=[message])
    with pytest.raises(ValueError, match=rf"missing required field.*{missing}"):
        validate_ms_swift_record(record)


def test_unanswered_tool_call_is_valid_format_and_quality_metadata_carries_the_gap():
    record = standard_ms_swift_record(messages=[{
        "role": "assistant", "content": "", "reasoning_content": "",
        "tool_calls": [{
            "type": "function", "id": "call-1",
            "function": {"name": "read", "arguments": {"path": "a.txt"}},
        }],
    }])
    record["completeness_tag"] = "incomplete_main_no_sub"
    record["completeness"]["trailing_unanswered_call"] = True
    validate_ms_swift_record(record)


def test_duplicate_tool_results_are_not_standard_format():
    record = standard_ms_swift_record(messages=[
        {
            "role": "assistant", "content": "", "reasoning_content": "",
            "tool_calls": [{
                "type": "function", "id": "call-1",
                "function": {"name": "read", "arguments": {}},
            }],
        },
        {"role": "tool", "tool_call_id": "call-1", "name": "read", "content": "a"},
        {"role": "tool", "tool_call_id": "call-1", "name": "read", "content": "b"},
    ])
    with pytest.raises(ValueError, match=r"tool_call_id duplicates"):
        validate_ms_swift_record(record)


def test_missing_tool_definition_is_quality_issue_not_format_error():
    record = standard_ms_swift_record(messages=[{
        "role": "assistant", "content": "", "reasoning_content": "",
        "tool_calls": [{
            "type": "function", "id": "call-1",
            "function": {"name": "read", "arguments": {}},
        }],
    }])
    record["tool_defs_tag"] = "incomplete"
    record["missing_tool_defs"] = ["read"]
    record["tool_call_tag"] = "inconsistent"
    record["tool_call_check"]["undefined_tool_calls"] = 1
    record["tool_call_check"]["mismatch_calls"] = 1
    validate_ms_swift_record(record)


def test_nested_trajectory_is_validated_recursively():
    child = standard_ms_swift_record()
    child.pop("completeness_tag")
    child.pop("completeness")
    parent = standard_ms_swift_record(sub_agent_trajectory={"spawn-1": child})
    validate_ms_swift_record(parent)
    invalid = copy.deepcopy(parent)
    invalid["sub_agent_trajectory"]["spawn-1"].pop("tools")
    with pytest.raises(ValueError, match=r"sub_agent_trajectory.*missing required field.*tools"):
        validate_ms_swift_record(invalid)


def test_declared_statistics_must_match_messages():
    record = standard_ms_swift_record()
    record["total_tool_calls"] = 1
    with pytest.raises(ValueError, match=r"total_tool_calls.*actual tool-call count 0"):
        validate_ms_swift_record(record)


def test_mismatch_detail_requires_its_standard_fields():
    record = standard_ms_swift_record()
    record["tool_call_check"]["mismatches"] = [{"tool": "read"}]
    with pytest.raises(ValueError, match=r"mismatches\[0\].*missing required field.*reasons"):
        validate_ms_swift_record(record)


def test_invalid_json_has_format_error():
    # JSON syntax must still be parsed before a Data object can reach any rule.
    with pytest.raises(ValueError, match=r"malformed: invalid JSON"):
        convert("{not json")
