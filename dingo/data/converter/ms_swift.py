"""ms-swift JSONL conversion with independently prepared evaluator fields.

Only configured, supported evaluators generate derived fields. Original fields
are preserved. The initial LLM inputs deliberately contain only message roles
and contents, with an empty task prompt; each preparer can evolve independently.
"""

import json
from typing import Any, Callable, Dict, List, Union

from dingo.config import InputArgs
from dingo.data.converter.base import BaseConverter
from dingo.io import Data


def _messages_content(record: Dict[str, Any]) -> str:
    messages = [
        {"role": message.get("role", ""), "content": message.get("content", "")}
        for message in record["messages"]
    ]
    return json.dumps(messages, ensure_ascii=False)


def _extract_tool_calls(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten assistant calls in source order without renaming arguments."""
    calls = []
    for message_index, message in enumerate(record["messages"]):
        if message.get("role") != "assistant":
            continue
        tool_calls = message.get("tool_calls", [])
        if tool_calls is None:
            tool_calls = []
        if not isinstance(tool_calls, list):
            raise ValueError(f"ms_swift messages[{message_index}].tool_calls must be a list")
        for call_index, call in enumerate(tool_calls):
            path = f"ms_swift messages[{message_index}].tool_calls[{call_index}].function"
            function = call.get("function") if isinstance(call, dict) else None
            if not isinstance(function, dict):
                raise ValueError(f"{path} must be an object")
            name = function.get("name")
            if not isinstance(name, str) or not name:
                raise ValueError(f"{path}.name must be a non-empty string")
            arguments = function.get("arguments", {})
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError as error:
                    raise ValueError(f"{path}.arguments must contain a JSON object") from error
            if not isinstance(arguments, dict):
                raise ValueError(f"{path}.arguments must be an object")
            calls.append({"tool_name": name, "args": arguments})
    return calls


def prepare_llm_agent_task_completion(record: Dict[str, Any]) -> Dict[str, str]:
    """Prepare the initial conversation-only task completion input."""
    return {
        "LLMAgentTaskCompletion_prompt": "",
        "LLMAgentTaskCompletion_content": _messages_content(record),
    }


def prepare_rule_agent_trace_loop_detection(record: Dict[str, Any]) -> Dict[str, str]:
    """Prepare ordered names and arguments for loop detection."""
    return {
        "RuleAgentTraceLoopDetection_content": json.dumps(
            {"tool_calls": _extract_tool_calls(record)}, ensure_ascii=False,
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
    return {
        "RuleAgentTraceDestructiveAction_content": json.dumps(
            {"tool_calls": _extract_tool_calls(record)}, ensure_ascii=False,
        ),
    }


_PREPARERS = {
    "LLMAgentTaskCompletion": prepare_llm_agent_task_completion,
    "RuleAgentTraceLoopDetection": prepare_rule_agent_trace_loop_detection,
    "LLMAgentToolCorrectness": prepare_llm_agent_tool_correctness,
    "RuleAgentTraceDestructiveAction": prepare_rule_agent_trace_destructive_action,
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
        preparers = [prepare for name, prepare in _PREPARERS.items() if name in selected_names]

        def _convert(raw: Union[str, Dict[str, Any]]) -> Data:
            record = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(record, dict):
                raise ValueError("ms_swift record must be a JSON object")
            messages = record.get("messages")
            if not isinstance(messages, list):
                raise ValueError("ms_swift messages must be a list")
            for index, message in enumerate(messages):
                if not isinstance(message, dict):
                    raise ValueError(f"ms_swift messages[{index}] must be an object")

            converted = dict(record)
            derived_fields = set()
            for prepare in preparers:
                extra_fields = prepare(record)
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
