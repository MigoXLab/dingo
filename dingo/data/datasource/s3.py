from typing import Any, Dict, Generator, Optional

import boto3
import boto3.s3
from botocore.config import Config

from dingo.config import InputArgs
from dingo.data.datasource.base import DataSource


@DataSource.register()
class S3DataSource(DataSource):
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
        self.client = self._get_client(
            input_args.dataset.s3_config.s3_ak,
            input_args.dataset.s3_config.s3_sk,
            input_args.dataset.s3_config.s3_endpoint_url,
            input_args.dataset.s3_config.s3_addressing_style,
        )
        self.path = input_args.input_path
        self.bucket = input_args.dataset.s3_config.s3_bucket
        self.config_name = config_name
        super().__init__(input_args=input_args)

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
        if self.input_args.dataset.format in ["json", "listjson"]:
            raise RuntimeError("Format must in be 'jsonl' or 'plaintext'")
        return self._load()

    def _load(self) -> Generator[str, None, None]:
        if not self.path.endswith("/"):
            obj = self.client.get_object(
                Bucket=self.bucket, Key=self.path
            )
            obj_list = [obj]
        else:
            contents = self.client.list_objects(
                Bucket=self.bucket, Prefix=self.path
            )["Contents"]
            obj_list = [
                self.client.get_object(Bucket=self.bucket, Key=obj["Key"])
                for obj in contents
            ]
        for obj in obj_list:
            for line in obj["Body"].iter_lines():
                yield line.decode("utf-8")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "config_name": self.config_name,
        }
