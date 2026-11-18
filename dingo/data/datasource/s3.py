import io
from contextlib import closing
from typing import Any, BinaryIO, Callable, Dict, Generator, Iterator, Optional
from urllib.parse import unquote, urlsplit

import boto3
import boto3.s3
from botocore.config import Config

from dingo.config import InputArgs
from dingo.data.datasource.base import DataSource

_S3_READ_SIZE = 1024 * 1024


class _S3RangeReader(io.RawIOBase):
    def __init__(self, client, bucket: str, key: str, size: int, etag: Optional[str]):
        super().__init__()
        self._client = client
        self._object = {"Bucket": bucket, "Key": key}
        if etag is not None:
            self._object["IfMatch"] = etag
        self._size = size
        self._offset = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._offset

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_CUR:
            offset += self._offset
        elif whence == io.SEEK_END:
            offset += self._size
        elif whence != io.SEEK_SET:
            raise ValueError("Invalid seek mode")
        if offset < 0:
            raise ValueError("Negative seek position")
        self._offset = offset
        return offset

    def readinto(self, buffer) -> int:
        target = memoryview(buffer).cast("B")
        size = min(len(target), self._size - self._offset, _S3_READ_SIZE)
        if size <= 0:
            return 0
        start = self._offset
        end = start + size - 1
        response = self._client.get_object(**self._object, Range=f"bytes={start}-{end}")
        with closing(response["Body"]) as body:
            if response.get("ContentRange") != f"bytes {start}-{end}/{self._size}":
                raise OSError("S3 returned an unexpected byte range")
            content = body.read(size)
        if len(content) != size:
            raise OSError("S3 returned an incomplete byte range")
        target[:size] = content
        self._offset += size
        return size


@DataSource.register()
class S3DataSource(DataSource):
    SUPPORTED_FORMATS = {"jsonl", "ms_swift", "plaintext", "hdf5"}

    def __init__(
        self,
        input_args: InputArgs = None,
        config_name: Optional[str] = None,
    ):
        """Create a `S3DataSource` instance.
        Args:
            input_args: A `InputArgs` instance to load the dataset from.
            config_name: Optional configuration name.
        """
        self.uri = input_args.input_path
        self.bucket, self.path = self._parse_s3_uri(self.uri)
        self.client = self._get_client(
            input_args.dataset.s3_config.s3_ak,
            input_args.dataset.s3_config.s3_sk,
            input_args.dataset.s3_config.s3_endpoint_url,
            input_args.dataset.s3_config.s3_addressing_style,
        )
        self.config_name = config_name
        super().__init__(input_args=input_args)

    @staticmethod
    def _parse_s3_uri(uri: str) -> tuple[str, str]:
        parsed = urlsplit(uri)
        if parsed.scheme.lower() != "s3" or not parsed.netloc:
            raise ValueError(
                "S3 input_path must be a full URI such as "
                "'s3://bucket/path/to/data.jsonl'."
            )
        if parsed.query or parsed.fragment:
            raise ValueError("S3 input_path must not contain a query or fragment.")
        return parsed.netloc, unquote(parsed.path.lstrip("/"))

    @staticmethod
    def _get_client(ak: str, sk: str, endpoint_url: str, addressing_style: str):
        if ak == "" or sk == "" or endpoint_url == "":
            raise RuntimeError("S3 param must be set when using S3 datasource.")
        s3_client = boto3.client(
            service_name="s3",
            aws_access_key_id=ak,
            aws_secret_access_key=sk,
            endpoint_url=endpoint_url,
            config=Config(
                s3={"addressing_style": addressing_style},
                retries={"max_attempts": 5, "mode": "standard"},
            ),
        )
        return s3_client

    @staticmethod
    def get_source_type() -> str:
        return "s3"

    def load(self, **kwargs) -> Generator[str | Callable[[], BinaryIO], None, None]:
        """Iterate text records or provide a binary opener for HDF5."""
        data_format = self.input_args.dataset.format
        if data_format not in self.SUPPORTED_FORMATS:
            supported = ", ".join(sorted(self.SUPPORTED_FORMATS))
            raise RuntimeError(f"S3 format must be one of: {supported}")
        if data_format == "hdf5":
            return self._load_hdf5()
        return self._load()

    def _load_hdf5(self) -> Generator[Callable[[], BinaryIO], None, None]:
        if not self.path or self.path.endswith("/"):
            raise ValueError("HDF5 input_path must point to a single S3 object")
        yield self._open_hdf5

    def _open_hdf5(self) -> BinaryIO:
        metadata = self.client.head_object(Bucket=self.bucket, Key=self.path)
        reader = _S3RangeReader(
            self.client, self.bucket, self.path, metadata["ContentLength"], metadata.get("ETag"),
        )
        return io.BufferedReader(reader, buffer_size=_S3_READ_SIZE)

    def _load(self) -> Generator[str, None, None]:
        if self.path and not self.path.endswith("/"):
            keys = iter((self.path,))
        else:
            keys = self._iter_object_keys()

        for key in keys:
            obj = self.client.get_object(Bucket=self.bucket, Key=key)
            body = obj["Body"]
            try:
                for line in body.iter_lines():
                    yield line.decode("utf-8")
            finally:
                body.close()

    def _iter_object_keys(self) -> Iterator[str]:
        """Yield every matching object key under the configured prefix."""
        paginator = self.client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=self.bucket, Prefix=self.path)
        for page in pages:
            for obj in page.get("Contents", []):
                key = obj["Key"]
                if (
                    self.input_args.dataset.format in ("jsonl", "ms_swift")
                    and not key.lower().endswith(".jsonl")
                ):
                    continue
                yield key

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.uri,
            "config_name": self.config_name,
        }
