"""Verify evaluator isolation, source preservation and usable rule inputs."""

import copy
import importlib
import json
import pickle
from test.scripts.ms_swift_test_utils import refresh_ms_swift_statistics, standard_ms_swift_record

import pytest

from dingo.config import InputArgs
from dingo.data.converter import converters
from dingo.data.dataset.local import LocalDataset
from dingo.data.datasource.local import LocalDataSource
from dingo.io import Data
from dingo.model.llm.agent_eval.llm_agent_task_completion import LLMAgentTaskCompletion
from dingo.model.llm.agent_eval.llm_agent_tool_correctness import LLMAgentToolCorrectness
from dingo.model.rule.rule_agent import RuleAgentTraceDestructiveAction, RuleAgentTraceLoopDetection

EVALUATORS = (
    "LLMAgentTaskCompletion",
    "RuleAgentTraceLoopDetection",
    "LLMAgentToolCorrectness",
    "RuleAgentTraceDestructiveAction",
)
ALL_PREPARER_NAMES = tuple(
    importlib.import_module("dingo.data.converter.ms_swift")._PREPARERS
)


def make_args(names=EVALUATORS, **kwargs):
    return InputArgs(
        dataset={"source": "local", "format": "ms_swift"},
        evaluator=[{"evals": [{"name": name}]} for name in names],
        **kwargs,
    )


@pytest.fixture
def record():
    return standard_ms_swift_record(
        tools=[{
            "type": "function", "name": "search", "description": "Search documents",
            "parameters": {},
        }, {
            "type": "function", "name": "read", "description": "Read documents",
            "parameters": {},
        }],
        messages=[
            {"role": "system", "content": "遵循用户要求"},
            {"role": "user", "content": "查找资料"},
            {
                "role": "assistant", "content": "", "reasoning_content": "先搜索",
                "tool_calls": [
                    {"type": "function", "id": "call-1", "function": {
                        "name": "search", "arguments": {"query": "资料"},
                    }},
                    {"type": "function", "id": "call-2", "function": {
                        "name": "read", "arguments": {"path": "notes.txt"},
                    }},
                ],
            },
            {"role": "tool", "name": "search", "tool_call_id": "call-1", "content": "找到了"},
            {"role": "tool", "name": "read", "tool_call_id": "call-2", "content": "资料正文"},
            {"role": "assistant", "content": "已完成", "reasoning_content": ""},
        ],
        data_id="trace-1",
    )


@pytest.mark.parametrize("as_json", [False, True])
def test_independent_fields_and_source_preservation(record, as_json):
    original = copy.deepcopy(record)
    raw = json.dumps(record, ensure_ascii=False) if as_json else record
    data = converters["ms_swift"].convertor(make_args())(raw)
    converted = data.to_dict()
    assert record == original
    assert {key: converted[key] for key in original} == original
    assert set(converted) - set(original) == {
        "LLMAgentTaskCompletion_prompt", "LLMAgentTaskCompletion_content",
        "RuleAgentTraceLoopDetection_content",
        "LLMAgentToolCorrectness_prompt", "LLMAgentToolCorrectness_content",
        "RuleAgentTraceDestructiveAction_content",
    }
    assert data._derived_fields == set(converted) - set(original)
    assert "_derived_fields" not in data.model_dump()
    for name in ("LLMAgentTaskCompletion", "LLMAgentToolCorrectness"):
        assert converted[f"{name}_prompt"] == ""
        assert "资料" in converted[f"{name}_content"]
        assert json.loads(converted[f"{name}_content"]) == [
            {"role": "system", "content": "遵循用户要求"},
            {"role": "user", "content": "查找资料"},
            {"role": "assistant", "content": ""},
            {"role": "tool", "content": "找到了"},
            {"role": "tool", "content": "资料正文"},
            {"role": "assistant", "content": "已完成"},
        ]
    for name in ("RuleAgentTraceLoopDetection", "RuleAgentTraceDestructiveAction"):
        assert json.loads(converted[f"{name}_content"]) == {"tool_calls": [
            {"tool_name": "search", "args": {"query": "资料"}},
            {"tool_name": "read", "args": {"path": "notes.txt"}},
        ]}


@pytest.mark.parametrize("name", ALL_PREPARER_NAMES)
def test_generates_only_selected_evaluator_fields(record, name):
    module = importlib.import_module("dingo.data.converter.ms_swift")
    data = converters["ms_swift"].convertor(make_args((name,)))(record)
    converted = data.to_dict()
    added = set(converted) - set(record)
    expected = set(module._PREPARER_EMPTY_OUTPUTS[name])
    assert added == expected
    assert data._derived_fields == expected


def test_llm_projection_does_not_perform_full_schema_validation(record):
    record["messages"][2]["tool_calls"] = "not a valid tool call list"
    converted = converters["ms_swift"].convertor(
        make_args(("LLMAgentTaskCompletion",))
    )(record)
    assert converted.messages[2]["tool_calls"] == "not a valid tool call list"
    assert converted.LLMAgentTaskCompletion_content


@pytest.mark.parametrize("names", [(), ("RuleAbnormalChar",)])
def test_no_supported_evaluator_preserves_original_only(record, names):
    data = converters["ms_swift"].convertor(make_args(names))(record)
    assert data.to_dict() == record
    assert data._derived_fields == set()


def test_tracks_actual_fields_per_record_without_a_static_list(monkeypatch):
    module = importlib.import_module("dingo.data.converter.ms_swift")

    def prepare(record):
        return {f"custom_{record['data_id']}": "derived"}

    monkeypatch.setitem(module._PREPARERS, "RuleAgentTraceLoopDetection", prepare)
    convert = converters["ms_swift"].convertor(make_args(("RuleAgentTraceLoopDetection",)))
    first = convert(standard_ms_swift_record(data_id="first"))
    second = convert(standard_ms_swift_record(data_id="second"))
    assert first._derived_fields == {"custom_first"}
    assert second._derived_fields == {"custom_second"}
    assert pickle.loads(pickle.dumps(first))._derived_fields == {"custom_first"}


def test_every_preparer_has_an_explicit_typed_empty_output_contract():
    module = importlib.import_module("dingo.data.converter.ms_swift")

    assert set(module._PREPARER_EMPTY_OUTPUTS) == set(module._PREPARERS)
    assert all(
        isinstance(value, str)
        for fields in module._PREPARER_EMPTY_OUTPUTS.values()
        for value in fields.values()
    )


@pytest.mark.parametrize("name", ALL_PREPARER_NAMES)
def test_preparer_failure_sets_only_its_declared_fields_to_typed_empty_values(
    monkeypatch, record, name,
):
    module = importlib.import_module("dingo.data.converter.ms_swift")

    def fail(_record):
        raise RuntimeError("extraction failed")

    monkeypatch.setitem(module._PREPARERS, name, fail)
    converted = converters["ms_swift"].convertor(make_args((name,)))(record)
    expected = module._PREPARER_EMPTY_OUTPUTS[name]

    assert {field: getattr(converted, field) for field in expected} == expected
    assert converted._derived_fields == set(expected)


def test_one_preparer_failure_does_not_block_other_preparers(monkeypatch, record):
    module = importlib.import_module("dingo.data.converter.ms_swift")

    def fail(_record):
        raise TypeError("bad source type")

    monkeypatch.setitem(module._PREPARERS, "RuleAgentTraceLoopDetection", fail)
    converted = converters["ms_swift"].convertor(make_args((
        "RuleAgentTraceLoopDetection",
        "RuleAgentTraceTokenBudget",
    )))(record)

    assert converted.RuleAgentTraceLoopDetection_content == ""
    assert json.loads(converted.RuleAgentTraceTokenBudget_content) == {}


def test_missing_shared_source_only_empties_dependent_preparers(record):
    record.pop("messages")
    converted = converters["ms_swift"].convertor(make_args(ALL_PREPARER_NAMES))(record)

    for name in ALL_PREPARER_NAMES:
        content = getattr(converted, f"{name}_content")
        if name == "RuleAgentTraceTokenBudget":
            assert json.loads(content) == {}
        else:
            assert content == ""


@pytest.mark.parametrize("messages", [None, {}, [None], [{"role": 1, "content": "x"}]])
def test_invalid_shared_message_structure_empties_dependent_preparers(record, messages):
    record["messages"] = messages
    converted = converters["ms_swift"].convertor(make_args(ALL_PREPARER_NAMES))(record)

    for name in ALL_PREPARER_NAMES:
        content = getattr(converted, f"{name}_content")
        if name == "RuleAgentTraceTokenBudget":
            assert json.loads(content) == {}
        else:
            assert content == ""


def test_invalid_message_content_empties_llm_fields_but_not_rule_fields(record):
    record["messages"][0]["content"] = None
    converted = converters["ms_swift"].convertor(make_args(ALL_PREPARER_NAMES))(record)

    for name in ALL_PREPARER_NAMES:
        content = getattr(converted, f"{name}_content")
        if name.startswith("LLM"):
            assert content == ""
        else:
            assert content != ""


def test_rejects_derived_field_collision_without_overwriting_source(record):
    field = "RuleAgentTraceLoopDetection_content"
    record[field] = "user value"
    original = copy.deepcopy(record)
    with pytest.raises(ValueError, match=field):
        converters["ms_swift"].convertor(make_args(("RuleAgentTraceLoopDetection",)))(record)
    assert record == original


def test_converted_sequence_can_detect_loops(record):
    calls = record["messages"][2]["tool_calls"]
    record["messages"] = record["messages"][:3]
    record["messages"][2]["tool_calls"] = [
        dict(copy.deepcopy(call), id=f"loop-{repeat}-{index}")
        for repeat in range(3)
        for index, call in enumerate(calls)
    ]
    refresh_ms_swift_statistics(record)
    converted = converters["ms_swift"].convertor(make_args(("RuleAgentTraceLoopDetection",)))(record)
    result = RuleAgentTraceLoopDetection.eval(Data(content=converted.RuleAgentTraceLoopDetection_content))
    assert result.applicable
    assert result.status
    assert "Loop detected" in result.reason[0]
    # Six calls with different arguments must not turn into a name-only loop.
    record["messages"][2]["tool_calls"] = [
        {"type": "function", "id": f"search-{index}", "function": {
            "name": "search", "arguments": {"query": str(index)},
        }}
        for index in range(6)
    ]
    refresh_ms_swift_statistics(record)
    converted = converters["ms_swift"].convertor(make_args(("RuleAgentTraceLoopDetection",)))(record)
    result = RuleAgentTraceLoopDetection.eval(Data(content=converted.RuleAgentTraceLoopDetection_content))
    assert result.applicable
    assert not result.status


def test_destructive_rule_input_and_unchanged_cmd(record):
    record["messages"][2]["tool_calls"] = [
        {"type": "function", "id": "shell-1", "function": {
            "name": "shell", "arguments": {"command": "rm -rf /important"},
        }},
        {"type": "function", "id": "shell-2", "function": {
            "name": "exec_command", "arguments": {"cmd": "rm -rf /other"},
        }},
    ]
    record["messages"] = record["messages"][:3]
    refresh_ms_swift_statistics(record)
    converted = converters["ms_swift"].convertor(make_args(("RuleAgentTraceDestructiveAction",)))(record)
    content = converted.RuleAgentTraceDestructiveAction_content
    assert json.loads(content)["tool_calls"][1]["args"] == {"cmd": "rm -rf /other"}
    result = RuleAgentTraceDestructiveAction.eval(Data(content=content))
    assert result.status
    assert "call 1" in result.reason[0]


def test_field_mapping_builds_llm_messages_with_empty_prompts(record):
    args = make_args()
    for pipeline in args.evaluator:
        name = pipeline.evals[0].name
        pipeline.fields = {"content": f"{name}_content"}
        if name.startswith("LLM"):
            pipeline.fields["prompt"] = f"{name}_prompt"
    converted = converters["ms_swift"].convertor(args)(record).to_dict()
    models = {"LLMAgentTaskCompletion": LLMAgentTaskCompletion, "LLMAgentToolCorrectness": LLMAgentToolCorrectness}
    for pipeline in args.evaluator:
        name = pipeline.evals[0].name
        mapped = Data(**{key: converted[source] for key, source in pipeline.fields.items()})
        if name in models:
            assert mapped.prompt == ""
            messages = models[name].build_messages(mapped)
            assert mapped.content in messages[0]["content"]
        else:
            assert isinstance(json.loads(mapped.content)["tool_calls"], list)


def test_local_dataset_reads_jsonl_records_and_filters_directory(tmp_path, record):
    records = [record, dict(record, data_id="trace-2")]
    (tmp_path / "traces.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in records), encoding="utf-8",
    )
    (tmp_path / "unrelated.json").write_text("[]", encoding="utf-8")
    args = make_args(("RuleAgentTraceLoopDetection",), input_path=str(tmp_path))
    data = list(LocalDataset(LocalDataSource(args)).get_data())
    assert [item.data_id for item in data] == ["trace-1", "trace-2"]
    assert all(json.loads(item.RuleAgentTraceLoopDetection_content)["tool_calls"] for item in data)


def test_converter_preserves_record_without_running_full_schema_validation():
    converted = converters["ms_swift"].convertor(make_args(()))({"messages": []})
    assert converted.messages == []


@pytest.mark.parametrize("mutate", [
    lambda item: item.update(messages=[None]),
    lambda item: item.update(messages=[{
        "role": "assistant", "content": "", "reasoning_content": "", "tool_calls": {},
    }]),
    lambda item: item["messages"][0].pop("content"),
])
def test_converter_leaves_invalid_structure_for_schema_rule(mutate):
    record = standard_ms_swift_record(messages=[{"role": "user", "content": "x"}])
    mutate(record)
    converted = converters["ms_swift"].convertor(make_args(()))(record)
    assert converted.messages == record["messages"]
