"""Rule for validating ms-swift records against the delivery schema."""

from collections import Counter
from typing import Any, Dict, Iterable, Tuple

from dingo.io.input import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule

_TRAJECTORY_FIELDS = (
    "messages",
    "tools",
    "termination",
    "source",
    "harness",
    "model",
    "total_rounds",
    "total_tool_calls",
    "tool_counts",
    "reasoning_total_tokens",
    "tool_defs_tag",
    "missing_tool_defs",
    "tool_call_tag",
    "tool_call_check",
    "server_tool_calls",
    "metadata",
)
_TOP_LEVEL_FIELDS = _TRAJECTORY_FIELDS + ("completeness_tag", "completeness")
_TOOL_CALL_CHECK_FIELDS = (
    "total_calls",
    "hallucinated_calls",
    "undefined_tool_calls",
    "unverifiable_calls",
    "checked_calls",
    "extra_arg_calls",
    "missing_required_calls",
    "type_mismatch_calls",
    "defaulted_missing_calls",
    "mismatch_calls",
    "mismatches",
    "mismatches_truncated",
)
_COMPLETENESS_FIELDS = (
    "is_subagent",
    "spawn_calls",
    "mounted_subs",
    "subtree_complete",
    "unkeyed_mounts",
    "relay_mounts",
    "trailing_unanswered_call",
    "no_final_assistant_turn",
)
_MESSAGE_ROLES = frozenset({"system", "developer", "user", "assistant", "tool"})
_TOP_TOOL_DEF_TAGS = frozenset({"complete", "incomplete", "complete_with_incomplete_sub"})
_NESTED_TOOL_DEF_TAGS = frozenset({"complete", "incomplete"})
_TOP_TOOL_CALL_TAGS = frozenset({"consistent", "inconsistent", "consistent_with_inconsistent_sub"})
_NESTED_TOOL_CALL_TAGS = frozenset({"consistent", "inconsistent"})
_COMPLETENESS_TAGS = frozenset({
    "orphan_sub",
    "complete_main_no_sub",
    "incomplete_main_no_sub",
    "complete_main_with_complete_sub",
    "complete_main_with_incomplete_sub",
    "incomplete_main_with_complete_sub",
    "incomplete_main_with_incomplete_sub",
})
_MISMATCH_REASONS = frozenset({
    "undefined_tool", "extra_args", "missing_required", "type_mismatch",
})


def _fail(path: str, detail: str) -> None:
    raise ValueError(f"ms_swift record is malformed: {path} {detail}")


def _require_fields(value: Dict[str, Any], fields: Iterable[str], path: str) -> None:
    missing = sorted(field for field in fields if field not in value)
    if missing:
        _fail(path, f"is missing required field(s): {missing}")


def _require_object(value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    return value


def _require_list(value: Any, path: str) -> list:
    if not isinstance(value, list):
        _fail(path, "must be a list")
    return value


def _require_string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        _fail(path, "must be a string")
    return value


def _require_integer(value: Any, path: str, *, non_negative: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(path, "must be an integer")
    if non_negative and value < 0:
        _fail(path, "must be a non-negative integer")
    return value


def _require_boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(path, "must be a boolean")
    return value


def _validate_string_list(value: Any, path: str) -> None:
    for index, item in enumerate(_require_list(value, path)):
        _require_string(item, f"{path}[{index}]")


def _validate_messages(messages: Any, path: str) -> Tuple[int, list, Counter]:
    messages = _require_list(messages, path)
    assistant_count = 0
    calls = []
    tool_counts = Counter()
    call_ids = {}
    result_ids = {}
    tool_results = []

    for message_index, item in enumerate(messages):
        message_path = f"{path}[{message_index}]"
        message = _require_object(item, message_path)
        _require_fields(message, ("role", "content"), message_path)
        role = _require_string(message["role"], f"{message_path}.role")
        if role not in _MESSAGE_ROLES:
            _fail(f"{message_path}.role", f"must be one of {sorted(_MESSAGE_ROLES)}")
        _require_string(message["content"], f"{message_path}.content")

        if role == "assistant":
            assistant_count += 1
            _require_fields(message, ("reasoning_content",), message_path)
            _require_string(message["reasoning_content"], f"{message_path}.reasoning_content")
            if "reasoning_details" in message:
                details_path = f"{message_path}.reasoning_details"
                for detail_index, detail in enumerate(_require_list(message["reasoning_details"], details_path)):
                    _require_object(detail, f"{details_path}[{detail_index}]")
            if "tool_calls" not in message:
                continue
            tool_calls = _require_list(message["tool_calls"], f"{message_path}.tool_calls")
            for call_index, item_call in enumerate(tool_calls):
                call_path = f"{message_path}.tool_calls[{call_index}]"
                call = _require_object(item_call, call_path)
                _require_fields(call, ("type", "id", "function"), call_path)
                call_type = _require_string(call["type"], f"{call_path}.type")
                if call_type != "function":
                    _fail(f"{call_path}.type", "must equal 'function'")
                call_id = _require_string(call["id"], f"{call_path}.id")
                if call_id in call_ids:
                    _fail(f"{call_path}.id", f"duplicates {call_ids[call_id]}")
                call_ids[call_id] = f"{call_path}.id"
                function_path = f"{call_path}.function"
                function = _require_object(call["function"], function_path)
                _require_fields(function, ("name", "arguments"), function_path)
                name = _require_string(function["name"], f"{function_path}.name")
                if not name:
                    _fail(f"{function_path}.name", "must be non-empty")
                calls.append(call)
                tool_counts[name] += 1

        elif role == "tool":
            _require_fields(message, ("tool_call_id", "name"), message_path)
            tool_call_id = _require_string(message["tool_call_id"], f"{message_path}.tool_call_id")
            if tool_call_id in result_ids:
                _fail(
                    f"{message_path}.tool_call_id",
                    f"duplicates {result_ids[tool_call_id]}",
                )
            result_ids[tool_call_id] = f"{message_path}.tool_call_id"
            _require_string(message["name"], f"{message_path}.name")
            tool_results.append((f"{message_path}.tool_call_id", tool_call_id))

    for result_path, tool_call_id in tool_results:
        if tool_call_id not in call_ids:
            _fail(result_path, f"does not match any assistant tool call id: {tool_call_id!r}")
    return assistant_count, calls, tool_counts


def _validate_tools(tools: Any, path: str) -> None:
    names = set()
    for index, item in enumerate(_require_list(tools, path)):
        tool_path = f"{path}[{index}]"
        tool = _require_object(item, tool_path)
        _require_fields(tool, ("type", "name", "description", "parameters"), tool_path)
        tool_type = _require_string(tool["type"], f"{tool_path}.type")
        if tool_type != "function":
            _fail(f"{tool_path}.type", "must equal 'function'")
        name = _require_string(tool["name"], f"{tool_path}.name")
        if not name:
            _fail(f"{tool_path}.name", "must be non-empty")
        if name in names:
            _fail(f"{tool_path}.name", f"duplicates tool definition {name!r}")
        names.add(name)
        _require_string(tool["description"], f"{tool_path}.description")
        _require_object(tool["parameters"], f"{tool_path}.parameters")


def _validate_tool_call_check(value: Any, path: str, actual_calls: int) -> None:
    check = _require_object(value, path)
    _require_fields(check, _TOOL_CALL_CHECK_FIELDS, path)
    for field in _TOOL_CALL_CHECK_FIELDS:
        if field == "mismatches":
            mismatches = _require_list(check[field], f"{path}.{field}")
            if len(mismatches) > 50:
                _fail(f"{path}.{field}", "must contain at most 50 entries")
            for index, item in enumerate(mismatches):
                mismatch_path = f"{path}.{field}[{index}]"
                mismatch = _require_object(item, mismatch_path)
                _require_fields(
                    mismatch,
                    (
                        "tool", "tool_call_id", "message_index", "reasons",
                        "extra_args", "missing_required", "type_mismatch",
                    ),
                    mismatch_path,
                )
                _require_string(mismatch["tool"], f"{mismatch_path}.tool")
                _require_string(mismatch["tool_call_id"], f"{mismatch_path}.tool_call_id")
                _require_integer(
                    mismatch["message_index"], f"{mismatch_path}.message_index",
                    non_negative=True,
                )
                _validate_string_list(mismatch["reasons"], f"{mismatch_path}.reasons")
                unknown_reasons = set(mismatch["reasons"]) - _MISMATCH_REASONS
                if unknown_reasons:
                    _fail(
                        f"{mismatch_path}.reasons",
                        f"contains unsupported value(s): {sorted(unknown_reasons)}",
                    )
                _validate_string_list(mismatch["extra_args"], f"{mismatch_path}.extra_args")
                _validate_string_list(
                    mismatch["missing_required"], f"{mismatch_path}.missing_required",
                )
                type_mismatches_path = f"{mismatch_path}.type_mismatch"
                for type_index, type_item in enumerate(
                    _require_list(mismatch["type_mismatch"], type_mismatches_path)
                ):
                    type_path = f"{type_mismatches_path}[{type_index}]"
                    type_mismatch = _require_object(type_item, type_path)
                    _require_fields(type_mismatch, ("arg", "declared", "actual"), type_path)
                    _require_string(type_mismatch["arg"], f"{type_path}.arg")
                    _validate_string_list(type_mismatch["declared"], f"{type_path}.declared")
                    _require_string(type_mismatch["actual"], f"{type_path}.actual")
        else:
            _require_integer(check[field], f"{path}.{field}", non_negative=True)
    if check["total_calls"] != actual_calls:
        _fail(f"{path}.total_calls", f"must equal the actual tool-call count {actual_calls}")


def _validate_server_tool_calls(value: Any, path: str) -> None:
    for index, item in enumerate(_require_list(value, path)):
        call_path = f"{path}[{index}]"
        call = _require_object(item, call_path)
        _require_fields(call, ("name", "id", "arguments", "origin", "result"), call_path)
        _require_string(call["name"], f"{call_path}.name")
        _require_string(call["id"], f"{call_path}.id")
        origin = _require_string(call["origin"], f"{call_path}.origin")
        if origin not in ("history", "response"):
            _fail(f"{call_path}.origin", "must equal 'history' or 'response'")
        if call["result"] is not None:
            _require_object(call["result"], f"{call_path}.result")


def _validate_metadata(value: Any, path: str) -> None:
    metadata = _require_object(value, path)
    _require_fields(metadata, ("source_file", "line_no", "created_at"), path)
    _require_string(metadata["source_file"], f"{path}.source_file")
    _require_integer(metadata["line_no"], f"{path}.line_no", non_negative=True)
    _require_string(metadata["created_at"], f"{path}.created_at")


def _validate_completeness(value: Any, path: str) -> None:
    completeness = _require_object(value, path)
    _require_fields(completeness, _COMPLETENESS_FIELDS, path)
    for field in ("is_subagent", "subtree_complete", "trailing_unanswered_call", "no_final_assistant_turn"):
        _require_boolean(completeness[field], f"{path}.{field}")
    for field in ("spawn_calls", "mounted_subs", "unkeyed_mounts", "relay_mounts"):
        _require_integer(completeness[field], f"{path}.{field}", non_negative=True)


def _validate_trajectory(record: Any, path: str, *, top_level: bool) -> None:
    record = _require_object(record, path)
    _require_fields(record, _TOP_LEVEL_FIELDS if top_level else _TRAJECTORY_FIELDS, path)

    for field in ("termination", "source", "harness", "model"):
        _require_string(record[field], f"{path}.{field}")
    assistant_count, calls, actual_tool_counts = _validate_messages(
        record["messages"], f"{path}.messages",
    )
    _validate_tools(record["tools"], f"{path}.tools")

    total_rounds = _require_integer(record["total_rounds"], f"{path}.total_rounds", non_negative=True)
    total_tool_calls = _require_integer(
        record["total_tool_calls"], f"{path}.total_tool_calls", non_negative=True,
    )
    if total_rounds != assistant_count:
        _fail(f"{path}.total_rounds", f"must equal the assistant-message count {assistant_count}")
    if total_tool_calls != len(calls):
        _fail(f"{path}.total_tool_calls", f"must equal the actual tool-call count {len(calls)}")

    tool_counts = _require_object(record["tool_counts"], f"{path}.tool_counts")
    for name, count in tool_counts.items():
        _require_string(name, f"{path}.tool_counts key")
        _require_integer(count, f"{path}.tool_counts[{name!r}]", non_negative=True)
    if tool_counts != dict(actual_tool_counts):
        _fail(f"{path}.tool_counts", f"must equal the actual counts {dict(actual_tool_counts)}")

    _require_integer(record["reasoning_total_tokens"], f"{path}.reasoning_total_tokens", non_negative=True)
    tool_defs_tag = _require_string(record["tool_defs_tag"], f"{path}.tool_defs_tag")
    tool_call_tag = _require_string(record["tool_call_tag"], f"{path}.tool_call_tag")
    valid_def_tags = _TOP_TOOL_DEF_TAGS if top_level else _NESTED_TOOL_DEF_TAGS
    valid_call_tags = _TOP_TOOL_CALL_TAGS if top_level else _NESTED_TOOL_CALL_TAGS
    if tool_defs_tag not in valid_def_tags:
        _fail(f"{path}.tool_defs_tag", f"must be one of {sorted(valid_def_tags)}")
    if tool_call_tag not in valid_call_tags:
        _fail(f"{path}.tool_call_tag", f"must be one of {sorted(valid_call_tags)}")
    _validate_string_list(record["missing_tool_defs"], f"{path}.missing_tool_defs")
    _validate_tool_call_check(record["tool_call_check"], f"{path}.tool_call_check", len(calls))
    _validate_server_tool_calls(record["server_tool_calls"], f"{path}.server_tool_calls")
    _validate_metadata(record["metadata"], f"{path}.metadata")

    if top_level:
        completeness_tag = _require_string(record["completeness_tag"], f"{path}.completeness_tag")
        if completeness_tag not in _COMPLETENESS_TAGS:
            _fail(f"{path}.completeness_tag", f"must be one of {sorted(_COMPLETENESS_TAGS)}")
        _validate_completeness(record["completeness"], f"{path}.completeness")

    if "sub_agent_relay_mounts" in record:
        mounts = _require_object(record["sub_agent_relay_mounts"], f"{path}.sub_agent_relay_mounts")
        for spawn_id, relay_id in mounts.items():
            _require_string(spawn_id, f"{path}.sub_agent_relay_mounts key")
            _require_string(relay_id, f"{path}.sub_agent_relay_mounts[{spawn_id!r}]")
    if "sub_agent_trajectory" in record:
        trajectories = _require_object(record["sub_agent_trajectory"], f"{path}.sub_agent_trajectory")
        for call_id, trajectory in trajectories.items():
            _require_string(call_id, f"{path}.sub_agent_trajectory key")
            _validate_trajectory(
                trajectory, f"{path}.sub_agent_trajectory[{call_id!r}]", top_level=False,
            )


@Model.rule_register("AGENT_TRACE_QUALITY", ["agent_trace_basic"])
class RuleMsSwiftSchema(BaseRule):
    """Validate one raw ms-swift dataset record against the delivery schema.

    This is a regular record-level rule rather than an Agent Trace evaluator.
    It consumes the complete ``Data`` object directly, so it has no converter
    preparer and requires no ``fields`` mapping in evaluator configuration.
    """

    _required_fields = []

    _metric_info = {
        "metric_name": "RuleMsSwiftSchema",
        "metric_group": "AGENT_TRACE_QUALITY",
        "description": (
            "Checks a raw ms-swift record for required fields, field types, "
            "nested message and tool-call structure, and declared-count consistency."
        ),
    }

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        result = EvalDetail(metric=cls.__name__)
        record = input_data.to_dict()

        try:
            _validate_trajectory(record, "ms_swift", top_level=True)
        except ValueError as error:
            result.status = True
            result.label = [f"{cls.metric_type}.{cls.__name__}"]
            result.reason = [str(error)]
            return result

        result.label = [QualityLabel.QUALITY_GOOD]
        result.reason = ["The record matches the standardized ms-swift schema"]
        return result
