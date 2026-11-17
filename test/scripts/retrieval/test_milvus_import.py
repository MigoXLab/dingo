"""Offline checks for ANN import preparation and the backend placeholder."""

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


def test_milvus_write_is_explicitly_unimplemented():
    with pytest.raises(NotImplementedError, match="Milvus"):
        MilvusImportClient().write_batch([ImportRecord(source_id=7, vector=[1.0, 2.0])])
