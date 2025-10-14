"""
Dataset Hallucination Evaluation Example

This example demonstrates how to use Dingo's hallucination detection capability
for batch evaluation of datasets, particularly useful for:
- RAG system evaluation
- LLM response validation
- SFT data quality assessment
"""
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor
# Force import hallucination detection modules
from dingo.model.llm.llm_hallucination import LLMHallucination
from dingo.model.prompt.prompt_hallucination import PromptHallucination
from dingo.model.rule.rule_hallucination_hhem import RuleHallucinationHHEM


def evaluate_hallucination_jsonl_dataset():
    """
    Example 1: Evaluate a JSONL dataset for hallucinations
    Expected JSONL format:
    {"data_id": "1", "prompt": "question", "content": "response", "context": ["context1", "context2"]}
    """
    print("=== Example 1: JSONL Dataset Evaluation ===")

    input_data = {
        "input_path": str(Path("test/data/hallucination_test.jsonl")),  # Your JSONL file path
        "output_path": "output/hallucination_evaluation/",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "prompt": "prompt",
                "content": "content",
                "context": "context",
            }
        },
        "executor": {
            "prompt_list": ["PromptHallucination"],
            "result_save": {
                "bad": True
            }
        },
        "evaluator": {
            "llm_config": {
                "LLMHallucination": {
                    "model": "deepseek-chat",
                    "key": "Your API Key",
                    "api_url": "https://api.deepseek.com/v1"
                }
            }
        }
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()

    print(result)


def evaluate_hallucination_with_hhem_rule():
    """
    Example 2: Evaluate hallucinations using RuleHallucinationHHEM (Local HHEM model)

    RuleHallucinationHHEM uses Vectara's HHEM-2.1-Open model for local inference:
    - Superior performance compared to GPT-3.5/GPT-4 on benchmarks
    - Local inference with <600MB RAM usage
    - Fast processing (~1.5s for 2k tokens on modern CPU)
    - No API costs or rate limits
    """
    print("=== Example 2: HHEM Rule-Based Evaluation ===")

    input_data = {
        "input_path": str(Path("test/data/hallucination_test.jsonl")),
        "output_path": "output/hhem_evaluation/",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "prompt": "prompt",
                "content": "content",
                "context": "context",
            }
        },
        "executor": {
            "rule_list": ["RuleHallucinationHHEM"],  # Use HHEM rule instead of LLM
            "result_save": {
                "bad": True,
                "good": True  # Also save good examples for comparison
            }
        },
        "evaluator": {
            "rule_config": {
                "RuleHallucinationHHEM": {
                    "threshold": 0.8  # Default threshold (0.0-1.0, higher = more strict)
                }
            }
        }
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()

    print(result)


def evaluate_combined_llm_and_hhem():
    """
    Example 3: Combined evaluation using both LLM and HHEM for comprehensive analysis
    """
    print("=== Example 3: Combined LLM + HHEM Evaluation ===")

    input_data = {
        "input_path": str(Path("test/data/hallucination_test.jsonl")),
        "output_path": "output/combined_evaluation/",
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "prompt": "prompt",
                "content": "content",
                "context": "context",
            }
        },
        "executor": {
            "rule_list": ["RuleHallucinationHHEM"],  # Local HHEM rule
            "prompt_list": ["PromptHallucination"],   # LLM-based evaluation
            "result_save": {
                "bad": True,
                "good": True
            }
        },
        "evaluator": {
            "rule_config": {
                "RuleHallucinationHHEM": {
                    "threshold": 0.5  # HHEM threshold
                }
            },
            "llm_config": {
                "LLMHallucination": {
                    "model": "deepseek-chat",
                    "key": "Your API Key",
                    "api_url": "https://api.deepseek.com/v1"
                }
            }
        }
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()

    print(result)


def create_sample_test_data():
    """
    Helper function to create sample test data for demonstration
    """
    import json
    import os

    # Create test directory
    os.makedirs("test_data", exist_ok=True)

    # Sample hallucination test data
    hallucination_samples = [
        {
            "data_id": "1",
            "prompt": "When did Einstein win the Nobel Prize?",
            "content": "Einstein won the Nobel Prize in 1969 for his discovery of the photoelectric effect.",
            "context": ["Einstein won the Nobel Prize in 1921.", "The prize was for his work on the photoelectric effect."]
        },
        {
            "data_id": "2",
            "prompt": "What is the capital of Japan?",
            "content": "The capital of Japan is Tokyo, which is located on the eastern coast of Honshu island.",
            "context": ["Tokyo is the capital of Japan.", "Tokyo is located on Honshu island."]
        },
        {
            "data_id": "3",
            "prompt": "How many continents are there?",
            "content": "There are 8 continents in the world including Asia, Europe, North America, South America, Africa, Australia, Antarctica, and Atlantis.",
            "context": ["There are 7 continents.", "The continents are Asia, Europe, North America, South America, Africa, Australia, and Antarctica."]
        }
    ]

    # Write to JSONL file
    with open("test/data/hallucination_test.jsonl", "w", encoding="utf-8") as f:
        for sample in hallucination_samples:
            f.write(json.dumps(sample, ensure_ascii=False) + "\n")

    print("✅ Sample test data created in test_data/hallucination_test.jsonl")


if __name__ == "__main__":
    # Create sample data first (if needed)
    # create_sample_test_data()  # Commented out - using pre-built test data
    print()

    # Run examples (comment out if you don't have actual data)
    # evaluate_hallucination_jsonl_dataset()
    evaluate_hallucination_with_hhem_rule()
    # evaluate_combined_llm_and_hhem()  # Uncomment to test combined approach

    print("💡 Usage Tips:")
    print("- Use lower thresholds (0.2-0.3) for sensitive hallucination detection")
    print("- Use higher thresholds (0.6-0.8) for more permissive evaluation")
    print("- Combine with other quality metrics for comprehensive assessment")
    print("- Use parallel processing (max_workers) for large datasets")
    print("- Check output files for detailed per-item analysis")
    print()
