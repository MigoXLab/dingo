"""
Test suite for AgentFactCheck hallucination detection agent.

Tests cover:
- Agent registration
- Input formatting (with/without prompt, context)
- System prompt generation (context-aware)
- Output parsing (structured format + fallbacks)
- Error handling (empty output, parsing failures)
- Integration scenarios (mocked agent execution)
"""

from unittest.mock import patch

from dingo.io import Data
from dingo.io.output.eval_detail import QualityLabel
from dingo.model import Model
from dingo.model.llm.agent.agent_fact_check import AgentFactCheck


class TestAgentFactCheckRegistration:
    """Test agent registration and configuration."""

    def test_agent_registered(self):
        """Test that AgentFactCheck is registered in Model registry."""
        assert "AgentFactCheck" in Model.llm_name_map
        assert Model.llm_name_map["AgentFactCheck"] == AgentFactCheck

    def test_agent_configuration(self):
        """Test agent configuration attributes."""
        assert AgentFactCheck.use_agent_executor is True
        assert "tavily_search" in AgentFactCheck.available_tools
        assert AgentFactCheck.max_iterations == 10


class TestFormatAgentInput:
    """Test _format_agent_input method with various input combinations."""

    def test_format_with_prompt_and_content_only(self):
        """Test formatting with prompt and content, no context."""
        data = Data(prompt="What is 2+2?", content="The answer is 5")

        result = AgentFactCheck._format_agent_input(data)

        assert "**Question:**" in result
        assert "What is 2+2?" in result
        assert "**Response to Evaluate:**" in result
        assert "The answer is 5" in result
        assert "**Context:** None provided" in result

    def test_format_with_prompt_content_and_context(self):
        """Test formatting with all fields present."""
        data = Data(
            prompt="What is the capital of France?",
            content="The capital is Berlin",
            context="France's capital is Paris"
        )

        result = AgentFactCheck._format_agent_input(data)

        assert "**Question:**" in result
        assert "capital of France" in result
        assert "**Response to Evaluate:**" in result
        assert "Berlin" in result
        assert "**Context:**" in result
        assert "Paris" in result
        assert "None provided" not in result

    def test_format_with_context_list(self):
        """Test formatting when context is a list."""
        data = Data(
            prompt="Who wrote Hamlet?",
            content="Charles Dickens",
            context=["Shakespeare wrote Hamlet", "Hamlet is a tragedy"]
        )

        result = AgentFactCheck._format_agent_input(data)

        assert "**Context:**" in result
        assert "- Shakespeare wrote Hamlet" in result
        assert "- Hamlet is a tragedy" in result

    def test_format_without_prompt(self):
        """Test formatting when prompt is missing."""
        # Create Data without prompt attribute
        data = Data(content="Some content to evaluate")
        # Ensure prompt attribute doesn't exist
        if hasattr(data, 'prompt'):
            delattr(data, 'prompt')

        result = AgentFactCheck._format_agent_input(data)

        assert "**Response to Evaluate:**" in result
        assert "Some content to evaluate" in result
        # Should not have Question section when prompt doesn't exist
        # But our implementation checks input_data.prompt, so it will get None
        # and skip the question section


class TestGetSystemPrompt:
    """Test _get_system_prompt method."""

    def test_system_prompt_with_context(self):
        """Test system prompt when context is available."""
        data = Data(
            prompt="Test question",
            content="Test content",
            context="Test context"
        )

        prompt = AgentFactCheck._get_system_prompt(data)

        assert "fact-checking agent" in prompt
        assert "Context is provided" in prompt
        assert "MAY use web search" in prompt
        assert "Make your own decision" in prompt
        assert "HALLUCINATION_DETECTED:" in prompt
        assert "YES or NO" in prompt

    def test_system_prompt_without_context(self):
        """Test system prompt when context is not available."""
        data = Data(prompt="Test question", content="Test content")

        prompt = AgentFactCheck._get_system_prompt(data)

        assert "fact-checking agent" in prompt
        assert "NO Context is available" in prompt
        assert "MUST use web search" in prompt
        assert "HALLUCINATION_DETECTED:" in prompt

    def test_system_prompt_includes_format_instructions(self):
        """Test that system prompt includes format instructions."""
        data = Data(prompt="Test", content="Test")

        prompt = AgentFactCheck._get_system_prompt(data)

        assert "HALLUCINATION_DETECTED:" in prompt
        assert "EXPLANATION:" in prompt
        assert "EVIDENCE:" in prompt
        assert "Example:" in prompt


class TestDetectHallucinationFromOutput:
    """Test _detect_hallucination_from_output method."""

    def test_detect_yes_structured_format(self):
        """Test detection of YES in structured format."""
        output = """HALLUCINATION_DETECTED: YES
EXPLANATION: The response claims incorrect information.
EVIDENCE: According to reliable sources, this is false."""

        result = AgentFactCheck._detect_hallucination_from_output(output)

        assert result is True

    def test_detect_no_structured_format(self):
        """Test detection of NO in structured format."""
        output = """HALLUCINATION_DETECTED: NO
EXPLANATION: The response is factually accurate.
EVIDENCE: All claims verified against multiple sources."""

        result = AgentFactCheck._detect_hallucination_from_output(output)

        assert result is False

    def test_detect_case_insensitive(self):
        """Test that detection is case insensitive."""
        output1 = "hallucination_detected: yes\nExplanation here..."
        output2 = "HALLUCINATION_DETECTED: no\nExplanation here..."

        assert AgentFactCheck._detect_hallucination_from_output(output1) is True
        assert AgentFactCheck._detect_hallucination_from_output(output2) is False

    def test_detect_with_extra_whitespace(self):
        """Test detection handles extra whitespace."""
        output = "HALLUCINATION_DETECTED:   YES  \nMore text..."

        result = AgentFactCheck._detect_hallucination_from_output(output)

        assert result is True

    def test_detect_fallback_to_keywords_yes(self):
        """Test fallback keyword detection for hallucination."""
        output = "Analysis: Hallucination detected in the response. The claim is false."

        result = AgentFactCheck._detect_hallucination_from_output(output)

        assert result is True

    def test_detect_fallback_to_keywords_no(self):
        """Test fallback keyword detection for no hallucination."""
        output = "Analysis: No hallucination detected. The information is factually accurate."

        result = AgentFactCheck._detect_hallucination_from_output(output)

        assert result is False

    def test_detect_empty_output(self):
        """Test detection with empty output returns False."""
        assert AgentFactCheck._detect_hallucination_from_output("") is False
        assert AgentFactCheck._detect_hallucination_from_output(None) is False

    def test_detect_ambiguous_output_defaults_to_false(self):
        """Test that ambiguous output defaults to False (no hallucination)."""
        output = "This is some text without clear signals."

        result = AgentFactCheck._detect_hallucination_from_output(output)

        # Should default to False to avoid false positives
        assert result is False

    def test_detect_at_start_of_response(self):
        """Test detection when marker is at start."""
        output = "HALLUCINATION_DETECTED: YES\nBecause XYZ..."

        result = AgentFactCheck._detect_hallucination_from_output(output)

        assert result is True


class TestExtractSourcesFromOutput:
    """Test _extract_sources_from_output method."""

    def test_extract_sources_with_dashes(self):
        """Test extraction of sources with - prefix."""
        output = """HALLUCINATION_DETECTED: YES
EXPLANATION: Some explanation
SOURCES:
- https://example.com/source1
- https://example.com/source2
EVIDENCE: Some evidence"""

        sources = AgentFactCheck._extract_sources_from_output(output)

        assert len(sources) == 2
        assert "https://example.com/source1" in sources
        assert "https://example.com/source2" in sources

    def test_extract_sources_with_bullets(self):
        """Test extraction of sources with • prefix."""
        output = """SOURCES:
• https://example.com/source1
• https://example.com/source2"""

        sources = AgentFactCheck._extract_sources_from_output(output)

        assert len(sources) == 2
        assert "https://example.com/source1" in sources
        assert "https://example.com/source2" in sources

    def test_extract_sources_direct_urls(self):
        """Test extraction of direct URLs without prefix."""
        output = """SOURCES:
https://example.com/source1
https://example.com/source2"""

        sources = AgentFactCheck._extract_sources_from_output(output)

        assert len(sources) == 2
        assert "https://example.com/source1" in sources
        assert "https://example.com/source2" in sources

    def test_extract_sources_no_sources_section(self):
        """Test when output has no SOURCES section."""
        output = """HALLUCINATION_DETECTED: NO
EXPLANATION: Everything is correct"""

        sources = AgentFactCheck._extract_sources_from_output(output)

        assert len(sources) == 0
        assert sources == []

    def test_extract_sources_empty_sources_section(self):
        """Test when SOURCES section is empty."""
        output = """HALLUCINATION_DETECTED: YES
SOURCES:
EXPLANATION: Some explanation"""

        sources = AgentFactCheck._extract_sources_from_output(output)

        assert len(sources) == 0

    def test_extract_sources_mixed_format(self):
        """Test extraction with mixed formats."""
        output = """SOURCES:
- https://example.com/source1
• https://example.com/source2
https://example.com/source3"""

        sources = AgentFactCheck._extract_sources_from_output(output)

        assert len(sources) == 3

    def test_extract_sources_case_insensitive(self):
        """Test that SOURCES detection is case insensitive."""
        output = """sources:
- https://example.com/source1"""

        sources = AgentFactCheck._extract_sources_from_output(output)

        assert len(sources) == 1
        assert "https://example.com/source1" in sources

    def test_extract_sources_stops_at_next_section(self):
        """Test that extraction stops at the next section header."""
        output = """SOURCES:
- https://example.com/source1
- https://example.com/source2
EXPLANATION: This should not be included
- https://example.com/source3"""

        sources = AgentFactCheck._extract_sources_from_output(output)

        # Should only get the first two sources, not the third
        assert len(sources) == 2
        assert "https://example.com/source3" not in sources


class TestAggregateResults:
    """Test aggregate_results method."""

    def test_aggregate_with_no_results(self):
        """Test aggregation when no results returned."""
        data = Data(prompt="Test", content="Test")

        result = AgentFactCheck.aggregate_results(data, [])

        assert result.status is True  # Error status
        assert "AGENT_ERROR" in result.label[0]
        assert "No results" in result.reason[0]

    def test_aggregate_with_failure_result(self):
        """Test aggregation when agent execution failed."""
        data = Data(prompt="Test", content="Test")
        agent_result = {
            'success': False,
            'error': 'Execution timeout'
        }

        result = AgentFactCheck.aggregate_results(data, [agent_result])

        assert result.status is True
        assert "AGENT_ERROR" in result.label[0]
        assert "timeout" in result.reason[0].lower()

    def test_aggregate_with_empty_output(self):
        """Test aggregation when agent returns empty output."""
        data = Data(prompt="Test", content="Test")
        agent_result = {
            'success': True,
            'output': '',
            'tool_calls': [],
            'reasoning_steps': 0
        }

        result = AgentFactCheck.aggregate_results(data, [agent_result])

        assert result.status is True
        assert "AGENT_ERROR" in result.label[0]
        assert "empty output" in result.reason[0].lower()

    def test_aggregate_hallucination_detected(self):
        """Test aggregation when hallucination is detected."""
        data = Data(prompt="Test", content="Test")
        agent_result = {
            'success': True,
            'output': 'HALLUCINATION_DETECTED: YES\nExplanation: Incorrect claim.',
            'tool_calls': [{'tool': 'tavily_search'}],
            'reasoning_steps': 3
        }

        result = AgentFactCheck.aggregate_results(data, [agent_result])

        assert result.status is True  # Hallucination found
        assert "HALLUCINATION" in result.label[0]
        assert "YES" in result.reason[0]
        assert "Web searches performed: 1" in result.reason[2]

    def test_aggregate_no_hallucination(self):
        """Test aggregation when no hallucination detected."""
        data = Data(prompt="Test", content="Test")
        agent_result = {
            'success': True,
            'output': 'HALLUCINATION_DETECTED: NO\nExplanation: All facts verified.',
            'tool_calls': [],
            'reasoning_steps': 2
        }

        result = AgentFactCheck.aggregate_results(data, [agent_result])

        assert result.status is False  # No hallucination
        assert result.label[0] == QualityLabel.QUALITY_GOOD
        assert "NO" in result.reason[0]
        assert "Web searches performed: 0" in result.reason[2]

    def test_aggregate_with_parsing_exception(self):
        """Test aggregation handles parsing exceptions."""
        data = Data(prompt="Test", content="Test")
        agent_result = {
            'success': True,
            'output': 'Valid output',
            'tool_calls': [],
            'reasoning_steps': 1
        }

        # Mock _detect_hallucination_from_output to raise exception
        with patch.object(
            AgentFactCheck,
            '_detect_hallucination_from_output',
            side_effect=ValueError("Parse error")
        ):
            result = AgentFactCheck.aggregate_results(data, [agent_result])

        assert result.status is True  # Error status
        assert "AGENT_ERROR" in result.label[0]
        assert "Failed to parse" in result.reason[0]


class TestIntegration:
    """Integration tests with mocked agent execution."""

    @patch('dingo.model.llm.agent.agent_wrapper.AgentWrapper')
    @patch.object(AgentFactCheck, 'create_client')
    @patch.object(AgentFactCheck, 'get_langchain_tools')
    @patch.object(AgentFactCheck, 'get_langchain_llm')
    @patch.object(AgentFactCheck, '_check_langchain_available', return_value=True)
    def test_eval_with_context_no_search(
        self,
        mock_check_langchain,
        mock_get_llm,
        mock_get_tools,
        mock_create_client,
        mock_wrapper
    ):
        """Test evaluation with context where agent doesn't search."""
        # Setup mocks
        mock_get_tools.return_value = []
        mock_get_llm.return_value = "mock_llm"
        mock_wrapper.create_agent.return_value = "mock_agent"
        mock_wrapper.invoke_and_format.return_value = {
            'success': True,
            'output': 'HALLUCINATION_DETECTED: NO\nContext was sufficient.',
            'tool_calls': [],  # No search performed
            'reasoning_steps': 2
        }

        data = Data(
            prompt="What is 2+2?",
            content="The answer is 4",
            context="2+2=4 is correct"
        )

        result = AgentFactCheck.eval(data)

        assert result.status is False  # No hallucination
        assert "QUALITY_GOOD" in result.label[0]
        # Verify input formatting was used
        call_args = mock_wrapper.invoke_and_format.call_args
        input_text = call_args[1]['input_text']
        assert "**Question:**" in input_text
        assert "**Response to Evaluate:**" in input_text
        assert "**Context:**" in input_text

    @patch('dingo.model.llm.agent.agent_wrapper.AgentWrapper')
    @patch.object(AgentFactCheck, 'create_client')
    @patch.object(AgentFactCheck, 'get_langchain_tools')
    @patch.object(AgentFactCheck, 'get_langchain_llm')
    @patch.object(AgentFactCheck, '_check_langchain_available', return_value=True)
    def test_eval_without_context_must_search(
        self,
        mock_check_langchain,
        mock_get_llm,
        mock_get_tools,
        mock_create_client,
        mock_wrapper
    ):
        """Test evaluation without context where agent must search."""
        # Setup mocks
        mock_get_tools.return_value = []
        mock_get_llm.return_value = "mock_llm"
        mock_wrapper.create_agent.return_value = "mock_agent"
        mock_wrapper.invoke_and_format.return_value = {
            'success': True,
            'output': 'HALLUCINATION_DETECTED: YES\nWeb search revealed error.',
            'tool_calls': [{'tool': 'tavily_search', 'query': 'fact check'}],
            'reasoning_steps': 4
        }

        data = Data(
            prompt="What is the capital of Mars?",
            content="The capital is Olympus City"
        )

        result = AgentFactCheck.eval(data)

        assert result.status is True  # Hallucination found
        assert "HALLUCINATION" in result.label[0]
        # Verify system prompt instructs to search
        call_args = mock_wrapper.create_agent.call_args
        system_prompt = call_args[1]['system_prompt']
        assert "MUST use web search" in system_prompt


class TestPlanExecution:
    """Test plan_execution method."""

    def test_plan_execution_returns_empty(self):
        """Test that plan_execution returns empty list for LangChain agents."""
        data = Data(prompt="Test", content="Test")

        result = AgentFactCheck.plan_execution(data)

        assert result == []
        assert isinstance(result, list)
