"""
Dingo Rule-based HHEM-2.1-Open Hallucination Detection Example

This example demonstrates how to use the HHEM-2.1-Open model as a rule-based
hallucination detection tool for efficient local inference without API costs.

Rule-based HHEM offers:
- Better architecture fit (rules vs LLM for deterministic local models)
- Superior performance than GPT-3.5 and GPT-4 on benchmarks
- Local inference with <600MB RAM usage
- Fast processing (~1.5s for 2k tokens on modern CPU)
- No API costs or rate limits
"""

from dingo.io.input import Data
from dingo.model.rule.rule_hallucination_hhem import RuleHallucinationHHEM


def example_1_basic_rule_hhem_detection():
    """Example 1: Basic rule-based HHEM hallucination detection"""
    print("=== Example 1: Basic Rule-based HHEM Detection ===")

    # Test case with hallucination (incorrect date)
    data = Data(
        data_id='rule_hhem_test_1',
        prompt="When did Einstein win the Nobel Prize?",
        content="Einstein won the Nobel Prize in 1969 for his discovery of the photoelectric effect.",
        context=[
            "Einstein won the Nobel Prize for his discovery of the photoelectric effect.",
            "Einstein won the Nobel Prize in 1921."
        ]
    )

    result = RuleHallucinationHHEM.eval(data)

    print(f"Error Status: {result.status}")  # True = hallucination detected, False = no hallucination
    print(f"Label: {result.label}")
    print(f"HHEM Score: {getattr(result, 'score', 'N/A'):.3f}")
    print(f"Threshold: {RuleHallucinationHHEM.dynamic_config.threshold}")
    print("\nDetailed Analysis:")
    print(result.reason[0] if result.reason else "N/A")
    print()


def example_2_no_hallucination_rule():
    """Example 2: Rule-based response with no hallucination"""
    print("=== Example 2: No Hallucination (Rule-based HHEM) ===")

    # Test case without hallucination
    data = Data(
        data_id='rule_hhem_no_hallucination',
        prompt="What is the capital of France?",
        content="The capital of France is Paris.",
        context=[
            "Paris is the capital of France.",
            "Paris is located in north-central France."
        ]
    )

    result = RuleHallucinationHHEM.eval(data)

    print(f"Error Status: {result.status}")  # True = hallucination detected, False = no hallucination
    print(f"Label: {result.label}")
    print(f"HHEM Score: {getattr(result, 'score', 'N/A'):.3f}")
    print("\nDetailed Analysis:")
    print(result.reason[0] if result.reason else "N/A")
    print()


def example_3_complex_scenario_rule():
    """Example 3: Complex rule-based scenario with multiple contexts"""
    print("=== Example 3: Complex Rule-based HHEM Evaluation ===")

    contexts = [
        "The Great Wall of China was built over many centuries.",
        "The Great Wall of China is approximately 21,000 kilometers long.",
        "The Great Wall was built primarily during the Ming Dynasty.",
        "The Great Wall of China is NOT visible from space with the naked eye."
    ]

    data = Data(
        data_id='rule_hhem_complex_test',
        prompt="Tell me about the Great Wall of China",
        content="The Great Wall of China is an ancient fortification built over many centuries, primarily during the Ming Dynasty. It stretches approximately 21,000 kilometers. It is clearly visible from space with the naked eye.",
        context=contexts
    )

    result = RuleHallucinationHHEM.eval(data)

    print(f"Error Status: {result.status}")  # True = hallucination detected, False = no hallucination
    print(f"Label: {result.label}")
    print(f"HHEM Score: {getattr(result, 'score', 'N/A'):.3f}")
    print("\nDetailed Analysis:")
    print(result.reason[0] if result.reason else "N/A")
    print()


def example_4_detailed_output_rule():
    """Example 4: Using detailed output method for rule-based evaluation"""
    print("=== Example 4: Detailed Rule-based HHEM Output ===")

    data = Data(
        data_id='rule_detailed_test',
        prompt="Explain photosynthesis",
        content="Photosynthesis is the process where plants use sunlight to convert water and carbon dioxide into glucose and oxygen. The main byproduct is actually carbon monoxide, not oxygen.",
        context=[
            "Photosynthesis is the process by which plants convert sunlight into chemical energy.",
            "During photosynthesis, plants absorb carbon dioxide and water.",
            "The main products of photosynthesis are glucose and oxygen."
        ]
    )

    # Use detailed evaluation method
    detailed_result = RuleHallucinationHHEM.evaluate_with_detailed_output(data)

    print("Detailed Rule-based Evaluation Results:")
    for key, value in detailed_result.items():
        print(f"  {key}: {value}")
    print()


def example_5_batch_evaluation_rule():
    """Example 5: Batch evaluation for efficiency with rules"""
    print("=== Example 5: Batch Rule-based HHEM Evaluation ===")

    # Multiple test cases
    data_list = [
        Data(
            data_id='rule_batch_1',
            prompt="Who invented the telephone?",
            content="Alexander Graham Bell invented the telephone in 1876.",
            context=["Alexander Graham Bell is credited with inventing the telephone."]
        ),
        Data(
            data_id='rule_batch_2',
            prompt="What is the speed of light?",
            content="The speed of light is approximately 300,000 kilometers per second.",
            context=["The speed of light in vacuum is approximately 299,792,458 meters per second."]
        ),
        Data(
            data_id='rule_batch_3',
            prompt="When was the moon landing?",
            content="The moon landing happened in 1970 during the Apollo 11 mission.",
            context=["The Apollo 11 mission landed on the moon on July 20, 1969."]
        )
    ]

    # Batch evaluation (more efficient for multiple items)
    results = RuleHallucinationHHEM.batch_evaluate(data_list)

    print("Batch Rule-based Evaluation Results:")
    for i, result in enumerate(results):
        print(f"  Item {i + 1}: Error={result.status}, Score={getattr(result, 'score', 'N/A'):.3f}")
    print()


def example_6_threshold_comparison_rule():
    """Example 6: Compare different threshold settings for rules"""
    print("=== Example 6: Rule-based Threshold Comparison ===")

    data = Data(
        data_id='rule_threshold_test',
        prompt="What is AI?",
        content="AI stands for Artificial Intelligence. It was invented by Alan Turing in 1950 and is primarily used for playing chess.",
        context=[
            "Artificial Intelligence (AI) refers to computer systems that can perform tasks typically requiring human intelligence.",
            "AI has many applications including natural language processing, computer vision, and robotics."
        ]
    )

    # Test with different thresholds
    thresholds = [0.3, 0.5, 0.7]
    original_threshold = RuleHallucinationHHEM.dynamic_config.threshold

    for threshold in thresholds:
        RuleHallucinationHHEM.dynamic_config.threshold = threshold
        result = RuleHallucinationHHEM.eval(data)

        print(f"Threshold {threshold}: Error={result.status}, Score={getattr(result, 'score', 'N/A'):.3f}")

    # Restore original threshold
    RuleHallucinationHHEM.dynamic_config.threshold = original_threshold
    print()


def example_7_performance_benchmark_rule():
    """Example 7: Performance benchmark for rule-based approach"""
    print("=== Example 7: Rule-based Performance Benchmark ===")

    import time

    data = Data(
        data_id='rule_perf_test',
        prompt="Describe machine learning",
        content="Machine learning is a subset of artificial intelligence that enables computers to learn and improve from experience without being explicitly programmed for every task.",
        context=[
            "Machine learning is a method of data analysis that automates analytical model building.",
            "It is a branch of artificial intelligence based on the idea that systems can learn from data."
        ]
    )

    # Measure inference time
    start_time = time.time()
    result = RuleHallucinationHHEM.eval(data)
    end_time = time.time()

    print(f"Rule-based HHEM Inference Time: {end_time - start_time:.3f} seconds")
    print(f"Result: Error={result.status}, Score={getattr(result, 'score', 'N/A'):.3f}")
    print(f"Model Info: Local HHEM-2.1-Open (Rule-based)")
    print()


if __name__ == "__main__":
    print("🔍 Dingo Rule-based HHEM-2.1-Open Hallucination Detection Examples")
    print("=" * 70)
    print()

    print("💡 Rule-based HHEM-2.1-Open Advantages:")
    print("- Better architecture: Rules for deterministic local models")
    print("- Local inference (no API costs)")
    print("- High performance (better than GPT-3.5/GPT-4 on benchmarks)")
    print("- Low resource usage (<600MB RAM)")
    print("- Fast inference (~1.5s for 2k tokens)")
    print()

    print("⚠️  First run will download the model (~400MB)")
    print("⚠️  Requires: pip install transformers")
    print()

    try:
        example_1_basic_rule_hhem_detection()
        example_2_no_hallucination_rule()
        example_3_complex_scenario_rule()
        example_4_detailed_output_rule()
        example_5_batch_evaluation_rule()
        example_6_threshold_comparison_rule()
        example_7_performance_benchmark_rule()

        print("🎉 All Rule-based HHEM examples completed successfully!")

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("Please install required dependencies: pip install transformers")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Please check your setup and try again")

    print()
    print("📈 Rule-based vs LLM-based Comparison:")
    print("- Architecture: Rule-based (✓) vs LLM-based (for API models)")
    print("- Performance: HHEM-2.1 > GPT-4 > GPT-3.5")
    print("- Cost: Rule-based (Free) vs LLM-based (API costs)")
    print("- Speed: Rule-based (~1.5s) vs LLM-based (3-10s)")
    print("- Privacy: Rule-based (Local) vs LLM-based (Cloud)")
    print("- Resource: Rule-based (<600MB) vs LLM-based (API dependency)")
