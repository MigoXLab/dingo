"""
Unit tests for ATS Resume tools (LLMKeywordMatcher, LLMResumeOptimizer, and LLMScout).

These tests verify the core functionality without requiring actual LLM API calls.
"""

import json

import pytest

from dingo.io.input import Data
from dingo.model.llm.llm_keyword_matcher import SYNONYM_MAP, LLMKeywordMatcher
from dingo.model.llm.llm_resume_optimizer import LLMResumeOptimizer
from dingo.model.llm.llm_scout import SCORE_WEIGHTS, TIER_THRESHOLDS, LLMScout


def _has_error(result) -> bool:
    """Check if result indicates an error (compatible with both branches)."""
    # EvalDetail uses 'status', ModelRes uses 'error_status'
    if hasattr(result, 'error_status'):
        return result.error_status is True
    if hasattr(result, 'status'):
        return result.status is True
    return False


def _create_data_with_context(data_id: str, content: str, prompt: str, context: str):
    """Create Data object with context if supported, otherwise without."""
    try:
        return Data(data_id=data_id, content=content, prompt=prompt, context=context)
    except TypeError:
        # Main branch Data doesn't have context field
        return None


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

        assert _has_error(result)

    def test_eval_missing_prompt(self):
        """Test eval with missing prompt (JD)."""
        data = Data(data_id='test_4', content='Some resume', prompt='')
        result = LLMKeywordMatcher.eval(data)

        assert _has_error(result)


class TestLLMResumeOptimizer:
    """Tests for LLMResumeOptimizer."""

    def test_build_messages_general_mode(self):
        """Test general mode (no context) - skip if Data doesn't support context."""
        # On main branch, Data doesn't have context field, so we test differently
        data = Data(
            data_id='test_1',
            content='Python developer resume',
            prompt='Senior Python Developer'
        )
        # Set context via attribute if possible (for branches that support it)
        if not hasattr(data, 'context'):
            pytest.skip("Data class doesn't support context field (main branch)")

        messages = LLMResumeOptimizer.build_messages(data)

        assert len(messages) == 1
        assert messages[0]['role'] == 'user'
        # General mode should not have keyword injection instructions
        assert 'P1 - Force Inject' not in messages[0]['content']

    def test_build_messages_targeted_mode(self):
        """Test targeted mode (with context) - skip if Data doesn't support context."""
        context = json.dumps({
            'match_details': {
                'missing': [{'skill': 'Docker', 'importance': 'Required'}],
                'negative_warnings': []
            }
        })
        data = _create_data_with_context(
            data_id='test_2',
            content='Python developer resume',
            prompt='Senior Python Developer',
            context=context
        )
        if data is None:
            pytest.skip("Data class doesn't support context field (main branch)")

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

        assert _has_error(result)


class TestLLMScout:
    """Tests for LLMScout."""

    def test_build_messages_basic(self):
        """Test basic message building."""
        data = Data(
            data_id='test_1',
            content='行业报告：某科技公司ROE上升10%，计划扩招100人',
            prompt='我是23届CS硕士，会Python和PyTorch'
        )
        messages = LLMScout.build_messages(data)

        assert len(messages) == 1
        assert messages[0]['role'] == 'user'
        assert '行业报告' in messages[0]['content']
        assert 'CS硕士' in messages[0]['content']

    def test_build_messages_with_resume(self):
        """Test message building with resume context."""
        data = _create_data_with_context(
            data_id='test_2',
            content='行业报告：AI公司融资情况良好',
            prompt='应届生，想找AI方向',
            context='简历：熟悉Python、TensorFlow、PyTorch'
        )
        if data is None:
            pytest.skip("Data class doesn't support context field")

        messages = LLMScout.build_messages(data)

        assert len(messages) == 1
        assert '简历' in messages[0]['content'] or 'context' in str(messages[0])

    def test_score_weights(self):
        """Test score weights configuration."""
        assert 'skill_match' in SCORE_WEIGHTS
        assert 'risk_alignment' in SCORE_WEIGHTS
        assert 'financial_health' in SCORE_WEIGHTS
        # Weights should sum to 1.0
        total = sum(SCORE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_tier_thresholds(self):
        """Test tier threshold configuration."""
        assert 'tier1' in TIER_THRESHOLDS
        assert 'tier2' in TIER_THRESHOLDS
        assert TIER_THRESHOLDS['tier1'] > TIER_THRESHOLDS['tier2']

    def test_calculate_match_score(self):
        """Test match score calculation."""
        scoring_breakdown = {
            'skill_match': {'score': 0.8},
            'risk_alignment': {'score': 0.7},
            'career_stage_fit': {'score': 0.9},
            'location_match': {'score': 0.6},
            'financial_health': {'score': 0.8}
        }
        score, tier = LLMScout._calculate_match_score(scoring_breakdown)

        assert 0 <= score <= 1
        assert tier in ['Tier 1', 'Tier 2', 'Not Recommended']

    def test_calculate_match_score_high(self):
        """Test high match score results in Tier 1."""
        scoring_breakdown = {
            'skill_match': {'score': 0.9},
            'risk_alignment': {'score': 0.9},
            'career_stage_fit': {'score': 0.9},
            'location_match': {'score': 0.9},
            'financial_health': {'score': 0.9}
        }
        score, tier = LLMScout._calculate_match_score(scoring_breakdown)

        assert score >= 0.75
        assert tier == 'Tier 1'

    def test_calculate_match_score_low(self):
        """Test low match score results in Not Recommended."""
        scoring_breakdown = {
            'skill_match': {'score': 0.2},
            'risk_alignment': {'score': 0.3},
            'career_stage_fit': {'score': 0.2},
            'location_match': {'score': 0.1},
            'financial_health': {'score': 0.2}
        }
        score, tier = LLMScout._calculate_match_score(scoring_breakdown)

        assert score < 0.5
        assert tier == 'Not Recommended'

    def test_filter_by_confidence(self):
        """Test company filtering by confidence."""
        companies = [
            {
                'name': 'Good Company',
                'financial_status': 'expansion',
                'financial_evidence': {'confidence': 0.8, 'source_quotes': ['ROE上升']}
            },
            {
                'name': 'Low Confidence',
                'financial_status': 'stable',
                'financial_evidence': {'confidence': 0.3, 'source_quotes': []}
            },
            {
                'name': 'Contraction Company',
                'financial_status': 'contraction',
                'financial_evidence': {'confidence': 0.9, 'source_quotes': ['裁员']}
            }
        ]
        qualified, insufficient, not_recommended = LLMScout._filter_by_confidence(companies)

        assert len(qualified) == 1
        assert qualified[0]['name'] == 'Good Company'
        assert len(insufficient) == 1
        assert insufficient[0]['name'] == 'Low Confidence'
        assert len(not_recommended) == 1
        assert not_recommended[0]['name'] == 'Contraction Company'

    def test_generate_reason(self):
        """Test reason generation."""
        result_data = {
            'target_companies': [
                {'name': 'ABC公司', 'tier': 'Tier 1', 'match_score': 0.85}
            ],
            'insufficient_data': [],
            'not_recommended': [],
            'meta': {'analysis_confidence': 0.8}
        }
        reason = LLMScout._generate_reason(result_data)

        assert 'ABC公司' in reason
        assert 'Tier 1' in reason

    def test_eval_missing_content(self):
        """Test eval with missing content (industry report)."""
        data = Data(data_id='test_3', content='', prompt='用户画像')
        result = LLMScout.eval(data)

        assert _has_error(result)

    def test_eval_missing_prompt(self):
        """Test eval with missing prompt (user profile)."""
        data = Data(data_id='test_4', content='行业报告', prompt='')
        result = LLMScout.eval(data)

        assert _has_error(result)

    def test_clean_response(self):
        """Test response cleaning."""
        # Test markdown code block removal
        response = '```json\n{"test": "value"}\n```'
        cleaned = LLMScout._clean_response(response)
        assert cleaned == '{"test": "value"}'

        # Test think tag removal
        response = '<think>reasoning</think>{"test": "value"}'
        cleaned = LLMScout._clean_response(response)
        assert cleaned == '{"test": "value"}'

    def test_extract_think_content(self):
        """Test think content extraction."""
        response = '<think>This is my reasoning</think>{"result": "value"}'
        think = LLMScout._extract_think_content(response)
        assert think == 'This is my reasoning'

        # No think tag
        response = '{"result": "value"}'
        think = LLMScout._extract_think_content(response)
        assert think == ''


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
