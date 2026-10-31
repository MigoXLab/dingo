import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

_spec = importlib.util.spec_from_file_location(
    "repository_executor_example",
    Path(__file__).resolve().parents[4]
    / "examples/repository_code_quality/evaluate_repository_executor.py",
)
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)


def test_runner_uses_local_executor_and_preserves_repository_fields(
    tmp_path, monkeypatch, capsys
):
    source = tmp_path / "input.jsonl"
    source.write_text(
        json.dumps(
            {
                "track_id": "one",
                "source": "unit-test",
                "language": "python",
                "file_name": "one.py",
                "content": "print(1)",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    configs = []

    class FakeExecutor:
        def __init__(self, config):
            configs.append(config)

        def execute(self):
            return SimpleNamespace(
                total=1,
                num_good=1,
                num_bad=0,
                score=100.0,
                type_count={"default": {"QUALITY_GOOD": 1}},
                output_path=str(tmp_path / "results"),
            )

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setattr(runner, "LocalExecutor", FakeExecutor)
    monkeypatch.setattr(
        "sys.argv",
        [
            "runner",
            "--input",
            str(source),
            "--output",
            str(tmp_path / "output"),
            "--workers",
            "3",
        ],
    )

    runner.main()

    config = configs[0]
    assert config.executor.max_workers == 3
    assert config.dataset.format == "jsonl"
    assert config.evaluator[0].fields == {}
    evaluator = config.evaluator[0].evals[0]
    assert evaluator.name == "LLMRepositoryCodeQualityPipeline"
    assert evaluator.config.key == "test-key"
    assert json.loads(capsys.readouterr().out)["total"] == 1
