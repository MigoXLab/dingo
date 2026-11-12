"""Spark per-record regression tests; no live cluster is required."""

import json
from unittest.mock import MagicMock

from dingo.config import InputArgs
from dingo.exec.spark import SparkExecutor


def test_ms_swift_spark_output_preserves_json_result_strings():
    args = InputArgs(
        dataset={"source": "local", "format": "ms_swift"},
        executor={"result_save": {"all_labels": True}},
        evaluator=[{
            "fields": {"content": "RuleAgentTraceLoopDetection_content"},
            "evals": [{"name": "RuleAgentTraceLoopDetection"}],
        }],
    )
    body = '  {"ok":true,"items":[1,2]}  '
    source = {
        "messages": [{"role": "tool", "tool_call_id": "c", "content": body}],
        "RuleAgentTraceLoopDetection_content": json.dumps({"tool_calls": [
            {"name": "a", "args": {}, "result": body} for _ in range(3)
        ]}),
    }
    row = MagicMock()
    row.asDict.return_value = source
    result = SparkExecutor(args).evaluate(row)
    assert result["eval_status"] is True
    assert result["raw_data"]["messages"] == source["messages"]
    assert result["raw_data"]["messages"][0]["content"] == body


def test_loop_configuration_is_isolated_through_spark_executor():
    executor = SparkExecutor(InputArgs(
        executor={"result_save": {"all_labels": True}},
    ))
    payload = json.dumps({"tool_calls": [
        {"name": "a", "args": {}, "result": text} for text in ("ab", "ba", "ab")
    ]})
    for config, expected in (
        ({"result_ngram_size": 1, "threshold": 1}, True),
        (None, False),
        ({"result_ngram_size": 1, "result_match_mode": "exact"}, False),
    ):
        evaluators = InputArgs(evaluator=[{"evals": [
            {"name": "RuleAgentTraceLoopDetection", "config": config},
        ]}]).evaluator[0].evals
        result = executor.evaluate_item({"content": "input"}, "rule",
                                        {"content": payload}, evaluators)
        assert result.eval_status is expected
