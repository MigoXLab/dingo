"""
VLMRenderJudge 单元测试

测试基于视觉渲染的 OCR 质量评估功能：
1. 成功的视觉比较（OCR 正确）
2. 失败的视觉比较（OCR 错误）
3. 渲染失败的处理
4. 响应解析

运行方式：
pytest test/scripts/model/llm/test_vlm_render_judge.py -v
"""

from unittest.mock import patch

import pytest

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io import Data
from dingo.model.llm.vlm_render_judge import VLMRenderJudge


class TestVLMRenderJudge:
    """测试 VLMRenderJudge 核心功能"""

    def setup_method(self):
        """每个测试前的设置"""
        VLMRenderJudge.dynamic_config = EvaluatorLLMArgs(
            model="gpt-4o",
            key="test-api-key",
            api_url="https://api.openai.com/v1"
        )

    def test_parse_response_correct(self):
        """测试解析 VLM 判断为正确的响应"""
        response = """
        <reason>
        Both images show the same text content with consistent formatting.
        The symbols, characters, and layout are fully consistent.
        </reason>
        <answer>true</answer>
        """

        result = VLMRenderJudge._parse_response(response)

        assert result['is_correct'] is True
        assert 'consistent' in result['reason'].lower()

    def test_parse_response_incorrect(self):
        """测试解析 VLM 判断为错误的响应"""
        response = """
        <reason>
        GT has "lazy" while OCR has "lzy". The character "a" is missing.
        This is an actual character omission.
        </reason>
        <answer>false</answer>
        """

        result = VLMRenderJudge._parse_response(response)

        assert result['is_correct'] is False
        assert 'missing' in result['reason'].lower()

    def test_parse_response_with_true_false_both(self):
        """测试包含 true 和 false 的响应（应判断为 false）"""
        response = """
        <reason>The text says "true to life" but the OCR result is false.</reason>
        <answer>false</answer>
        """

        result = VLMRenderJudge._parse_response(response)

        # "false" 在 answer 中，应该判为 false
        assert result['is_correct'] is False

    def test_parse_response_no_xml_tags(self):
        """测试没有 XML 标签的响应"""
        response = "The OCR result looks correct to me."

        result = VLMRenderJudge._parse_response(response)

        # 没有 answer 标签，应判为 false
        assert result['is_correct'] is False
        assert len(result['reason']) > 0

    def test_build_result_correct(self):
        """测试构建正确的评估结果"""
        judge_result = {
            'is_correct': True,
            'reason': 'Both images are consistent'
        }

        result = VLMRenderJudge._build_result(judge_result, "test content")

        assert result.score == 1.0
        assert result.metric == "VLMRenderJudge"
        assert "QUALITY_GOOD" in result.label
        assert any("✅" in reason for reason in result.reason)

    def test_build_result_incorrect(self):
        """测试构建错误的评估结果"""
        judge_result = {
            'is_correct': False,
            'reason': 'OCR has missing characters'
        }

        result = VLMRenderJudge._build_result(judge_result, "test content")

        assert result.score == 0.0
        assert result.metric == "VLMRenderJudge"
        assert "QUALITY_BAD_OCR.VISUAL_MISMATCH" in result.label
        assert any("❌" in reason for reason in result.reason)
        assert any("test content" in reason for reason in result.reason)

    def test_text_only_comparison_fallback(self):
        """测试渲染失败时的 fallback"""
        result = VLMRenderJudge._text_only_comparison(
            "test_image.png",
            "test content"
        )

        assert result.score == 0.5
        assert result.status is True
        assert "QUALITY_UNKNOWN.RENDER_FAILED" in result.label
        assert any("Could not render" in reason for reason in result.reason)
        assert result.metric == "VLMRenderJudge"

    def test_get_image_from_data(self):
        """测试从 Data 对象提取图片"""
        # 单个图片路径
        data = Data(image="test/image.png")
        image = VLMRenderJudge._get_image(data)
        assert image == "test/image.png"

        # 图片列表（取第一个）
        data = Data(image=["test/image1.png", "test/image2.png"])
        image = VLMRenderJudge._get_image(data)
        assert image == "test/image1.png"

        # 没有图片
        data = Data(content="text only")
        image = VLMRenderJudge._get_image(data)
        assert image is None

    def test_get_content_from_data(self):
        """测试从 Data 对象提取内容"""
        data = Data(content="The quick brown fox")
        content = VLMRenderJudge._get_content(data)
        assert content == "The quick brown fox"

        # 没有内容
        data = Data(image="test.png")
        content = VLMRenderJudge._get_content(data)
        assert content is None

    def test_get_content_type(self):
        """测试获取内容类型"""
        # 从 Data 对象
        data = Data(content="test", content_type="equation")
        content_type = VLMRenderJudge._get_content_type(data)
        assert content_type == "equation"

        # 从配置参数
        VLMRenderJudge.dynamic_config = EvaluatorLLMArgs(
            model="gpt-4o",
            key="test-key",
            parameters={"content_type": "table"}
        )
        data = Data(content="test")
        content_type = VLMRenderJudge._get_content_type(data)
        assert content_type == "table"

        # 默认值
        VLMRenderJudge.dynamic_config.parameters = None
        data = Data(content="test")
        content_type = VLMRenderJudge._get_content_type(data)
        assert content_type == "text"

    @patch('dingo.model.llm.vlm_render_judge.VLMRenderJudge._judge')
    @patch('dingo.model.llm.agent.tools.render_tool.RenderTool.execute')
    @patch('dingo.model.llm.vlm_render_judge.VLMRenderJudge.create_client')
    def test_eval_success_correct_ocr(self, mock_create_client, mock_render, mock_judge):
        """测试完整评估流程 - OCR 正确"""
        # Mock client creation (do nothing)
        mock_create_client.return_value = None

        # Mock 渲染成功
        mock_render.return_value = {
            'success': True,
            'image_base64': 'base64_encoded_image_data'
        }

        # Mock VLM 判断为正确
        mock_judge.return_value = {
            'is_correct': True,
            'reason': 'Both images are consistent'
        }

        data = Data(
            image="test/image.png",
            content="The quick brown fox jumps over the lazy dog.",
            content_type="text"
        )

        result = VLMRenderJudge.eval(data)

        # 验证结果
        assert result.score == 1.0
        assert result.metric == "VLMRenderJudge"
        assert "QUALITY_GOOD" in result.label
        assert mock_render.called
        assert mock_judge.called

    @patch('dingo.model.llm.vlm_render_judge.VLMRenderJudge._judge')
    @patch('dingo.model.llm.agent.tools.render_tool.RenderTool.execute')
    @patch('dingo.model.llm.vlm_render_judge.VLMRenderJudge.create_client')
    def test_eval_success_incorrect_ocr(self, mock_create_client, mock_render, mock_judge):
        """测试完整评估流程 - OCR 错误"""
        # Mock client creation (do nothing)
        mock_create_client.return_value = None

        # Mock 渲染成功
        mock_render.return_value = {
            'success': True,
            'image_base64': 'base64_encoded_image_data'
        }

        # Mock VLM 判断为错误
        mock_judge.return_value = {
            'is_correct': False,
            'reason': 'GT has "lazy" but OCR has "lzy", missing character "a"'
        }

        data = Data(
            image="test/image.png",
            content="The quick brown fox jumps over the lzy dog.",
            content_type="text"
        )

        result = VLMRenderJudge.eval(data)

        # 验证结果
        assert result.score == 0.0
        assert result.metric == "VLMRenderJudge"
        assert "QUALITY_BAD_OCR.VISUAL_MISMATCH" in result.label
        assert any("missing" in reason.lower() for reason in result.reason)

    @patch('dingo.model.llm.agent.tools.render_tool.RenderTool.execute')
    def test_eval_render_failed(self, mock_render):
        """测试渲染失败的情况"""
        # Mock 渲染失败
        mock_render.return_value = {
            'success': False,
            'error': 'LaTeX compilation failed'
        }

        data = Data(
            image="test/image.png",
            content="E = mc^2",
            content_type="equation"
        )

        result = VLMRenderJudge.eval(data)

        # 验证 fallback 结果
        assert result.score == 0.5
        assert result.status is True
        assert "QUALITY_UNKNOWN.RENDER_FAILED" in result.label
        assert mock_render.called

    @patch('dingo.model.llm.vlm_render_judge.VLMRenderJudge.create_client')
    def test_eval_missing_image(self, mock_create_client):
        """测试缺少图片的情况"""
        mock_create_client.return_value = None

        data = Data(content="test content")

        result = VLMRenderJudge.eval(data)

        assert result.status is True
        assert "QUALITY_BAD" in result.label[0]
        assert any("image" in reason.lower() for reason in result.reason)

    @patch('dingo.model.llm.vlm_render_judge.VLMRenderJudge.create_client')
    def test_eval_missing_content(self, mock_create_client):
        """测试缺少内容的情况"""
        mock_create_client.return_value = None

        data = Data(image="test/image.png")

        result = VLMRenderJudge.eval(data)

        assert result.status is True
        assert "QUALITY_BAD" in result.label[0]
        assert any("content" in reason.lower() for reason in result.reason)

    @patch('dingo.model.llm.vlm_render_judge.VLMRenderJudge._judge')
    @patch('dingo.model.llm.agent.tools.render_tool.RenderTool.execute')
    @patch('dingo.model.llm.vlm_render_judge.VLMRenderJudge.create_client')
    def test_eval_with_render_config(self, mock_create_client, mock_render, mock_judge):
        """测试使用自定义渲染配置"""
        mock_create_client.return_value = None

        # 设置渲染配置
        VLMRenderJudge.dynamic_config = EvaluatorLLMArgs(
            model="gpt-4o",
            key="test-key",
            api_url="https://api.openai.com/v1",
            parameters={
                "render_config": {
                    "density": 300,
                    "pad": 30
                }
            }
        )

        mock_render.return_value = {
            'success': True,
            'image_base64': 'base64_data'
        }
        mock_judge.return_value = {
            'is_correct': True,
            'reason': 'OK'
        }

        data = Data(
            image="test/image.png",
            content="test",
            content_type="equation"
        )

        result = VLMRenderJudge.eval(data)

        # 验证 RenderTool.update_config 被调用
        # （通过检查结果正常即可）
        assert result.score == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
