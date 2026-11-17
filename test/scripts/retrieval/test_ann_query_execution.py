"""Offline ANN query execution checks; fake hits never represent a service run."""

import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from dingo.retrieval.backends.milvus import MilvusSearchClient, VectorHit
from dingo.retrieval.search_client import SearchClient, list_backends


@pytest.fixture(scope="module")
def runner():
    path = Path(__file__).resolve().parents[3] / "examples/Milvus_benchmark/2-query-execution/run_queries.py"
    spec = importlib.util.spec_from_file_location("ann_query_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def data():
    return SimpleNamespace(queries=np.arange(24, dtype="float32").reshape(8, 3),
                           metadata={"name": "fixture-ann", "dimension": 3})


class FakeClient:
    name = "offline-test"

    def __init__(self, replies):
        self.replies = iter(replies)
        self.calls = []

    def search(self, query, limit):
        self.calls.append((list(query), limit))
        reply = next(self.replies)
        if isinstance(reply, Exception):
            raise reply
        return reply


def execute(runner, data, client, *, start=2, count=1, top_k=3):
    output = io.StringIO()
    written = runner.write_queries(client, data, start_row=start, count=count, top_k=top_k, output=output)
    rows = [json.loads(line) for line in output.getvalue().splitlines()]
    assert written == len(rows)
    return rows


def test_original_query_ids_vectors_and_ordered_duplicate_hits(runner, data):
    hits = [VectorHit(6, 4.5), VectorHit(2, 1.5), VectorHit(6, 4.5)]
    client = FakeClient([hits, hits, hits])
    rows = execute(runner, data, client, start=5, count=3)
    assert [row["query_id"] for row in rows] == [5, 6, 7]
    np.testing.assert_array_equal([call[0] for call in client.calls], data.queries[5:8])
    assert all(call[1] == 3 for call in client.calls)
    assert rows[0]["hits"] == [
        {"id": 6, "rank": 1, "distance": 4.5},
        {"id": 2, "rank": 2, "distance": 1.5},
        {"id": 6, "rank": 3, "distance": 4.5},
    ]
    assert all(row["dataset"] == "fixture-ann" and row["backend"] == "offline-test" for row in rows)
    assert all(row["status"] == "ok" and row["error"] is None for row in rows)


def test_each_attempt_written_with_empty_timeout_and_error(runner, data):
    client = FakeClient([[], TimeoutError("timed out"), RuntimeError("service failed"), [VectorHit("x", 0.0)]])
    rows = execute(runner, data, client, start=1, count=4)
    assert [row["query_id"] for row in rows] == [1, 2, 3, 4]
    assert [row["status"] for row in rows] == ["empty", "timeout", "error", "ok"]
    assert rows[1]["error"] and rows[2]["error"]
    assert all(row["elapsed_ms"] >= 0 for row in rows)


@pytest.mark.parametrize("reply", [
    None, [{"id": 1, "distance": 0.0}], [VectorHit(True, 0.0)], [VectorHit("", 0.0)],
    [VectorHit(1.5, 0.0)], [VectorHit(1, float("nan"))], [VectorHit(1, float("inf"))],
    [VectorHit(1, True)], [VectorHit(1, "0.1")],
    [VectorHit(2, 0.2), VectorHit(None, 0.3)],
])
def test_malformed_reply_fails_whole_attempt(runner, data, reply):
    row = execute(runner, data, FakeClient([reply]))[0]
    assert row["status"] == "error"
    assert row["hits"] == []
    assert row["error"]


def test_timing_covers_search_call_only(runner, data, monkeypatch):
    events = []
    ticks = iter([10.0, 10.125])

    def clock():
        events.append("clock")
        return next(ticks)

    class Client:
        name = "timing-test"

        def search(self, query, limit):
            events.append("search")
            return []

    monkeypatch.setattr(runner, "perf_counter", clock)
    row = execute(runner, data, Client())[0]
    assert events == ["clock", "search", "clock"]
    assert row["elapsed_ms"] == pytest.approx(125.0)


@pytest.mark.parametrize("start,count,top_k", [(-1, 1, 1), (0, 0, 1), (0, 1, 0), (7, 2, 1), (8, 1, 1)])
def test_invalid_ranges_do_not_call_client_or_write(runner, data, start, count, top_k):
    output = io.StringIO()
    client = FakeClient([])
    with pytest.raises(ValueError):
        runner.write_queries(client, data, start_row=start, count=count, top_k=top_k, output=output)
    assert output.getvalue() == ""
    assert client.calls == []


def test_invalid_dimensions_do_not_call_client(runner, data):
    data.metadata["dimension"] = 4
    with pytest.raises(ValueError, match="[Dd]imension"):
        execute(runner, data, FakeClient([]))


def test_placeholder_uses_generic_root_and_remains_unimplemented(runner, data):
    assert isinstance(MilvusSearchClient(), SearchClient)
    with pytest.raises(NotImplementedError, match="Milvus"):
        execute(runner, data, MilvusSearchClient())
    assert "sciverse_mcp" in list_backends()


def test_cli_never_overwrites_existing_output(runner, tmp_path, monkeypatch):
    from dingo.data.datasource.ann_benchmarks import ANNBenchmarksDataSource

    def forbidden_load(self, *args, **kwargs):
        pytest.fail("Existing output must be rejected before loading or downloading data")

    monkeypatch.setattr(ANNBenchmarksDataSource, "__init__", forbidden_load)
    monkeypatch.setattr(ANNBenchmarksDataSource, "load", forbidden_load)
    output = tmp_path / "existing.jsonl"
    output.write_text("keep original\n")
    monkeypatch.setattr("sys.argv", ["run_queries.py", "--output", str(output)])
    with pytest.raises(SystemExit):
        runner.main()
    assert output.read_text() == "keep original\n"
