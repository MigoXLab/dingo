import json
from pathlib import Path

from dingo.data.converter import converters
from dingo.data.converter.repository import DERIVED_DUPLICATE_FIELD

REPOSITORY_CONVERTER = converters["repository_jsonl"]

DUPLICATE_CODE = (
    "def add_left_pad(a, b):\n    total = a + b\n    return total\n\n\n"
    "def sub_left_pad(a, b):\n    delta = a - b\n    return delta\n\n\nVALUE = 64\n"
)


def _record(track_id, content):
    return {
        "track_id": track_id,
        "source": "unit-test",
        "language": "python",
        "file_name": f"{track_id}.py",
        "content": content,
    }


def _convert_all(records):
    convert = REPOSITORY_CONVERTER.convertor(None)
    return [convert(json.dumps(record, ensure_ascii=False)) for record in records]


def test_converter_annotates_only_later_members_of_duplicate_group():
    first, second = _convert_all([_record("one", DUPLICATE_CODE), _record("two", DUPLICATE_CODE)])

    assert not hasattr(first, DERIVED_DUPLICATE_FIELD)
    assert DERIVED_DUPLICATE_FIELD not in first.to_dict()

    findings = getattr(second, DERIVED_DUPLICATE_FIELD)
    assert [item["label"] for item in findings] == ["Similarity.Normalized_Token_Duplicate"]
    assert DERIVED_DUPLICATE_FIELD in second.to_dict()


def test_converter_keeps_unique_records_unannotated():
    (only,) = _convert_all([_record("one", DUPLICATE_CODE)])

    assert not hasattr(only, DERIVED_DUPLICATE_FIELD)


def test_local_executor_surfaces_cross_record_duplicates_and_strips_derived_field(tmp_path, monkeypatch):
    from dingo.config import InputArgs
    from dingo.exec.local import LocalExecutor
    from dingo.io.output.eval_detail import EvalDetail
    from dingo.model.llm.repository_code_quality import LLMRepositoryCodeQualityPipeline

    def fake_stage(cls, evaluator, input_data, config):
        return EvalDetail(metric=evaluator.__name__, label=["QUALITY_GOOD"], reason=["reviewed"])

    monkeypatch.setattr(LLMRepositoryCodeQualityPipeline, "_run_stage", classmethod(fake_stage))
    monkeypatch.setenv("LOCAL_DEPLOYMENT_MODE", "true")

    source = tmp_path / "input.jsonl"
    source.write_text(
        "\n".join(json.dumps(_record(track_id, DUPLICATE_CODE), ensure_ascii=False) for track_id in ("one", "two")) + "\n",
        encoding="utf-8",
    )
    config = InputArgs(
        task_name="repository_converter_executor",
        input_path=str(source),
        output_path=str(tmp_path / "output"),
        dataset={"source": "local", "format": "repository_jsonl"},
        executor={"max_workers": 2, "batch_size": 2, "result_save": {"bad": True, "good": True, "merge": True}},
        evaluator=[
            {
                "fields": {},
                "evals": [
                    {
                        "name": "LLMRepositoryCodeQualityPipeline",
                        "config": {
                            "key": "test-key",
                            "api_url": "https://example.invalid/v1",
                            "model": "test-model",
                        },
                    }
                ],
            }
        ],
    )

    summary = LocalExecutor(config).execute()

    assert summary.num_good == 1
    assert summary.num_bad == 1
    labels = {label for counts in summary.type_count.values() for label in counts}
    assert "Similarity.Normalized_Token_Duplicate" in labels

    results_path = Path(summary.output_path) / "all_results.jsonl"
    rows = {row["raw_data"]["track_id"]: row for line in results_path.read_text(encoding="utf-8").splitlines() if line.strip() for row in [json.loads(line)]}
    assert DERIVED_DUPLICATE_FIELD not in rows["one"]["raw_data"]
    assert rows["two"]["raw_data"][DERIVED_DUPLICATE_FIELD][0]["label"] == "Similarity.Normalized_Token_Duplicate"
