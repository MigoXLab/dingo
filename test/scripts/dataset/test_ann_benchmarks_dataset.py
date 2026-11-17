"""Offline tests for ANN-Benchmarks loading, schema and file lifetime"""

import builtins
import io

import numpy as np
import pytest

import dingo.data.datasource.ann_benchmarks as source_module
from dingo.config import InputArgs
from dingo.data import converters, dataset_map, datasource_map

h5py = pytest.importorskip("h5py")


def make_file(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as f:
        f.attrs["dimension"] = 2
        f.attrs["distance"] = "euclidean"
        f.create_dataset("train", data=np.array([[0, 0], [1, 0], [0, 1]], dtype="float32"))
        f.create_dataset("test", data=np.array([[0, 0]], dtype="float32"))
        f.create_dataset("neighbors", data=np.array([[0, 1]], dtype="int32"))
        f.create_dataset("distances", data=np.array([[0, 1]], dtype="float32"))
    return path


def make_source(tmp_path):
    args = InputArgs(input_path="sift-128-euclidean", dataset={
        "source": "ann_benchmarks", "format": "ann_benchmarks",
        "ann_benchmarks_config": {"cache_dir": str(tmp_path)},
    })
    return datasource_map["ann_benchmarks"](args)


def test_download_and_cache_reuse(tmp_path, monkeypatch):
    payload = make_file(tmp_path / "fixture.hdf5").read_bytes()
    source = make_source(tmp_path / "cache")
    calls = []

    def download(request, timeout):
        calls.append(request.full_url)
        return io.BytesIO(payload)
    monkeypatch.setattr(source_module, "urlopen", download)
    for _ in range(2):
        with source.load() as f:
            assert f["train"].shape == (3, 2)
    assert calls == [source.URLS[source.name]]
    assert not list(source.cache_dir.glob("*.part"))


def test_mapping_slices_and_context_close(tmp_path):
    source = make_source(tmp_path)
    make_file(source.path)
    assert "ann_benchmarks" in converters
    dataset = dataset_map["ann_benchmarks"](source=source)
    with dataset:
        data = next(dataset.get_data())
        assert isinstance(data.base, h5py.Dataset)
        np.testing.assert_array_equal(data.base[1:2], [[1, 0]])
        np.testing.assert_array_equal(data.ground_truth[:], [[0, 1]])
        assert data.metadata["dimension"] == 2
        assert data.metadata["distance"] == "euclidean"
        assert dataset.to_dict()["source_type"] == "ann_benchmarks"
        assert data.base.id.valid
    assert not data.base.id.valid
    with pytest.raises(RuntimeError, match="with block"):
        next(dataset.get_data())
    with dataset:
        assert next(dataset.get_data()).base.id.valid


def test_exception_closes_file(tmp_path):
    source = make_source(tmp_path)
    make_file(source.path)
    with pytest.raises(RuntimeError, match="consumer error"):
        with dataset_map["ann_benchmarks"](source=source) as dataset:
            data = next(dataset.get_data())
            raise RuntimeError("consumer error")
    assert not data.base.id.valid


@pytest.mark.parametrize("field,value,error", [
    ("test", np.zeros((1, 3)), "dimensions"),
    ("neighbors", np.array([[0, 3]]), "outside"),
    ("neighbors", np.array([[0, -1]]), "outside"),
    ("neighbors", np.array([[0.0, 1.0]]), "integer"),
    ("distances", np.zeros((2, 2)), "shapes"),
    ("train", np.zeros((0, 2)), "nonempty"),
    ("train", np.zeros(3), "two-dimensional"),
    ("train", np.array([[b"a", b"b"]]), "numeric"),
])
def test_invalid_arrays_close_file(tmp_path, field, value, error):
    source = make_source(tmp_path)
    make_file(source.path)
    with h5py.File(source.path, "r+") as f:
        del f[field]
        f.create_dataset(field, data=value)
    dataset = dataset_map["ann_benchmarks"](source=source)
    with pytest.raises(ValueError, match=error):
        with dataset:
            next(dataset.get_data())
    assert dataset._file is None
    assert not dataset._active


@pytest.mark.parametrize("payload", [b"broken HDF5", None])
def test_failed_download_never_publishes_cache(tmp_path, monkeypatch, payload):
    source = make_source(tmp_path)

    def download(*args, **kwargs):
        if payload is None:
            raise TimeoutError("network timeout")
        return io.BytesIO(payload)
    monkeypatch.setattr(source_module, "urlopen", download)
    with pytest.raises((OSError, TimeoutError)):
        source.load()
    assert not source.path.exists()
    assert not list(tmp_path.glob("*.part"))


def test_missing_fields(tmp_path):
    source = make_source(tmp_path)
    make_file(source.path)
    with h5py.File(source.path, "r+") as f:
        del f["neighbors"]
    with pytest.raises(ValueError, match="neighbors"):
        with dataset_map["ann_benchmarks"](source=source) as dataset:
            next(dataset.get_data())


def test_corrupt_existing_cache(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    source.path.write_bytes(b"broken")
    monkeypatch.setattr(source_module, "urlopen", lambda *a, **k: pytest.fail("Unexpected download"))
    with pytest.raises(ValueError, match="Invalid HDF5 cache"):
        source.load()


def test_unknown_dataset():
    args = InputArgs(input_path="../unknown")
    with pytest.raises(ValueError, match="Unsupported"):
        datasource_map["ann_benchmarks"](args)


def test_missing_optional_dependency(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    original = builtins.__import__

    def no_h5py(name, *args, **kwargs):
        if name == "h5py":
            raise ModuleNotFoundError("h5py unavailable")
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", no_h5py)
    with pytest.raises(ImportError, match="dingo-python"):
        source.load()


@pytest.mark.parametrize("attribute,value,error", [
    ("dimension", 128, "dimension"),
    ("distance", "angular", "euclidean"),
])
def test_invalid_metadata(tmp_path, attribute, value, error):
    source = make_source(tmp_path)
    make_file(source.path)
    with h5py.File(source.path, "r+") as f:
        f.attrs[attribute] = value
    with pytest.raises(ValueError, match=error):
        with dataset_map["ann_benchmarks"](source=source) as dataset:
            next(dataset.get_data())
    assert dataset._file is None


def test_existing_cache_requires_no_network(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    make_file(source.path)
    monkeypatch.setattr(source_module, "urlopen", lambda *a, **k: pytest.fail("Unexpected download"))
    with dataset_map["ann_benchmarks"](source=source) as dataset:
        data = next(dataset.get_data())
        assert isinstance(data.queries, h5py.Dataset)
        assert isinstance(data.ground_truth, h5py.Dataset)
        assert isinstance(data.distances, h5py.Dataset)
        assert data.metadata["dimension"] == 2
        assert len(data.base) == 3
    assert not data.queries.id.valid


def test_nested_context_rejected(tmp_path):
    dataset = dataset_map["ann_benchmarks"](source=make_source(tmp_path))
    with dataset:
        with pytest.raises(RuntimeError, match="already active"):
            with dataset:
                pass
    assert not dataset._active


def test_converter_keeps_vectors_lazy(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    make_file(source.path)
    original = h5py.Dataset.__getitem__
    reads = []

    def track_reads(array, key):
        reads.append(array.name)
        return original(array, key)

    monkeypatch.setattr(h5py.Dataset, "__getitem__", track_reads)
    with dataset_map["ann_benchmarks"](source=source) as dataset:
        data = next(dataset.get_data())
        assert reads == ["/neighbors"]
        np.testing.assert_array_equal(data.queries[:1], [[0, 0]])
        assert reads == ["/neighbors", "/test"]
