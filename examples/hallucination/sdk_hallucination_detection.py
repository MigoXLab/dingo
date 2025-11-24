"""
Dingo Hallucination Detection Example

This example demonstrates how to use the integrated hallucination detection capability
based on DeepEval's HallucinationMetric, adapted for Dingo's architecture.

The hallucination detector evaluates whether LLM responses contain factual contradictions
against provided reference contexts.
"""

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.llm_hallucination import LLMHallucination

# Configure LLM
LLMHallucination.dynamic_config = EvaluatorLLMArgs(
    key='sk-xxx',
    api_url='https://api.deepseek.com',
    model='deepseek-chat',
)


def example_1_basic_hallucination_detection():
    """Example 1: Basic hallucination detection with single context"""
    print("=== Example 1: Basic Hallucination Detection ===")

    # Test case with hallucination (incorrect date)
    data = Data(
        data_id='hallucination_test_1',
        prompt="When did Einstein win the Nobel Prize?",
        content="Einstein won the Nobel Prize in 1969 for his discovery of the photoelectric effect.",
        context='["Einstein won the Nobel Prize for his discovery of the photoelectric effect.", "Einstein won the Nobel Prize in 1921."]'
    )

    result = LLMHallucination.eval(data)

    print(f"Error Status: {result.eval_status}")
    # print(f"Type: {result.type}")
    # print(f"Name: {result.name}")
    print(f"Type: {result.eval_details}")
    print(f"Reason: {result.reason[0]}")
    print(f"Score: {getattr(result, 'score', 'N/A')}")
    print()


def example_2_no_hallucination():
    """Example 2: Response that aligns with context (no hallucination)"""
    print("=== Example 2: No Hallucination Detected ===")

    # Test case without hallucination
    data = Data(
        data_id='no_hallucination_test',
        prompt="What is the capital of France?",
        content="The capital of France is Paris, which is located in the north-central part of the country.",
        context='["Paris is the capital and most populous city of France.", "Paris is located in north-central France."]'
    )

    result = LLMHallucination.eval(data)

    print(f"Error Status: {result.eval_status}")
    # print(f"Type: {result.type}")
    # print(f"Name: {result.name}")
    print(f"Type: {result.eval_details}")
    print(f"Reason: {result.reason[0]}")
    print(f"Score: {getattr(result, 'score', 'N/A')}")
    print()


def example_3_multiple_contexts():
    """Example 3: Multiple contexts with mixed verdicts"""
    print("=== Example 3: Multiple Contexts Assessment ===")

    contexts = [
        "The Great Wall of China is visible from space with the naked eye.",
        "The Great Wall of China was built over many centuries.",
        "The Great Wall of China is approximately 21,000 kilometers long.",
        "The Great Wall was built primarily during the Ming Dynasty."
    ]

    data = Data(
        data_id='multiple_contexts_test',
        prompt="Tell me about the Great Wall of China",
        content="The Great Wall of China is an ancient fortification that was built over many centuries, primarily during the Ming Dynasty. It stretches approximately 21,000 kilometers across northern China. Contrary to popular belief, it is not visible from space with the naked eye.",
        context=contexts
    )

    result = LLMHallucination.eval(data)

    print(f"Error Status: {result.eval_status}")
    # print(f"Type: {result.type}")
    # print(f"Name: {result.name}")
    print(f"Type: {result.eval_details}")
    print(f"Score: {getattr(result, 'score', 'N/A')}")
    # print(f"Verdict Details:")
    # for detail in getattr(result, 'verdict_details', []):
    #     print(f"  - {detail}")
    print()


def example_4_rag_scenario():
    """Example 4: RAG scenario with retrieved context"""
    print("=== Example 4: RAG Scenario ===")

    # Simulating a RAG scenario where contexts are retrieved documents
    retrieved_contexts = [
        "Photosynthesis is the process by which plants convert sunlight into chemical energy.",
        "During photosynthesis, plants absorb carbon dioxide from the air and water from the soil.",
        "The main products of photosynthesis are glucose and oxygen.",
        "Photosynthesis occurs primarily in the chloroplasts of plant cells."
    ]

    data = Data(
        data_id='rag_test',
        prompt="Explain how photosynthesis works",
        content="Photosynthesis is the process where plants use sunlight to convert water and carbon dioxide into glucose and oxygen. This process mainly happens in the chloroplasts of plant cells. However, the main product is actually carbon monoxide, not oxygen.",
        context=retrieved_contexts
    )

    result = LLMHallucination.eval(data)

    print(f"Error Status: {result.eval_status}")
    # print(f"Type: {result.type}")
    # print(f"Name: {result.name}")
    print(f"Type: {result.eval_details}")
    print(f"Score: {getattr(result, 'score', 'N/A')}")
    print("Detailed Analysis:")
    print(result.reason[0])
    print()


def example_5_missing_context():
    """Example 5: Error handling when context is missing"""
    print("=== Example 5: Missing Context Handling ===")

    data = Data(
        data_id='missing_context_test',
        prompt="What is artificial intelligence?",
        content="Artificial intelligence is a field of computer science that aims to create intelligent machines."
        # Note: no context provided
    )

    result = LLMHallucination.eval(data)

    print(f"Error Status: {result.eval_status}")
    # print(f"Type: {result.type}")
    # print(f"Name: {result.name}")
    print(f"Type: {result.eval_details}")
    print(f"Reason: {result.reason[0]}")
    print()


def example_6_clear_hallucination():
    """Example 6: Clear hallucination case that triggers eval_status=True"""
    print("=== Example 6: Clear Hallucination (Error Triggered) ===")

    # Create a case where the response clearly contradicts multiple contexts
    contexts = [
        "水的沸点在标准大气压下是100摄氏度。",
        "水在0摄氏度时结冰。",
        "水是无色无味的液体。",
        "水的化学分子式是H2O。"
    ]

    data = Data(
        data_id='clear_hallucination_test',
        prompt="请介绍一下水的基本性质",
        content="水是一种红色的液体，在标准大气压下沸点是150摄氏度，结冰点是-10摄氏度。水的分子式是H3O，具有强烈的甜味。这些都是水的基本物理和化学性质。",
        context=contexts
    )

    result = LLMHallucination.eval(data)

    print(f"Error Status: {result.eval_status}")
    # print(f"Type: {result.type}")
    # print(f"Name: {result.name}")
    print(f"Type: {result.eval_details}")
    print(f"Score: {getattr(result, 'score', 'N/A')}")
    print("Detailed Analysis:")
    print(result.reason[0])
    # if hasattr(result, 'verdict_details'):
    #     print("Verdict Details:")
    #     for detail in result.verdict_details:
    #         print(f"  - {detail}")
    print()


if __name__ == "__main__":
    print("🔍 Dingo Hallucination Detection Examples")
    print("=" * 50)
    print()

    # Note: Make sure to set your API key before running
    print("⚠️  Please set your OpenAI API key in the EvaluatorLLMArgs before running these examples!")
    print()

    # example_1_basic_hallucination_detection()
    # example_2_no_hallucination()
    # example_3_multiple_contexts()
    # example_4_rag_scenario()
    # example_5_missing_context()
    example_6_clear_hallucination()

    print("🎉 Selected examples completed!")
    print()
    print("💡 Key Features:")
    print("- Verdict-based evaluation for each context")
    print("- Numerical hallucination score (0.0 = no hallucination, 1.0 = full hallucination)")
    print("- Configurable threshold for error detection")
    print("- Detailed reasoning for each assessment")
    print("- Support for multiple contexts (RAG scenarios)")
    print("- Error handling for missing context")
