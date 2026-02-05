"""
AgentFactCheck: LangChain-based fact-checking agent with autonomous search control.

This module implements a hallucination detection agent that autonomously decides
when to use web search based on context availability, following LangChain 2025
best practices for structured output and reliable parsing.
"""

import re
from typing import Any, Dict, List

from dingo.io import Data
from dingo.io.input.required_field import RequiredField
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.agent.base_agent import BaseAgent


@Model.llm_register("AgentFactCheck")
class AgentFactCheck(BaseAgent):
    """
    LangChain-based fact-checking agent with autonomous search control.

    Implementation Pattern: Framework-Driven (LangChain 1.0)
    ========================================================

    This agent uses LangChain 1.0's create_agent with ReAct pattern, allowing the
    framework to autonomously handle tool calling and multi-step reasoning. The agent
    evaluates responses for hallucinations by analyzing prompt, response, and context
    together, with full autonomy over when and how to use web search.

    Key Characteristics:
    -------------------
    - Sets `use_agent_executor = True` to enable LangChain agent path
    - Overrides `_format_agent_input()` for custom input formatting
    - Overrides `_get_system_prompt()` for task-specific instructions
    - LangChain automatically manages tool calls and reasoning loop
    - Parses structured output in `aggregate_results()`

    Agent Behavior:
    --------------
    - With context: Agent MAY search for additional verification (autonomous decision)
    - Without context: Agent MUST search to verify facts (enforced by prompt)
    - Uses explicit output format instructions (HALLUCINATION_DETECTED: YES/NO)
    - Parses with regex (primary) + keyword fallback for robustness
    - Handles errors gracefully with detailed error messages

    When to Use This Pattern:
    ------------------------
    ✅ Complex multi-step reasoning required
    ✅ Benefit from LangChain's battle-tested agent orchestration
    ✅ Prefer declarative over imperative style
    ✅ Need rapid prototyping with minimal code

    When NOT to Use:
    ---------------
    ❌ Need fine-grained control over every execution step
    ❌ Want to compose with existing Dingo evaluators
    ❌ Prefer explicit control flow over framework magic

    See Also:
    --------
    - docs/agent_development_guide.md - Comprehensive agent development guide
    - AgentHallucination - Custom workflow pattern for comparison

    Configuration Example:
    {
        "name": "AgentFactCheck",
        "config": {
            "key": "your-openai-api-key",
            "api_url": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini-2025-04-14",
            "parameters": {
                "agent_config": {
                    "max_iterations": 5,
                    "tools": {
                        "tavily_search": {
                            "api_key": "your-tavily-api-key",
                            "max_results": 5,
                            "search_depth": "advanced"
                        }
                    }
                }
            }
        }
    }
    """

    use_agent_executor = True  # Enable LangChain agent mode
    available_tools = ["tavily_search"]
    max_iterations = 10
    threshold = 0.5

    _required_fields = [RequiredField.PROMPT, RequiredField.CONTENT]
    # Note: CONTEXT is optional - agent adapts behavior based on availability

    _metric_info = {
        "metric_name": "AgentFactCheck",
        "description": "Agent-based hallucination detection with autonomous web search"
    }

    @classmethod
    def _format_agent_input(cls, input_data: Data) -> str:
        """
        Format prompt + content + context for agent.

        Structures the input to provide clear context for hallucination detection.
        Uses markdown-style headers for readability.

        Args:
            input_data: Data object with prompt, content, and optional context

        Returns:
            Formatted input string with clear section delineation
        """
        parts = []

        # Safely check for prompt attribute
        if hasattr(input_data, 'prompt') and input_data.prompt:
            parts.append(f"**Question:**\n{input_data.prompt}")

        parts.append(f"**Response to Evaluate:**\n{input_data.content}")

        if hasattr(input_data, 'context') and input_data.context:
            # Handle both list and string contexts
            if isinstance(input_data.context, list):
                context_str = "\n".join(f"- {c}" for c in input_data.context)
            else:
                context_str = str(input_data.context)
            parts.append(f"**Context:**\n{context_str}")
        else:
            parts.append("**Context:** None provided - use web search to verify")

        return "\n\n".join(parts)

    @classmethod
    def _get_system_prompt(cls, input_data: Data) -> str:
        """
        System prompt adapts based on context availability.

        Following LangChain best practices: explicitly defines output format
        for reliable parsing without relying on keyword detection.

        With context: Agent has autonomy to decide if web search is needed
        Without context: Agent must use web search to verify facts

        Args:
            input_data: Input data (used to check context availability)

        Returns:
            System prompt with clear instructions and format requirements
        """
        has_context = hasattr(input_data, 'context') and input_data.context

        base_instructions = """You are a fact-checking agent with web search capabilities.

Your task:
1. Analyze the Question and Response provided"""

        if has_context:
            context_instruction = """
2. Context is provided - evaluate the Response against it
3. You MAY use web search for additional verification if needed
4. Make your own decision about whether web search is necessary"""
        else:
            context_instruction = """
2. NO Context is available - you MUST use web search to verify facts
3. Search for reliable sources to fact-check the response"""

        output_format = """

**IMPORTANT: You must return your analysis in exactly this format:**

HALLUCINATION_DETECTED: [YES or NO]
EXPLANATION: [Your detailed analysis of what is correct or incorrect]
EVIDENCE: [Specific sources, facts, or reasoning that support your judgment]
SOURCES: [List of URLs consulted, one per line with - prefix]

Example:
HALLUCINATION_DETECTED: YES
EXPLANATION: The response claims the Eiffel Tower is 450 meters tall, but it is actually 330 meters
(including antennas).
EVIDENCE: According to multiple reliable sources including the official Eiffel Tower website,
the structure's height is 330 meters.
SOURCES:
- https://www.toureiffel.paris/en/the-monument
- https://en.wikipedia.org/wiki/Eiffel_Tower

Be precise and clear. Start your response with "HALLUCINATION_DETECTED:" followed by YES or NO.
Always include SOURCES with specific URLs when you perform web searches."""

        return base_instructions + context_instruction + output_format

    @classmethod
    def aggregate_results(cls, input_data: Data, results: List[Any]) -> EvalDetail:
        """
        Parse agent output to determine hallucination status.

        Implements robust error handling following LangChain best practices.
        Returns error status for any parsing or execution failures.

        Args:
            input_data: Original input data
            results: List containing agent execution result dictionary

        Returns:
            EvalDetail with hallucination detection results or error status
        """
        if not results:
            return cls._create_error_result("No results from agent")

        agent_result = results[0]

        # Check for execution errors
        if not agent_result.get('success', True):
            error_msg = agent_result.get('error', 'Unknown error')
            return cls._create_error_result(error_msg)

        # Extract agent output with defensive checks
        output = agent_result.get('output', '')
        tool_calls = agent_result.get('tool_calls', [])
        reasoning_steps = agent_result.get('reasoning_steps', 0)

        # Validate output exists
        if not output or not output.strip():
            return cls._create_error_result(
                "Agent returned empty output. "
                "This may indicate the agent reached max_iterations without completing."
            )

        # Parse hallucination detection from structured output
        try:
            has_hallucination = cls._detect_hallucination_from_output(output)
        except Exception as e:
            # If parsing fails, treat as error rather than false positive/negative
            return cls._create_error_result(
                f"Failed to parse agent output: {str(e)}\nOutput: {output[:200]}..."
            )

        # Build result
        result = EvalDetail(metric=cls.__name__)
        result.status = has_hallucination
        result.label = [
            f"{QualityLabel.QUALITY_BAD_PREFIX}HALLUCINATION"
            if has_hallucination
            else QualityLabel.QUALITY_GOOD
        ]

        # Extract sources from output
        sources = cls._extract_sources_from_output(output)

        result.reason = [
            f"Agent Analysis:\n{output}",
            "",
            f"🔍 Web searches performed: {len(tool_calls)}",
            f"🤖 Reasoning steps: {reasoning_steps}",
            f"⚙️  Agent autonomously decided: "
            f"{'Use web search' if tool_calls else 'Context sufficient'}"
        ]

        # Add sources section
        result.reason.append("")
        if sources:
            result.reason.append("📚 Sources consulted:")
            for source in sources:
                result.reason.append(f"   • {source}")
        else:
            result.reason.append("📚 Sources: None explicitly cited")

        return result

    @classmethod
    def _extract_sources_from_output(cls, output: str) -> List[str]:
        """
        Extract source URLs from agent output.

        Looks for a SOURCES section in the agent output and extracts URLs.
        Supports multiple formats:
        - Lines starting with "- " or "• "
        - Direct URLs (http://, https://)

        Args:
            output: Agent's text output

        Returns:
            List of source URLs found in the output

        Example:
            SOURCES:
            - https://example.com/source1
            - https://example.com/source2
        """
        sources = []
        in_sources_section = False

        for line in output.split('\n'):
            line = line.strip()

            # Check if we're entering the SOURCES section
            if line.upper().startswith('SOURCES:'):
                in_sources_section = True
                continue

            if in_sources_section:
                # Check if we've reached a new section (ends SOURCES section)
                if line and ':' in line:
                    section_header = line.split(':')[0].upper()
                    if section_header in ['EXPLANATION', 'EVIDENCE', 'HALLUCINATION_DETECTED']:
                        break

                # Extract URL (with - or • prefix, or direct URL)
                if line.startswith(('- ', '• ', 'http://', 'https://')):
                    url = line.lstrip('- •').strip()
                    if url:
                        sources.append(url)

        return sources

    @classmethod
    def _detect_hallucination_from_output(cls, output: str) -> bool:
        """
        Parse agent output to detect hallucinations.

        Following LangChain best practices: parses structured format rather than
        relying on keyword detection. This is more reliable and follows the
        pattern recommended in LangChain documentation for agent output parsing.

        Parsing strategy (in priority order):
        1. Regex match for "HALLUCINATION_DETECTED: YES/NO" (case insensitive)
        2. Check if response starts with marker, extract YES/NO
        3. Fallback to keyword detection for robustness
        4. Default to False (no hallucination) if no clear signal

        Expected format from agent:
        HALLUCINATION_DETECTED: [YES/NO]
        EXPLANATION: ...
        EVIDENCE: ...

        Args:
            output: Agent's text output

        Returns:
            True if hallucination detected, False otherwise

        Raises:
            Exception: If parsing encounters unexpected errors (caught by caller)
        """
        if not output:
            # Empty output - return False to avoid false positives
            return False

        # Primary parsing: Look for structured format with regex
        # Pattern: "HALLUCINATION_DETECTED: YES" or "HALLUCINATION_DETECTED: NO"
        match = re.search(
            r'HALLUCINATION_DETECTED:\s*(YES|NO)',
            output,
            re.IGNORECASE
        )

        if match:
            detected = match.group(1).upper()
            return detected == 'YES'

        # Fallback 1: Look for the marker at start of response (case insensitive)
        output_upper = output.upper().strip()
        if output_upper.startswith('HALLUCINATION_DETECTED:'):
            # Extract YES/NO from first line
            first_line = output_upper.split('\n')[0]
            if 'YES' in first_line:
                return True
            if 'NO' in first_line:
                return False

        # Fallback 2: If format is not followed, use defensive keyword detection
        # This maintains backward compatibility if agent doesn't follow instructions
        output_lower = output.lower()

        # IMPORTANT: Check negative indicators FIRST to avoid false positives
        # E.g., "no hallucination detected" contains "hallucination detected"
        strong_no_indicators = [
            'no hallucination detected',
            'no factual error',
            'factually accurate',
            'hallucination: no'
        ]

        strong_indicators = [
            'hallucination detected',
            'factual error detected',
            'contains hallucination',
            'hallucination: yes'
        ]

        # Check negative indicators first (must check before positive to avoid substring matches)
        if any(indicator in output_lower for indicator in strong_no_indicators):
            return False
        if any(indicator in output_lower for indicator in strong_indicators):
            return True

        # If no clear signal, default to False (no hallucination) to avoid false positives
        # This is safer than defaulting to True
        return False

    @classmethod
    def _create_error_result(cls, error_message: str) -> EvalDetail:
        """
        Create error result for agent execution or parsing failures.

        Args:
            error_message: Description of the error

        Returns:
            EvalDetail with error status
        """
        result = EvalDetail(metric=cls.__name__)
        result.status = True  # True indicates an issue/error
        result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}AGENT_ERROR"]
        result.reason = [f"Agent evaluation failed: {error_message}"]
        return result

    @classmethod
    def plan_execution(cls, input_data: Data) -> List[Dict[str, Any]]:
        """
        Not used with LangChain agent (agent handles planning).

        When use_agent_executor=True, the LangChain agent autonomously plans
        its execution using the ReAct pattern. This method is only called for
        the legacy agent path (use_agent_executor=False).

        Args:
            input_data: Input data (unused)

        Returns:
            Empty list (no manual planning needed)
        """
        return []
