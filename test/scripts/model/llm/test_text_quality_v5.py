"""
测试 LLMTextQualityV5 优化后的 prompt 效果
"""
import json

import pytest

from dingo.model.llm.text_quality.llm_text_quality_v5 import LLMTextQualityV5


class TestLLMTextQualityV5:
    """测试 V5 版本的文本质量评估"""

    def test_good_quality_text_response(self):
        """测试解析 Good 质量文本的响应"""
        response = json.dumps({
            "score": 1,
            "type": "Good",
            "name": "None",
            "reason": "Clear, well-formatted text with proper LaTeX"
        })

        result = LLMTextQualityV5.process_response(response)

        assert result.status is False
        assert result.label == ["QUALITY_GOOD"]
        assert result.reason == ["Clear, well-formatted text with proper LaTeX"]
        assert result.metric == "LLMTextQualityV5"

    def test_completeness_error_response(self):
        """测试解析 Completeness 错误的响应"""
        response = json.dumps({
            "score": 0,
            "type": "Completeness",
            "name": "Error_Formula",
            "reason": "Inconsistent delimiters: mixed $$ and $ without proper closure"
        })

        result = LLMTextQualityV5.process_response(response)

        assert result.status is True
        assert result.label == ["Completeness.Error_Formula"]
        assert "Inconsistent delimiters" in result.reason[0]
        assert result.metric == "LLMTextQualityV5"

    def test_effectiveness_error_response(self):
        """测试解析 Effectiveness 错误的响应"""
        response = json.dumps({
            "score": 0,
            "type": "Effectiveness",
            "name": "Error_Garbled_Characters",
            "reason": "Contains encoding corruption (�, □) and missing spaces (>1% of text)"
        })

        result = LLMTextQualityV5.process_response(response)

        assert result.status is True
        assert result.label == ["Effectiveness.Error_Garbled_Characters"]
        assert "encoding corruption" in result.reason[0]

    def test_similarity_error_response(self):
        """测试解析 Similarity 错误的响应"""
        response = json.dumps({
            "score": 0,
            "type": "Similarity",
            "name": "Error_Duplicate",
            "reason": "Same sentence repeats 6 times, indicating low content diversity"
        })

        result = LLMTextQualityV5.process_response(response)

        assert result.status is True
        assert result.label == ["Similarity.Error_Duplicate"]
        assert "repeats 6 times" in result.reason[0]

    def test_security_error_response(self):
        """测试解析 Security 错误的响应"""
        response = json.dumps({
            "score": 0,
            "type": "Security",
            "name": "Error_Prohibition",
            "reason": "Contains prohibited content"
        })

        result = LLMTextQualityV5.process_response(response)

        assert result.status is True
        assert result.label == ["Security.Error_Prohibition"]

    def test_markdown_code_block_cleanup(self):
        """测试 markdown 代码块清理"""
        response_with_markdown = '```json\n{"score": 1, "type": "Good", "name": "None", "reason": "Test"}\n```'

        result = LLMTextQualityV5.process_response(response_with_markdown)

        assert result.status is False
        assert result.label == ["QUALITY_GOOD"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
