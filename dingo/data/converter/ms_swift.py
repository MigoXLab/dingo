"""ms-swift JSONL conversion with independently prepared evaluator fields.

Only configured, supported evaluators generate derived fields. Original fields
are preserved. The initial LLM inputs deliberately contain only message roles
and contents, with an empty task prompt. Deterministic rule conversions are
self-contained so their input handling can evolve independently.
"""

import json
from typing import Any, Callable, Dict, Union

from dingo.config import InputArgs
from dingo.data.converter.base import BaseConverter
from dingo.io import Data


def _messages(record: Dict[str, Any]) -> list:
    """Return messages only when their shared structure is extractable."""
    messages = record.get("messages")
    if not isinstance(messages, list):
        raise TypeError("ms_swift messages must be a list")
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            raise TypeError(f"ms_swift messages[{index}] must be an object")
        if not isinstance(message.get("role"), str):
            raise TypeError(f"ms_swift messages[{index}].role must be a string")
    return messages


def _messages_content(record: Dict[str, Any]) -> str:
    messages = []
    for index, message in enumerate(_messages(record)):
        if not isinstance(message.get("content"), str):
            raise TypeError(f"ms_swift messages[{index}].content must be a string")
        messages.append({"role": message["role"], "content": message["content"]})
    return json.dumps(messages, ensure_ascii=False)


def _tool_call_name_and_arguments(call: Dict[str, Any]):
    """Read fields already guaranteed by the standardized-format validator."""
    function = call["function"]
    arguments = function["arguments"]
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            # A string is itself a valid JSON value under the standard.
            pass
    return function["name"], arguments


def prepare_llm_agent_task_completion(record: Dict[str, Any]) -> Dict[str, str]:
    """Prepare the initial conversation-only task completion input."""
    return {
        "LLMAgentTaskCompletion_prompt": "",
        "LLMAgentTaskCompletion_content": _messages_content(record),
    }


def prepare_rule_agent_trace_loop_detection(record: Dict[str, Any]) -> Dict[str, str]:
    """Prepare ordered names and arguments for loop detection."""
    calls = []
    for message_index, message in enumerate(_messages(record)):
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls", [])
        if tool_calls is None:
            tool_calls = []
        if not isinstance(tool_calls, list):
            raise ValueError(f"ms_swift messages[{message_index}].tool_calls must be a list")
        for call in tool_calls:
            name, arguments = _tool_call_name_and_arguments(call)
            item = {"tool_name": name, "args": arguments}
            calls.append(item)
    return {
        "RuleAgentTraceLoopDetection_content": json.dumps(
            {"tool_calls": calls}, ensure_ascii=False,
        ),
    }


def prepare_llm_agent_tool_correctness(record: Dict[str, Any]) -> Dict[str, str]:
    """Prepare the initial conversation-only tool correctness input."""
    return {
        "LLMAgentToolCorrectness_prompt": "",
        "LLMAgentToolCorrectness_content": _messages_content(record),
    }


def prepare_rule_agent_trace_destructive_action(record: Dict[str, Any]) -> Dict[str, str]:
    """Prepare tool arguments as recorded, including unchanged ``cmd`` keys."""
    calls = []
    for message_index, message in enumerate(_messages(record)):
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls", [])
        if tool_calls is None:
            tool_calls = []
        if not isinstance(tool_calls, list):
            raise ValueError(f"ms_swift messages[{message_index}].tool_calls must be a list")
        for call in tool_calls:
            name, arguments = _tool_call_name_and_arguments(call)
            item = {"tool_name": name, "args": arguments}
            calls.append(item)
    return {
        "RuleAgentTraceDestructiveAction_content": json.dumps(
            {"tool_calls": calls}, ensure_ascii=False,
        ),
    }


def prepare_rule_agent_trace_gateway_bypass(record: Dict[str, Any]) -> Dict[str, str]:
    """Associate policy responses and explicit execution status by call ID."""
    observations = {}
    for index, message in enumerate(_messages(record)):
        call_id = message.get("tool_call_id")
        if message.get("role") == "tool" and isinstance(call_id, str) and call_id:
            if call_id in observations:
                raise ValueError(f"ms_swift messages[{index}] has duplicate tool_call_id {call_id!r}")
            observations[call_id] = message
    calls = []
    seen_ids = set()
    for message_index, message in enumerate(_messages(record)):
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls", [])
        if tool_calls is None:
            tool_calls = []
        if not isinstance(tool_calls, list):
            raise ValueError(f"ms_swift messages[{message_index}].tool_calls must be a list")
        for call_index, call in enumerate(tool_calls):
            path = f"ms_swift messages[{message_index}].tool_calls[{call_index}].function"
            name, arguments = _tool_call_name_and_arguments(call)
            item = {"tool_name": name, "args": arguments}
            call_id = call.get("id")
            observation = {}
            if isinstance(call_id, str) and call_id:
                if call_id in seen_ids:
                    raise ValueError(f"ms_swift {path} has duplicate call id {call_id!r}")
                seen_ids.add(call_id)
                item["call_id"] = call_id
                observation = observations.get(call_id, {})
            if "content" in observation:
                item["result"] = observation["content"]
            # These extensions must be explicit; never derive status from prose.
            for key in ("status", "duration", "duration_seconds", "group", "type"):
                if key in observation:
                    item[key] = observation[key]
                elif key in call:
                    item[key] = call[key]
            calls.append(item)
    return {
        "RuleAgentTraceGatewayBypass_content": json.dumps(
            {"tool_calls": calls}, ensure_ascii=False,
        ),
    }


def prepare_rule_agent_trace_integrity(record: Dict[str, Any]) -> Dict[str, str]:
    """Check delivered-file counters without claiming upstream completeness."""
    observations = {}
    for index, message in enumerate(_messages(record)):
        call_id = message.get("tool_call_id")
        if message.get("role") == "tool" and isinstance(call_id, str) and call_id:
            if call_id in observations:
                raise ValueError(f"ms_swift messages[{index}] has duplicate tool_call_id {call_id!r}")
            observations[call_id] = message
    tool_spans_recorded = 0
    open_observation_count = 0
    seen_ids = set()
    for message_index, message in enumerate(_messages(record)):
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls", [])
        if tool_calls is None:
            tool_calls = []
        if not isinstance(tool_calls, list):
            raise ValueError(f"ms_swift messages[{message_index}].tool_calls must be a list")
        for call_index, call in enumerate(tool_calls):
            path = f"ms_swift messages[{message_index}].tool_calls[{call_index}].function"
            name, arguments = _tool_call_name_and_arguments(call)
            tool_spans_recorded += 1
            call_id = call.get("id")
            if isinstance(call_id, str) and call_id:
                if call_id in seen_ids:
                    raise ValueError(f"ms_swift {path} has duplicate call id {call_id!r}")
                seen_ids.add(call_id)
                if call_id not in observations:
                    open_observation_count += 1
            else:
                open_observation_count += 1
    content = {
        "tool_spans_recorded": tool_spans_recorded,
        "open_observation_count": open_observation_count,
    }
    if "total_tool_calls" in record:
        content["tool_calls_expected"] = record["total_tool_calls"]
    if "trace_truncated" in record:
        content["trace_truncated"] = record["trace_truncated"]
    return {"RuleAgentTraceIntegrity_content": json.dumps(content, ensure_ascii=False)}


def prepare_rule_agent_trace_latency_anomaly(record: Dict[str, Any]) -> Dict[str, str]:
    """Use only explicitly recorded per-call timings and peer groups."""
    observations = {}
    for index, message in enumerate(_messages(record)):
        call_id = message.get("tool_call_id")
        if message.get("role") == "tool" and isinstance(call_id, str) and call_id:
            if call_id in observations:
                raise ValueError(f"ms_swift messages[{index}] has duplicate tool_call_id {call_id!r}")
            observations[call_id] = message
    steps = []
    seen_ids = set()
    for message_index, message in enumerate(_messages(record)):
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls", [])
        if tool_calls is None:
            tool_calls = []
        if not isinstance(tool_calls, list):
            raise ValueError(f"ms_swift messages[{message_index}].tool_calls must be a list")
        for call_index, call in enumerate(tool_calls):
            path = f"ms_swift messages[{message_index}].tool_calls[{call_index}].function"
            name, arguments = _tool_call_name_and_arguments(call)
            step = {"name": name}
            call_id = call.get("id")
            observation = {}
            if isinstance(call_id, str) and call_id:
                if call_id in seen_ids:
                    raise ValueError(f"ms_swift {path} has duplicate call id {call_id!r}")
                seen_ids.add(call_id)
                observation = observations.get(call_id, {})
            # Copy recorded timings and groups, preferring matched tool results.
            for key in ("duration", "duration_seconds", "group", "type"):
                if key in observation:
                    value = observation[key]
                elif key in call:
                    value = call[key]
                else:
                    continue
                # Standard ms-swift reserves call.type="function" for the
                # invocation kind; it is not a latency peer-group label.
                if key == "type" and value == "function":
                    continue
                step[key] = value
            steps.append(step)
    return {"RuleAgentTraceLatencyAnomaly_content": json.dumps({"steps": steps}, ensure_ascii=False)}


def prepare_rule_agent_trace_sandbox_explicitly_disabled(record: Dict[str, Any]) -> Dict[str, str]:
    """Preserve the explicit sandbox-disable argument."""
    calls = []
    for message_index, message in enumerate(_messages(record)):
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls", [])
        if tool_calls is None:
            tool_calls = []
        if not isinstance(tool_calls, list):
            raise ValueError(f"ms_swift messages[{message_index}].tool_calls must be a list")
        for call in tool_calls:
            name, arguments = _tool_call_name_and_arguments(call)
            item = {"tool_name": name, "args": arguments}
            calls.append(item)
    return {
        "RuleAgentTraceSandboxExplicitlyDisabled_content": json.dumps(
            {"tool_calls": calls}, ensure_ascii=False,
        ),
    }


def prepare_rule_agent_trace_secret_exposure(record: Dict[str, Any]) -> Dict[str, str]:
    """Supply actual tool observations matched by ID, never by array position."""
    observations = {}
    for index, message in enumerate(_messages(record)):
        call_id = message.get("tool_call_id")
        if message.get("role") == "tool" and isinstance(call_id, str) and call_id:
            if call_id in observations:
                raise ValueError(f"ms_swift messages[{index}] has duplicate tool_call_id {call_id!r}")
            observations[call_id] = message
    calls = []
    seen_ids = set()
    for message_index, message in enumerate(_messages(record)):
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls", [])
        if tool_calls is None:
            tool_calls = []
        if not isinstance(tool_calls, list):
            raise ValueError(f"ms_swift messages[{message_index}].tool_calls must be a list")
        for call_index, call in enumerate(tool_calls):
            path = f"ms_swift messages[{message_index}].tool_calls[{call_index}].function"
            name, arguments = _tool_call_name_and_arguments(call)
            item = {"tool_name": name, "args": arguments}
            call_id = call.get("id")
            observation = {}
            if isinstance(call_id, str) and call_id:
                if call_id in seen_ids:
                    raise ValueError(f"ms_swift {path} has duplicate call id {call_id!r}")
                seen_ids.add(call_id)
                item["call_id"] = call_id
                observation = observations.get(call_id, {})
            if "content" in observation:
                item["result"] = observation["content"]
            # These extensions must be explicit; never derive status from prose.
            for key in ("status", "duration", "duration_seconds", "group", "type"):
                if key in observation:
                    item[key] = observation[key]
                elif key in call:
                    item[key] = call[key]
            calls.append(item)
    return {
        "RuleAgentTraceSecretExposure_content": json.dumps(
            {"tool_calls": calls}, ensure_ascii=False,
        ),
    }


def prepare_rule_agent_trace_sensitive_access(record: Dict[str, Any]) -> Dict[str, str]:
    """Preserve parameter structure for the rule's sensitive-path scan."""
    calls = []
    for message_index, message in enumerate(_messages(record)):
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls", [])
        if tool_calls is None:
            tool_calls = []
        if not isinstance(tool_calls, list):
            raise ValueError(f"ms_swift messages[{message_index}].tool_calls must be a list")
        for call in tool_calls:
            name, arguments = _tool_call_name_and_arguments(call)
            item = {"tool_name": name, "args": arguments}
            calls.append(item)
    return {
        "RuleAgentTraceSensitiveAccess_content": json.dumps(
            {"tool_calls": calls}, ensure_ascii=False,
        ),
    }


def prepare_rule_agent_trace_token_budget(record: Dict[str, Any]) -> Dict[str, str]:
    """Do not substitute reasoning_total_tokens for total token usage."""
    content = {"total_tokens": record["total_tokens"]} if "total_tokens" in record else {}
    return {"RuleAgentTraceTokenBudget_content": json.dumps(content, ensure_ascii=False)}


def prepare_llm_agent_argument_correctness(record: Dict[str, Any]) -> Dict[str, str]:
    """Prepare the initial conversation-only argument correctness input."""
    return {
        "LLMAgentArgumentCorrectness_prompt": "",
        "LLMAgentArgumentCorrectness_content": _messages_content(record),
    }


def prepare_llm_agent_error_recovery(record: Dict[str, Any]) -> Dict[str, str]:
    """Prepare conversation evidence without inventing structured error events."""
    return {
        "LLMAgentErrorRecovery_prompt": "",
        "LLMAgentErrorRecovery_content": _messages_content(record),
    }


def prepare_llm_agent_plan_adherence(record: Dict[str, Any]) -> Dict[str, str]:
    """Leave both the original plan and the task goal explicitly unset."""
    return {
        "LLMAgentPlanAdherence_prompt": "",
        "LLMAgentPlanAdherence_content": _messages_content(record),
        "LLMAgentPlanAdherence_context": "",
    }


def prepare_llm_agent_plan_quality(record: Dict[str, Any]) -> Dict[str, str]:
    """Prepare the initial conversation-only plan quality input."""
    return {
        "LLMAgentPlanQuality_prompt": "",
        "LLMAgentPlanQuality_content": _messages_content(record),
    }


def prepare_llm_agent_step_efficiency(record: Dict[str, Any]) -> Dict[str, str]:
    """Prepare the initial conversation-only step efficiency input."""
    return {
        "LLMAgentStepEfficiency_prompt": "",
        "LLMAgentStepEfficiency_content": _messages_content(record),
    }


_PREPARERS = {
    "LLMAgentTaskCompletion": prepare_llm_agent_task_completion,
    "RuleAgentTraceLoopDetection": prepare_rule_agent_trace_loop_detection,
    "LLMAgentToolCorrectness": prepare_llm_agent_tool_correctness,
    "RuleAgentTraceDestructiveAction": prepare_rule_agent_trace_destructive_action,
    "RuleAgentTraceGatewayBypass": prepare_rule_agent_trace_gateway_bypass,
    "RuleAgentTraceIntegrity": prepare_rule_agent_trace_integrity,
    "RuleAgentTraceLatencyAnomaly": prepare_rule_agent_trace_latency_anomaly,
    "RuleAgentTraceSandboxExplicitlyDisabled": prepare_rule_agent_trace_sandbox_explicitly_disabled,
    "RuleAgentTraceSecretExposure": prepare_rule_agent_trace_secret_exposure,
    "RuleAgentTraceSensitiveAccess": prepare_rule_agent_trace_sensitive_access,
    "RuleAgentTraceTokenBudget": prepare_rule_agent_trace_token_budget,
    "LLMAgentArgumentCorrectness": prepare_llm_agent_argument_correctness,
    "LLMAgentErrorRecovery": prepare_llm_agent_error_recovery,
    "LLMAgentPlanAdherence": prepare_llm_agent_plan_adherence,
    "LLMAgentPlanQuality": prepare_llm_agent_plan_quality,
    "LLMAgentStepEfficiency": prepare_llm_agent_step_efficiency,
}

# Empty values follow each preparer's public output contract. All current
# ms-swift derived fields are strings: rule ``content`` fields contain JSON
# strings on success, while LLM ``prompt``/``content``/``context`` fields are
# plain strings. Keep this mapping explicit so a future list/dict field can use
# []/{} here instead of being guessed from its name.
_PREPARER_EMPTY_OUTPUTS = {
    "LLMAgentTaskCompletion": {
        "LLMAgentTaskCompletion_prompt": "",
        "LLMAgentTaskCompletion_content": "",
    },
    "RuleAgentTraceLoopDetection": {"RuleAgentTraceLoopDetection_content": ""},
    "LLMAgentToolCorrectness": {
        "LLMAgentToolCorrectness_prompt": "",
        "LLMAgentToolCorrectness_content": "",
    },
    "RuleAgentTraceDestructiveAction": {"RuleAgentTraceDestructiveAction_content": ""},
    "RuleAgentTraceGatewayBypass": {"RuleAgentTraceGatewayBypass_content": ""},
    "RuleAgentTraceIntegrity": {"RuleAgentTraceIntegrity_content": ""},
    "RuleAgentTraceLatencyAnomaly": {"RuleAgentTraceLatencyAnomaly_content": ""},
    "RuleAgentTraceSandboxExplicitlyDisabled": {
        "RuleAgentTraceSandboxExplicitlyDisabled_content": "",
    },
    "RuleAgentTraceSecretExposure": {"RuleAgentTraceSecretExposure_content": ""},
    "RuleAgentTraceSensitiveAccess": {"RuleAgentTraceSensitiveAccess_content": ""},
    "RuleAgentTraceTokenBudget": {"RuleAgentTraceTokenBudget_content": ""},
    "LLMAgentArgumentCorrectness": {
        "LLMAgentArgumentCorrectness_prompt": "",
        "LLMAgentArgumentCorrectness_content": "",
    },
    "LLMAgentErrorRecovery": {
        "LLMAgentErrorRecovery_prompt": "",
        "LLMAgentErrorRecovery_content": "",
    },
    "LLMAgentPlanAdherence": {
        "LLMAgentPlanAdherence_prompt": "",
        "LLMAgentPlanAdherence_content": "",
        "LLMAgentPlanAdherence_context": "",
    },
    "LLMAgentPlanQuality": {
        "LLMAgentPlanQuality_prompt": "",
        "LLMAgentPlanQuality_content": "",
    },
    "LLMAgentStepEfficiency": {
        "LLMAgentStepEfficiency_prompt": "",
        "LLMAgentStepEfficiency_content": "",
    },
}


@BaseConverter.register("ms_swift")
class MsSwiftConverter(BaseConverter):
    """Convert one ms-swift record into one Data with evaluator-specific fields."""

    @classmethod
    def convertor(cls, input_args: InputArgs) -> Callable:
        selected_names = {
            evaluator.name
            for pipeline in input_args.evaluator
            for evaluator in pipeline.evals
        }
        preparers = [
            (name, prepare)
            for name, prepare in _PREPARERS.items()
            if name in selected_names
        ]

        def _convert(raw: Union[str, Dict[str, Any]]) -> Data:
            if isinstance(raw, str):
                try:
                    record = json.loads(raw)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        f"ms_swift record is malformed: invalid JSON ({error.msg})"
                    ) from error
            else:
                record = raw

            converted = dict(record)
            derived_fields = set()
            for name, prepare in preparers:
                try:
                    extra_fields = prepare(record)
                except Exception:
                    # Extraction failures are data-level gaps for this metric,
                    # not a reason to discard the record or block other metrics.
                    # Each evaluator receives empty values of its declared type
                    # and decides how to report the missing input.
                    extra_fields = dict(_PREPARER_EMPTY_OUTPUTS[name])
                conflicts = extra_fields.keys() & converted.keys()
                if conflicts:
                    raise ValueError(
                        f"ms_swift derived fields conflict with existing fields: {sorted(conflicts)}"
                    )
                converted.update(extra_fields)
                derived_fields.update(extra_fields)
            data = Data(**converted)
            data._derived_fields = derived_fields
            return data

        return _convert
