"""Offline evaluation fixtures and fake results, never service benchmarks."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from dingo.config import InputArgs
from dingo.data import dataset_map, datasource_map

h5py = pytest.importorskip("h5py")


def load_example(relative, name):
    path = Path(__file__).resolve().parents[3] / "examples/Milvus_benchmark" / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def evaluator():
    return load_example("3-evaluation/evaluate_queries.py", "ann_offline_evaluator")


@pytest.fixture
def cache(tmp_path):
    cache = tmp_path / "cache"
    cache.mkdir()
    with h5py.File(cache / "sift-128-euclidean.hdf5", "w") as f:
        f.attrs["dimension"] = 2
        f.attrs["distance"] = "euclidean"
        f.create_dataset("train", data=np.arange(40, dtype="float32").reshape(20, 2))
        f.create_dataset("test", data=np.arange(6, dtype="float32").reshape(3, 2))
        f.create_dataset("neighbors", data=np.tile(np.arange(20, dtype="int32"), (3, 1)))
        f.create_dataset("distances", data=np.tile(np.arange(20, dtype="float32"), (3, 1)))
    return cache


def attempt(ids=(), *, query_id=0, status="ok", elapsed=10.0):
    return {
        "dataset": "sift-128-euclidean", "query_id": query_id, "backend": "offline-test", "top_k": 10,
        "hits": [{"id": value, "rank": rank, "distance": float(rank)} for rank, value in enumerate(ids, 1)],
        "elapsed_ms": elapsed, "status": status, "error": None if status in ("ok", "empty") else "fixture failure",
    }


def write_input(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    return path


def load_data(cache):
    args = InputArgs(input_path="sift-128-euclidean", dataset={
        "source": "ann_benchmarks", "format": "ann_benchmarks",
        "ann_benchmarks_config": {"cache_dir": str(cache)},
    })
    return dataset_map["ann_benchmarks"](source=datasource_map["ann_benchmarks"](args))


def test_raw_cutoff_invalid_slots_duplicates_and_official_top10(evaluator, cache):
    rows = [attempt([0, 0, "1", -1, 20, 2, 10, 11, 12, 13, 3]), attempt(range(10, 20), query_id=1)]
    with load_data(cache) as dataset:
        data = next(dataset.get_data())
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


@pytest.mark.parametrize("change", ["missing", "rank", "status_hits", "backend"])
def test_incompatible_or_inconsistent_records(evaluator, tmp_path, change):
    row = attempt([0])
    if change == "missing":
        del row["error"]
    elif change == "rank":
        row["hits"][0]["rank"] = 2
    elif change == "status_hits":
        row["status"] = "empty"
    else:
        row["backend"] = "another-backend"
    with pytest.raises(ValueError):
        evaluator.read_attempts(write_input(tmp_path / "bad.jsonl", [attempt([0]), row]))


def test_bad_json_reports_line(evaluator, tmp_path):
    source = tmp_path / "bad.jsonl"
    source.write_text(json.dumps(attempt([0])) + "\n{broken\n")
    with pytest.raises(ValueError, match="[Ll]ine 2"):
        evaluator.read_attempts(source)


def test_query_id_must_exist_in_hdf5(evaluator, cache):
    with load_data(cache) as dataset:
        with pytest.raises(ValueError):
            evaluator.score_attempts([attempt([0], query_id=3)], next(dataset.get_data()))


def test_cli_reports_hand_computed_denominators(evaluator, cache, tmp_path, monkeypatch):
    rows = [attempt(range(10), elapsed=10), attempt([0, 0, "1", -1], elapsed=30),
            attempt(status="empty", elapsed=20), attempt(status="timeout", elapsed=500),
            attempt(status="error", elapsed=100)]
    source = write_input(tmp_path / "attempts.jsonl", rows)
    output = tmp_path / "reports"
    monkeypatch.setattr("sys.argv", ["evaluate_queries.py", "--input", str(source), "--cache-dir", str(cache),
                                     "--output-dir", str(output)])
    monkeypatch.setattr("dingo.data.datasource.ann_benchmarks.urlopen", lambda *a, **k: pytest.fail("network"))
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
    monkeypatch.setattr("sys.argv", ["evaluate_queries.py", "--input", str(source), "--output-dir", str(output)])
    monkeypatch.setattr("dingo.data.datasource.ann_benchmarks.ANNBenchmarksDataSource.load",
                        lambda *a, **k: pytest.fail("must reject output collision before loading"))
    with pytest.raises(SystemExit):
        evaluator.main()
    assert {p.name: p.read_text() for p in output.iterdir()} == {existing: "original\n"}


def test_missing_cache_never_downloads(evaluator, tmp_path, monkeypatch):
    source = write_input(tmp_path / "attempts.jsonl", [attempt([0])])
    output = tmp_path / "reports"
    monkeypatch.setattr("sys.argv", ["evaluate_queries.py", "--input", str(source), "--cache-dir",
                                     str(tmp_path / "absent"), "--output-dir", str(output)])
    monkeypatch.setattr("dingo.data.datasource.ann_benchmarks.ANNBenchmarksDataSource.load",
                        lambda *a, **k: pytest.fail("missing cache must not load or download"))
    with pytest.raises(SystemExit):
        evaluator.main()
    assert not output.exists() or not list(output.iterdir())


def test_current_query_writer_output_can_be_evaluated(evaluator, cache, tmp_path):
    from dingo.retrieval.backends.milvus import VectorHit

    runner = load_example("2-query-execution/run_queries.py", "ann_evaluation_query_producer")

    class FakeClient:
        name = "offline-test"

        def search(self, query, limit):
            return [VectorHit(row_id, float(row_id)) for row_id in range(limit)]

    path = tmp_path / "fake_attempts.jsonl"
    with load_data(cache) as dataset:
        data = next(dataset.get_data())
        with path.open("x") as output:
            runner.write_queries(FakeClient(), data, start_row=1, count=2, top_k=10, output=output)
        scored = evaluator.score_attempts(evaluator.read_attempts(path), data)
    assert [row["query_id"] for row in scored] == [1, 2]
    assert [row["recall_at_10"] for row in scored] == [1.0, 1.0]
    assert not data.ground_truth.id.valid


def test_official_top10_must_be_distinct(evaluator, cache):
    with h5py.File(cache / "sift-128-euclidean.hdf5", "r+") as f:
        f["neighbors"][0, 1] = 0
    with load_data(cache) as dataset:
        with pytest.raises(ValueError, match="distinct"):
            evaluator.score_attempts([attempt([0])], next(dataset.get_data()))


@pytest.mark.parametrize("filename", ["per_query.jsonl", "summary.json"])
@pytest.mark.parametrize("entry", ["write_reports", "main"])
def test_dangling_report_link_blocks_all_output(evaluator, cache, tmp_path, monkeypatch, filename, entry):
    output = tmp_path / "reports"
    output.mkdir()
    target = tmp_path / "missing-target.json"
    link = output / filename
    link.symlink_to(target)
    original_target = link.readlink()

    if entry == "write_reports":
        with load_data(cache) as dataset:
            scored = evaluator.score_attempts([attempt([0])], next(dataset.get_data()))
        with pytest.raises(FileExistsError):
            evaluator.write_reports(scored, output)
    else:
        def forbidden(*args, **kwargs):
            pytest.fail("Report collision must be rejected before input or dataset access")

        monkeypatch.setattr(evaluator, "read_attempts", forbidden)
        monkeypatch.setattr("dingo.data.datasource.ann_benchmarks.ANNBenchmarksDataSource.__init__", forbidden)
        monkeypatch.setattr("dingo.data.datasource.ann_benchmarks.ANNBenchmarksDataSource.load", forbidden)
        monkeypatch.setattr("sys.argv", ["evaluate_queries.py", "--input", str(tmp_path / "unread.jsonl"),
                                         "--output-dir", str(output)])
        with pytest.raises(SystemExit) as exc:
            evaluator.main()
        assert exc.value.code == 2

    assert link.is_symlink()
    assert link.readlink() == original_target
    assert not target.exists()
    assert list(output.iterdir()) == [link]
