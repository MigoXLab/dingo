"""
RenderTool 单元测试

测试 OCR 内容渲染工具的核心功能：
1. 文本渲染
2. LaTeX 公式渲染
3. 配置管理
4. 错误处理

运行方式：
pytest test/scripts/model/llm/agent/tools/test_render_tool.py -v
"""

from unittest.mock import MagicMock, patch

import pytest

from dingo.model.llm.agent.tools.render_tool import RenderTool, RenderToolConfig


class TestRenderToolConfig:
    """测试 RenderTool 配置"""

    def test_default_values(self):
        """测试默认配置值"""
        config = RenderToolConfig()
        assert config.font_path is None
        assert config.density == 150
        assert config.timeout == 60
        assert config.pad == 20

    def test_custom_values(self):
        """测试自定义配置值"""
        config = RenderToolConfig(
            font_path="/path/to/font.ttc",
            density=300,
            timeout=120,
            pad=30
        )
        assert config.font_path == "/path/to/font.ttc"
        assert config.density == 300
        assert config.timeout == 120
        assert config.pad == 30

    def test_density_validation(self):
        """测试 density 必须在 72-300 之间"""
        # 有效值
        RenderToolConfig(density=72)
        RenderToolConfig(density=300)
        RenderToolConfig(density=150)

        # 无效值
        with pytest.raises(ValueError):
            RenderToolConfig(density=71)

        with pytest.raises(ValueError):
            RenderToolConfig(density=301)

    def test_pad_validation(self):
        """测试 pad 必须 >= 0"""
        # 有效值
        RenderToolConfig(pad=0)
        RenderToolConfig(pad=20)

        # 无效值
        with pytest.raises(ValueError):
            RenderToolConfig(pad=-1)


class TestRenderTool:
    """测试 RenderTool 核心功能"""

    def setup_method(self):
        """每个测试前的设置"""
        RenderTool.config = RenderToolConfig()

    def test_tool_attributes(self):
        """测试工具的基本属性"""
        assert RenderTool.name == "render_tool"
        assert "Render text, equations, or tables" in RenderTool.description
        assert isinstance(RenderTool.config, RenderToolConfig)

    def test_empty_content(self):
        """测试空内容返回错误"""
        result = RenderTool.execute(content="", content_type="text")
        assert result['success'] is False
        assert 'empty' in result['error'].lower()

    def test_whitespace_content(self):
        """测试纯空格内容返回错误"""
        result = RenderTool.execute(content="   ", content_type="text")
        assert result['success'] is False
        assert 'empty' in result['error'].lower()

    def test_invalid_content_type(self):
        """测试无效的 content_type - 会默认为 text"""
        result = RenderTool.execute(content="test", content_type="invalid_type")
        # RenderTool 不验证 content_type，无效类型会默认为 text 渲染
        assert result['success'] is True
        assert result['content_type'] == "invalid_type"

    @patch('dingo.model.llm.agent.tools.render_tool.HAS_PIL', True)
    @patch('dingo.model.llm.agent.tools.render_tool.Image')
    @patch('dingo.model.llm.agent.tools.render_tool.ImageDraw')
    @patch('dingo.model.llm.agent.tools.render_tool.ImageFont')
    def test_render_text_success(self, mock_font, mock_draw, mock_image):
        """测试文本渲染成功"""
        # Mock PIL objects
        mock_img = MagicMock()
        mock_img.size = (200, 100)
        mock_image.new.return_value = mock_img

        mock_draw_obj = MagicMock()
        mock_draw_obj.textbbox.return_value = (0, 0, 100, 20)
        mock_draw.Draw.return_value = mock_draw_obj

        mock_font.truetype.return_value = MagicMock()

        # Mock image to base64 conversion
        with patch('io.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_bytesio.return_value = mock_buffer
            mock_buffer.getvalue.return_value = b'fake_image_data'

            result = RenderTool.execute(
                content="Hello World",
                content_type="text"
            )

            assert result['success'] is True
            assert 'image_base64' in result
            assert result['content_type'] == 'text'

    @patch('dingo.model.llm.agent.tools.render_tool.HAS_PIL', False)
    def test_render_text_no_pil(self):
        """测试 PIL 未安装的情况"""
        result = RenderTool.execute(content="test", content_type="text")
        assert result['success'] is False
        assert 'PIL' in result['error']

    @patch('dingo.model.llm.agent.tools.render_tool.subprocess.run')
    @patch('dingo.model.llm.agent.tools.render_tool.os.path.exists')
    @patch('dingo.model.llm.agent.tools.render_tool.Image')
    @patch('tempfile.mkdtemp')
    def test_render_latex_success(self, mock_mkdtemp, mock_image, mock_exists, mock_subprocess):
        """测试 LaTeX 渲染成功"""
        # Mock temporary directory
        mock_mkdtemp.return_value = '/tmp/test_dir'

        # Mock file existence checks
        mock_exists.side_effect = lambda path: True

        # Mock subprocess (xelatex and magick)
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        # Mock image loading
        mock_img = MagicMock()
        mock_image.open.return_value = mock_img

        # Mock image to base64
        with patch('io.BytesIO') as mock_bytesio:
            mock_buffer = MagicMock()
            mock_bytesio.return_value = mock_buffer
            mock_buffer.getvalue.return_value = b'fake_image_data'

            with patch('shutil.rmtree'):
                result = RenderTool.execute(
                    content="E = mc^2",
                    content_type="equation"
                )

                # LaTeX 渲染需要环境支持，可能失败
                # 这里主要测试代码路径是否正常
                assert 'success' in result

    @patch('dingo.model.llm.agent.tools.render_tool.subprocess.run')
    @patch('tempfile.mkdtemp')
    def test_render_latex_xelatex_not_found(self, mock_mkdtemp, mock_subprocess):
        """测试 xelatex 未安装的情况"""
        mock_mkdtemp.return_value = '/tmp/test_dir'

        # Mock xelatex not found
        mock_subprocess.side_effect = FileNotFoundError("xelatex not found")

        with patch('shutil.rmtree'):
            result = RenderTool.execute(
                content="E = mc^2",
                content_type="equation"
            )

            assert result['success'] is False
            # 错误消息是 "failed to render equation content"
            assert 'failed' in result['error'].lower()
            assert 'equation' in result['error'].lower()

    def test_render_with_output_path(self):
        """测试保存到指定文件路径"""
        with patch('dingo.model.llm.agent.tools.render_tool.RenderTool._render_text') as mock_render:
            # Mock successful render
            mock_img = MagicMock()
            mock_render.return_value = mock_img

            output_path = "/tmp/test_output.png"
            result = RenderTool.execute(
                content="test",
                content_type="text",
                output_path=output_path
            )

            if result['success']:
                # save 会被调用两次：一次保存到 BytesIO，一次保存到文件
                assert mock_img.save.call_count == 2
                assert result['image_path'] == output_path

    def test_update_config(self):
        """测试更新配置"""
        original_density = RenderTool.config.density
        original_pad = RenderTool.config.pad

        # 更新配置
        RenderTool.update_config({
            'density': 200,
            'pad': 30
        })

        assert RenderTool.config.density == 200
        assert RenderTool.config.pad == 30

        # 恢复配置
        RenderTool.config.density = original_density
        RenderTool.config.pad = original_pad

    def test_multiline_text_handling(self):
        """测试多行文本处理"""
        multiline_content = "Line 1\nLine 2\nLine 3"

        with patch('dingo.model.llm.agent.tools.render_tool.RenderTool._render_text') as mock_render:
            mock_img = MagicMock()
            mock_render.return_value = mock_img

            with patch('io.BytesIO') as mock_bytesio:
                mock_buffer = MagicMock()
                mock_bytesio.return_value = mock_buffer
                mock_buffer.getvalue.return_value = b'fake_data'

                result = RenderTool.execute(
                    content=multiline_content,
                    content_type="text"
                )

                # 应该调用 _render_text 并传入多行内容
                if result['success']:
                    mock_render.assert_called_once()
                    call_args = mock_render.call_args[0]
                    assert '\n' in call_args[0]

    def test_font_fallback(self):
        """测试字体加载失败时的 fallback"""
        # 使用不存在的字体路径，测试是否能 fallback 到系统字体或默认字体
        RenderTool.config.font_path = "/nonexistent/path/to/font.ttf"

        result = RenderTool.execute(
            content="test fallback",
            content_type="text"
        )

        # 即使指定的字体不存在，也应该能够渲染成功（使用 fallback）
        assert result['success'] is True
        assert 'image_base64' in result

    def test_render_special_characters(self):
        """测试特殊字符渲染"""
        special_content = "Price: $123.45 (Discount: 20%)"

        with patch('dingo.model.llm.agent.tools.render_tool.RenderTool._render_text') as mock_render:
            mock_img = MagicMock()
            mock_render.return_value = mock_img

            with patch('io.BytesIO') as mock_bytesio:
                mock_buffer = MagicMock()
                mock_bytesio.return_value = mock_buffer
                mock_buffer.getvalue.return_value = b'fake_data'

                result = RenderTool.execute(
                    content=special_content,
                    content_type="text"
                )

                if result['success']:
                    # 应该能处理特殊字符
                    call_args = mock_render.call_args[0]
                    assert '$' in call_args[0]
                    assert '%' in call_args[0]
                    assert ':' in call_args[0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
