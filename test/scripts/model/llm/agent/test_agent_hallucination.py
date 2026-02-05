"""
Integration tests for AgentHallucination evaluator
"""

import json
from unittest.mock import patch

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model.llm.agent.agent_hallucination import AgentHallucination


class TestAgentHallucination:
    """Test AgentHallucination evaluator"""

    def setup_method(self):
        """Setup for each test"""
        AgentHallucination.dynamic_config = EvaluatorLLMArgs(
            key="test_key",
            api_url="https://api.test.com",
            model="gpt-4.1-mini-2025-04-14"
        )

    def test_agent_registration(self):
        """Test that AgentHallucination is properly registered"""
        from dingo.model import Model
        Model.load_model()
        assert "AgentHallucination" in Model.llm_name_map
        assert Model.llm_name_map["AgentHallucination"] == AgentHallucination

    def test_has_context_with_direct_attribute(self):
        """Test context detection with direct context attribute"""
        data = Data(content="test", context=["context1"])
        assert AgentHallucination._has_context(data) is True

    def test_has_context_with_raw_data(self):
        """Test context detection with raw_data fallback"""
        data = Data(content="test", raw_data={"context": ["context1"]})
        assert AgentHallucination._has_context(data) is True

    def test_has_context_without_context(self):
        """Test context detection when no context present"""
        data = Data(content="test")
        assert AgentHallucination._has_context(data) is False

    def test_has_context_with_empty_context(self):
        """Test context detection with empty context"""
        data = Data(content="test", context=[])
        assert AgentHallucination._has_context(data) is False

    @patch('dingo.model.llm.llm_hallucination.LLMHallucination')
    def test_eval_with_context_delegates(self, mock_llm_hal):
        """Test that evaluation with context delegates to LLMHallucination"""
        # Mock LLMHallucination.eval
        mock_result = EvalDetail(metric="LLMHallucination")
        mock_result.status = False
        mock_result.reason = ["Test reason"]
        mock_llm_hal.eval.return_value = mock_result

        # Create data with context
        data = Data(
            content="Paris is the capital of France",
            context=["Paris is the capital of France"]
        )

        # Evaluate
        result = AgentHallucination.eval(data)

        # Verify delegation occurred
        mock_llm_hal.eval.assert_called_once()
        assert result.status is False
        assert any("LLMHallucination" in r for r in result.reason)

    def test_eval_without_context_no_claims(self):
        """Test evaluation when no factual claims are found"""
        with patch.object(AgentHallucination, '_extract_claims', return_value=[]):
            data = Data(content="Hello, how are you?")

            result = AgentHallucination.eval(data)

            assert result.status is False  # No issues
            assert any("No factual claims" in r for r in result.reason)

    @patch.object(AgentHallucination, 'create_client')
    @patch.object(AgentHallucination, 'send_messages')
    @patch.object(AgentHallucination, 'execute_tool')
    @patch('dingo.model.llm.llm_hallucination.LLMHallucination')
    def test_eval_without_context_with_web_search(self, mock_llm_hal, mock_exec_tool, mock_send, mock_create_client):
        """Test complete workflow without context using web search"""
        # Mock claim extraction
        mock_send.return_value = '{"claims": ["Paris is the capital of France"]}'

        # Mock web search
        mock_exec_tool.return_value = {
            'success': True,
            'answer': 'Paris is the capital of France',
            'results': [{
                'title': 'Paris',
                'url': 'https://example.com',
                'content': 'Paris is the capital of France',
                'score': 0.95
            }]
        }

        # Mock final evaluation
        mock_result = EvalDetail(metric="LLMHallucination")
        mock_result.status = False
        mock_result.reason = ["No hallucination detected"]
        mock_llm_hal.eval.return_value = mock_result

        # Create data without context
        data = Data(content="Paris is the capital of France")

        # Evaluate
        result = AgentHallucination.eval(data)

        # Verify workflow
        assert mock_send.called  # Claim extraction
        assert mock_exec_tool.called  # Web search
        assert mock_llm_hal.eval.called  # Final evaluation
        assert result.status is False
        assert any("Agent-Based Evaluation" in r for r in result.reason)

    def test_extract_claims_valid_json(self):
        """Test claim extraction with valid JSON response"""
        with patch.object(AgentHallucination, 'send_messages') as mock_send:
            mock_send.return_value = '{"claims": ["Claim 1", "Claim 2", "Claim 3"]}'

            data = Data(content="Test content")
            claims = AgentHallucination._extract_claims(data)

            assert len(claims) == 3
            assert claims[0] == "Claim 1"

    def test_extract_claims_with_markdown(self):
        """Test claim extraction with markdown code blocks"""
        with patch.object(AgentHallucination, 'send_messages') as mock_send:
            mock_send.return_value = '```json\n{"claims": ["Claim 1"]}\n```'

            data = Data(content="Test content")
            claims = AgentHallucination._extract_claims(data)

            assert len(claims) == 1
            assert claims[0] == "Claim 1"

    def test_extract_claims_invalid_json(self):
        """Test claim extraction with invalid JSON"""
        with patch.object(AgentHallucination, 'send_messages') as mock_send:
            mock_send.return_value = 'Not valid JSON'

            data = Data(content="Test content")
            claims = AgentHallucination._extract_claims(data)

            assert claims == []

    def test_extract_claims_limits_to_five(self):
        """Test that claim extraction limits to 5 claims"""
        with patch.object(AgentHallucination, 'send_messages') as mock_send:
            many_claims = [f"Claim {i}" for i in range(10)]
            mock_send.return_value = f'{{"claims": {json.dumps(many_claims)}}}'

            data = Data(content="Test content")
            claims = AgentHallucination._extract_claims(data)

            assert len(claims) == 5

    def test_search_claims_success(self):
        """Test searching claims successfully"""
        with patch.object(AgentHallucination, 'execute_tool') as mock_exec:
            mock_exec.return_value = {
                'success': True,
                'results': [{'content': 'Result content'}]
            }

            claims = ["Claim 1", "Claim 2"]
            results = AgentHallucination._search_claims(claims)

            assert len(results) == 2
            assert all(r['success'] for r in results)
            assert mock_exec.call_count == 2

    def test_search_claims_with_errors(self):
        """Test searching claims with some failures"""
        def mock_execute(tool, **kwargs):
            if kwargs['query'] == "Claim 1":
                return {'success': True, 'results': []}
            else:
                raise Exception("Search failed")

        with patch.object(AgentHallucination, 'execute_tool', side_effect=mock_execute):
            claims = ["Claim 1", "Claim 2"]
            results = AgentHallucination._search_claims(claims)

            assert len(results) == 2
            assert results[0]['success'] is True
            assert results[1]['success'] is False

    def test_synthesize_context_with_answers(self):
        """Test context synthesis with AI-generated answers"""
        search_results = [
            {
                'success': True,
                'answer': 'Answer 1',
                'results': [
                    {'content': 'Content 1', 'url': 'https://example.com/1'}
                ]
            },
            {
                'success': True,
                'answer': 'Answer 2',
                'results': [
                    {'content': 'Content 2', 'url': 'https://example.com/2'}
                ]
            }
        ]

        contexts = AgentHallucination._synthesize_context(search_results)

        assert len(contexts) > 0
        assert any('Answer 1' in c for c in contexts)
        assert any('Answer 2' in c for c in contexts)

    def test_synthesize_context_with_failed_searches(self):
        """Test context synthesis with failed searches"""
        search_results = [
            {'success': False, 'error': 'API error'},
            {'success': True, 'answer': 'Valid answer', 'results': []}
        ]

        contexts = AgentHallucination._synthesize_context(search_results)

        assert len(contexts) == 1
        assert 'Valid answer' in contexts[0]

    def test_synthesize_context_empty_results(self):
        """Test context synthesis with empty results"""
        search_results = []
        contexts = AgentHallucination._synthesize_context(search_results)
        assert contexts == []

    def test_synthesize_context_includes_source_attribution(self):
        """Test that synthesized context includes source URLs"""
        search_results = [
            {
                'success': True,
                'results': [
                    {
                        'content': 'Test content',
                        'url': 'https://source.com',
                        'title': 'Test'
                    }
                ]
            }
        ]

        contexts = AgentHallucination._synthesize_context(search_results)

        assert any('https://source.com' in c for c in contexts)
        assert any('[Source:' in c for c in contexts)

    @patch.object(AgentHallucination, 'create_client')
    @patch.object(AgentHallucination, '_extract_claims')
    def test_eval_without_context_no_web_context(self, mock_extract, mock_create_client):
        """Test evaluation when web search fails to gather context"""
        mock_extract.return_value = ["Claim 1"]

        with patch.object(AgentHallucination, '_search_claims', return_value=[]):
            data = Data(content="Test content")
            result = AgentHallucination.eval(data)

            assert result.status is True  # Error condition
            assert any("NO_WEB_CONTEXT" in label for label in result.label)

    @patch.object(AgentHallucination, 'create_client')
    @patch.object(AgentHallucination, '_extract_claims')
    def test_eval_without_context_search_all_fail(self, mock_extract, mock_create_client):
        """Test evaluation when all searches fail"""
        mock_extract.return_value = ["Claim 1", "Claim 2"]

        failed_results = [
            {'success': False, 'error': 'Error 1'},
            {'success': False, 'error': 'Error 2'}
        ]

        with patch.object(AgentHallucination, '_search_claims', return_value=failed_results):
            data = Data(content="Test content")
            result = AgentHallucination.eval(data)

            assert result.status is True
            assert any("NO_WEB_CONTEXT" in label for label in result.label)

    def test_tool_availability(self):
        """Test that tavily_search is in available_tools"""
        assert "tavily_search" in AgentHallucination.available_tools

    def test_max_iterations_configured(self):
        """Test that max_iterations is properly configured"""
        assert AgentHallucination.max_iterations == 3

    def test_metadata_present(self):
        """Test that _metric_info metadata is present"""
        assert hasattr(AgentHallucination, '_metric_info')
        assert 'metric_name' in AgentHallucination._metric_info
        assert 'description' in AgentHallucination._metric_info
