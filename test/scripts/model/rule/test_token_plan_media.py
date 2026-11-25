import io
import json
from pathlib import Path
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError
from PIL import Image

from dingo.config import InputArgs
from dingo.io import Data
from dingo.model import Model
from dingo.model.rule.rule_agent import RuleAgentTrajectoryMediaIntegrity

PREFIX = "raw/v001/dt=2026-10-31/7/"
FIXTURE = Path(__file__).resolve().parents[3] / "data/agent/token_plan_media.jsonl"


def task(secret="test-secret"):
    return InputArgs(evaluator=[{"evals": [{"name": "RuleAgentTrajectoryMediaIntegrity", "config": {
        "media_config": {"raw_base_uri": "s3://unit-test/raw/v001/", "partition_date": "2026-10-31"},
        "s3_config": {"s3_endpoint_url": "https://s3.example.test", "s3_ak": "test-id", "s3_sk": secret},
    }}]}])


def run(record, args=None):
    settings = (args or task()).evaluator[0].evals[0]
    rule = Model.get_rule_by_name(settings.name)()
    assert isinstance(rule, RuleAgentTrajectoryMediaIntegrity)
    Model.set_config_rule(rule, settings.config)
    return rule.eval(Data(**record))


def s3_error(code):
    return ClientError({"Error": {"Code": code}}, "GetObject")


@pytest.fixture
def record():
    return json.loads(FIXTURE.read_bytes())


@pytest.fixture
def storage(monkeypatch):
    objects = {}
    client = Mock()

    def head(Bucket, Key):
        assert Bucket == "unit-test"
        if Key not in objects:
            raise s3_error("404")

    def get(Bucket, Key):
        assert Bucket == "unit-test"
        value = objects[Key]
        if isinstance(value, Exception):
            raise value
        return {"Body": io.BytesIO(value)}

    client.head_object.side_effect = head
    client.get_object.side_effect = get
    factory = Mock(return_value=client)
    monkeypatch.setattr("boto3.session.Session.client", factory)
    return objects, client, factory


@pytest.fixture
def png():
    data = io.BytesIO()
    Image.new("RGB", (3, 3), "red").save(data, format="PNG")
    return data.getvalue()


@pytest.mark.parametrize("directory", ["demo/normalized-id", "demo/no_session_id", "normalized-id", "no_session_id"])
def test_layouts_and_explicit_credentials(record, storage, png, directory):
    objects, client, factory = storage
    objects[PREFIX + directory + "/image.png"] = png
    record["multimodal_file_mapping"] *= 2
    for secret in ("first-secret", "second-secret"):
        args = task(secret)
        assert secret not in json.dumps(args.to_dict())
        result = run(record, args)
        assert result.effective_verdict == "pass"
        assert result.statistics == {"images": 1, "valid": 1, "bad": 0, "unchecked": 0}
        assert factory.call_args.kwargs["aws_secret_access_key"] == secret
        assert factory.call_args.kwargs["aws_access_key_id"] == "test-id"
    assert client.get_object.call_count == client.close.call_count == 2
    assert all(call.kwargs["Key"].endswith("/image.png") for call in client.head_object.call_args_list)


def test_corrupt_idat_and_partial_permission(record, storage, png):
    objects, _, _ = storage
    # Flip the IDAT checksum, retaining a readable PNG header and image data.
    bad = bytearray(png)
    marker = bad.index(b"IDAT")
    crc = marker + 4 + int.from_bytes(bad[marker - 4:marker], "big")
    bad[crc] ^= 1
    objects[PREFIX + "demo/no_session_id/image.png"] = bad
    objects[PREFIX + "demo/no_session_id/private.jpg"] = s3_error("AccessDenied")
    record["multimodal_file_mapping"].append({"object_name": "private.jpg"})
    result = run(record)
    assert result.effective_verdict == "issue"
    assert [r["code"] for r in result.reason] == ["IMAGE_DECODE_FAILED", "S3_ACCESS_DENIED"]
    assert result.statistics == {"images": 2, "valid": 0, "bad": 1, "unchecked": 1}


@pytest.mark.parametrize("error, code, verdict", [
    (s3_error("403"), "S3_ACCESS_DENIED", "n/a"),
    (s3_error("NoSuchKey"), "OBJECT_MISSING", "issue"),
    (ReadTimeoutError(endpoint_url="https://s3.example.test"), "S3_READ_ERROR", "n/a"),
])
def test_read_errors(record, storage, error, code, verdict):
    objects, _, _ = storage
    objects[PREFIX + "normalized-id/image.png"] = error
    result = run(record)
    assert result.effective_verdict == verdict
    assert result.reason[0]["code"] == code
    if verdict == "n/a":
        assert result.not_applicable_kind == "execution_error"


def test_unresolved_and_ambiguous(record, storage, png):
    objects, client, _ = storage
    assert run(record).not_applicable_code == "PATH_UNRESOLVED"
    objects[PREFIX + "demo/no_session_id/image.png"] = png
    objects[PREFIX + "demo/normalized-id/image.png"] = png
    assert run(record).not_applicable_code == "AMBIGUOUS_PATH"
    client.get_object.assert_not_called()


def test_truncated_jpeg_with_readable_header(record, storage):
    raw = io.BytesIO()
    Image.new("RGB", (80, 80), "blue").save(raw, format="JPEG")
    truncated = raw.getvalue()[:-20]
    with Image.open(io.BytesIO(truncated)) as img:
        assert img.size == (80, 80)
    objects, _, _ = storage
    record["multimodal_file_mapping"] = [{"object_name": "frame.jpg"}]
    objects[PREFIX + "demo/no_session_id/frame.jpg"] = truncated
    result = run(record)
    assert result.reason[0]["code"] == "IMAGE_DECODE_FAILED"
    assert result.status


def test_nested_media_and_skips(record, storage, png):
    objects, _, factory = storage
    record["metadata"]["session_id"] = "tp-prefix:abc"
    objects[PREFIX + "demo/tp-prefix:abc/image.png"] = png
    parent = {"multimodal_file_mapping": [{"object_name": "audio.wav"}]}
    assert run(parent).not_applicable_code == "NO_MAPPED_IMAGES"
    factory.assert_not_called()
    parent["sub_agent_trajectory"] = {"call": record}
    assert run(parent).statistics["valid"] == 1


def test_bad_config_does_not_fall_back_to_worker_credentials(record, storage):
    _, _, factory = storage
    assert run(record, task(secret="")).not_applicable_code == "CONFIG_INVALID"
    factory.assert_not_called()
