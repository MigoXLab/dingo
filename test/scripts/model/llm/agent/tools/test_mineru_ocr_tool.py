"""
MinerUOCRTool 单元测试

测试 MinerU API OCR 工具的核心功能

运行方式：
pytest test/scripts/model/llm/agent/tools/test_mineru_ocr_tool.py -v
"""

import base64
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from dingo.model.llm.agent.tools.mineru_ocr_tool import MinerUOCRTool, MinerUOCRToolConfig


class TestMinerUOCRToolConfig:
    """测试 MinerUOCRToolConfig 配置类"""

    def test_default_values(self):
        """测试默认配置值"""
        config = MinerUOCRToolConfig()
        assert config.api_key is None
        assert config.api_url == "https://mineru.net/api/v4/extract/task"
        assert config.timeout == 120
        assert config.poll_interval == 3

    def test_custom_values(self):
        """测试自定义配置值"""
        config = MinerUOCRToolConfig(
            api_key="test_key_123",
            timeout=60,
            poll_interval=5
        )
        assert config.api_key == "test_key_123"
        assert config.timeout == 60
        assert config.poll_interval == 5


class TestMinerUOCRTool:
    """测试 MinerUOCRTool 核心功能"""

    def setup_method(self):
        """每个测试前的设置"""
        MinerUOCRTool.config = MinerUOCRToolConfig(
            api_key="test_api_key",
            timeout=120,
            poll_interval=3
        )

    def test_tool_attributes(self):
        """测试工具的基本属性"""
        assert MinerUOCRTool.name == "mineru_ocr_tool"
        assert "MinerU API" in MinerUOCRTool.description
        assert isinstance(MinerUOCRTool.config, MinerUOCRToolConfig)

    def test_execute_missing_api_key(self):
        """测试缺少 API key 的情况"""
        MinerUOCRTool.config.api_key = None

        result = MinerUOCRTool.execute(image_path="test.png")

        assert result['success'] is False
        assert 'API key not configured' in result['error']

    def test_execute_missing_image(self):
        """测试缺少图像输入的情况"""
        result = MinerUOCRTool.execute()

        assert result['success'] is False
        assert 'No image provided' in result['error']

    def test_execute_with_image_path(self):
        """测试使用图像路径的情况"""
        # 创建临时图像文件
        with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as f:
            f.write(b'fake_image_data')
            temp_path = f.name

        try:
            with patch.object(MinerUOCRTool, '_submit_and_wait') as mock_submit:
                mock_submit.return_value = {
                    'success': True,
                    'content': 'Extracted text',
                    'task_id': 'test_task_123'
                }

                result = MinerUOCRTool.execute(image_path=temp_path)

                assert result['success'] is True
                assert result['content'] == 'Extracted text'
                assert result['task_id'] == 'test_task_123'

                # 验证 _submit_and_wait 被调用
                assert mock_submit.called
                call_args = mock_submit.call_args[0]
                assert isinstance(call_args[0], str)  # Base64 string
        finally:
            import os
            os.unlink(temp_path)

    def test_execute_with_image_base64(self):
        """测试使用 Base64 图像数据的情况"""
        fake_base64 = base64.b64encode(b'fake_image_data').decode('utf-8')

        with patch.object(MinerUOCRTool, '_submit_and_wait') as mock_submit:
            mock_submit.return_value = {
                'success': True,
                'content': 'OCR result from base64',
                'task_id': 'test_task_456'
            }

            result = MinerUOCRTool.execute(image_base64=fake_base64)

            assert result['success'] is True
            assert result['content'] == 'OCR result from base64'
            assert mock_submit.called

    @patch('dingo.model.llm.agent.tools.mineru_ocr_tool.requests.post')
    def test_submit_and_wait_success(self, mock_post):
        """测试成功的任务提交"""
        # Mock submit response
        mock_submit_response = MagicMock()
        mock_submit_response.json.return_value = {
            "code": 0,
            "msg": "success",
            "data": {"task_id": "test_task_789"}
        }
        mock_post.return_value = mock_submit_response

        with patch.object(MinerUOCRTool, '_poll_result') as mock_poll:
            mock_poll.return_value = {
                'success': True,
                'content': 'Final OCR result',
                'task_id': 'test_task_789'
            }

            result = MinerUOCRTool._submit_and_wait("fake_base64", "text")

            assert result['success'] is True
            assert result['content'] == 'Final OCR result'

            # 验证 API 调用
            assert mock_post.called
            call_kwargs = mock_post.call_args[1]
            assert 'headers' in call_kwargs
            assert 'json' in call_kwargs
            assert 'Bearer test_api_key' in call_kwargs['headers']['Authorization']

    @patch('dingo.model.llm.agent.tools.mineru_ocr_tool.requests.post')
    def test_submit_and_wait_api_error(self, mock_post):
        """测试 API 返回错误的情况"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 400,
            "msg": "Invalid request",
            "data": None
        }
        mock_post.return_value = mock_response

        result = MinerUOCRTool._submit_and_wait("fake_base64", "text")

        assert result['success'] is False
        assert 'MinerU API error' in result['error']

    @patch('dingo.model.llm.agent.tools.mineru_ocr_tool.requests.get')
    def test_poll_result_immediate_success(self, mock_get):
        """测试立即成功的任务轮询"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "status": "success",
                "markdown": "# OCR Result\n\nExtracted content here."
            }
        }
        mock_get.return_value = mock_response

        headers = {"Authorization": "Bearer test_key"}
        result = MinerUOCRTool._poll_result("task_123", headers)

        assert result['success'] is True
        assert result['content'] == "# OCR Result\n\nExtracted content here."
        assert result['task_id'] == "task_123"

    def test_poll_result_task_failed(self):
        """测试任务失败的情况"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "status": "failed",
                "msg": "OCR processing failed"
            }
        }

        with patch('dingo.model.llm.agent.tools.mineru_ocr_tool.requests.get', return_value=mock_response):
            headers = {"Authorization": "Bearer test_key"}
            result = MinerUOCRTool._poll_result("task_789", headers)

            assert result['success'] is False
            assert 'task failed' in result['error'].lower()

    def test_extract_content_markdown(self):
        """测试从 markdown 字段提取内容"""
        data = {"markdown": "# Title\n\nContent here."}
        content = MinerUOCRTool._extract_content(data)
        assert content == "# Title\n\nContent here."

    def test_extract_content_text(self):
        """测试从 text 字段提取内容"""
        data = {"text": "Plain text content"}
        content = MinerUOCRTool._extract_content(data)
        assert content == "Plain text content"

    def test_extract_content_pages(self):
        """测试从多页结果提取内容"""
        data = {
            "pages": [
                {"markdown": "Page 1"},
                {"markdown": "Page 2"}
            ]
        }
        content = MinerUOCRTool._extract_content(data)
        assert "Page 1" in content
        assert "Page 2" in content

    def test_execute_exception_handling(self):
        """测试异常处理"""
        with patch.object(MinerUOCRTool, '_submit_and_wait') as mock_submit:
            mock_submit.side_effect = Exception("Unexpected error")

            result = MinerUOCRTool.execute(image_base64="fake_base64")

            assert result['success'] is False
            assert 'Unexpected error' in result['error']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
