"""Remaining ms-swift metrics, including evidence gaps and output cleanup."""

import copy
import importlib
import json
from test.scripts.ms_swift_test_utils import refresh_ms_swift_statistics, standard_ms_swift_record

import pytest

from dingo.config import InputArgs
from dingo.data.converter import converters
from dingo.exec import LocalExecutor
from dingo.io import Data, ResultInfo
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.model.rule import rule_agent

RULE_NAMES = (
    "RuleAgentTraceDestructiveAction", "RuleAgentTraceGatewayBypass", "RuleAgentTraceIntegrity",
    "RuleAgentTraceLatencyAnomaly", "RuleAgentTraceLoopDetection", "RuleAgentTraceSandboxExplicitlyDisabled",
    "RuleAgentTraceSecretExposure", "RuleAgentTraceSensitiveAccess", "RuleAgentTraceTokenBudget",
)
LLM_MODULES = {
    "LLMAgentArgumentCorrectness": "llm_agent_argument_correctness",
    "LLMAgentToolCorrectness": "llm_agent_tool_correctness",
    "LLMAgentErrorRecovery": "llm_agent_error_recovery",
    "LLMAgentPlanAdherence": "llm_agent_plan_adherence",
    "LLMAgentPlanQuality": "llm_agent_plan_quality",
    "LLMAgentStepEfficiency": "llm_agent_step_efficiency",
    "LLMAgentTaskCompletion": "llm_agent_task_completion",
}
LLM_MODELS = {
    name: getattr(importlib.import_module(f"dingo.model.llm.agent_eval.{module}"), name)
    for name, module in LLM_MODULES.items()
}
ALL_NAMES = RULE_NAMES + tuple(LLM_MODELS)


def make_args(names=ALL_NAMES, **kwargs):
    pipelines = []
    for name in names:
        fields = {"content": f"{name}_content"}
        if name.startswith("LLM"):
            fields["prompt"] = f"{name}_prompt"
        if name == "LLMAgentPlanAdherence":
            fields["context"] = f"{name}_context"
        pipelines.append({"fields": fields, "evals": [{"name": name}]})
    return InputArgs(
        dataset={"source": "local", "format": "ms_swift"}, evaluator=pipelines, **kwargs,
    )


def convert(record, names=ALL_NAMES):
    return converters["ms_swift"].convertor(make_args(names))(record)


def evaluate_rule(record, name):
    data = convert(record, (name,))
    return getattr(rule_agent, name).eval(Data(content=getattr(data, f"{name}_content")))


@pytest.fixture
def record():
    return standard_ms_swift_record(
        data_id="trace-1", total_tokens=600001,
        tools=[{
            "type": "function", "name": "search", "description": "Search",
            "parameters": {},
        }, {
            "type": "function", "name": "read", "description": "Read",
            "parameters": {},
        }],
        messages=[
            {"role": "user", "content": "查找文档并总结结果"},
            {"role": "assistant", "content": "", "reasoning_content": "这是推理，不一定是计划", "tool_calls": [
                {"type": "function", "id": "a", "function": {
                    "name": "search", "arguments": {"query": "documents"},
                }},
                {"type": "function", "id": "b", "function": {
                    "name": "read", "arguments": {"path": "notes.txt"},
                }},
            ]},
            {"role": "tool", "name": "read", "tool_call_id": "b", "content": "document"},
            {"role": "tool", "name": "search", "tool_call_id": "a", "content": "found"},
            {"role": "assistant", "content": "已完成", "reasoning_content": ""},
        ],
    )


@pytest.mark.parametrize("name", ALL_NAMES)
def test_each_metric_generates_only_its_actual_fields(record, name):
    original = copy.deepcopy(record)
    args = make_args((name,))
    data = converters["ms_swift"].convertor(args)(record)
    expected = set(args.evaluator[0].fields.values())
    assert data._derived_fields == expected
    assert set(data.to_dict()) - set(record) == expected
    assert record == original


@pytest.mark.parametrize("raw", [False, True])
def test_all_16_metrics_keep_independent_inputs_and_cleanup(record, raw):
    args = make_args(executor={"result_save": {"raw": raw}})
    data = converters["ms_swift"].convertor(args)(record)
    assert len(data._derived_fields) == 24
    result = ResultInfo(dingo_id="1", raw_data=data.to_dict(), derived_fields=data._derived_fields)
    output = json.loads(LocalExecutor(args)._build_output_json(args, result))
    source = output if raw else output["raw_data"]
    assert {key: source[key] for key in record} == record
    assert not data._derived_fields.intersection(source)
    assert result.raw_data.keys() >= data._derived_fields


@pytest.mark.parametrize("name", tuple(LLM_MODELS))
def test_all_llm_inputs_follow_the_selected_simplified_contract(record, monkeypatch, name):
    args = make_args((name,))
    data = convert(record, (name,)).to_dict()
    mapped = Data(**{key: data[source] for key, source in args.evaluator[0].fields.items()})
    assert mapped.prompt == ""
    assert json.loads(mapped.content) == [
        {"role": message["role"], "content": message["content"]} for message in record["messages"]
    ]
    if name == "LLMAgentPlanAdherence":
        assert mapped.context == ""
    model = LLM_MODELS[name]
    requests = []

    def send(cls, messages):
        requests.append(messages)
        return '{"score": 8, "reason": "mock evaluation"}'

    monkeypatch.setattr(BaseOpenAI, "create_client", classmethod(lambda cls: None))
    monkeypatch.setattr(BaseOpenAI, "send_messages", classmethod(send))
    result = model.eval(mapped)
    assert result.applicable
    assert result.score == 0.8
    assert mapped.content in requests[0][0]["content"]


def test_secret_results_are_paired_by_id_even_when_return_order_differs(record):
    record["messages"][2]["content"] = "-----BEGIN PRIVATE KEY-----"
    name = "RuleAgentTraceSecretExposure"
    payload = json.loads(getattr(convert(record, (name,)), f"{name}_content"))
    assert [call["result"] for call in payload["tool_calls"]] == ["found", "-----BEGIN PRIVATE KEY-----"]
    result = evaluate_rule(record, name)
    assert result.status
    assert "call 2" in result.reason[0]


def test_missing_result_is_not_guessed_from_an_unrelated_tool_message(record):
    record["messages"].pop(2)
    payload = json.loads(convert(record).RuleAgentTraceSecretExposure_content)
    assert "result" not in payload["tool_calls"][1]
    integrity = json.loads(convert(record).RuleAgentTraceIntegrity_content)
    assert integrity["open_observation_count"] == 1


@pytest.mark.parametrize("name", (
    "RuleAgentTraceDestructiveAction", "RuleAgentTraceGatewayBypass", "RuleAgentTraceLoopDetection",
    "RuleAgentTraceSandboxExplicitlyDisabled", "RuleAgentTraceSecretExposure", "RuleAgentTraceSensitiveAccess",
))
def test_tool_call_preparers_parse_json_arguments_without_changing_source(record, name):
    record["messages"][1]["tool_calls"][1]["function"]["arguments"] = '{"path": "notes.txt"}'
    original = copy.deepcopy(record)
    payload = json.loads(getattr(convert(record, (name,)), f"{name}_content"))
    assert payload["tool_calls"][1]["args"] == {"path": "notes.txt"}
    assert record == original


@pytest.mark.parametrize("name", RULE_NAMES[:-1])
def test_rule_preparers_accept_non_object_arguments_allowed_by_standard(record, name):
    record["messages"][1]["tool_calls"][1]["function"]["arguments"] = "invalid JSON"
    original = copy.deepcopy(record)
    convert(record, (name,))
    assert record == original


@pytest.mark.parametrize("name", (
    "RuleAgentTraceGatewayBypass", "RuleAgentTraceIntegrity",
    "RuleAgentTraceLatencyAnomaly", "RuleAgentTraceSecretExposure",
))
@pytest.mark.parametrize("duplicate_call", [False, True])
def test_ambiguous_call_ids_produce_empty_metric_input(record, name, duplicate_call):
    if duplicate_call:
        record["messages"][1]["tool_calls"][1]["id"] = "a"
    else:
        record["messages"][2]["tool_call_id"] = "a"
    converted = convert(record, (name,))
    assert getattr(converted, f"{name}_content") == ""
    schema_result = rule_agent.RuleMsSwiftSchema.eval(Data(**record))
    assert schema_result.status is True
    assert "duplicate" in schema_result.reason[0]


def test_gateway_maps_explicit_status_without_changing_rule_behavior():
    record = standard_ms_swift_record(messages=[
        {"role": "assistant", "content": "", "reasoning_content": "", "tool_calls": [
            {"type": "function", "id": "a", "function": {
                "name": "WebFetch", "arguments": {"url": "https://example.org"},
            }},
        ]},
        {
            "role": "tool", "name": "WebFetch", "tool_call_id": "a",
            "status": "error", "content": "GATEWAY BLOCKED",
        },
        {"role": "assistant", "content": "", "reasoning_content": "", "tool_calls": [
            {"type": "function", "id": "b", "function": {
                "name": "shell", "arguments": {"command": "curl https://example.org"},
            }},
        ]},
    ])
    name = "RuleAgentTraceGatewayBypass"
    assert evaluate_rule(record, name).status
    record["messages"][1].pop("status")
    assert not evaluate_rule(record, name).status
    record["messages"][2]["tool_calls"][0]["function"] = {
        "name": "exec_command", "arguments": {"cmd": "curl https://example.org"},
    }
    refresh_ms_swift_statistics(record)
    payload = json.loads(getattr(convert(record, (name,)), f"{name}_content"))
    assert "status" not in payload["tool_calls"][0]
    assert payload["tool_calls"][1]["tool_name"] == "exec_command"
    assert payload["tool_calls"][1]["args"] == {"cmd": "curl https://example.org"}


def test_integrity_uses_source_counter_while_schema_rule_reports_mismatch(record):
    name = "RuleAgentTraceIntegrity"
    payload = json.loads(getattr(convert(record, (name,)), f"{name}_content"))
    assert payload == {"tool_calls_expected": 2, "tool_spans_recorded": 2, "open_observation_count": 0}
    record["total_tool_calls"] = 3
    payload = json.loads(getattr(convert(record, (name,)), f"{name}_content"))
    assert payload["tool_calls_expected"] == 3
    schema_result = rule_agent.RuleMsSwiftSchema.eval(Data(**record))
    assert schema_result.status is True
    assert "total_tool_calls" in schema_result.reason[0]
    assert "actual tool-call count 2" in schema_result.reason[0]


def test_latency_is_na_without_explicit_timings_and_uses_recorded_extensions(record):
    name = "RuleAgentTraceLatencyAnomaly"
    assert not evaluate_rule(record, name).applicable
    calls = record["messages"][1]["tool_calls"]
    record["messages"][1]["tool_calls"] = [
        {
            "type": "function", "id": f"latency-{index}",
            "function": calls[0]["function"],
            "duration": 1 if index < 10 else 100, "group": "tool",
        }
        for index in range(11)
    ]
    record["messages"] = record["messages"][:2] + record["messages"][4:]
    refresh_ms_swift_statistics(record)
    payload = json.loads(getattr(convert(record, (name,)), f"{name}_content"))
    assert payload["steps"][-1] == {"name": "search", "duration": 100, "group": "tool"}
    assert evaluate_rule(record, name).status


def test_latency_pairs_timings_by_id_and_prefers_tool_message_extensions(record):
    name = "RuleAgentTraceLatencyAnomaly"
    record["messages"][1]["tool_calls"][0].update(duration=10, group="call")
    record["messages"][1]["tool_calls"][1].update(duration_seconds=20, group="fallback")
    record["messages"][3].update(duration=1, group="observation", type="tool")
    payload = json.loads(getattr(convert(record, (name,)), f"{name}_content"))
    assert payload["steps"] == [
        {"name": "search", "duration": 1, "group": "observation", "type": "tool"},
        {"name": "read", "duration_seconds": 20, "group": "fallback"},
    ]


@pytest.mark.parametrize("name,args", [
    ("RuleAgentTraceSandboxExplicitlyDisabled", {"dangerouslyDisableSandbox": True}),
    ("RuleAgentTraceSensitiveAccess", {"path": "~/.ssh/id_rsa"}),
    ("RuleAgentTraceDestructiveAction", {"command": "rm -rf /srv/production"}),
])
def test_parameter_rules_use_original_argument_names(record, name, args):
    record["messages"][1]["tool_calls"][0]["function"]["arguments"] = args
    assert evaluate_rule(record, name).status


def test_cmd_is_preserved_without_extending_the_existing_rule(record):
    name = "RuleAgentTraceDestructiveAction"
    args = {"cmd": "rm -rf /srv/production"}
    record["messages"][1]["tool_calls"][0]["function"]["arguments"] = args
    payload = json.loads(getattr(convert(record, (name,)), f"{name}_content"))
    assert payload["tool_calls"][0]["args"] == args
    assert not evaluate_rule(record, name).status


def test_token_budget_never_substitutes_reasoning_tokens(record):
    name = "RuleAgentTraceTokenBudget"
    assert evaluate_rule(record, name).status
    record.pop("total_tokens")
    record["reasoning_total_tokens"] = 900000
    assert json.loads(getattr(convert(record, (name,)), f"{name}_content")) == {}
    assert not evaluate_rule(record, name).applicable


@pytest.mark.parametrize("raw", [False, True])
def test_local_executor_runs_all_16_metrics_and_cleans_outputs(tmp_path, monkeypatch, record, raw):
    monkeypatch.setenv("LOCAL_DEPLOYMENT_MODE", "true")
    monkeypatch.setattr(BaseOpenAI, "create_client", classmethod(lambda cls: None))
    monkeypatch.setattr(
        BaseOpenAI, "send_messages", classmethod(lambda cls, messages: '{"score": 8, "reason": "mock"}'),
    )
    path = tmp_path / "trace.jsonl"
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    args = make_args(
        input_path=str(path), output_path=str(tmp_path / "outputs"),
        executor={"max_workers": 2, "result_save": {"raw": raw, "merge": True, "all_labels": True}},
    )
    executor = LocalExecutor(args)
    summary = executor.execute()
    assert summary.total == 1
    output = executor.get_bad_info_list()[0]
    source = output if raw else output["raw_data"]
    assert {key: source[key] for key in record} == record
    assert set(source) == set(record) | ({"dingo_id", "dingo_result"} if raw else set())
    details = output["dingo_result"]["eval_details"] if raw else output["eval_details"]
    assert {detail["metric"] for group in details.values() for detail in group} == set(ALL_NAMES)
    assert set(ALL_NAMES) <= set(Model.rule_name_map) | set(Model.llm_name_map)
