"""
Unit tests for ATS Resume tools (LLMKeywordMatcher and LLMResumeOptimizer).

These tests verify the core functionality without requiring actual LLM API calls.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from dingo.io.input import Data
from dingo.model.llm.llm_keyword_matcher import LLMKeywordMatcher, SYNONYM_MAP
from dingo.model.llm.llm_resume_optimizer import LLMResumeOptimizer


class TestLLMKeywordMatcher:
    """Tests for LLMKeywordMatcher."""

    def test_build_messages_basic(self):
        """Test basic message building."""
        data = Data(
            data_id='test_1',
            content='Python developer with 5 years experience',
            prompt='Senior Python Developer required'
        )
        messages = LLMKeywordMatcher.build_messages(data)

        assert len(messages) == 1
        assert messages[0]['role'] == 'user'
        assert 'Python developer' in messages[0]['content']
        assert 'Senior Python Developer' in messages[0]['content']

    def test_build_messages_chinese(self):
        """Test Chinese content detection - uses English prompt for JD analysis."""
        data = Data(
            data_id='test_2',
            content='我是一名Python开发工程师，有5年工作经验',
            prompt='高级Python开发工程师'
        )
        messages = LLMKeywordMatcher.build_messages(data)

        assert len(messages) == 1
        # KeywordMatcher always uses English prompt (JD analysis is language-agnostic)
        assert 'ATS' in messages[0]['content']
        assert '高级Python开发工程师' in messages[0]['content']

    def test_synonym_map(self):
        """Test synonym normalization map exists."""
        assert 'k8s' in SYNONYM_MAP
        assert SYNONYM_MAP['k8s'] == 'Kubernetes'
        assert 'js' in SYNONYM_MAP
        assert SYNONYM_MAP['js'] == 'JavaScript'

    def test_calculate_match_score(self):
        """Test match score calculation."""
        keyword_analysis = [
            {'keyword': 'Python', 'importance': 'required', 'match_status': 'matched'},
            {'keyword': 'Docker', 'importance': 'required', 'match_status': 'missing'},
            {'keyword': 'AWS', 'importance': 'nice-to-have', 'match_status': 'matched'},
        ]
        score = LLMKeywordMatcher._calculate_match_score(keyword_analysis)

        # Score should be between 0 and 1
        assert 0 <= score <= 1
        # With 1/2 required matched and 1/1 nice-to-have matched
        # Actual calculation may vary based on weights, just verify it's reasonable
        assert 0.5 <= score <= 0.75

    def test_eval_missing_content(self):
        """Test eval with missing content."""
        data = Data(data_id='test_3', content='', prompt='Some JD')
        result = LLMKeywordMatcher.eval(data)

        assert result.error_status is True or getattr(result, 'status', False) is True

    def test_eval_missing_prompt(self):
        """Test eval with missing prompt (JD)."""
        data = Data(data_id='test_4', content='Some resume', prompt='')
        result = LLMKeywordMatcher.eval(data)

        assert result.error_status is True or getattr(result, 'status', False) is True


class TestLLMResumeOptimizer:
    """Tests for LLMResumeOptimizer."""

    def test_build_messages_general_mode(self):
        """Test general mode (no context)."""
        data = Data(
            data_id='test_1',
            content='Python developer resume',
            prompt='Senior Python Developer'
        )
        messages = LLMResumeOptimizer.build_messages(data)

        assert len(messages) == 1
        assert messages[0]['role'] == 'user'
        # General mode should not have keyword injection instructions
        assert 'P1 - Force Inject' not in messages[0]['content']

    def test_build_messages_targeted_mode(self):
        """Test targeted mode (with context)."""
        context = json.dumps({
            'match_details': {
                'missing': [{'skill': 'Docker', 'importance': 'Required'}],
                'negative_warnings': []
            }
        })
        data = Data(
            data_id='test_2',
            content='Python developer resume',
            prompt='Senior Python Developer',
            context=context
        )
        messages = LLMResumeOptimizer.build_messages(data)

        assert len(messages) == 1
        # Targeted mode should include Docker in the prompt
        assert 'Docker' in messages[0]['content']

    def test_detect_chinese(self):
        """Test Chinese language detection."""
        assert LLMResumeOptimizer._detect_chinese('我是一名开发者') is True
        assert LLMResumeOptimizer._detect_chinese('I am a developer') is False
        assert LLMResumeOptimizer._detect_chinese('') is False

    def test_parse_match_report_plugin_format(self):
        """Test parsing Plugin format match report."""
        report = {
            'match_details': {
                'missing': [
                    {'skill': 'Docker', 'importance': 'Required'},
                    {'skill': 'AWS', 'importance': 'Nice-to-have'}
                ],
                'negative_warnings': [{'skill': 'PHP'}]
            }
        }
        missing_req, missing_nice, negative, is_targeted = \
            LLMResumeOptimizer._parse_match_report(report)

        assert 'Docker' in missing_req
        assert 'AWS' in missing_nice
        assert 'PHP' in negative
        assert is_targeted is True

    def test_parse_match_report_list_format(self):
        """Test parsing list format match report."""
        report = ['Python', 'Docker', 'Kubernetes']
        missing_req, missing_nice, negative, is_targeted = \
            LLMResumeOptimizer._parse_match_report(report)

        assert missing_req == ['Python', 'Docker', 'Kubernetes']
        assert is_targeted is True

    def test_parse_match_report_empty(self):
        """Test parsing empty match report."""
        missing_req, missing_nice, negative, is_targeted = \
            LLMResumeOptimizer._parse_match_report('')

        assert missing_req == []
        assert is_targeted is False

    def test_eval_missing_content(self):
        """Test eval with missing content."""
        data = Data(data_id='test_3', content='', prompt='Some position')
        result = LLMResumeOptimizer.eval(data)

        assert result.error_status is True or getattr(result, 'status', False) is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

