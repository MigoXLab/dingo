"""
LLMHtmlExtractCompareV2 核心测试

测试覆盖核心功能：
1. Diff 算法
2. 消息构建
3. 响应解析
4. 结果转换

运行方式：
pytest test/scripts/model/llm/test_llm_html_extract_compare_v2.py -v
"""

from unittest.mock import Mock, patch

import pytest

from dingo.io import Data
from dingo.model.llm.llm_html_extract_compare_v2 import LLMHtmlExtractCompareV2
from dingo.model.response.response_class import ResponseNameReason


class TestExtractTextDiff:
    """测试 diff 算法核心功能"""

    def test_basic_diff(self):
        """测试基本差异提取"""
        text_a = "Hello World"
        text_b = "Hello Python World"

        result = LLMHtmlExtractCompareV2.extract_text_diff(text_a, text_b)

        assert "unique_a" in result
        assert "unique_b" in result
        assert "common" in result

    def test_chinese_diff(self):
        """测试中文文本"""
        text_a = "机器学习是人工智能的分支"
        text_b = "机器学习是人工智能的重要分支"

        result = LLMHtmlExtractCompareV2.extract_text_diff(text_a, text_b)

        assert "重要" in result["unique_b"]
        assert len(result["common"]) > 0


class TestBuildMessages:
    """测试消息构建"""

    def test_chinese_message(self):
        """测试中文消息"""
        data = Data(
            data_id="test_001",
            prompt="工具A的内容",
            content="工具B的内容",
            raw_data={"language": "zh"}
        )

        messages = LLMHtmlExtractCompareV2.build_messages(data)

        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert "核心信息内容" in messages[0]["content"]

    def test_english_message(self):
        """测试英文消息"""
        data = Data(
            data_id="test_002",
            prompt="Tool A content",
            content="Tool B content",
            raw_data={"language": "en"}
        )

        messages = LLMHtmlExtractCompareV2.build_messages(data)

        assert len(messages) == 1
        assert "core informational content" in messages[0]["content"]


class TestParseResponse:
    """测试响应解析"""

    def test_parse_judgement_a(self):
        """测试判断A"""
        response = "思考过程...\n<Judgement>A</Judgement>"

        result = LLMHtmlExtractCompareV2._parse_response_to_structured(response)

        assert result.name == "A"
        assert "思考过程" in result.reason

    def test_parse_judgement_b(self):
        """测试判断B"""
        response = "<Judgement>B</Judgement>"

        result = LLMHtmlExtractCompareV2._parse_response_to_structured(response)

        assert result.name == "B"

    def test_parse_judgement_c(self):
        """测试判断C"""
        response = "<Judgement>C</Judgement>"

        result = LLMHtmlExtractCompareV2._parse_response_to_structured(response)

        assert result.name == "C"

    def test_parse_chinese_format(self):
        """测试中文格式"""
        response = "判断：A"

        result = LLMHtmlExtractCompareV2._parse_response_to_structured(response)

        assert result.name == "A"


class TestConvertResult:
    """测试结果转换"""

    def test_convert_a_to_tool_one_better(self):
        """A -> TOOL_ONE_BETTER"""
        structured = ResponseNameReason(name="A", reason="工具A更完整")
        result = LLMHtmlExtractCompareV2._convert_to_model_result(structured)

        assert result.type == "TOOL_ONE_BETTER"
        assert result.error_status is False

    def test_convert_b_to_equal(self):
        """B -> TOOL_EQUAL"""
        structured = ResponseNameReason(name="B", reason="两者相同")
        result = LLMHtmlExtractCompareV2._convert_to_model_result(structured)

        assert result.type == "TOOL_EQUAL"
        assert result.error_status is False

    def test_convert_c_to_tool_two_better(self):
        """C -> TOOL_TWO_BETTER"""
        structured = ResponseNameReason(name="C", reason="工具B更完整")
        result = LLMHtmlExtractCompareV2._convert_to_model_result(structured)

        assert result.type == "TOOL_TWO_BETTER"
        assert result.error_status is True


class TestCompleteFlow:
    """测试完整流程"""

    def test_process_response_a(self):
        """测试完整流程A"""
        response = "分析...\n<Judgement>A</Judgement>"
        result = LLMHtmlExtractCompareV2.process_response(response)

        assert result.type == "TOOL_ONE_BETTER"
        assert result.error_status is False

    def test_process_response_b(self):
        """测试完整流程B"""
        response = "判断：B"
        result = LLMHtmlExtractCompareV2.process_response(response)

        assert result.type == "TOOL_EQUAL"
        assert result.error_status is False

    def test_process_response_c(self):
        """测试完整流程C"""
        response = "<Judgement>C</Judgement>"
        result = LLMHtmlExtractCompareV2.process_response(response)

        assert result.type == "TOOL_TWO_BETTER"
        assert result.error_status is True
