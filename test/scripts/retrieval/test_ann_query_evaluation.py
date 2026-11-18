"""Offline evaluation fixtures and fake results, never service benchmarks."""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

from dingo.config import InputArgs

h5py = pytest.importorskip("h5py")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

hdf5_input = importlib.import_module("examples.milvus_benchmark.0-data-loading.hdf5_input")


def load_example(relative, name):
    path = PROJECT_ROOT / "examples/milvus_benchmark" / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def evaluator():
    return load_example("3-evaluation/evaluate_queries.py", "ann_offline_evaluator")


@pytest.fixture
def hdf5_path(tmp_path):
    path = tmp_path / "fixture-vectors.hdf5"
    with h5py.File(path, "w") as f:
        f.create_dataset("train", data=np.arange(40, dtype="float32").reshape(20, 2))
        f.create_dataset("test", data=np.arange(6, dtype="float32").reshape(3, 2))
        f.create_dataset("neighbors", data=np.tile(np.arange(20, dtype="int32"), (3, 1)))
    return path


def attempt(ids=(), *, query_id=0, status="ok", elapsed=10.0):
    return {
        "dataset": "fixture-vectors", "query_id": query_id, "backend": "offline-test", "top_k": 10,
        "hits": [{"id": value, "rank": rank, "distance": float(rank)} for rank, value in enumerate(ids, 1)],
        "elapsed_ms": elapsed, "status": status, "error": None if status in ("ok", "empty") else "fixture failure",
    }


def write_input(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


def input_args(path):
    return InputArgs(input_path=str(path), dataset={"source": "local", "format": "hdf5"})


def load_data(path):
    return hdf5_input.open_evaluation_data(input_args(path), base_key="train", ground_truth_key="neighbors")


def test_raw_cutoff_invalid_slots_duplicates_and_official_top10(evaluator, hdf5_path):
    rows = [attempt([0, 0, "1", -1, 20, 2, 10, 11, 12, 13, 3]), attempt(range(10, 20), query_id=1)]
    with load_data(hdf5_path) as data:
        scored = evaluator.score_attempts(rows, data)
        assert [row["recall_at_10"] for row in scored] == [pytest.approx(0.2), 0.0]
        assert scored[0]["quality"] == {
            "returned_count": 11, "valid_count": 8, "duplicate_count": 1, "top_k_adherent": False,
        }
    assert not data.ground_truth.id.valid


@pytest.mark.parametrize("field,value", [
    ("query_id", True), ("query_id", "0"), ("query_id", -1), ("top_k", 5),
    ("status", "unknown"), ("elapsed_ms", -1), ("elapsed_ms", float("nan")),
])
def test_malformed_attempt_reports_line(evaluator, tmp_path, field, value):
    row = attempt([0])
    row[field] = value
    source = write_input(tmp_path / "bad.jsonl", [attempt([0]), row])
    with pytest.raises(ValueError, match="[Ll]ine 2"):
        evaluator.read_attempts(source)


@pytest.mark.parametrize("change", ["missing", "rank", "status_hits", "backend", "dataset"])
def test_incompatible_or_inconsistent_records(evaluator, tmp_path, change):
    row = attempt([0])
    if change == "missing":
        del row["error"]
    elif change == "rank":
        row["hits"][0]["rank"] = 2
    elif change == "status_hits":
        row["status"] = "empty"
    elif change == "backend":
        row["backend"] = "another-backend"
    else:
        row["dataset"] = "another-dataset"
    with pytest.raises(ValueError):
        evaluator.read_attempts(write_input(tmp_path / "bad.jsonl", [attempt([0]), row]))


def test_bad_json_reports_line(evaluator, tmp_path):
    source = tmp_path / "bad.jsonl"
    source.write_text(json.dumps(attempt([0])) + "\n{broken\n")
    with pytest.raises(ValueError, match="[Ll]ine 2"):
        evaluator.read_attempts(source)


def test_query_id_must_exist_in_hdf5(evaluator, hdf5_path):
    with load_data(hdf5_path) as data:
        with pytest.raises(ValueError):
            evaluator.score_attempts([attempt([0], query_id=3)], data)


def test_cli_reports_hand_computed_denominators(evaluator, hdf5_path, tmp_path, monkeypatch):
    rows = [attempt(range(10), elapsed=10), attempt([0, 0, "1", -1], elapsed=30),
            attempt(status="empty", elapsed=20), attempt(status="timeout", elapsed=500),
            attempt(status="error", elapsed=100)]
    source = write_input(tmp_path / "attempts.jsonl", rows)
    output = tmp_path / "reports"
    monkeypatch.setattr("sys.argv", ["evaluate_queries.py", "--input", str(source), "--input-path", str(hdf5_path),
                                     "--output-dir", str(output)])
    evaluator.main()
    scored = [json.loads(line) for line in (output / "per_query.jsonl").read_text().splitlines()]
    report = json.loads((output / "summary.json").read_text())
    assert report["units"]["rate_unit"] == "fraction"
    assert report["populations"]["latency_population"] == "ok_and_empty"
    summary = report["metrics"]
    assert len(scored) == 5
    assert [row["query_id"] for row in scored] == [0] * 5
    assert summary["attempt_count"] == 5
    assert summary["success_count"] == 3
    assert summary["timeout_count"] == 1
    assert summary["ok_count"] == 2
    assert summary["recall_at_10"] == pytest.approx(0.22)
    assert summary["success_rate"] == pytest.approx(0.6)
    assert summary["timeout_rate"] == pytest.approx(0.2)
    assert summary["has_results_rate"] == pytest.approx(2 / 3)
    assert summary["valid_hit_rate"] == pytest.approx(12 / 14)
    assert summary["duplicate_rate"] == pytest.approx(1 / 14)
    assert summary["top_k_adherence_rate"] == pytest.approx(1 / 5)
    assert summary["mean_latency_ms"] == pytest.approx(20)
    assert summary["p50_latency_ms"] == 20
    assert summary["p95_latency_ms"] == 30
    assert summary["p99_latency_ms"] == 30


@pytest.mark.parametrize("existing", ["per_query.jsonl", "summary.json"])
def test_either_report_collision_preserves_every_file(evaluator, tmp_path, monkeypatch, existing):
    output = tmp_path / "reports"
    output.mkdir()
    (output / existing).write_text("original\n")
    source = write_input(tmp_path / "attempts.jsonl", [attempt([0])])
    monkeypatch.setattr("sys.argv", ["evaluate_queries.py", "--input", str(source), "--output-dir", str(output),
                                     "--input-path", str(tmp_path / "unread.hdf5")])
    monkeypatch.setattr(hdf5_input, "open_hdf5",
                        lambda *a, **k: pytest.fail("must reject output collision before loading"))
    with pytest.raises(SystemExit):
        evaluator.main()
    assert {p.name: p.read_text() for p in output.iterdir()} == {existing: "original\n"}


def test_missing_hdf5_does_not_write_reports(evaluator, tmp_path, monkeypatch, capsys):
    source = write_input(tmp_path / "attempts.jsonl", [attempt([0])])
    output = tmp_path / "reports"
    monkeypatch.setattr("sys.argv", ["evaluate_queries.py", "--input", str(source), "--input-path",
                                     str(tmp_path / "absent"), "--output-dir", str(output)])
    with pytest.raises(SystemExit):
        evaluator.main()
    assert not output.exists() or not list(output.iterdir())
    assert "HDF5 input is not a file" in capsys.readouterr().err


def test_current_query_writer_output_can_be_evaluated(evaluator, hdf5_path, tmp_path):
    from dingo.retrieval.backends.milvus import VectorHit

    runner = load_example("2-query-execution/run_queries.py", "ann_evaluation_query_producer")

    class FakeClient:
        name = "offline-test"

        def search(self, query, limit):
            return [VectorHit(row_id, float(row_id)) for row_id in range(limit)]

    path = tmp_path / "fake_attempts.jsonl"
    with hdf5_input.open_vector_data(input_args(hdf5_path), key="test", field="queries") as data:
        with path.open("x") as output:
            runner.write_queries(FakeClient(), data, start_row=1, count=2, top_k=10, output=output)
    with load_data(hdf5_path) as data:
        scored = evaluator.score_attempts(evaluator.read_attempts(path), data)
    assert [row["query_id"] for row in scored] == [1, 2]
    assert [row["recall_at_10"] for row in scored] == [1.0, 1.0]
    assert not data.ground_truth.id.valid


def test_official_top10_must_be_distinct(evaluator, hdf5_path):
    with h5py.File(hdf5_path, "r+") as f:
        f["neighbors"][0, 1] = 0
    with load_data(hdf5_path) as data:
        with pytest.raises(ValueError, match="distinct"):
            evaluator.score_attempts([attempt([0])], data)


@pytest.mark.parametrize("problem,message", [
    ("missing", "neighbors"),
    ("dtype", "integer IDs"),
    ("neighbor", "distinct valid base IDs"),
])
def test_ann_fields_are_validated_after_hdf5_loading(evaluator, hdf5_path, problem, message):
    with h5py.File(hdf5_path, "r+") as hdf5:
        if problem == "missing":
            del hdf5["neighbors"]
        elif problem == "dtype":
            neighbors = hdf5["neighbors"][:].astype(float)
            del hdf5["neighbors"]
            hdf5.create_dataset("neighbors", data=neighbors)
        else:
            hdf5["neighbors"][0, 0] = len(hdf5["train"])
    with pytest.raises(ValueError, match=message):
        evaluator.evaluate_attempts([attempt([0])], input_args=input_args(hdf5_path))


@pytest.mark.parametrize("filename", ["per_query.jsonl", "summary.json"])
@pytest.mark.parametrize("entry", ["write_reports", "main"])
def test_dangling_report_link_blocks_all_output(evaluator, hdf5_path, tmp_path, monkeypatch, filename, entry):
    output = tmp_path / "reports"
    output.mkdir()
    target = tmp_path / "missing-target.json"
    link = output / filename
    link.symlink_to(target)
    original_target = link.readlink()

    if entry == "write_reports":
        with load_data(hdf5_path) as data:
            scored = evaluator.score_attempts([attempt([0])], data)
        with pytest.raises(FileExistsError):
            evaluator.write_reports(scored, output)
    else:
        def forbidden(*args, **kwargs):
            pytest.fail("Report collision must be rejected before input or dataset access")

        monkeypatch.setattr(evaluator, "read_attempts", forbidden)
        monkeypatch.setattr(hdf5_input, "open_hdf5", forbidden)
        monkeypatch.setattr("sys.argv", ["evaluate_queries.py", "--input", str(tmp_path / "unread.jsonl"),
                                         "--input-path", str(hdf5_path), "--output-dir", str(output)])
        with pytest.raises(SystemExit) as exc:
            evaluator.main()
        assert exc.value.code == 2

    assert link.is_symlink()
    assert link.readlink() == original_target
    assert not target.exists()
    assert list(output.iterdir()) == [link]


def test_non_sift_custom_fields_from_import_through_recall_at_twenty(evaluator, tmp_path, monkeypatch):
    importer = load_example("1-data-import/import_ann_dataset.py", "ann_config_import")
    runner = load_example("2-query-execution/run_queries.py", "ann_config_query")
    hdf5_path = tmp_path / "custom.hdf5"
    vectors = np.arange(50, dtype=np.float32).reshape(25, 2)
    with h5py.File(hdf5_path, "w") as hdf5:
        hdf5.create_dataset("embeddings", data=vectors)
        hdf5.create_dataset("queries", data=vectors[:1])
        hdf5.create_dataset("truth_ids", data=np.arange(20)[None, :])

    class MemoryMilvus:
        def __init__(self):
            self.rows = {}

        def insert(self, *, data, **kwargs):
            self.rows.update((row["id"], row["vector"]) for row in data)
            return {"insert_count": len(data), "ids": [row["id"] for row in data]}

        def search(self, *, data, limit, **kwargs):
            query = np.asarray(data[0])
            ranked = sorted((float(np.sum((vector - query) ** 2)), row_id) for row_id, vector in self.rows.items())
            return [[{"id": row_id, "distance": distance} for distance, row_id in ranked[:limit]]]

        def close(self):
            pass

    sdk = MemoryMilvus()
    monkeypatch.setattr(importer, "create_milvus_client", lambda options, retrieval: sdk)
    monkeypatch.setattr(runner, "create_milvus_client", lambda options, retrieval: sdk)
    connection = ["--milvus-uri", "http://example.invalid", "--milvus-db-name", "fixture",
                  "--milvus-collection", "fixture"]
    source = ["--input-path", str(hdf5_path)]
    importer.main(source + connection + ["--vector-key", "embeddings", "--count", "25", "--write-milvus"])
    assert sorted(sdk.rows) == list(range(25))
    attempts_file = tmp_path / "attempts.jsonl"
    runner.main(source + connection + ["--query-key", "queries", "--dataset-id", "custom-benchmark",
                                       "--count", "1", "--top-k", "20", "--output", str(attempts_file)])
    output = tmp_path / "report"
    monkeypatch.setattr(sys, "argv", [
        "evaluate_queries.py", "--input", str(attempts_file), "--output-dir", str(output),
        *source, "--base-key", "embeddings", "--ground-truth-key", "truth_ids",
        "--dataset-id", "custom-benchmark", "--metrics", "recall",
    ])
    evaluator.main()
    report = json.loads((output / "summary.json").read_text())
    assert report["dataset"] == "custom-benchmark" and report["top_k"] == 20
    assert report["metrics"]["recall_at_20"] == 1.0
    assert set(report["metrics"]) == {"attempt_count", "success_count", "timeout_count", "ok_count", "recall_at_20"}
    with pytest.raises(ValueError, match="top_k must match 10"):
        evaluator.read_attempts(attempts_file, top_k=10)


def test_latency_only_uses_jsonl_without_hdf5(evaluator, tmp_path, monkeypatch):
    source = write_input(tmp_path / "attempts.jsonl", [
        attempt([0], elapsed=7), attempt(status="timeout", elapsed=200),
    ])
    output = tmp_path / "reports"
    monkeypatch.setattr(hdf5_input, "open_hdf5", lambda *args: pytest.fail("must not open HDF5"))
    monkeypatch.setattr(sys, "argv", [
        "evaluate_queries.py", "--input", str(source), "--metrics", "latency", "--output-dir", str(output),
    ])
    evaluator.main()
    report = json.loads((output / "summary.json").read_text())
    assert report["metrics"]["mean_latency_ms"] == 7
    assert report["metrics"]["p99_latency_ms"] == 7
    assert "recall_at_10" not in report["metrics"]
