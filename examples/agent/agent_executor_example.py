"""
LangChain 1.0 Agent Example: Fact-Checking Agent

This example demonstrates how to use LangChain 1.0's create_agent with Dingo
by setting use_agent_executor = True.

Uses langchain.agents.create_agent (November 2025 release) which provides:
- Simple API (no explicit graph/node/state concepts)
- Built on LangGraph runtime (persistence, checkpointing, HITL)
- Industry-standard ReAct pattern

Features demonstrated:
1. Automatic ReAct loop (no manual plan_execution needed)
2. Dynamic tool calling by the agent
3. Simple aggregate_results implementation
4. Custom system prompt

Requirements:
- Set OPENAI_API_KEY environment variable
- Set TAVILY_API_KEY environment variable
"""

import os
from typing import Any, Dict, List

from dingo.config import InputArgs
from dingo.exec import Executor
from dingo.io import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model import Model
from dingo.model.llm.agent.base_agent import BaseAgent

# Ensure models are loaded
Model.load_model()


@Model.llm_register("AgentFactCheck")
class AgentFactCheck(BaseAgent):
    """
    Fact-checking agent using LangChain 1.0 create_agent.

    Workflow (automatic via LangChain agent):
    1. Agent analyzes text for factual claims
    2. Dynamically calls tavily_search tool to verify claims
    3. Makes judgment based on evidence
    4. Returns evaluation result

    No manual orchestration needed - create_agent handles the ReAct loop.
    """

    use_agent_executor = True  # Enable AgentExecutor path
    available_tools = ["tavily_search"]
    max_iterations = 5

    _metric_info = {
        "metric_name": "AgentFactCheck",
        "description": "Agent-based fact checking with web search"
    }

    @classmethod
    def plan_execution(cls, input_data: Data) -> List[Dict[str, Any]]:
        """
        Not used with LangChain agent (can return empty list).

        The LangChain agent handles planning dynamically.
        """
        return []

    @classmethod
    def _get_system_prompt(cls, input_data: Data) -> str:
        """
        Custom system prompt for the fact-checking agent.

        This defines the agent's behavior and task.
        """
        return """You are a fact-checking agent. Your task is to verify factual claims in text.

Process:
1. Carefully read the text and identify any factual claims that can be verified
2. For each significant claim, use the tavily_search tool to find evidence
3. Compare the claims against the search results
4. Make a final judgment: are there any factual errors or is the information accurate?

Be thorough and objective. If you find errors, explain what is incorrect and what the correct information is.
If the text is accurate, confirm that it aligns with the evidence you found."""

    @classmethod
    def aggregate_results(
        cls,
        input_data: Data,
        results: List[Any]
    ) -> EvalDetail:
        """
        Parse LangChain agent output → EvalDetail.

        Args:
            results: [{'output': str, 'tool_calls': List, 'messages': ...}]

        Returns:
            EvalDetail with evaluation result
        """
        if not results:
            return EvalDetail(
                metric=cls.__name__,
                status=True,
                label=[f"{QualityLabel.QUALITY_BAD_PREFIX}NO_RESULT"],
                reason=["No evaluation result returned"]
            )

        agent_result = results[0]

        # Check execution success
        if not agent_result.get('success', True):
            return EvalDetail(
                metric=cls.__name__,
                status=True,
                label=[f"{QualityLabel.QUALITY_BAD_PREFIX}AGENT_ERROR"],
                reason=[agent_result.get('error', 'Unknown error')]
            )

        # Parse agent output
        output = agent_result.get('output', '')
        tool_calls = agent_result.get('tool_calls', [])

        # Detect factual errors based on agent's output
        has_factual_error = any(
            keyword in output.lower()
            for keyword in ['incorrect', 'false', 'error', 'wrong', 'inaccurate', 'mistaken']
        )

        result = EvalDetail(metric=cls.__name__)
        result.status = has_factual_error
        result.label = [
            f"{QualityLabel.QUALITY_BAD_PREFIX}FACTUAL_ERROR" if has_factual_error
            else QualityLabel.QUALITY_GOOD
        ]
        result.reason = [
            f"Agent Analysis: {output}",
            f"🔍 Web searches performed: {len(tool_calls)}",
            f"🤖 Reasoning steps: {agent_result.get('reasoning_steps', 0)}"
        ]

        return result


def main():
    """Run the fact-checking agent example."""
    print("=" * 70)
    print("AgentFactCheck Example (using LangChain 1.0 create_agent)")
    print("=" * 70)
    print()

    # Configuration
    config = {
        "task_name": "agent_fact_check_example",
        "input_path": "test/data/factcheck_test.jsonl",
        "output_path": "outputs/agent_fact_check_example/",
        "dataset": {
            "source": "local",
            "format": "jsonl"
        },
        "executor": {
            "start_index": 0,
            "end_index": 3,  # Test on first 3 samples
            "max_workers": 1,
            "batch_size": 1,
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": [{
            "fields": {
                "content": "content"
            },
            "evals": [{
                "name": "AgentFactCheck",
                "config": {
                    "key": os.getenv("OPENAI_API_KEY", "your-openai-api-key"),
                    "api_url": os.getenv("OPENAI_API_URL", "https://api.openai.com/v1"),
                    "model": "gpt-4.1-mini-2025-04-14",
                    "parameters": {
                        "temperature": 0.1,
                        "max_tokens": 16384,
                        "agent_config": {
                            "max_iterations": 5,
                            "tools": {
                                "tavily_search": {
                                    "api_key": os.getenv("TAVILY_API_KEY", "your-tavily-api-key"),
                                    "max_results": 5,
                                    "search_depth": "advanced"
                                }
                            }
                        }
                    }
                }
            }]
        }]
    }

    print("Configuration:")
    print("  Model: gpt-4.1-mini")
    print("  LangChain Agent: Enabled (create_agent)")
    print("  Tools: tavily_search")
    print("  Max Iterations: 5")
    print()

    # Execute
    input_args = InputArgs(**config)
    executor = Executor.exec_map["local"](input_args)

    print("Running evaluation...")
    print()

    summary = executor.execute()

    # Display results
    print()
    print("=" * 70)
    print("Results:")
    print("=" * 70)
    print(f"  Total: {summary.total}")
    print(f"  Good: {summary.num_good}")
    print(f"  Bad: {summary.num_bad}")
    print(f"  Score: {summary.score:.2f}%")
    print()
    print(f"Output saved to: {config['output_path']}")
    print()
    print("✨ Check the output files to see:")
    print("   • Agent's reasoning trace")
    print("   • Web search results")
    print("   • Fact-checking analysis")
    print()
    print("=" * 70)
    print("Example completed!")
    print("=" * 70)


if __name__ == "__main__":
    main()
