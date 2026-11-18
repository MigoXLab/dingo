import io
from contextlib import closing

import numpy as np
import pytest
from botocore.response import StreamingBody

from dingo.config import InputArgs
from dingo.data import dataset_map, datasource_map

h5py = pytest.importorskip("h5py")


class FakeS3:
    def __init__(self, objects):
        self.objects = objects
        self.opened_keys = []
        self.requests = []
        self.responses = []

    def get_paginator(self, operation):
        assert operation == "list_objects_v2"
        return self

    def paginate(self, *, Bucket, Prefix):
        assert Bucket == "fixture"
        for key in self.objects:
            if key.startswith(Prefix):
                yield {"Contents": [{"Key": key}]}

    def head_object(self, *, Bucket, Key):
        assert Bucket == "fixture"
        self.opened_keys.append(Key)
        return {"ContentLength": len(self.objects[Key]), "ETag": '"fixture"'}

    def get_object(self, *, Bucket, Key, Range, IfMatch):
        assert (Bucket, IfMatch) == ("fixture", '"fixture"')
        content = self.objects[Key]
        start, end = map(int, Range.removeprefix("bytes=").split("-"))
        assert 0 <= start <= end < len(content)
        self.requests.append((start, end))
        chunk = content[start:end + 1]
        response = io.BytesIO(chunk)
        self.responses.append(response)
        return {
            "ContentRange": f"bytes {start}-{end}/{len(content)}",
            "Body": StreamingBody(response, len(chunk)),
        }


def make_source(source, path):
    args = InputArgs(input_path=str(path), dataset={"source": source, "format": "hdf5"})
    return datasource_map[source](input_args=args)


def read_slices(source_name, path, slices):
    source = make_source(source_name, path)
    dataset = dataset_map[source_name](source=source)
    with closing(dataset.get_data()) as records:
        hdf5 = next(records).hdf5
        assert isinstance(hdf5["vectors/embeddings"], h5py.Dataset)
        results = [hdf5["vectors/embeddings"][rows] for rows in slices]
    assert not hdf5.id.valid
    return results


def test_local_and_s3_read_same_hdf5_slices_and_close(tmp_path, monkeypatch):
    path = tmp_path / "vectors.h5"
    vectors = np.arange(65536 * 8, dtype=np.float32).reshape(-1, 8)
    with h5py.File(path, "w") as hdf5:
        hdf5.create_dataset("vectors/embeddings", data=vectors)
    payload = path.read_bytes()
    client = FakeS3({"vectors.h5": payload})
    monkeypatch.setattr(datasource_map["s3"], "_get_client", staticmethod(lambda *args: client))

    slices = (slice(-3, None), slice(2, 5))
    local_results = read_slices("local", path, slices)
    s3_results = read_slices("s3", "s3://fixture/vectors.h5", slices)
    for rows, local_result, s3_result in zip(slices, local_results, s3_results):
        np.testing.assert_array_equal(local_result, vectors[rows])
        np.testing.assert_array_equal(s3_result, local_result)
    assert len(client.requests) > 1
    assert all(end - start + 1 < len(payload) for start, end in client.requests)
    assert all(response.closed for response in client.responses)


def test_s3_binary_reader_can_seek_backwards_and_read_eof(monkeypatch):
    client = FakeS3({"vectors.h5": b"abcdef"})
    monkeypatch.setattr(datasource_map["s3"], "_get_client", staticmethod(lambda *args: client))
    source = make_source("s3", "s3://fixture/vectors.h5")
    with next(source.load())() as stream:
        assert stream.seek(-2, io.SEEK_END) == 4
        assert stream.read(4) == b"ef"
        assert client.requests == [(4, 5)]
        assert stream.seek(1) == 1
        assert stream.read(2) == b"bc"
    assert all(response.closed for response in client.responses)


@pytest.mark.parametrize("source_name", ["local", "s3"])
def test_hdf5_directory_or_prefix_yields_sorted_files_and_closes_each(source_name, tmp_path, monkeypatch):
    objects = {}
    for name, value in [("nested/second.HDF5", 2), ("first.h5", 1)]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(path, "w") as hdf5:
            hdf5.create_dataset("vectors", data=[[value]])
        objects[f"sample/{name}"] = path.read_bytes()
    (tmp_path / "notes.txt").write_text("Ignore this file", encoding="utf-8")
    objects["sample/notes.txt"] = b"Ignore this file"
    objects["other.h5"] = b"Outside the prefix"
    client = FakeS3(objects)
    monkeypatch.setattr(datasource_map["s3"], "_get_client", staticmethod(lambda *args: client))
    path = tmp_path if source_name == "local" else "s3://fixture/sample/"
    dataset = dataset_map[source_name](source=make_source(source_name, path))

    with closing(dataset.get_data()) as records:
        first = next(records).hdf5
        assert first["vectors"][0, 0] == 1
        if source_name == "s3":
            assert client.opened_keys == ["sample/first.h5"]
        second = next(records).hdf5
        assert not first.id.valid
        assert second["vectors"][0, 0] == 2
        assert list(records) == []
    assert not second.id.valid
    if source_name == "s3":
        assert client.opened_keys == ["sample/first.h5", "sample/nested/second.HDF5"]
        assert all(response.closed for response in client.responses)
