"""Offline ANN query execution checks; fake hits never represent a service run."""

import importlib.util
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from dingo.config import InputArgs
from dingo.retrieval.backends.milvus import MilvusSearchClient, VectorHit
from dingo.retrieval.search_client import SearchClient, list_backends


@pytest.fixture(scope="module")
def runner():
    path = Path(__file__).resolve().parents[3] / "examples/milvus_benchmark/2-query-execution/run_queries.py"
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


def test_cli_never_overwrites_existing_output(runner, tmp_path, monkeypatch):
    hdf5_input = importlib.import_module("examples.milvus_benchmark.0-data-loading.hdf5_input")

    def forbidden_load(*args, **kwargs):
        pytest.fail("Existing output must be rejected before loading data")

    monkeypatch.setattr(hdf5_input, "open_hdf5", forbidden_load)
    output = tmp_path / "existing.jsonl"
    output.write_text("keep original\n")
    monkeypatch.setattr("sys.argv", ["run_queries.py"] + milvus_args(output))
    with pytest.raises(SystemExit):
        runner.main()
    assert output.read_text() == "keep original\n"


class FakeSDK:
    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.calls = []
        self.closed = False

    def search(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.reply

    def close(self):
        self.closed = True


def searcher(sdk, **kwargs):
    options = dict(collection_name="fixture_vectors", id_field="source_key", vector_field="embedding", timeout=2.5)
    options.update(kwargs)
    return MilvusSearchClient(sdk, **options)


def test_sdk_search_arguments_and_ordered_extra_duplicate_hits():
    sdk = FakeSDK([[{"id": 19, "distance": 8}, {"id": "source-7", "distance": 1.5},
                    {"id": 19, "distance": 8}]])
    client = searcher(sdk, search_params={"metric_type": "L2", "params": {"nprobe": 7}})
    assert isinstance(client, SearchClient)
    assert client.search([1, 2, 3], limit=2) == [VectorHit(19, 8.0), VectorHit("source-7", 1.5), VectorHit(19, 8.0)]
    assert sdk.calls == [{"collection_name": "fixture_vectors", "data": [[1.0, 2.0, 3.0]],
                          "anns_field": "embedding", "limit": 2, "timeout": 2.5,
                          "search_params": {"metric_type": "L2", "params": {"nprobe": 7}}}]
    assert "sciverse_mcp" in list_backends()


def test_sdk_empty_hits():
    assert searcher(FakeSDK([[]])).search([1, 2], limit=1) == []


@pytest.mark.parametrize("reply", [
    None, [], {}, [[], []], [[None]], [[{"id": 1}]], [[{"distance": 0.0}]],
    [[{"id": True, "distance": 0.0}]], [[{"id": " ", "distance": 0.0}]],
    [[{"id": 1.5, "distance": 0.0}]], [[{"id": 1, "distance": True}]],
    [[{"id": 1, "distance": "0.1"}]], [[{"id": 1, "distance": float("nan")}]],
    [[{"id": 1, "distance": float("inf")}]],
    [[{"id": 2, "distance": 0.2}, {"id": None, "distance": 0.3}]],
])
def test_malformed_sdk_reply_fails_whole_attempt(runner, data, reply):
    sdk = FakeSDK(reply)
    row = execute(runner, data, searcher(sdk))[0]
    assert row["status"] == "error"
    assert row["hits"] == []
    assert row["error"]
    assert len(sdk.calls) == 1


@pytest.mark.parametrize("query,limit", [
    ([], 1), ([True, 1], 1), (["1", 2], 1), ([float("nan"), 1], 1),
    ([float("inf"), 1], 1), ([[1], [2]], 1), ([1, 2], 0), ([1, 2], -1),
    ([1, 2], True), ([1, 2], 1.5),
])
def test_invalid_search_arguments_do_not_call_sdk(query, limit):
    sdk = FakeSDK([[]])
    with pytest.raises((ValueError, TypeError)):
        searcher(sdk).search(query, limit=limit)
    assert sdk.calls == []


@pytest.mark.parametrize("options", [
    {"collection_name": ""}, {"id_field": ""}, {"vector_field": " "},
    {"id_field": "embedding"}, {"timeout": 0}, {"timeout": -1},
    {"timeout": True}, {"timeout": float("nan")}, {"timeout": float("inf")},
    {"search_params": []},
])
def test_invalid_search_configuration(options):
    with pytest.raises((ValueError, TypeError)):
        searcher(FakeSDK(), **options)


def test_sdk_timeout_and_service_error_are_distinct(runner, data):
    for error, status in [(TimeoutError("deadline"), "timeout"), (RuntimeError("service failed"), "error")]:
        sdk = FakeSDK(error=error)
        row = execute(runner, data, searcher(sdk))[0]
        assert row["status"] == status
        assert row["hits"] == []
        assert len(sdk.calls) == 1


@pytest.fixture
def hdf5_input_file(tmp_path, data):
    h5py = pytest.importorskip("h5py")
    path = tmp_path / "vectors.hdf5"
    with h5py.File(path, "w") as hdf5:
        hdf5.create_dataset("test", data=data.queries)
    return path


def milvus_args(output, input_path=None):
    return ["--milvus-uri", "http://example.invalid:19530", "--milvus-db-name", "fixture_db",
            "--milvus-collection", "fixture_vectors", "--milvus-id-field", "source_key",
            "--milvus-vector-field", "embedding", "--timeout", "2.5", "--output", str(output),
            "--input-path", str(input_path or output.with_name("vectors.hdf5"))]


def test_query_cli_forwards_configuration_writes_format_and_closes(runner, hdf5_input_file, tmp_path, monkeypatch):
    hdf5_input = importlib.import_module("examples.milvus_benchmark.0-data-loading.hdf5_input")
    open_vector_data = hdf5_input.open_vector_data
    loaded_configs = []
    sdk = FakeSDK([[{"source_key": 19, "distance": 0.5}]])
    constructors = []

    def open_data(input_args, **kwargs):
        loaded_configs.append(input_args)
        return open_vector_data(input_args, **kwargs)

    def constructor(**kwargs):
        constructors.append(kwargs)
        return sdk

    monkeypatch.setattr(hdf5_input, "open_vector_data", open_data)
    monkeypatch.setitem(sys.modules, "pymilvus", SimpleNamespace(MilvusClient=constructor))
    monkeypatch.setenv("MILVUS_TOKEN", "fixture-token")
    monkeypatch.chdir(tmp_path)
    output = Path("logs") / "queries.custom.jsonl"
    output.parent.mkdir()
    runner.main(milvus_args(output, hdf5_input_file) + [
        "--start-row", "2", "--count", "1", "--top-k", "3",
        "--search-params", '{"metric_type":"L2","params":{"nprobe":7}}',
    ])
    input_args, = loaded_configs
    assert isinstance(input_args, InputArgs)
    assert input_args.input_path == str(hdf5_input_file)
    assert input_args.output_path == str(output.parent)
    retrieval = input_args.executor.retrieval
    assert retrieval.backend == "milvus"
    assert retrieval.api_url == "http://example.invalid:19530"
    assert retrieval.limit == 3
    assert retrieval.timeout == 2.5
    assert constructors == [{"uri": "http://example.invalid:19530", "db_name": "fixture_db",
                             "token": "fixture-token", "timeout": 2.5}]
    assert sdk.calls == [{"collection_name": "fixture_vectors", "data": [[6.0, 7.0, 8.0]],
                          "anns_field": "embedding", "limit": 3, "timeout": 2.5,
                          "search_params": {"metric_type": "L2", "params": {"nprobe": 7}}}]
    row = json.loads(output.read_text())
    assert set(row) == {"dataset", "query_id", "backend", "top_k", "hits", "elapsed_ms", "status", "error"}
    assert row["query_id"] == 2 and row["status"] == "ok"
    assert row["hits"] == [{"id": 19, "rank": 1, "distance": 0.5}]
    assert sdk.closed


@pytest.mark.parametrize("extra", [["--count", "0"], ["--start-row", "8", "--count", "1"],
                                   ["--search-params", "[]"], ["--search-params", "invalid"],
                                   ["--timeout", "nan"], ["--timeout", "0"]])
def test_invalid_query_cli_never_connects_or_creates_output(runner, hdf5_input_file, tmp_path, monkeypatch, extra):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid configuration or range must be rejected before SDK construction")

    monkeypatch.setattr(runner, "create_milvus_client", forbidden)
    output = tmp_path / "queries.jsonl"
    with pytest.raises(SystemExit):
        runner.main(milvus_args(output) + extra)
    assert not output.exists()


def test_query_connection_failure_does_not_create_output(runner, hdf5_input_file, tmp_path, monkeypatch):
    def failing(**kwargs):
        raise RuntimeError("fixture connection failure")

    monkeypatch.setitem(sys.modules, "pymilvus", SimpleNamespace(MilvusClient=failing))
    output = tmp_path / "queries.jsonl"
    with pytest.raises(RuntimeError, match="fixture connection failure"):
        runner.main(milvus_args(output))
    assert not output.exists()


def test_query_missing_configuration_never_connects(runner, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Missing configuration must be rejected before SDK construction")

    monkeypatch.setattr(runner, "create_milvus_client", forbidden)
    with pytest.raises(SystemExit):
        runner.main(["--output", str(tmp_path / "queries.jsonl")])


def test_query_dangling_output_symlink_is_rejected_before_load(runner, tmp_path, monkeypatch):
    hdf5_input = importlib.import_module("examples.milvus_benchmark.0-data-loading.hdf5_input")

    def forbidden(*args, **kwargs):
        pytest.fail("An existing output path must be rejected before loading or connecting")

    monkeypatch.setattr(hdf5_input, "open_hdf5", forbidden)
    output = tmp_path / "queries.jsonl"
    output.symlink_to(tmp_path / "missing.jsonl")
    with pytest.raises(SystemExit):
        runner.main(milvus_args(output))
    assert output.is_symlink()


@pytest.mark.parametrize("kind,status", [
    ("future", "timeout"), ("deadline", "timeout"), ("wrapped", "timeout"),
    ("retry", "timeout"), ("milvus_deadline", "timeout"), ("unavailable", "error"),
    ("unrelated_timeout_text", "error"),
])
def test_sdk_and_rpc_timeout_normalization(runner, data, monkeypatch, kind, status):
    class RpcError(Exception):
        def __init__(self, code):
            self.status = code

        def code(self):
            return self.status

    class FutureTimeoutError(Exception):
        pass

    codes = SimpleNamespace(DEADLINE_EXCEEDED=object(), UNAVAILABLE=object())
    monkeypatch.setitem(sys.modules, "grpc", SimpleNamespace(
        RpcError=RpcError, FutureTimeoutError=FutureTimeoutError, StatusCode=codes,
    ))

    class MilvusException(Exception):
        def __init__(self, message, code=1):
            super().__init__(message)
            self.message = message
            self.code = code

    MilvusException.__module__ = "pymilvus.exceptions"
    errors = {
        "future": FutureTimeoutError(),
        "deadline": RpcError(codes.DEADLINE_EXCEEDED),
        "retry": MilvusException("[search] Retry timeout: timeout=2.5"),
        "milvus_deadline": MilvusException("Deadline Exceeded", codes.DEADLINE_EXCEEDED),
        "unavailable": RpcError(codes.UNAVAILABLE),
        "unrelated_timeout_text": MilvusException("collection timeout_config does not exist"),
    }
    wrapped = RuntimeError("wrapped deadline")
    wrapped.__cause__ = errors["deadline"]
    errors["wrapped"] = wrapped
    sdk = FakeSDK(error=errors[kind])
    row = execute(runner, data, searcher(sdk))[0]
    assert row["status"] == status
    assert row["error"]
    assert row["hits"] == []
    assert len(sdk.calls) == 1


def test_query_output_open_failure_closes_constructed_sdk(runner, hdf5_input_file, tmp_path, monkeypatch):
    sdk = FakeSDK([[]])
    monkeypatch.setitem(sys.modules, "pymilvus", SimpleNamespace(MilvusClient=lambda **kwargs: sdk))
    with pytest.raises(FileNotFoundError):
        runner.main(milvus_args(tmp_path / "missing" / "queries.jsonl", hdf5_input_file))
    assert sdk.closed
    assert sdk.calls == []
