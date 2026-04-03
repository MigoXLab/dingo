"""
LLMHtmlExtractCompareV3 核心测试

覆盖：
1. build_messages（中英全文、language 解析）
2. process_response（score→label、status、markdown 围栏、思考块剥离）
3. 非法 JSON → ConvertJsonError

pytest test/scripts/model/llm/test_llm_html_extract_compare_v3.py -v
"""

import json

import pytest

from dingo.io import Data
from dingo.model.llm.compare.llm_html_extract_compare_v3 import LLMHtmlExtractCompareV3
from dingo.utils.exception import ConvertJsonError


class TestBuildMessages:
    def test_chinese_includes_full_text_and_dimensions(self):
        data = Data(
            data_id="t1",
            prompt="工具A完整正文",
            content="工具B完整正文",
            raw_data={"language": "zh"},
        )
        messages = LLMHtmlExtractCompareV3.build_messages(data)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        body = messages[0]["content"]
        assert "工具A完整正文" in body
        assert "工具B完整正文" in body
        assert "Error_Content_Coverage" in body or "质量维度" in body

    def test_english_includes_full_text(self):
        data = Data(
            data_id="t2",
            prompt="Full text A from extraction 1",
            content="Full text B from extraction 2",
            raw_data={"language": "en"},
        )
        messages = LLMHtmlExtractCompareV3.build_messages(data)
        body = messages[0]["content"]
        assert "Full text A from extraction 1" in body
        assert "Full text B from extraction 2" in body
        assert "Error_Formula" in body or "Quality Dimensions" in body

    def test_default_language_english_when_unset(self):
        data = Data(
            data_id="t3",
            prompt="alpha",
            content="beta",
        )
        messages = LLMHtmlExtractCompareV3.build_messages(data)
        assert "Quality Dimensions" in messages[0]["content"]

    def test_language_from_top_level_field(self):
        data = Data(
            data_id="t4",
            prompt="中文A",
            content="中文B",
            language="zh",
        )
        messages = LLMHtmlExtractCompareV3.build_messages(data)
        assert "文本A" in messages[0]["content"]


class TestProcessResponse:
    def test_score_1_prompt_better(self):
        raw = json.dumps(
            {"score": 1, "name": "Error_Content_Coverage", "reason": "A 覆盖更全"},
            ensure_ascii=False,
        )
        result = LLMHtmlExtractCompareV3.process_response(raw)
        assert result.metric == "LLMHtmlExtractCompareV3"
        assert result.label == ["PROMPT_BETTER.Error_Content_Coverage"]
        assert result.status is False
        parsed = json.loads(result.reason[0])
        assert parsed["score"] == 1

    def test_score_2_content_better(self):
        raw = json.dumps(
            {"score": 2, "name": "Error_Formula", "reason": "B 公式更完整"},
            ensure_ascii=False,
        )
        result = LLMHtmlExtractCompareV3.process_response(raw)
        assert result.label == ["CONTENT_BETTER.Error_Formula"]
        assert result.status is True

    def test_score_0_extraction_equal(self):
        raw = json.dumps(
            {"score": 0, "name": "None", "reason": "质量相当"},
            ensure_ascii=False,
        )
        result = LLMHtmlExtractCompareV3.process_response(raw)
        assert result.label == ["EXTRACTION_EQUAL.None"]
        assert result.status is True

    def test_json_fenced_with_markdown(self):
        inner = '{"score": 1, "name": "None", "reason": "ok"}'
        wrapped = f"```json\n{inner}\n```"
        result = LLMHtmlExtractCompareV3.process_response(wrapped)
        assert "PROMPT_BETTER" in result.label[0]

    def test_redacted_thinking_appended_to_reason(self):
        # 与 llm_html_extract_compare 等实现一致：短标签 <think>...</think>
        body = (
            "<think>internal</think>\n"
            '{"score": 2, "name": "Error_Table", "reason": "Brief."}'
        )
        result = LLMHtmlExtractCompareV3.process_response(body)
        assert "CONTENT_BETTER.Error_Table" == result.label[0]
        parsed = json.loads(result.reason[0])
        assert "internal" in parsed["reason"]

    def test_invalid_json_raises(self):
        with pytest.raises(ConvertJsonError):
            LLMHtmlExtractCompareV3.process_response("not json")
