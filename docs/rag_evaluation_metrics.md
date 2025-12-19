# RAG Evaluation Metrics - Complete Guide

## 🎯 Overview

Dingo's RAG evaluation metrics system is based on best practices from the [RAGAS paper](https://arxiv.org/abs/2309.15217), DeepEval, and TruLens, providing comprehensive RAG system evaluation capabilities.

### ✅ Supported Metrics (5/5)

| Metric | Evaluation Dimension | Required Fields | Source |
|--------|---------------------|-----------------|--------|
| **Faithfulness** | Answer Faithfulness | user_input, response, retrieved_contexts | RAGAS |
| **Answer Relevancy** | Answer Relevance | user_input, response | RAGAS |
| **Context Relevancy** | Context Relevance | user_input, retrieved_contexts | RAGAS + DeepEval + TruLens |
| **Context Recall** | Context Recall | user_input, retrieved_contexts, reference | RAGAS |
| **Context Precision** | Context Precision | user_input, retrieved_contexts, reference | RAGAS |

## 🚀 Quick Start

### 1. Run Examples

```bash
# Dataset mode - batch evaluation (recommended)
python examples/rag/dataset_rag_eval_baseline.py

# SDK mode - single evaluation
python examples/rag/sdk_rag_eval.py

# Simulate RAG system and evaluate
python examples/rag/e2e_RAG_eval_with_mockRAG_fiqa.py
```

### 2. SDK Mode - Single Evaluation

```python
import os
from dingo.config.input_args import EvaluatorLLMArgs, EmbeddingConfigArgs
from dingo.io.input import Data
from dingo.model.llm.rag.llm_rag_faithfulness import LLMRAGFaithfulness

# Configure LLM
LLMRAGFaithfulness.dynamic_config = EvaluatorLLMArgs(
    key=os.getenv("OPENAI_API_KEY"),
    api_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
)

# Prepare data
data = Data(
    data_id="example_1",
    prompt="What is machine learning?",
    content="Machine learning is a branch of AI that enables computers to learn from data.",
    context=[
        "Machine learning is a subfield of AI.",
        "ML systems learn from data without explicit programming."
    ]
)

# Evaluate
result = LLMRAGFaithfulness.eval(data)

# View results
print(f"Score: {result.score}/10")
print(f"Passed: {not result.status}")  # status=False means passed
print(f"Reason: {result.reason[0]}")
```

### 3. Dataset Mode - Batch Evaluation

```python
from dingo.config import InputArgs
from dingo.exec import Executor

# Configuration
llm_config = {
    "model": "gpt-4o-mini",
    "key": "YOUR_API_KEY",
    "api_url": "https://api.openai.com/v1",
}

llm_config_embedding = {
    "model": "gpt-4o-mini",
    "key": "YOUR_API_KEY",
    "api_url": "https://api.openai.com/v1",
    "embedding_config": {  # ⭐ Required for Answer Relevancy
        "model": "text-embedding-3-large",
        "api_url": "https://api.openai.com/v1",
        "key": "YOUR_API_KEY"
    },
    "parameters": {
        "strictness": 3,
        "threshold": 5
    }
}

input_data = {
    "task_name": "rag_evaluation",
    "input_path": "test/data/fiqa.jsonl",
    "output_path": "outputs/",
    "dataset": {"source": "local", "format": "jsonl"},
    "executor": {
        "max_workers": 10,
        "result_save": {"good": True, "bad": True, "all_labels": True}
    },
    "evaluator": [
        {
            "fields": {
                "prompt": "user_input",
                "content": "response",
                "context": "retrieved_contexts",
                "reference": "reference"
            },
            "evals": [
                {"name": "LLMRAGFaithfulness", "config": llm_config},
                {"name": "LLMRAGAnswerRelevancy", "config": llm_config_embedding},
                {"name": "LLMRAGContextRelevancy", "config": llm_config},
                {"name": "LLMRAGContextRecall", "config": llm_config},
                {"name": "LLMRAGContextPrecision", "config": llm_config}
            ]
        }
    ]
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
summary = executor.execute()
```

## 📋 Data Format

### Required Fields

| Metric | user_input | response | retrieved_contexts | reference | Notes |
|--------|-----------|----------|-------------------|-----------|-------|
| **Faithfulness** | ✅ | ✅ | ✅ | - | Measures if answer is based on context |
| **Answer Relevancy** | ✅ | ✅ | - | - | Measures if answer addresses the question |
| **Context Relevancy** | ✅ | - | ✅ | - | Measures if retrieved contexts are relevant |
| **Context Recall** | ✅ | - | ✅ | ✅ | Measures if all needed info is retrieved |
| **Context Precision** | ✅ | - | ✅ | ✅ | Measures ranking quality of retrieved contexts |

### Data Example (JSONL)

```jsonl
{"user_input": "What is deep learning?", "response": "Deep learning uses neural networks...", "retrieved_contexts": ["Deep learning is a subset of ML...", "Deep learning is used for image recognition..."]}
{"user_input": "Python features?", "response": "Python is concise and has rich libraries.", "retrieved_contexts": ["Python has clean syntax.", "Python has NumPy and other libraries."], "reference": "Python has clean syntax and a rich ecosystem."}
```

## ⚙️ Configuration

### Configurable Parameters

| Parameter | Applicable Metrics | Default | Description |
|-----------|-------------------|---------|-------------|
| `threshold` | All metrics | 5.0 | Pass threshold (0-10) |
| `strictness` | Answer Relevancy | 3 | Number of questions to generate (1-5) |
| `embedding_config` | Answer Relevancy | - | **Required**: includes `model`, `api_url`, `key` |

### Embedding Configuration (Answer Relevancy)

`LLMRAGAnswerRelevancy` **requires `embedding_config`**:

**Option 1: Cloud LLM + Cloud Embedding**

```python
"config": {
    "model": "deepseek-chat",
    "key": "YOUR_API_KEY",
    "api_url": "https://api.deepseek.com",
    "embedding_config": {  # ⭐ Required
        "model": "text-embedding-3-large",
        "api_url": "https://api.deepseek.com",
        "key": "YOUR_API_KEY"
    },
    "parameters": {"strictness": 3, "threshold": 5}
}
```

**Option 2: Cloud LLM + Local Embedding (Recommended: Cost-effective)**

```python
"config": {
    "model": "deepseek-chat",
    "key": "YOUR_API_KEY",
    "api_url": "https://api.deepseek.com",
    "embedding_config": {  # ⭐ Independent embedding service
        "model": "BAAI/bge-m3",
        "api_url": "http://localhost:8000/v1",  # Local vLLM/Xinference
        "key": "dummy-key"
    },
    "parameters": {"strictness": 3, "threshold": 5}
}
```

**Deploy Local Embedding (vLLM)**:

```bash
pip install vllm
python -m vllm.entrypoints.openai.api_server \
  --model BAAI/bge-m3 \
  --port 8000 \
  --host 0.0.0.0
```

**What happens if not configured?**

Runtime exception:

```
ValueError: Embedding model not initialized. Please configure 'embedding_config' in your LLM config with:
  - model: embedding model name (e.g., 'BAAI/bge-m3')
  - api_url: embedding service URL
  - key: API key (optional for local services)
```

## 📊 Metric Details

### 1️⃣ Faithfulness (Answer Faithfulness)

**Evaluation Goal**: Measure if the answer is entirely based on retrieved context, avoiding hallucinations

**Calculation**:
1. Break down answer into independent statements (claims)
2. Judge if each statement is supported by context
3. Faithfulness score = (Supported statements / Total statements) × 10

**Formula**:
```
Faithfulness = (Context-supported claims / Total claims) × 10
```

**Recommended Threshold**: 7 (out of 10)

---

### 2️⃣ Answer Relevancy (Answer Relevance)

**Evaluation Goal**: Measure if the answer directly addresses the user question

**Calculation**:
1. Generate N reverse questions from the answer (questions inferred by LLM from the answer)
2. Calculate cosine similarity between embeddings of generated questions and original question
3. Answer Relevancy = Average of all similarities

**Formula**:
```
Answer Relevancy = (1/N) × Σ cosine_sim(E_gi, E_o)

Where:
- N: Number of generated questions, default 3 (adjustable via strictness parameter)
- E_gi: Embedding of the i-th generated question
- E_o: Embedding of the original question
```

**⚠️ Important**: This metric **requires `embedding_config`**:
- `model`: Embedding model name (e.g., `text-embedding-3-large`, `BAAI/bge-m3`)
- `api_url`: Embedding service address
- `key`: API key (optional for local services)

**Recommended Threshold**: 5 (out of 10)

---

### 3️⃣ Context Relevancy (Context Relevance)

**Evaluation Goal**: Measure if retrieved contexts are relevant to the question

**Calculation**:
Uses a **Dual-Judge System** from NVIDIA research:

**Judge 1 Scoring**:
- **0** = Context completely irrelevant
- **1** = Context partially relevant
- **2** = Context fully relevant

**Judge 2 Scoring**:
- Uses different prompt wording for another perspective
- Same 0-2 scoring standard
- Purpose: Reduce single-prompt bias

**Final Score**:
```
Context Relevancy = (Relevant contexts / Total contexts) × 10

Where:
- Relevant context: Average score from both judges ≥ threshold (default 1.0)
- Irrelevant context: Average score < threshold
```

**Recommended Threshold**: 5 (out of 10)

---

### 4️⃣ Context Recall (Context Recall)

**Evaluation Goal**: Measure if all needed information is retrieved (requires reference answer)

**Calculation**:
1. Extract independent statements from reference answer
2. Judge if each statement can be attributed from retrieved contexts
3. Recall = (Context-supported reference statements / Total reference statements) × 10

**Formula**:
```
Context Recall = (Context-supported reference claims / Total reference claims) × 10
```

**Note**: **Requires reference answer (reference)**, typically used in evaluation phase

**Recommended Threshold**: 5 (out of 10)

---

### 5️⃣ Context Precision (Context Precision)

**Evaluation Goal**: Measure ranking quality of retrieval results, whether relevant docs are at the top (requires reference answer)

**Calculation**:
1. For each position k, judge if the context is relevant (supports reference answer)
2. Calculate Precision@k for each position
3. Use relevance indicator (v_k) for weighted sum

**Formula**:
```
Context Precision = Σ(Precision@k × v_k) / Total relevant items in top K

Where:
- K: Total retrieved documents, e.g., 5 documents
- k: Current position (1st, 2nd, 3rd, ..., K-th)
- v_k: Relevance indicator, 0 (irrelevant) or 1 (relevant)
- Precision@k: Precision in first k documents, 0.0 to 1.0
- Precision@k = Relevant count in first k / k
```

**Note**: **Requires reference answer (reference)** to judge which contexts are relevant

**Recommended Threshold**: 5 (out of 10)

## 🌟 Best Practices

### 1. Metric Combinations

**Complete Evaluation** (5 metrics):
```python
"evals": [
    {"name": "LLMRAGFaithfulness"},       # Detect hallucinations
    {"name": "LLMRAGAnswerRelevancy"},    # Check answer relevance
    {"name": "LLMRAGContextRelevancy"},   # Check context noise
    {"name": "LLMRAGContextRecall"},      # Evaluate retrieval completeness
    {"name": "LLMRAGContextPrecision"}    # Evaluate retrieval ranking
]
```

**Production Environment** (no reference needed):
```python
"evals": [
    {"name": "LLMRAGFaithfulness"},       # ⭐ Most important: prevent hallucinations
    {"name": "LLMRAGAnswerRelevancy"},    # Ensure direct answers
    {"name": "LLMRAGContextRelevancy"}    # Check retrieval noise
]
```

**Evaluation Phase** (requires reference):
```python
"evals": [
    {"name": "LLMRAGContextRecall"},      # Evaluate retrieval completeness
    {"name": "LLMRAGContextPrecision"}    # Evaluate retrieval ranking
]
```

### 2. Threshold Adjustment

Adjust thresholds (default 5) based on scenario:

- **Strict scenarios** (finance, medical): threshold 7-8
- **General scenarios** (Q&A systems): threshold 5-6
- **Loose scenarios** (exploratory search): threshold 3-4

### 3. Iterative Optimization

1. **Initial Evaluation**: Evaluate current system with all 5 metrics
2. **Identify Issues**:
   - **Low Faithfulness** → Generation model produces hallucinations
     - Optimize: Adjust generation prompts, use stronger models, enhance fact-checking
   - **Low Answer Relevancy** → Answer off-topic or contains irrelevant info
     - Optimize: Improve generation prompts, limit answer length, enhance question understanding
   - **Low Context Relevancy** → Retrieval introduces noise
     - Optimize: Improve retrieval algorithm, adjust similarity threshold, improve embedding model
   - **Low Context Recall** → Retrieval misses important info
     - Optimize: Increase Top-K, improve query rewriting, expand knowledge base
   - **Low Context Precision** → Relevant docs ranked lower
     - Optimize: Improve ranking algorithm, adjust reranker, improve relevance calculation
3. **Targeted Optimization**: Adjust components based on issues
4. **Re-evaluate**: Verify optimization effects
5. **Continuous Monitoring**: Monitor key metrics in production

### 4. Important Notes

- **LLM Dependency**: All metrics depend on LLM API, requiring correct API key and endpoint
- **Embedding Dependency**:
  - Answer Relevancy **requires `embedding_config`**: `model`, `api_url`, `key`
  - Can use cloud services (OpenAI, DeepSeek) or local deployment (vLLM, Xinference)
  - Not configuring will throw exception: `ValueError: Embedding model not initialized...`
- **Cost Considerations**: Evaluation generates API costs, recommendations:
  - Development: Sample evaluation (50-100 samples)
  - Production: Use key metrics only (Faithfulness, Answer Relevancy, Context Relevancy)
  - Evaluation: Full evaluation of all metrics
- **Reference Requirements**:
  - Context Recall and Context Precision **require** reference
  - Other three metrics don't need reference
  - Reference mainly used in evaluation phase, production usually doesn't need it

## 📖 For More Details

See the [Chinese version](rag_evaluation_metrics_zh.md) for comprehensive examples and detailed explanations.
