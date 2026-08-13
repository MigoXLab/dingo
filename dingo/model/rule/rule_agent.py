"""
Agent-specific rule evaluators for deterministic quality checks.

These rules run without LLM calls, checking structural properties
of agent execution traces (loops, token budget, latency anomalies).
"""

import hashlib
import json
import statistics
from typing import Any, List, Optional

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule


def _load_trace_items(content: Any, primary_key: str, secondary_key: str) -> List[dict]:
    """Parse agent-trace ``content`` into a list of step / tool-call items.

    Accepts a JSON string, an already-parsed list, or a dict wrapper. For a dict
    payload, returns the first non-empty list among ``primary_key`` /
    ``secondary_key`` — using ``or`` (not ``dict.get`` defaults) so a
    present-but-null key falls through instead of yielding ``None``. Returns
    ``[]`` for free text, JSON null, or any non-list payload, so callers can
    iterate the result without guarding against ``None``.
    """
    try:
        data = json.loads(content) if isinstance(content, str) else content
    except (json.JSONDecodeError, TypeError):
        return []

    if isinstance(data, dict):
        items = data.get(primary_key) or data.get(secondary_key) or []
    elif isinstance(data, list):
        items = data
    else:
        return []

    return items if isinstance(items, list) else []


@Model.rule_register("AGENT_TRACE_QUALITY", ["agent_trace_basic"])
class RuleAgentTraceLoopDetection(BaseRule):
    """Detect repetitive tool call patterns indicating infinite loops.

    Input: content = JSON array of tool call objects with 'tool_name' field.
    Detection: n-gram analysis on tool call signatures.
    A loop is detected when the same subsequence of 2+ calls repeats 3 or more
    consecutive times.

    A signature combines the tool name with a fingerprint of its arguments, so
    a fan-out over one tool with different arguments (eight distinct search
    queries) is not mistaken for a stuck loop, while the same call issued over
    and over still is. Calls carrying no arguments compare by name alone.
    """

    # Trace-level evaluator: declares input_data_type / eval_layer so agent
    # orchestrators (e.g. dingo-saas) feed it the whole tool-call sequence as
    # JSON rather than running it per-span on plain text.
    eval_layer = "trajectory"
    input_data_type = "agent_trace_json"

    _ARGUMENT_KEYS = ("args", "arguments", "tool_input", "input")

    _required_fields = [RequiredField.CONTENT]

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        result = EvalDetail(metric=cls.__name__)

        calls = cls._extract_calls(input_data.content)
        if len(calls) < 6:
            result.label = [QualityLabel.QUALITY_GOOD]
            # State what was checked. A pass with no reason is indistinguishable
            # from a rule that did not run, and reads as a clean bill of health
            # for a trace nobody looked at.
            result.reason = [
                f"{len(calls)} tool calls — too few to analyse for repetition "
                "(needs 6)"
            ]
            return result

        loop_info = cls._detect_loops([signature for _, signature in calls])
        if loop_info is None:
            loop_info = cls._detect_repeated_identical_calls(calls)
        if loop_info:
            start = loop_info["position"]
            pattern = [name for name, _ in calls[start : start + len(loop_info["pattern"])]]
            result.status = True
            result.label = [f"{cls.metric_type}.{cls.__name__}"]
            result.reason = [
                f"Loop detected: pattern {pattern} "
                f"repeats {loop_info['count']} times at position {start}"
            ]
        else:
            result.label = [QualityLabel.QUALITY_GOOD]
            result.reason = [
                f"{len(calls)} tool calls checked, no repeating pattern found"
            ]

        return result

    @classmethod
    def _extract_calls(cls, content: str) -> List[tuple]:
        """Return ``(tool_name, signature)`` per call, in trace order."""
        calls = []
        for item in _load_trace_items(content, "tool_calls", "steps"):
            if not isinstance(item, dict):
                continue
            name = item.get("tool_name") or item.get("name")
            if not name:
                continue
            calls.append((name, f"{name}|{cls._argument_fingerprint(item)}"))
        return calls

    @classmethod
    def _argument_fingerprint(cls, item: dict) -> str:
        """Stable fingerprint of a call's arguments; empty when it has none."""
        for key in cls._ARGUMENT_KEYS:
            value = item.get(key)
            if value in (None, "", {}, []):
                continue
            try:
                normalized = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
            except (TypeError, ValueError):
                normalized = str(value)
            return hashlib.sha256(normalized.encode()).hexdigest()[:12]
        return ""

    @classmethod
    def _detect_repeated_identical_calls(
        cls, calls: List[tuple], min_repeats: int = 3
    ) -> Optional[dict]:
        """Catch one call repeated verbatim, which ``_detect_loops`` cannot see.

        Loop detection starts at two-call patterns, so a tool invoked three
        times in a row with byte-identical arguments — a research agent asking
        the same calculation three times — is not a "pattern" and goes
        unreported, even though it is the plainest loop there is.

        Only signatures carrying a real argument fingerprint qualify. Without
        arguments, three consecutive calls to one tool are as likely to be three
        different files as one repeat, and flagging those would make every
        source that omits arguments look broken.
        """
        run_start = 0
        for index in range(1, len(calls) + 1):
            same = index < len(calls) and calls[index][1] == calls[run_start][1]
            if same:
                continue
            count = index - run_start
            fingerprint = calls[run_start][1].split("|", 1)[-1]
            if count >= min_repeats and fingerprint:
                return {
                    "pattern": [calls[run_start][1]],
                    "count": count,
                    "position": run_start,
                }
            run_start = index
        return None

    @classmethod
    def _detect_loops(
        cls, names: List[str], min_pattern_len: int = 2, min_repeats: int = 3
    ) -> Optional[dict]:
        for pattern_len in range(min_pattern_len, len(names) // min_repeats + 1):
            for start in range(len(names) - pattern_len * min_repeats + 1):
                pattern = names[start : start + pattern_len]
                count = 1
                pos = start + pattern_len
                while pos + pattern_len <= len(names):
                    if names[pos : pos + pattern_len] == pattern:
                        count += 1
                        pos += pattern_len
                    else:
                        break
                if count >= min_repeats:
                    return {
                        "pattern": pattern,
                        "count": count,
                        "position": start,
                    }
        return None


@Model.rule_register("AGENT_TRACE_QUALITY", ["agent_trace_basic"])
class RuleAgentTraceTokenBudget(BaseRule):
    """Check if total token usage exceeds a configurable budget.

    Input: content = JSON with 'total_tokens' field, or metadata with token info.
    Default budget: 500,000 tokens (configurable via dynamic_config.threshold).
    """

    # Trace-level evaluator (see RuleAgentTraceLoopDetection for rationale).
    eval_layer = "efficiency"
    input_data_type = "agent_trace_json"

    _required_fields = [RequiredField.CONTENT]
    # A real EvaluatorRuleArgs (not None) so set_config_rule's model_copy() in
    # the local/spark executors does not raise; the default also documents the
    # 500k budget and keeps it overridable via dynamic_config.threshold.
    dynamic_config = EvaluatorRuleArgs(threshold=500_000)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        result = EvalDetail(metric=cls.__name__)

        budget = 500_000
        if cls.dynamic_config and cls.dynamic_config.threshold is not None:
            try:
                budget = int(cls.dynamic_config.threshold)
            except (TypeError, ValueError):
                pass

        total_tokens = cls._extract_tokens(input_data)
        if total_tokens is None:
            result.label = [QualityLabel.QUALITY_GOOD]
            # Not "within budget" — unknown. Many sources record no usage, and
            # a silent pass there claims a check that never happened.
            result.reason = ["No token usage recorded, so the budget was not checked"]
            return result

        if total_tokens > budget:
            result.status = True
            result.label = [f"{cls.metric_type}.{cls.__name__}"]
            result.reason = [
                f"Token usage {total_tokens:,} exceeds budget {budget:,}"
            ]
            result.score = min(1.0, budget / total_tokens) if total_tokens > 0 else 0.0
        else:
            result.label = [QualityLabel.QUALITY_GOOD]
            result.reason = [
                f"Token usage {total_tokens:,} of budget {budget:,} "
                f"({total_tokens / budget:.0%})"
            ]
            result.score = 1.0

        return result

    @classmethod
    def _extract_tokens(cls, input_data: Data) -> Optional[int]:
        for source in [input_data.content, getattr(input_data, "metadata", None)]:
            if source is None:
                continue
            try:
                data = json.loads(source) if isinstance(source, str) else source
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(data, dict):
                val = data.get("total_tokens")
                if val is not None:
                    try:
                        return int(val)
                    except (TypeError, ValueError):
                        pass
        return None


@Model.rule_register("AGENT_TRACE_QUALITY", ["agent_trace_basic"])
class RuleAgentTraceLatencyAnomaly(BaseRule):
    """Detect abnormally slow steps using statistical outlier analysis.

    Input: content = JSON array of step objects with 'duration' or 'duration_seconds' field.
    A step is flagged if its duration exceeds mean + 3*stddev.

    Steps may declare a peer group via ``group`` (alias: ``type``); the outlier
    test then runs *within* each group. An agent trace is
    normally bimodal — tool calls finish in milliseconds while model inferences
    take seconds — and pooling them makes the statistics meaningless in both
    directions: the tool durations drag the mean down until a perfectly normal
    final generation trips the threshold, while a genuinely stuck tool call hides
    far below a threshold set by the inference times. Grouping compares each step
    against its own kind.

    Steps that declare no group are pooled together, so input without the field
    behaves exactly as before.
    """

    # Trace-level evaluator (see RuleAgentTraceLoopDetection for rationale).
    eval_layer = "efficiency"
    input_data_type = "agent_trace_json"

    _required_fields = [RequiredField.CONTENT]

    #: Minimum samples in a group before its statistics mean anything.
    _MIN_GROUP_SIZE = 3

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        result = EvalDetail(metric=cls.__name__)

        steps = cls._extract_steps(input_data.content)
        stats = cls._group_stats(steps)

        # Iterate in original step order so the reported anomalies keep the
        # trace's own ordering rather than the grouping's.
        anomalies = []
        for step in steps:
            group = stats.get(step["group"])
            if group and step["duration"] is not None and step["duration"] > group["threshold"]:
                anomalies.append((step, group))

        if anomalies:
            result.status = True
            result.label = [f"{cls.metric_type}.{cls.__name__}"]
            # Name the peer group only when there is more than one, so a reader
            # knows what an outlier was compared against.
            multi_group = len(stats) > 1
            result.reason = []
            for step, group in anomalies[:5]:
                label = f"{step['group']} " if multi_group and step["group"] else ""
                result.reason.append(
                    f"Step '{step['name']}' took {step['duration']:.2f}s "
                    f"({label}threshold: {group['threshold']:.2f}s, "
                    f"mean: {group['mean']:.2f}s)"
                )
        else:
            result.label = [QualityLabel.QUALITY_GOOD]
            if stats:
                checked = sum(g["count"] for g in stats.values())
                result.reason = [
                    f"{checked} timed steps in {len(stats)} peer "
                    f"{'group' if len(stats) == 1 else 'groups'}, no outliers"
                ]
            else:
                # Distinguish "nothing stood out" from "there was nothing to
                # compare": a group needs a few samples before its statistics
                # mean anything, and a bare pass hid that the test never ran.
                result.reason = [
                    "Too few timed steps to test for outliers "
                    f"(needs {cls._MIN_GROUP_SIZE} per peer group)"
                ]

        return result

    @classmethod
    def _group_stats(cls, steps: List[dict]) -> dict:
        """Per-group mean/threshold, skipping groups with too few samples."""
        durations: dict = {}
        for step in steps:
            if step["duration"] is not None and step["duration"] > 0:
                durations.setdefault(step["group"], []).append(step["duration"])

        stats = {}
        for group, values in durations.items():
            if len(values) < cls._MIN_GROUP_SIZE:
                continue
            mean = statistics.mean(values)
            stats[group] = {
                "mean": mean,
                "threshold": mean + 3 * statistics.stdev(values),
                # Carried so a passing verdict can say how much was examined.
                "count": len(values),
            }
        return stats

    @classmethod
    def _extract_steps(cls, content: str) -> List[dict]:
        return [
            {
                "name": item.get("name", "unknown"),
                "duration": cls._safe_float(
                    item.get("duration", item.get("duration_seconds"))
                ),
                "group": str(item.get("group") or item.get("type") or ""),
            }
            for item in _load_trace_items(content, "steps", "tool_calls")
            if isinstance(item, dict)
        ]

    @classmethod
    def _safe_float(cls, val) -> Optional[float]:
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None
