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

from dingo.config import InputArgs
from dingo.exec import Executor
from dingo.model import Model

# Ensure models are loaded
Model.load_model()


def main():
    """Run the fact-checking agent example."""
    print("=" * 70)
    print("AgentFactCheck Example")
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
                "prompt": "question",
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
