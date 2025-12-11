import json
import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from dingo.config import InputArgs
from dingo.data.datasource.s3 import S3DataSource


class TestS3DataSource(unittest.TestCase):
    """S3DataSource 单元测试"""

    def setUp(self):
        """设置测试环境"""
        self.mock_s3_client = MagicMock()

        # 基础配置
        self.base_config = {
            "input_path": "test/data.jsonl",
            "dataset": {
                "source": "s3",
                "format": "jsonl",
                "field": {
                    "content": "content"
                },
                "s3_config": {
                    "s3_ak": "test_access_key",
                    "s3_sk": "test_secret_key",
                    "s3_endpoint_url": "https://s3.amazonaws.com",
                    "s3_bucket": "test-bucket",
                    "s3_addressing_style": "path"
                }
            }
        }

    def tearDown(self):
        """清理测试环境"""
        pass

    def test_init_with_valid_config(self):
        """测试使用有效配置初始化"""
        with patch('dingo.data.datasource.s3.boto3.client', return_value=self.mock_s3_client):
            input_args = InputArgs(**self.base_config)
            datasource = S3DataSource(input_args=input_args)

            self.assertEqual(datasource.path, "test/data.jsonl")
            self.assertEqual(datasource.bucket, "test-bucket")
            self.assertIsNotNone(datasource.client)

    def test_init_missing_credentials(self):
        """测试缺少 S3 凭证时抛出异常"""
        config = self.base_config.copy()
        config["dataset"]["s3_config"]["s3_ak"] = ""

        input_args = InputArgs(**config)

        with self.assertRaises(RuntimeError) as context:
            S3DataSource(input_args=input_args)

        self.assertIn("S3 param must be set", str(context.exception))

    def test_init_missing_endpoint(self):
        """测试缺少 endpoint 时抛出异常"""
        config = self.base_config.copy()
        config["dataset"]["s3_config"]["s3_endpoint_url"] = ""

        input_args = InputArgs(**config)

        with self.assertRaises(RuntimeError) as context:
            S3DataSource(input_args=input_args)

        self.assertIn("S3 param must be set", str(context.exception))

    def test_get_source_type(self):
        """测试获取数据源类型"""
        self.assertEqual(S3DataSource.get_source_type(), "s3")

    def test_load_single_file_jsonl(self):
        """测试加载单个 JSONL 文件"""
        # Mock S3 响应
        mock_body = MagicMock()
        test_data = [
            '{"content": "第一行数据"}',
            '{"content": "第二行数据"}',
            '{"content": "第三行数据"}'
        ]
        mock_body.iter_lines.return_value = [line.encode('utf-8') for line in test_data]

        mock_response = {"Body": mock_body}
        self.mock_s3_client.get_object.return_value = mock_response

        with patch('dingo.data.datasource.s3.boto3.client', return_value=self.mock_s3_client):
            input_args = InputArgs(**self.base_config)
            datasource = S3DataSource(input_args=input_args)

            # 加载数据
            result = list(datasource.load())

            # 验证结果
            self.assertEqual(len(result), 3)
            self.assertEqual(result[0], '{"content": "第一行数据"}')
            self.assertEqual(result[1], '{"content": "第二行数据"}')
            self.assertEqual(result[2], '{"content": "第三行数据"}')

            # 验证 S3 调用
            self.mock_s3_client.get_object.assert_called_once_with(
                Bucket="test-bucket",
                Key="test/data.jsonl"
            )

    def test_load_directory_multiple_files(self):
        """测试加载目录中的多个文件"""
        config = self.base_config.copy()
        config["input_path"] = "test/data/"  # 以 / 结尾表示目录

        # Mock list_objects 响应
        mock_list_response = {
            "Contents": [
                {"Key": "test/data/file1.jsonl"},
                {"Key": "test/data/file2.jsonl"}
            ]
        }
        self.mock_s3_client.list_objects.return_value = mock_list_response

        # Mock get_object 响应
        def mock_get_object(Bucket, Key):
            mock_body = MagicMock()
            if "file1" in Key:
                mock_body.iter_lines.return_value = [b'{"content": "file1 data"}']
            else:
                mock_body.iter_lines.return_value = [b'{"content": "file2 data"}']
            return {"Body": mock_body}

        self.mock_s3_client.get_object.side_effect = mock_get_object

        with patch('dingo.data.datasource.s3.boto3.client', return_value=self.mock_s3_client):
            input_args = InputArgs(**config)
            datasource = S3DataSource(input_args=input_args)

            # 加载数据
            result = list(datasource.load())

            # 验证结果
            self.assertEqual(len(result), 2)
            self.assertIn('{"content": "file1 data"}', result)
            self.assertIn('{"content": "file2 data"}', result)

            # 验证 S3 调用
            self.mock_s3_client.list_objects.assert_called_once_with(
                Bucket="test-bucket",
                Prefix="test/data/"
            )

    def test_load_empty_file(self):
        """测试加载空文件"""
        # Mock 空文件响应
        mock_body = MagicMock()
        mock_body.iter_lines.return_value = []
        mock_response = {"Body": mock_body}
        self.mock_s3_client.get_object.return_value = mock_response

        with patch('dingo.data.datasource.s3.boto3.client', return_value=self.mock_s3_client):
            input_args = InputArgs(**self.base_config)
            datasource = S3DataSource(input_args=input_args)

            result = list(datasource.load())
            self.assertEqual(len(result), 0)

    def test_load_plaintext_format(self):
        """测试加载 plaintext 格式"""
        config = self.base_config.copy()
        config["dataset"]["format"] = "plaintext"

        # Mock S3 响应
        mock_body = MagicMock()
        test_data = ["第一行文本", "第二行文本", "第三行文本"]
        mock_body.iter_lines.return_value = [line.encode('utf-8') for line in test_data]
        mock_response = {"Body": mock_body}
        self.mock_s3_client.get_object.return_value = mock_response

        with patch('dingo.data.datasource.s3.boto3.client', return_value=self.mock_s3_client):
            input_args = InputArgs(**config)
            datasource = S3DataSource(input_args=input_args)

            result = list(datasource.load())
            self.assertEqual(len(result), 3)
            self.assertEqual(result[0], "第一行文本")

    def test_load_unsupported_format_error(self):
        """测试加载不支持的格式时抛出异常"""
        config = self.base_config.copy()
        config["dataset"]["format"] = "json"  # 不支持的格式

        with patch('dingo.data.datasource.s3.boto3.client', return_value=self.mock_s3_client):
            input_args = InputArgs(**config)
            datasource = S3DataSource(input_args=input_args)

            with self.assertRaises(RuntimeError) as context:
                list(datasource.load())

            self.assertIn("Format must in be 'jsonl' or 'plaintext'", str(context.exception))

    def test_to_dict(self):
        """测试转换为字典"""
        with patch('dingo.data.datasource.s3.boto3.client', return_value=self.mock_s3_client):
            input_args = InputArgs(**self.base_config)
            datasource = S3DataSource(input_args=input_args, config_name="test_config")

            result = datasource.to_dict()

            self.assertEqual(result["path"], "test/data.jsonl")
            self.assertEqual(result["config_name"], "test_config")

    def test_different_addressing_styles(self):
        """测试不同的 S3 addressing styles"""
        for style in ["path", "virtual"]:
            config = self.base_config.copy()
            config["dataset"]["s3_config"]["s3_addressing_style"] = style

            with patch('dingo.data.datasource.s3.boto3.client') as mock_client:
                mock_client.return_value = self.mock_s3_client

                # 验证 boto3.client 使用了正确的配置
                call_args = mock_client.call_args
                self.assertEqual(
                    call_args[1]['config'].s3['addressing_style'],
                    style
                )

    def test_load_large_file(self):
        """测试加载大文件（多行数据）"""
        # Mock S3 响应 - 1000 行数据
        mock_body = MagicMock()
        test_data = [f'{{"content": "第{i}行数据"}}'.encode('utf-8') for i in range(1000)]
        mock_body.iter_lines.return_value = test_data
        mock_response = {"Body": mock_body}
        self.mock_s3_client.get_object.return_value = mock_response

        with patch('dingo.data.datasource.s3.boto3.client', return_value=self.mock_s3_client):
            input_args = InputArgs(**self.base_config)
            datasource = S3DataSource(input_args=input_args)

            result = list(datasource.load())
            self.assertEqual(len(result), 1000)
            self.assertIn("第0行", result[0])
            self.assertIn("第999行", result[999])


class TestS3DataSourceIntegration(unittest.TestCase):
    """S3DataSource 集成测试（需要真实的 S3 环境或 localstack）"""

    @unittest.skip("需要真实的 S3 环境，跳过集成测试")
    def test_real_s3_connection(self):
        """测试真实的 S3 连接（需要配置真实凭证）"""
        # 这个测试需要真实的 S3 凭证和环境
        # 可以使用 localstack 或 minio 进行本地测试
        pass

    @unittest.skip("需要真实的 S3 环境，跳过集成测试")
    def test_real_s3_data_loading(self):
        """测试真实的 S3 数据加载"""
        pass


if __name__ == "__main__":
    # 运行测试
    unittest.main(verbosity=2)
