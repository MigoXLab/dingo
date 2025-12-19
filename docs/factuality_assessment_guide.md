# Dingo Factuality Assessment - Complete Guide

This guide introduces how to use integrated factuality assessment features in Dingo to evaluate factual accuracy of LLM-generated content.

## 🎯 Feature Overview

Factuality assessment evaluates whether LLM-generated responses contain factual errors or unverifiable claims. Particularly useful for:

- **Content Quality Control**: Verify accuracy of generated content
- **Knowledge Base Validation**: Ensure knowledge base information is accurate
- **Training Data Filtering**: Filter out factually incorrect training samples
- **Real-time Output Verification**: Check factual accuracy of model outputs

## 🔧 Core Principles

### Evaluation Process

1. **Claim Extraction**: Break down response into independent factual claims
2. **Fact Verification**: Verify each claim against reference materials or knowledge base
3. **Score Calculation**: Calculate overall factuality score
4. **Issue Identification**: Identify specific factual errors

### Scoring Mechanism

- **Score Range**: 0.0 - 10.0
- **Score Meaning**:
  - 8.0-10.0 = High factual accuracy
  - 5.0-7.9 = Moderate accuracy, some errors
  - 0.0-4.9 = Low accuracy, significant errors
- **Default Threshold**: 5.0 (configurable)

## 📋 Usage Requirements

### Data Format Requirements

```python
from dingo.io.input import Data

data = Data(
    data_id="test_1",
    prompt="User's question",  # Original question (optional)
    content="LLM's response",  # Response to assess
    context=["Reference material 1", "Reference material 2"]  # Reference materials (optional but recommended)
)
```

## 🚀 Quick Start

### SDK Mode - Single Assessment

```python
import os
from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.llm_factcheck import LLMFactCheck

# Configure LLM
LLMFactCheck.dynamic_config = EvaluatorLLMArgs(
    key=os.getenv("OPENAI_API_KEY"),
    api_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    parameters={"threshold": 5.0}
)

# Prepare data
data = Data(
    data_id="test_1",
    prompt="When was Python released?",
    content="Python was released in 1991 by Guido van Rossum.",
    context=["Python was created by Guido van Rossum.", "Python was first released in 1991."]
)

# Execute assessment
result = LLMFactCheck.eval(data)

# View results
print(f"Score: {result.score}/10")
print(f"Has issues: {result.status}")  # True = below threshold, False = passed
print(f"Reason: {result.reason[0]}")
```

### Dataset Mode - Batch Assessment

```python
from dingo.config import InputArgs
from dingo.exec import Executor

input_data = {
    "task_name": "factuality_assessment",
    "input_path": "test/data/responses.jsonl",
    "output_path": "outputs/",
    "dataset": {"source": "local", "format": "jsonl"},
    "executor": {
        "max_workers": 10,
        "result_save": {"good": True, "bad": True, "all_labels": True}
    },
    "evaluator": [
        {
            "fields": {
                "prompt": "question",
                "content": "response",
                "context": "references"
            },
            "evals": [
                {
                    "name": "LLMFactCheck",
                    "config": {
                        "model": "gpt-4o-mini",
                        "key": "YOUR_API_KEY",
                        "api_url": "https://api.openai.com/v1",
                        "parameters": {"threshold": 5.0}
                    }
                }
            ]
        }
    ]
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
summary = executor.execute()

print(f"Total: {summary.total}")
print(f"Passed: {summary.num_good}")
print(f"Issues: {summary.num_bad}")
print(f"Pass rate: {summary.score}%")
```

### Data File Format (JSONL)

```jsonl
{"question": "When was Python released?", "response": "Python was released in 1991 by Guido van Rossum.", "references": ["Python was created by Guido van Rossum.", "Python first appeared in 1991."]}
{"question": "What is the capital of France?", "response": "The capital of France is Paris.", "references": ["Paris is the capital and largest city of France."]}
```

## ⚙️ Configuration Options

### Threshold Adjustment

```python
LLMFactCheck.dynamic_config = EvaluatorLLMArgs(
    key="YOUR_API_KEY",
    api_url="https://api.openai.com/v1",
    model="gpt-4o-mini",
    parameters={"threshold": 5.0}  # Range: 0.0-10.0
)
```

**Threshold Recommendations**:
- **Strict scenarios** (medical, legal): threshold 7.0-8.0
- **General scenarios** (Q&A, documentation): threshold 5.0-6.0
- **Loose scenarios** (creative content, brainstorming): threshold 3.0-4.0

### Model Selection

```python
# Option 1: GPT-4 (highest accuracy, higher cost)
LLMFactCheck.dynamic_config = EvaluatorLLMArgs(
    model="gpt-4o",
    key="YOUR_API_KEY",
    api_url="https://api.openai.com/v1"
)

# Option 2: GPT-4o-mini (balanced, recommended)
LLMFactCheck.dynamic_config = EvaluatorLLMArgs(
    model="gpt-4o-mini",
    key="YOUR_API_KEY",
    api_url="https://api.openai.com/v1"
)

# Option 3: Alternative LLM (DeepSeek, etc.)
LLMFactCheck.dynamic_config = EvaluatorLLMArgs(
    model="deepseek-chat",
    key="YOUR_API_KEY",
    api_url="https://api.deepseek.com"
)
```

## 📊 Output Format

### SDK Mode Output

```python
result = LLMFactCheck.eval(data)

# Basic information
result.score          # Score: 0.0-10.0
result.status         # Has issues: True (below threshold) / False (passed)
result.label          # Labels: ["QUALITY_GOOD.FACTCHECK_PASS"] or ["QUALITY_BAD.FACTCHECK_FAIL"]
result.reason         # Detailed reasons
result.metric         # Metric name: "LLMFactCheck"
```

**Output Example (Passed)**:
```python
result.score = 8.5
result.status = False  # False = passed
result.label = ["QUALITY_GOOD.FACTCHECK_PASS"]
result.reason = ["Factual accuracy assessment passed (score: 8.5/10). All claims verified: Python was released in 1991, Creator is Guido van Rossum."]
```

**Output Example (Failed)**:
```python
result.score = 3.2
result.status = True  # True = failed
result.label = ["QUALITY_BAD.FACTCHECK_FAIL"]
result.reason = ["Factual accuracy assessment failed (score: 3.2/10). Errors detected: Python was not released in 1995 (correct: 1991)"]
```

## 🌟 Best Practices

### 1. Provide High-quality Reference Materials

**Good References**:
```python
context = [
    "Python was created by Guido van Rossum and first released in February 1991.",
    "Python is an interpreted, high-level programming language.",
    "Python 2.0 was released in 2000, Python 3.0 was released in 2008."
]
```

**Poor References**:
```python
context = [
    "Python",  # Too brief
    "Python is a programming language"  # Lacks details
]
```

### 2. Suitable Use Cases

**✅ Suitable for**:
- Verifiable factual claims (dates, names, numbers, events)
- Historical facts
- Technical specifications
- Statistical data

**❌ Not suitable for**:
- Subjective opinions
- Future predictions
- Creative content
- Open-ended questions

### 3. Combined Use with Other Metrics

```python
"evaluator": [
    {
        "fields": {
            "prompt": "user_input",
            "content": "response",
            "context": "retrieved_contexts"
        },
        "evals": [
            {"name": "LLMRAGFaithfulness"},       # Answer faithfulness
            {"name": "LLMFactCheck"},             # Factual accuracy
            {"name": "RuleHallucinationHHEM"}     # Hallucination detection
        ]
    }
]
```

### 4. Iterative Optimization

1. **Initial Testing**: Use default threshold (5.0)
2. **Analyze Results**: Review false positives and false negatives
3. **Adjust Threshold**: Fine-tune based on business requirements
4. **Re-validate**: Test with new threshold

## 📈 Metric Comparison

| Metric | Purpose | Score Range | Requires Reference | Best For |
|--------|---------|-------------|-------------------|----------|
| **Factuality** | Verify factual accuracy | 0-10 | Optional (recommended) | Fact verification, knowledge base validation |
| **Faithfulness** | Check if based on context | 0-10 | Yes | RAG systems, prevent hallucinations |
| **Hallucination** | Detect contradictions with context | 0-1 | Yes | Fast hallucination detection |

**Recommendations**:
- **RAG evaluation**: Combine Faithfulness + Hallucination + Factuality
- **Content generation**: Use Factuality alone
- **Real-time verification**: Prioritize Hallucination (fast) or Faithfulness

## ❓ FAQ

### Q1: Difference between Factuality and Faithfulness?

- **Factuality**: Verifies if content is factually correct (can use external knowledge)
- **Faithfulness**: Checks if response is based on provided context (only looks at context-response relationship)

### Q2: What if no reference materials provided?

LLM will use its internal knowledge for verification, but accuracy may be lower. **Recommendation**: Always provide reference materials for best results.

### Q3: How to handle domain-specific facts?

1. Provide domain-specific reference materials in `context`
2. Use domain-specific LLM models
3. Lower threshold to reduce false positives

### Q4: How to interpret scores?

- **8.0-10.0**: High accuracy, all or most facts verified
- **5.0-7.9**: Moderate accuracy, some errors or unverifiable claims
- **3.0-4.9**: Low accuracy, multiple errors
- **0.0-2.9**: Very low accuracy, serious factual errors

## 📖 Related Documents

- [RAG Evaluation Metrics Guide](rag_evaluation_metrics.md)
- [Hallucination Detection Guide](hallucination_detection_guide.md)
- [Response Quality Evaluation](../README.md#evaluation-metrics)

## 📝 Example Scenarios

### Scenario 1: Verify Historical Facts

```python
data = Data(
    content="Python was released in 1991 by Guido van Rossum at CWI in the Netherlands.",
    context=[
        "Python was created by Guido van Rossum.",
        "Python was first released in February 1991.",
        "Guido van Rossum began working on Python at CWI."
    ]
)

result = LLMFactCheck.eval(data)
# Expected: High score (>8.0), all facts verified
```

### Scenario 2: Detect Factual Errors

```python
data = Data(
    content="Python was released in 1995 by James Gosling.",  # Wrong year and author
    context=[
        "Python was created by Guido van Rossum.",
        "Python was first released in 1991."
    ]
)

result = LLMFactCheck.eval(data)
# Expected: Low score (<4.0), multiple errors detected
```

### Scenario 3: Assess Partially Correct Content

```python
data = Data(
    content="Python 3.0 was released in 2008. It introduced many breaking changes and removed backward compatibility with Python 2.x.",
    context=[
        "Python 3.0 was released on December 3, 2008.",
        "Python 3.0 was not backward compatible with Python 2.x series."
    ]
)

result = LLMFactCheck.eval(data)
# Expected: High score (7-9), facts mostly correct with minor imprecisions
```

### Scenario 4: Handle Unverifiable Claims

```python
data = Data(
    content="Python will become the most popular programming language in 2030.",  # Future prediction
    context=["Python is currently one of the most popular programming languages."]
)

result = LLMFactCheck.eval(data)
# Expected: Moderate score (4-6), future prediction cannot be verified
```
