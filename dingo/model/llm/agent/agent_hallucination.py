"""
Agent-Based Hallucination Detection

This module provides an enhanced hallucination detector that uses web search to verify
factual claims when context is not provided. It extends the standard hallucination
detection with adaptive context gathering capabilities.

Key Features:
- Automatic fallback to web search when context is missing
- Claim extraction and individual verification
- Multi-source fact checking
- Transparent reasoning trails
- Backward compatible with existing LLMHallucination
"""

import json
from typing import Any, Dict, List

from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.agent.base_agent import BaseAgent
from dingo.utils import log


@Model.llm_register("AgentHallucination")
class AgentHallucination(BaseAgent):
    """
    Agent-based hallucination detector with web search fallback.

    Enhances standard hallucination detection by:
    1. Using existing LLMHallucination when context is provided
    2. Automatically gathering context via web search when missing
    3. Extracting factual claims from responses
    4. Verifying each claim independently
    5. Providing transparent source attribution

    This agent bridges the gap between context-dependent and context-independent
    hallucination detection, making evaluation more robust and practical.

    Configuration Example:
    {
        "name": "AgentHallucination",
        "config": {
            "key": "openai-api-key",
            "api_url": "https://api.openai.com/v1",
            "model": "gpt-4.1-mini-2025-04-14",
            "parameters": {
                "agent_config": {
                    "max_iterations": 3,
                    "tools": {
                        "tavily_search": {
                            "api_key": "tavily-api-key",
                            "max_results": 5
                        }
                    }
                }
            }
        }
    }
    """

    # Metadata for documentation
    _metric_info = {
        "category": "SFT Data Assessment Metrics - Agent-Enhanced",
        "metric_name": "AgentHallucination",
        "description": "Agent-based hallucination detection with automatic web search for missing context",
        "features": [
            "Automatic context gathering via web search",
            "Factual claim extraction",
            "Multi-source verification",
            "Transparent reasoning trails"
        ]
    }

    available_tools = ["tavily_search"]
    max_iterations = 3
    threshold = 0.5

    # Claim extraction prompt
    CLAIM_EXTRACTION_PROMPT = """You are a precise claim extractor. Extract all factual claims from the given text.

A factual claim is a statement that can be verified as true or false (e.g., "Paris is the capital of France", "Einstein won the Nobel Prize in 1921").

Do NOT include:
- Opinions or subjective statements
- Questions
- Procedural instructions
- Generic statements that cannot be fact-checked

Return ONLY a JSON array of claim strings. If no factual claims exist, return an empty array.

Text: {content}

Return format:
{{"claims": ["claim 1", "claim 2", ...]}}
"""

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """
        Main evaluation method with intelligent context handling.

        Workflow:
        1. Check if context is provided
        2. If yes: Use standard LLMHallucination
        3. If no: Execute agent workflow (claim extraction + web search)
        4. Return evaluation with provenance information

        Args:
            input_data: Data object with content and optional context

        Returns:
            EvalDetail with hallucination evaluation results
        """
        # Check if context is available
        has_context = cls._has_context(input_data)

        if has_context:
            log.info(f"{cls.__name__}: Context provided, using LLMHallucination")
            return cls._eval_with_context(input_data)
        else:
            log.info(f"{cls.__name__}: No context, using web search agent workflow")
            return cls._eval_with_web_search(input_data)

    @classmethod
    def _has_context(cls, input_data: Data) -> bool:
        """
        Check if input data has usable context.

        Args:
            input_data: Data object to check

        Returns:
            True if context is present and non-empty
        """
        # Check direct context attribute
        if hasattr(input_data, 'context') and input_data.context:
            return True

        # Check raw_data fallback
        if hasattr(input_data, 'raw_data') and input_data.raw_data:
            if 'context' in input_data.raw_data and input_data.raw_data['context']:
                return True

        return False

    @classmethod
    def _eval_with_context(cls, input_data: Data) -> EvalDetail:
        """
        Delegate to existing LLMHallucination when context is available.

        Args:
            input_data: Data object with context

        Returns:
            EvalDetail from LLMHallucination
        """
        try:
            from dingo.model.llm.llm_hallucination import LLMHallucination

            # Share configuration with LLMHallucination
            if hasattr(cls, 'dynamic_config') and cls.dynamic_config:
                LLMHallucination.dynamic_config = cls.dynamic_config

            # Use standard hallucination detection
            result = LLMHallucination.eval(input_data)

            # Add metadata about evaluation method
            if result.reason:
                result.reason.append(
                    f"\n💡 Evaluation Method: Standard LLMHallucination (context provided)"
                )
            else:
                result.reason = [
                    f"💡 Evaluation Method: Standard LLMHallucination (context provided)"
                ]

            return result

        except Exception as e:
            log.error(f"LLMHallucination delegation failed: {e}")
            result = EvalDetail(metric=cls.__name__)
            result.status = True
            result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}DELEGATION_ERROR"]
            result.reason = [f"Failed to delegate to LLMHallucination: {str(e)}"]
            return result

    @classmethod
    def _eval_with_web_search(cls, input_data: Data) -> EvalDetail:
        """
        Execute agent workflow: extract claims → web search → evaluate.

        Args:
            input_data: Data object without context

        Returns:
            EvalDetail with agent-based evaluation
        """
        try:
            # Ensure client is created
            cls.create_client()

            # Step 1: Extract factual claims
            log.info(f"{cls.__name__}: Extracting factual claims")
            claims = cls._extract_claims(input_data)

            if not claims:
                log.info(f"{cls.__name__}: No factual claims found")
                result = EvalDetail(metric=cls.__name__)
                result.status = False
                result.label = [QualityLabel.QUALITY_GOOD]
                result.reason = [
                    "✅ No factual claims detected in response",
                    "💡 Evaluation Method: Agent-based (no claims to verify)"
                ]
                return result

            log.info(f"{cls.__name__}: Extracted {len(claims)} claims")

            # Step 2: Search web for each claim
            log.info(f"{cls.__name__}: Searching web for verification")
            search_results = cls._search_claims(claims)

            # Step 3: Synthesize context from search results
            synthesized_context = cls._synthesize_context(search_results)

            if not synthesized_context:
                log.warning(f"{cls.__name__}: Failed to gather web context")
                result = EvalDetail(metric=cls.__name__)
                result.status = True
                result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}NO_WEB_CONTEXT"]
                result.reason = [
                    "⚠️ Unable to gather sufficient web context for verification",
                    f"📊 Attempted to verify {len(claims)} claims",
                    "💡 Evaluation Method: Agent-based (web search failed)"
                ]
                return result

            # Step 4: Create enriched data with synthesized context
            enriched_data = Data(
                content=input_data.content,
                prompt=getattr(input_data, 'prompt', ''),
                context=synthesized_context
            )

            # Step 5: Evaluate with standard method
            log.info(f"{cls.__name__}: Evaluating with synthesized context")
            result = cls._eval_with_context(enriched_data)

            # Step 6: Add agent provenance information
            agent_info = [
                "\n" + "=" * 60,
                "🤖 Agent-Based Evaluation Details",
                "=" * 60,
                f"📝 Factual Claims Extracted: {len(claims)}",
                f"🔍 Web Searches Performed: {len(search_results)}",
                f"📚 Context Sources Synthesized: {len(synthesized_context)}",
                "",
                "💡 Evaluation Method: Agent-based with web search",
                "   • Claims extracted from response",
                "   • Each claim verified via Tavily web search",
                "   • Context synthesized from search results",
                "   • Standard hallucination detection applied"
            ]

            if result.reason:
                result.reason.extend(agent_info)
            else:
                result.reason = agent_info

            return result

        except Exception as e:
            log.error(f"{cls.__name__} agent workflow failed: {e}")
            result = EvalDetail(metric=cls.__name__)
            result.status = True
            result.label = [f"{QualityLabel.QUALITY_BAD_PREFIX}AGENT_ERROR"]
            result.reason = [
                f"❌ Agent workflow failed: {str(e)}",
                "💡 Evaluation Method: Agent-based (error occurred)"
            ]
            return result

    @classmethod
    def _extract_claims(cls, input_data: Data) -> List[str]:
        """
        Extract factual claims from response using LLM.

        Args:
            input_data: Data object with content

        Returns:
            List of factual claim strings
        """
        try:
            # Build claim extraction prompt
            prompt = cls.CLAIM_EXTRACTION_PROMPT.format(
                content=input_data.content
            )

            # Call LLM
            messages = [{"role": "user", "content": prompt}]
            response = cls.send_messages(messages)

            # Parse JSON response
            # Handle markdown code blocks
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            data = json.loads(response)
            claims = data.get('claims', [])

            # Validate claims
            if not isinstance(claims, list):
                log.warning("Claims extraction returned non-list")
                return []

            # Filter out empty claims
            claims = [c.strip() for c in claims if c and c.strip()]

            return claims[:5]  # Limit to 5 claims to avoid excessive API calls

        except json.JSONDecodeError as e:
            log.error(f"Failed to parse claims JSON: {e}")
            log.debug(f"Response was: {response}")
            return []
        except Exception as e:
            log.error(f"Claim extraction failed: {e}")
            return []

    @classmethod
    def _search_claims(cls, claims: List[str]) -> List[Dict[str, Any]]:
        """
        Search web for each claim using Tavily.

        Args:
            claims: List of factual claims to verify

        Returns:
            List of search results
        """
        results = []

        for claim in claims:
            try:
                result = cls.execute_tool('tavily_search', query=claim)
                results.append(result)
            except Exception as e:
                log.warning(f"Search failed for claim '{claim}': {e}")
                results.append({
                    'success': False,
                    'query': claim,
                    'error': str(e)
                })

        return results

    @classmethod
    def _synthesize_context(cls, search_results: List[Dict[str, Any]]) -> List[str]:
        """
        Synthesize context from web search results.

        Args:
            search_results: List of Tavily search results

        Returns:
            List of context strings
        """
        contexts = []

        for result in search_results:
            if not result.get('success'):
                continue

            # Add AI-generated answer if available
            if result.get('answer'):
                contexts.append(result['answer'])

            # Add top search result contents
            for search_item in result.get('results', [])[:2]:  # Top 2 per claim
                content = search_item.get('content', '').strip()
                if content:
                    # Add source attribution
                    source = search_item.get('url', 'Unknown')
                    contexts.append(f"{content} [Source: {source}]")

        return contexts

    @classmethod
    def plan_execution(cls, input_data: Data) -> List[Dict[str, Any]]:
        """
        Define execution plan (not used in current implementation).

        The current implementation uses a direct workflow in _eval_with_web_search
        rather than the generic plan_execution framework.
        """
        # Not used - we implement custom workflow in eval()
        return []

    @classmethod
    def aggregate_results(cls, input_data: Data, results: List[Any]) -> EvalDetail:
        """
        Aggregate results (not used in current implementation).

        The current implementation uses a direct workflow in _eval_with_web_search
        rather than the generic aggregate_results framework.
        """
        # Not used - we implement custom workflow in eval()
        return EvalDetail(metric=cls.__name__)
