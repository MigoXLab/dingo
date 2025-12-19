# Dingo Hallucination Detection - Complete Guide

This guide introduces how to use integrated hallucination detection features in Dingo, supporting two detection methods: **HHEM-2.1-Open local model** (recommended) and **GPT-based cloud detection**.

## 🎯 Feature Overview

Hallucination detection evaluates whether LLM-generated responses contain factual contradictions with provided reference context. Particularly useful for:

- **RAG System Evaluation**: Detect consistency between generated responses and retrieved documents
- **SFT Data Quality Assessment**: Verify factual accuracy of responses in training data
- **LLM Output Verification**: Real-time detection of hallucination issues in model outputs

## 🔧 Core Principles

### Evaluation Process

1. **Data Preparation**: Provide response to detect and reference context
2. **Consistency Analysis**: Judge if response is consistent with each context
3. **Score Calculation**: Calculate overall hallucination score
4. **Threshold Judgment**: Decide if flagging is needed based on set threshold

### Scoring Mechanism

- **Score Range**: 0.0 - 1.0
- **Score Meaning**:
  - 0.0 = No hallucination
  - 1.0 = Complete hallucination
- **Default Threshold**: 0.5 (configurable)

## 📋 Usage Requirements

### Data Format Requirements

```python
from dingo.io.input import Data

data = Data(
    data_id="test_1",
    prompt="User's question",  # Original question (optional)
    content="LLM's response",  # Response to detect
    context=["Reference context 1", "Reference context 2"]  # Reference context (required)
)
```

### Supported Context Formats

```python
# Method 1: String list
context = ["Context 1", "Context 2", "Context 3"]

# Method 2: Single string
context = "Complete context text"

# Method 3: Dict with passages key
context = {"passages": ["Context 1", "Context 2"]}
```

## 🚀 Quick Start

### Method 1: HHEM-2.1-Open Local Model (Recommended ⭐)

**Advantages**:
- ✅ Fast speed
- ✅ No API costs
- ✅ Data privacy
- ✅ Can run offline

**Installation**:

```bash
# Install extra dependencies
pip install dingo-python[hhem]

# Or install dependencies manually
pip install sentence-transformers torch
```

**Usage**:

```python
from dingo.config.input_args import EvaluatorRuleArgs
from dingo.io.input import Data
from dingo.model.rule.rule_hallucination_hhem import RuleHallucinationHHEM

# Configure (first run will auto-download model ~400MB)
RuleHallucinationHHEM.dynamic_config = EvaluatorRuleArgs(
    threshold=0.5  # Hallucination threshold, higher = stricter
)

# Prepare data
data = Data(
    data_id="test_1",
    content="Paris is the capital of Germany.",  # Response to detect
    context=["Paris is the capital of France."]  # Reference context
)

# Execute detection
result = RuleHallucinationHHEM.eval(data)

# View results
print(f"Score: {result.score}")  # 0.0-1.0, higher = more hallucination
print(f"Has issues: {result.status}")  # True = has hallucination, False = no hallucination
print(f"Reason: {result.reason}")
```

**Output Example**:

```
Score: 0.85
Has issues: True
Reason: ['Hallucination detected (score: 0.85, threshold: 0.5). Inconsistent parts: Paris is capital of Germany (context states: Paris is capital of France)']
```

### Method 2: GPT-based Cloud Detection

**Advantages**:
- ✅ No local model download needed
- ✅ High-quality detection with powerful LLM
- ✅ Easy integration

**Usage**:

```python
import os
from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.llm_hallucination import LLMHallucination

# Configure LLM
LLMHallucination.dynamic_config = EvaluatorLLMArgs(
    key=os.getenv("OPENAI_API_KEY"),
    api_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    parameters={"threshold": 0.5}
)

# Prepare data
data = Data(
    data_id="test_1",
    content="Paris is the capital of Germany.",
    context=["Paris is the capital of France."]
)

# Execute detection
result = LLMHallucination.eval(data)

# View results
print(f"Score: {result.score}")
print(f"Has issues: {result.status}")
print(f"Reason: {result.reason}")
```

## 📊 Batch Processing

### Dataset Mode

```python
from dingo.config import InputArgs
from dingo.exec import Executor

input_data = {
    "task_name": "hallucination_detection",
    "input_path": "test/data/rag_responses.jsonl",
    "output_path": "outputs/",
    "dataset": {"source": "local", "format": "jsonl"},
    "executor": {
        "max_workers": 10,
        "result_save": {
            "good": True,
            "bad": True,
            "all_labels": True
        }
    },
    "evaluator": [
        {
            "fields": {
                "content": "response",
                "context": "retrieved_contexts"
            },
            "evals": [
                {
                    "name": "RuleHallucinationHHEM",  # Or "LLMHallucination"
                    "config": {"threshold": 0.5}
                }
            ]
        }
    ]
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
summary = executor.execute()

print(f"Total: {summary.total}")
print(f"Issues: {summary.num_bad}")
print(f"Pass rate: {summary.score}%")
```

### Data File Format (JSONL)

```jsonl
{"response": "Paris is the capital of France.", "retrieved_contexts": ["Paris is the capital of France.", "France is in Western Europe."]}
{"response": "Python was created by Guido van Rossum.", "retrieved_contexts": ["Python was designed by Guido van Rossum.", "Python was first released in 1991."]}
```

## ⚙️ Configuration Options

### Threshold Adjustment

```python
# Method 1: Rule-based (HHEM)
RuleHallucinationHHEM.dynamic_config = EvaluatorRuleArgs(
    threshold=0.5  # Range: 0.0-1.0
)

# Method 2: LLM-based
LLMHallucination.dynamic_config = EvaluatorLLMArgs(
    key="YOUR_API_KEY",
    api_url="https://api.openai.com/v1",
    model="gpt-4o-mini",
    parameters={"threshold": 0.5}  # Range: 0.0-1.0
)
```

**Threshold Recommendations**:
- **Strict scenarios** (finance, medical): 0.3-0.4
- **General scenarios** (Q&A systems): 0.5-0.6
- **Loose scenarios** (creative content): 0.7-0.8

### Device Selection (HHEM Only)

```python
# Auto-select (default: uses GPU if available)
RuleHallucinationHHEM.dynamic_config = EvaluatorRuleArgs()

# Force CPU
import torch
RuleHallucinationHHEM.device = "cpu"

# Force GPU
RuleHallucinationHHEM.device = "cuda"

# Specific GPU
RuleHallucinationHHEM.device = "cuda:0"
```

## 📈 Performance Comparison

| Feature | HHEM-2.1-Open | GPT-based |
|---------|---------------|-----------|
| **Speed** | Fast (~50ms/sample) | Slower (~1-2s/sample) |
| **Cost** | Free | API costs |
| **Accuracy** | High (F1: 0.84) | Very High |
| **Privacy** | Local, secure | Data sent to API |
| **Deployment** | Needs model download (~400MB) | Needs API key |
| **Offline** | ✅ Supported | ❌ Requires network |

**Recommendations**:
- **Production environment**: HHEM-2.1-Open (fast, free, private)
- **High-precision scenarios**: GPT-based (highest accuracy)
- **Offline scenarios**: HHEM-2.1-Open (can run completely offline)

## 🌟 Best Practices

### 1. Context Quality

**Good Context**:
```python
context = [
    "Paris is the capital of France, located in northern France.",
    "France is a country in Western Europe with a population of about 67 million."
]
```

**Poor Context**:
```python
context = [
    "Paris",  # Too short, lacks information
    "France has many cities."  # Too vague
]
```

### 2. Handling Multiple Contexts

```python
# When multiple contexts exist, system automatically analyzes consistency with each
data = Data(
    content="Paris is the capital of France and the largest city in France.",
    context=[
        "Paris is the capital of France.",  # Supports first half
        "Paris is the largest city in France."  # Supports second half
    ]
)
```

### 3. Iterative Optimization

1. **Initial Testing**: Use default threshold (0.5)
2. **Analyze Results**: Check for false positives/negatives
3. **Adjust Threshold**: Refine based on business needs
4. **Verify Effects**: Re-test with new threshold

### 4. Integration with RAG Evaluation

```python
"evaluator": [
    {
        "fields": {
            "prompt": "user_input",
            "content": "response",
            "context": "retrieved_contexts"
        },
        "evals": [
            {"name": "LLMRAGFaithfulness"},       # Faithfulness (based on LLM)
            {"name": "RuleHallucinationHHEM"},    # Hallucination (model-based)
            {"name": "LLMRAGAnswerRelevancy"}     # Answer relevance
        ]
    }
]
```

## ❓ FAQ

### Q1: HHEM vs GPT-based, which to choose?

- **Production/large-scale**: HHEM (fast, free, private)
- **High-precision evaluation**: GPT-based (highest accuracy, but has costs)
- **Offline scenarios**: HHEM (can run completely offline)

### Q2: Why does HHEM download model on first run?

HHEM uses Sentence-Transformers model (~400MB), auto-downloads and caches on first run. Subsequent runs load directly from cache, no re-download needed.

### Q3: What if model download fails?

```bash
# Manually download
huggingface-cli download vectara/hallucination_evaluation_model --local-dir ~/.cache/huggingface/hub/models--vectara--hallucination_evaluation_model

# Or use mirror
export HF_ENDPOINT=https://hf-mirror.com
```

### Q4: How to interpret scores?

- **0.0-0.3**: Low hallucination risk, response highly consistent with context
- **0.3-0.5**: Moderate risk, some parts may be inconsistent, needs attention
- **0.5-0.7**: High risk, significant inconsistencies, needs review
- **0.7-1.0**: Severe hallucination, response seriously contradicts context

## 📖 Related Documents

- [RAG Evaluation Metrics Guide](rag_evaluation_metrics.md)
- [Factuality Assessment Guide](factuality_assessment_guide.md)
- [HHEM Paper](https://arxiv.org/abs/2406.09053)

## 📝 Example Scenarios

### Scenario 1: Detect Factual Errors

```python
data = Data(
    content="Python was released in 1995 by James Gosling.",  # Wrong: year and author
    context=["Python was created by Guido van Rossum and first released in 1991."]
)

result = RuleHallucinationHHEM.eval(data)
# Expected: High score (>0.7), detected as having hallucination
```

### Scenario 2: Detect Partial Hallucination

```python
data = Data(
    content="Machine learning is a branch of AI. It was invented in the 1950s by Alan Turing.",  # First sentence correct, second incorrect
    context=["Machine learning is a subfield of artificial intelligence."]
)

result = RuleHallucinationHHEM.eval(data)
# Expected: Moderate score (0.4-0.6), partial hallucination
```

### Scenario 3: Verify No Hallucination

```python
data = Data(
    content="Deep learning is a subset of machine learning that uses multi-layer neural networks.",
    context=["Deep learning is part of machine learning, characterized by using multi-layer neural networks."]
)

result = RuleHallucinationHHEM.eval(data)
# Expected: Low score (<0.3), no hallucination
```
