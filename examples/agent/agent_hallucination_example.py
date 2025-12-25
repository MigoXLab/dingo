"""
Agent-Based Hallucination Detection Example

This example demonstrates how to use the AgentHallucination evaluator with web search
fallback for cases where context is not provided.

Features demonstrated:
1. Evaluation with provided context (delegates to LLMHallucination)
2. Evaluation without context (uses web search to gather context)
3. Configuration of Tavily search tool
4. Interpretation of results

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


def example_with_context():
    """
    Example: Hallucination detection WITH context provided.
    This will delegate to standard LLMHallucination.
    """
    print("\n" + "=" * 70)
    print("Example 1: Hallucination Detection WITH Context")
    print("=" * 70)

    config = {
        "task_name": "agent_hallucination_with_context",
        "input_path": "test/data/hallucination_test.jsonl",
        "output_path": "outputs/agent_hallucination_with_context/",
        "dataset": {
            "source": "local",
            "format": "jsonl"
        },
        "executor": {
            "start_index": 0,
            "end_index": 2,  # Test on first 2 samples
            "max_workers": 1,
            "batch_size": 1,
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": [{
            "fields": {
                "content": "content",
                "prompt": "prompt",
                "context": "context"
            },
            "evals": [{
                "name": "AgentHallucination",
                "config": {
                    "key": os.getenv("OPENAI_API_KEY", "your-openai-api-key"),
                    "api_url": os.getenv("OPENAI_API_URL", "https://api.openai.com/v1"),
                    "model": "gpt-4.1-mini-2025-04-14",
                    "parameters": {
                        "temperature": 0.1,
                        "agent_config": {
                            "max_iterations": 3,
                            "tools": {
                                "tavily_search": {
                                    "api_key": os.getenv("TAVILY_API_KEY", "your-tavily-api-key")
                                }
                            }
                        }
                    }
                }
            }]
        }]
    }

    input_args = InputArgs(**config)
    executor = Executor.exec_map["local"](input_args)
    summary = executor.execute()

    print("\nResults:")
    print(f"  Total: {summary.total}")
    print(f"  Good: {summary.num_good}")
    print(f"  Bad: {summary.num_bad}")
    print(f"  Score: {summary.score:.2f}%")
    print(f"\nOutput saved to: {config['output_path']}")


def example_without_context():
    """
    Example: Hallucination detection WITHOUT context.
    This will use web search to gather context.
    """
    print("\n" + "=" * 70)
    print("Example 2: Hallucination Detection WITHOUT Context (Web Search)")
    print("=" * 70)

    # Create test data without context
    import os

    import jsonlines

    test_data = [
        {
            "id": "no_context_1",
            "question": "When was Python programming language created?",
            "response": "Python was created by Guido van Rossum and first released in 1991."
            # Note: NO context field - agent will search web
        },
        {
            "id": "no_context_2",
            "question": "What is the capital of France?",
            "response": "The capital of France is London."  # Hallucination!
            # Note: NO context field - agent will search web
        }
    ]

    # Write test data
    os.makedirs("test/data/agent", exist_ok=True)
    test_file = "test/data/agent/no_context_test.jsonl"
    with jsonlines.open(test_file, mode='w') as writer:
        writer.write_all(test_data)

    config = {
        "task_name": "agent_hallucination_no_context",
        "input_path": test_file,
        "output_path": "outputs/agent_hallucination_no_context/",
        "dataset": {
            "source": "local",
            "format": "jsonl"
        },
        "executor": {
            "max_workers": 1,
            "batch_size": 1,
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": [{
            "fields": {
                "content": "response",
                "prompt": "question"
                # Note: NO context field mapping
            },
            "evals": [{
                "name": "AgentHallucination",
                "config": {
                    "key": os.getenv("OPENAI_API_KEY", "your-openai-api-key"),
                    "api_url": os.getenv("OPENAI_API_URL", "https://api.openai.com/v1"),
                    "model": "gpt-4.1-mini-2025-04-14",
                    "parameters": {
                        "temperature": 0.1,
                        "agent_config": {
                            "max_iterations": 3,
                            "tools": {
                                "tavily_search": {
                                    "api_key": os.getenv("TAVILY_API_KEY", "your-tavily-api-key"),
                                    "max_results": 5,
                                    "search_depth": "advanced",
                                    "include_answer": True
                                }
                            }
                        }
                    }
                }
            }]
        }]
    }

    print("\nConfiguration:")
    print("  Model: gpt-4.1-mini")
    print("  Web Search: Enabled (Tavily)")
    print("  Max Results per Search: 5")
    print("  Search Depth: advanced")
    print(f"\nProcessing {len(test_data)} samples without context...")

    input_args = InputArgs(**config)
    executor = Executor.exec_map["local"](input_args)
    summary = executor.execute()

    print("\nResults:")
    print(f"  Total: {summary.total}")
    print(f"  Good: {summary.num_good}")
    print(f"  Bad: {summary.num_bad}")
    print(f"  Score: {summary.score:.2f}%")
    print(f"\nOutput saved to: {config['output_path']}")
    print("\n💡 Check the output files to see:")
    print("   • Extracted factual claims")
    print("   • Web search results")
    print("   • Synthesized context")
    print("   • Evaluation reasoning")


def example_sdk_usage():
    """
    Example: Direct SDK usage for programmatic evaluation.
    """
    print("\n" + "=" * 70)
    print("Example 3: Direct SDK Usage")
    print("=" * 70)

    from dingo.config.input_args import EvaluatorLLMArgs
    from dingo.io import Data
    from dingo.model.llm.agent.agent_hallucination import AgentHallucination

    # Configure the agent
    AgentHallucination.dynamic_config = EvaluatorLLMArgs(
        key=os.getenv("OPENAI_API_KEY", "your-openai-api-key"),
        api_url=os.getenv("OPENAI_API_URL", "https://api.openai.com/v1"),
        model="gpt-4.1-mini-2025-04-14",
        parameters={
            "temperature": 0.1,
            "agent_config": {
                "tools": {
                    "tavily_search": {
                        "api_key": os.getenv("TAVILY_API_KEY", "your-tavily-api-key")
                    }
                }
            }
        }
    )

    # Example 1: With context
    print("\nEvaluating response WITH context:")
    data_with_context = Data(
        content="Paris is the capital of France.",
        prompt="What is the capital of France?",
        context=["Paris is the capital and largest city of France."]
    )

    result = AgentHallucination.eval(data_with_context)
    print(f"  Status: {'❌ Hallucination' if result.status else '✅ No hallucination'}")
    print(f"  Label: {result.label}")

    # Example 2: Without context (requires API keys)
    print("\nEvaluating response WITHOUT context (will use web search):")
    data_without_context = Data(
        content="Einstein won the Nobel Prize in 1969.",  # Wrong year!
        prompt="When did Einstein win the Nobel Prize?"
        # No context - agent will search web
    )
    result = AgentHallucination.eval(data_without_context)
    print(f"  Status: {'❌ Hallucination' if result.status else '✅ No hallucination'}")
    print(f"  Label: {result.label}")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("AgentHallucination Examples")
    print("=" * 70)
    print("\n⚠️  IMPORTANT: Replace API keys in the code before running!")
    print("   • YOUR_OPENAI_API_KEY → Your OpenAI API key")
    print("   • YOUR_TAVILY_API_KEY → Your Tavily API key")
    print("\n📝 These examples demonstrate:")
    print("   1. Evaluation with provided context")
    print("   2. Evaluation without context (web search)")
    print("   3. Direct SDK usage")

    # Run all examples with configured API keys
    example_with_context()
    example_without_context()
    example_sdk_usage()

    print("\n" + "=" * 70)
    print("Examples completed!")
    print("=" * 70)
