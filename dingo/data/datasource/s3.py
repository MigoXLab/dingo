from typing import Any, Dict, Generator, Iterator, Optional
from urllib.parse import unquote, urlsplit

import boto3
import boto3.s3
from botocore.config import Config

from dingo.config import InputArgs
from dingo.data.datasource.base import DataSource


@DataSource.register()
class S3DataSource(DataSource):
    SUPPORTED_FORMATS = {"jsonl", "ms_swift", "plaintext"}

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

    def load(self, **kwargs) -> Generator[str, None, None]:
        """Load the local file dataset based on `LocalDataSource`.
        Args:
            kwargs: Additional keyword arguments used for loading the dataset.
        Returns:
            An instance of `Iterable`.
        """
        if self.input_args.dataset.format not in self.SUPPORTED_FORMATS:
            supported = ", ".join(sorted(self.SUPPORTED_FORMATS))
            raise RuntimeError(f"S3 format must be one of: {supported}")
        return self._load()

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
