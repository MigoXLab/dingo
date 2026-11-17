"""Offline checks for ANN import preparation and the injected Milvus SDK."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from dingo.retrieval.backends.importers.milvus import MilvusImportClient
from dingo.retrieval.import_client import ImportRecord, ImportResult


@pytest.fixture(scope="module")
def preview():
    path = Path(__file__).resolve().parents[3] / "examples/Milvus_benchmark/1-data-import/import_ann_dataset.py"
    spec = importlib.util.spec_from_file_location("ann_import_preview", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def data():
    return SimpleNamespace(base=np.arange(24, dtype="float32").reshape(8, 3), metadata={"dimension": 3})


def test_nonzero_ids_vectors_and_partial_tail(preview, data):
    batches = list(preview.iter_import_batches(data, start_row=2, count=5, batch_size=2))
    assert [[record.source_id for record in batch] for batch in batches] == [[2, 3], [4, 5], [6]]
    np.testing.assert_array_equal([record.vector for batch in batches for record in batch], data.base[2:7])
    assert all(isinstance(record, ImportRecord) for batch in batches for record in batch)


def test_last_row_boundary(preview, data):
    batches = list(preview.iter_import_batches(data, start_row=5, count=3, batch_size=2))
    assert [[record.source_id for record in batch] for batch in batches] == [[5, 6], [7]]
    np.testing.assert_array_equal(batches[-1][0].vector, data.base[-1])


@pytest.mark.parametrize("start,count,size", [
    (-1, 1, 1), (0, 0, 1), (0, -1, 1), (0, 1, 0), (0, 1, -1), (8, 1, 1), (7, 2, 1),
])
def test_invalid_range_and_batch_size(preview, data, start, count, size):
    with pytest.raises(ValueError):
        list(preview.iter_import_batches(data, start_row=start, count=count, batch_size=size))


def test_dimension_mismatch(preview, data):
    data.metadata["dimension"] = 4
    with pytest.raises(ValueError, match="[Dd]imension"):
        list(preview.iter_import_batches(data, start_row=0, count=1, batch_size=1))


def test_vectors_are_sliced_one_batch_at_a_time(preview, data):
    class SliceOnly:
        shape = data.base.shape
        ndim = 2

        def __len__(self):
            return self.shape[0]

        def __init__(self):
            self.reads = []

        def __getitem__(self, key):
            assert isinstance(key, slice)
            self.reads.append((key.start, key.stop))
            return data.base[key]

    base = SliceOnly()
    bundle = SimpleNamespace(base=base, metadata=data.metadata)
    batches = preview.iter_import_batches(bundle, start_row=2, count=5, batch_size=2)
    assert base.reads == []
    assert len(next(batches)) == 2
    assert base.reads == [(2, 4)]
    assert len(next(batches)) == 2
    assert base.reads == [(2, 4), (4, 6)]
    assert len(next(batches)) == 1
    assert base.reads == [(2, 4), (4, 6), (6, 7)]
    with pytest.raises(StopIteration):
        next(batches)


def test_import_result_accounts_for_all_outcomes():
    result = ImportResult(submitted=5, accepted=2, rejected=1, unknown=2, error="partial failure")
    assert result.accepted + result.rejected + result.unknown == result.submitted
    with pytest.raises(ValueError, match="nonnegative"):
        ImportResult(submitted=0, accepted=-1, rejected=0, unknown=1)
    with pytest.raises(ValueError, match="sum"):
        ImportResult(submitted=2, accepted=1, rejected=0, unknown=0)


class FakeSDK:
    def __init__(self, reply=None, error=None):
        self.reply = reply
        self.error = error
        self.calls = []
        self.closed = False

    def insert(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.reply

    def close(self):
        self.closed = True


def importer(sdk, **kwargs):
    options = dict(collection_name="fixture_vectors", id_field="source_key", vector_field="embedding", timeout=2.5)
    options.update(kwargs)
    return MilvusImportClient(sdk, **options)


def test_sdk_insert_preserves_ids_maps_fields_and_converts_vectors():
    sdk = FakeSDK({"insert_count": 2, "ids": [7, "source-19"]})
    records = [ImportRecord(7, [1, 2, 3], metadata={"discard": True}), ImportRecord("source-19", [4, 5, 6])]
    result = importer(sdk).write_batch(records)
    assert result == ImportResult(submitted=2, accepted=2, rejected=0, unknown=0)
    assert sdk.calls == [{"collection_name": "fixture_vectors", "timeout": 2.5, "data": [
        {"source_key": 7, "embedding": [1.0, 2.0, 3.0]},
        {"source_key": "source-19", "embedding": [4.0, 5.0, 6.0]},
    ]}]
    assert all(type(value) is float for row in sdk.calls[0]["data"] for value in row["embedding"])


def test_empty_batch_does_not_call_sdk():
    sdk = FakeSDK()
    assert importer(sdk).write_batch([]) == ImportResult(0, 0, 0, 0)
    assert sdk.calls == []


@pytest.mark.parametrize("records", [
    [ImportRecord(True, [1, 2])], [ImportRecord(" ", [1, 2])], [ImportRecord(1.5, [1, 2])],
    [ImportRecord(1, None)], [ImportRecord(1, [])], [ImportRecord(1, [True, 2])],
    [ImportRecord(1, ["1", 2])], [ImportRecord(1, [float("nan"), 2])],
    [ImportRecord(1, [1, float("inf")])], [ImportRecord(1, [[1], [2]])],
    [ImportRecord(1, [1, 2]), ImportRecord(2, [1, 2, 3])],
    [ImportRecord(1, [1, 2]), ImportRecord(1, [3, 4])],
    [ImportRecord(1, [1, 2]), ImportRecord(2, None)],
])
def test_invalid_batch_rejected_before_any_rpc(records):
    sdk = FakeSDK()
    result = importer(sdk).write_batch(records)
    assert result.submitted == result.rejected == len(records)
    assert result.accepted == result.unknown == 0
    assert result.error
    assert sdk.calls == []


@pytest.mark.parametrize("reply,accepted", [
    ({"insert_count": 2}, 2), ({"insert_count": 1}, 1),
    ({"insert_count": 1, "ids": [19]}, 1), ({"insert_count": 0, "ids": []}, 0),
])
def test_receipts_account_for_partial_acknowledgement(reply, accepted):
    sdk = FakeSDK(reply)
    result = importer(sdk).write_batch([ImportRecord(7, [1, 2]), ImportRecord(19, [3, 4])])
    assert (result.submitted, result.accepted, result.rejected, result.unknown) == (2, accepted, 0, 2 - accepted)
    assert bool(result.error) == (accepted < 2)
    assert len(sdk.calls) == 1


@pytest.mark.parametrize("reply", [
    None, [], {}, {"insert_count": True}, {"insert_count": "2"}, {"insert_count": -1},
    {"insert_count": 3}, {"insert_count": 2, "ids": [7]},
    {"insert_count": 2, "ids": [7, 7]}, {"insert_count": 2, "ids": [7, 99]},
    {"insert_count": 2, "ids": [7, True]},
])
def test_unverifiable_receipt_is_unknown_and_not_retried(reply):
    sdk = FakeSDK(reply)
    result = importer(sdk).write_batch([ImportRecord(7, [1, 2]), ImportRecord(19, [3, 4])])
    assert (result.accepted, result.rejected, result.unknown) == (0, 0, 2)
    assert result.error
    assert len(sdk.calls) == 1


@pytest.mark.parametrize("error", [TimeoutError("deadline"), RuntimeError("connection lost")])
def test_write_exception_is_unknown_and_not_retried(error):
    sdk = FakeSDK(error=error)
    result = importer(sdk).write_batch([ImportRecord(7, [1, 2])])
    assert (result.accepted, result.rejected, result.unknown) == (0, 0, 1)
    assert result.error
    assert len(sdk.calls) == 1


@pytest.mark.parametrize("options", [
    {"collection_name": ""}, {"id_field": ""}, {"vector_field": " "},
    {"id_field": "embedding"}, {"timeout": 0}, {"timeout": -1},
    {"timeout": True}, {"timeout": float("nan")}, {"timeout": float("inf")},
])
def test_invalid_import_configuration(options):
    with pytest.raises((ValueError, TypeError)):
        importer(FakeSDK(), **options)


@pytest.fixture
def fake_dataset(monkeypatch, data):
    from dingo.data import dataset_map, datasource_map

    class Dataset:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get_data(self):
            yield data

    monkeypatch.setitem(datasource_map, "ann_benchmarks", lambda **kwargs: object())
    monkeypatch.setitem(dataset_map, "ann_benchmarks", Dataset)


def milvus_args():
    return ["--milvus-uri", "http://example.invalid:19530", "--milvus-db-name", "fixture_db",
            "--milvus-collection", "fixture_vectors", "--milvus-id-field", "source_key",
            "--milvus-vector-field", "embedding", "--timeout", "2.5"]


def test_preview_runs_without_optional_sdk(preview, fake_dataset, monkeypatch, capsys):
    import sys

    monkeypatch.setitem(sys.modules, "pymilvus", None)
    preview.main(["--start-row", "2", "--count", "3", "--batch-size", "2", "--cache-dir", "/tmp/fixture-ann-cache"])
    assert "Total: records=3, batches=2" in capsys.readouterr().out


def test_write_cli_forwards_sdk_and_field_configuration_and_closes(preview, fake_dataset, monkeypatch):
    import sys

    sdk = FakeSDK({"insert_count": 2, "ids": [2, 3]})
    constructors = []

    def constructor(**kwargs):
        constructors.append(kwargs)
        return sdk

    monkeypatch.setitem(sys.modules, "pymilvus", SimpleNamespace(MilvusClient=constructor))
    monkeypatch.setenv("MILVUS_TOKEN", "fixture-token")
    preview.main(["--write-milvus", "--start-row", "2", "--count", "2", "--cache-dir", "/tmp/fixture-ann-cache"]
                 + milvus_args())
    assert constructors == [{"uri": "http://example.invalid:19530", "db_name": "fixture_db",
                             "token": "fixture-token", "timeout": 2.5}]
    assert sdk.closed
    assert sdk.calls == [{"collection_name": "fixture_vectors", "timeout": 2.5,
                          "data": [{"source_key": 2, "embedding": [6.0, 7.0, 8.0]},
                                   {"source_key": 3, "embedding": [9.0, 10.0, 11.0]}]}]


def test_write_cli_incomplete_ack_stops_without_retry_and_closes(preview, fake_dataset, monkeypatch):
    import sys

    sdk = FakeSDK({"insert_count": 1})
    monkeypatch.setitem(sys.modules, "pymilvus", SimpleNamespace(MilvusClient=lambda **kwargs: sdk))
    with pytest.raises(SystemExit, match="not fully acknowledged"):
        preview.main(["--write-milvus", "--count", "5", "--cache-dir", "/tmp/fixture-ann-cache"] + milvus_args())
    assert len(sdk.calls) == 1
    assert sdk.closed


@pytest.mark.parametrize("args", [["--write-milvus"], ["--write-milvus", "--start-row", "-1"],
                                  ["--write-milvus", "--start-row", "8"] + milvus_args()])
def test_invalid_import_cli_never_connects(preview, fake_dataset, monkeypatch, args):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid configuration or range must be rejected before SDK construction")

    monkeypatch.setattr(preview, "create_milvus_client", forbidden)
    with pytest.raises(SystemExit):
        preview.main(args + ["--count", "1", "--cache-dir", "/tmp/fixture-ann-cache"])


@pytest.fixture
def import_check(monkeypatch):
    import sys

    path = Path(__file__).resolve().parents[3] / "examples/Milvus_benchmark/4-vector-db-import/run_import_test.py"
    spec = importlib.util.spec_from_file_location("milvus_import_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    types = SimpleNamespace(INT64=5, FLOAT_VECTOR=101)
    monkeypatch.setitem(sys.modules, "pymilvus", SimpleNamespace(DataType=types))
    return module


class MemoryImportSDK:
    def get_server_version(self, **kwargs):
        return "fixture-version"

    def __init__(self, *, partial=False, corrupt=False):
        self.rows = {}
        self.calls = []
        self.partial = partial
        self.corrupt = corrupt

    def describe_collection(self, **kwargs):
        return {"auto_id": False, "fields": [
            {"name": "key", "type": 5, "is_primary": True},
            {"name": "embedding", "type": 101, "params": {"dim": 3}},
        ]}

    def insert(self, **kwargs):
        self.calls.append(kwargs)
        rows = kwargs["data"][:1] if self.partial else kwargs["data"]
        for row in rows:
            self.rows[row["key"]] = dict(row)
        return {"insert_count": len(rows), "ids": [row["key"] for row in rows]}

    def query(self, **kwargs):
        assert kwargs["consistency_level"] == "Strong"
        if kwargs["output_fields"] == ["count(*)"]:
            return [{"count(*)": len(self.rows)}]
        rows = [dict(self.rows[row_id]) for row_id in reversed(kwargs["ids"])]
        if self.corrupt:
            rows[0]["embedding"] = [value + 1 for value in rows[0]["embedding"]]
        return rows


def check_options(tmp_path):
    return SimpleNamespace(
        milvus_uri="http://example.invalid:19530", milvus_db_name="fixture_db", milvus_collection="fixture",
        milvus_id_field="key", milvus_vector_field="embedding", timeout=5.0,
        start_row=2, count=5, batch_size=2, cache_dir="fixture-cache", output_dir=tmp_path / "report",
    )


def test_complete_import_check_and_reports(import_check, preview, tmp_path):
    import json

    data = SimpleNamespace(base=np.arange(30, dtype="float32").reshape(10, 3),
                           metadata={"name": "fixture-ann", "dimension": 3})
    sdk = MemoryImportSDK()
    baseline = SimpleNamespace(list_collections=lambda **kwargs: ["existing"])
    options = check_options(tmp_path)
    report = import_check.run_check(sdk, baseline, data, options, preview)
    assert report["status"] == "passed"
    assert report["accepted"] == report["verified_count"] == report["final_count"] == 5
    assert report["batch_count"] == 3
    assert report["default_collection_names_unchanged"]
    assert sorted(sdk.rows) == [2, 3, 4, 5, 6]
    saved = json.loads((options.output_dir / "summary.json").read_text())
    assert saved == report
    assert len((options.output_dir / "batches.jsonl").read_text().splitlines()) == 3


@pytest.mark.parametrize("issue", ["nonempty", "range", "default"])
def test_import_check_preflight_prevents_writes(import_check, preview, tmp_path, issue):
    data = SimpleNamespace(base=np.zeros((10, 3)), metadata={"name": "fixture-ann", "dimension": 3})
    options = check_options(tmp_path)
    sdk = MemoryImportSDK()
    baseline = SimpleNamespace(list_collections=lambda **kwargs: ["existing"])
    if issue == "nonempty":
        sdk.rows[99] = {"key": 99, "embedding": [0.0] * 3}
    elif issue == "range":
        options.start_row = 9
    else:
        options.milvus_db_name = "default"
    with pytest.raises(ValueError):
        import_check.run_check(sdk, baseline, data, options, preview)
    assert sdk.calls == []
    assert not options.output_dir.exists()


@pytest.mark.parametrize("issue", ["partial", "corrupt"])
def test_import_check_failure_retains_report_without_retry(import_check, preview, tmp_path, issue):
    import json

    data = SimpleNamespace(base=np.zeros((10, 3)), metadata={"name": "fixture-ann", "dimension": 3})
    options = check_options(tmp_path)
    sdk = MemoryImportSDK(partial=issue == "partial", corrupt=issue == "corrupt")
    baseline = SimpleNamespace(list_collections=lambda **kwargs: ["existing"])
    report = import_check.run_check(sdk, baseline, data, options, preview)
    assert report["status"] == "failed"
    assert report["error"]
    assert report["default_collection_names_unchanged"]
    if issue == "partial":
        assert len(sdk.calls) == 1
        assert report["accepted"] == report["unknown"] == 1
    else:
        assert len(sdk.calls) == 3
        assert "Readback vectors" in report["error"]
    assert json.loads((options.output_dir / "summary.json").read_text()) == report


def test_insert_receipt_accepts_general_id_sequence():
    from collections import UserList

    sdk = FakeSDK({"insert_count": 2, "ids": UserList([7, 19])})
    result = importer(sdk).write_batch([ImportRecord(7, [1, 2]), ImportRecord(19, [3, 4])])
    assert result == ImportResult(2, 2, 0, 0)


@pytest.mark.parametrize("kind,ids", [("LongArray", [7, 19]), ("StringArray", ["a", "b"])])
def test_insert_receipt_accepts_real_protobuf_ids(kind, ids):
    pytest.importorskip("pymilvus")
    from pymilvus.grpc_gen import schema_pb2

    repeated = getattr(schema_pb2, kind)(data=ids).data
    sdk = FakeSDK({"insert_count": 2, "ids": repeated})
    result = importer(sdk).write_batch([ImportRecord(value, [1, 2]) for value in ids])
    assert result == ImportResult(2, 2, 0, 0)


@pytest.mark.parametrize("receipt_ids,source_ids", [("ab", ["a", "b"]), (b"\x07\x13", [7, 19])])
def test_string_and_binary_receipts_are_not_id_sequences(receipt_ids, source_ids):
    sdk = FakeSDK({"insert_count": 2, "ids": receipt_ids})
    result = importer(sdk).write_batch([ImportRecord(value, [1, 2]) for value in source_ids])
    assert result.accepted == 0
    assert result.unknown == 2
