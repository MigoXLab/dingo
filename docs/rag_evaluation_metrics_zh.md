# RAG评估指标 - 完整指南

## 🎯 概述

dingo 的 RAG 评估指标系统基于 [RAGAS 论文](https://arxiv.org/abs/2309.15217)、DeepEval 和 TruLens 的最佳实践，提供完整的 RAG 系统评估能力。

### ✅ 支持的指标 (5/5)

| 指标 | 评估维度 | 需要字段 | 论文来源 |
|------|---------|---------|---------|
| **Faithfulness** | 答案忠实度 | question, answer, contexts | RAGAS |
| **Context Precision** | 上下文精度 | question, answer, contexts | RAGAS |
| **Answer Relevancy** | 答案相关性 | question, answer | RAGAS |
| **Context Recall** | 上下文召回 | question, expected_output, contexts | RAGAS |
| **Context Relevancy** | 上下文相关性 | question, contexts | RAGAS + DeepEval + TruLens |


## 🚀 快速开始

### 1. 运行示例

```bash
# Dataset方式 - 批量评估（使用WikiEval数据集）
python examples/rag/dataset_rag_eavl.py

# SDK方式 - 单个评估
python examples/rag/sdk_rag_eval.py
```

### 2. SDK方式 - 单个评估

```python
import os
from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.rag.llm_rag_faithfulness import LLMRAGFaithfulness

# 配置LLM
LLMRAGFaithfulness.dynamic_config = EvaluatorLLMArgs(
    key=os.getenv("OPENAI_API_KEY"),
    api_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    model=os.getenv("OPENAI_MODEL", "deepseek-chat"),
)

# 准备数据
data = Data(
    data_id="example_1",
    prompt="什么是机器学习？",
    content="机器学习是人工智能的一个分支，使计算机能够从数据中学习。",
    context=[
        "机器学习是AI的子领域。",
        "ML系统从数据中学习而无需明确编程。"
    ]
)

# 评估
result = LLMRAGFaithfulness.eval(data)

# 查看结果
print(f"分数: {result.score}/10")
print(f"通过: {not result.error_status}")
print(f"理由: {result.reason[0]}")
```

### 3. Dataset方式 - 批量评估

```python
from dingo.config import InputArgs
from dingo.exec import Executor
from pathlib import Path

input_data = {
    "input_path": str(Path("test/data/WikiEval_samples_10.jsonl")),
    "dataset": {
        "source": "local",
        "format": "jsonl",
        "field": {
            "prompt": "question",
            "content": "answer",
            "context": "context_v1"
        }
    },
    "executor": {
        "prompt_list": [
            "PromptRAGFaithfulness"
        ],
        "result_save": {
            "good": True,
            "bad": True
        }
    },
    "evaluator": {
        "llm_config": {
            "LLMRAGFaithfulness": {
                "model": "deepseek-chat",
                "key": "YOUR_API_KEY",
                "api_url": "https://api.openai.com/v1",
            },
        }
    }
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
```

## 📋 数据格式

### 必需字段

每个指标需要不同的字段：

| 指标 | question | answer | contexts | expected_output | 说明 |
|------|----------|--------|----------|-----------------|------|
| Faithfulness | ✅ | ✅ | ✅ | - | 检测答案中的幻觉 |
| Context Precision | ✅ | ✅ | ✅ | - | 评估检索排序质量 |
| Answer Relevancy | ✅ | ✅ | - | - | 检测答案相关性 |
| Context Recall | ✅ | ✅ (作为expected_output) | ✅ | - | 评估上下文完整性 |
| Context Relevancy | ✅ | - | ✅ | - | 检测噪声上下文 |

### 数据示例 (SDK方式)

```python
from dingo.io.input import Data

# Faithfulness / Context Precision / Answer Relevancy
data = Data(
    data_id="example_1",
    prompt="什么是深度学习？",
    content="深度学习是机器学习的子领域，使用多层神经网络。",
    context=[
        "深度学习使用多层神经网络...",
        "深度学习在图像识别中很有用..."
    ]
)

# Context Recall (需要 expected_output)
data = Data(
    data_id="example_2",
    prompt="Python的特点？",
    content="Python简洁且有丰富的库。",  # 作为expected_output
    context=[
        "Python以其简洁的语法著称。",
        # 缺少关于库的信息，召回率会低
    ]
)

# Context Relevancy (只需问题和上下文)
data = Data(
    data_id="example_3",
    prompt="机器学习有哪些应用？",
    context=[
        "机器学习用于图像识别。",  # 相关
        "区块链是分布式技术。",  # 不相关
    ]
)
```

### 数据示例 (Dataset方式 - JSONL)

```jsonl
{"question": "什么是深度学习？", "answer": "深度学习使用神经网络...", "context_v1": "深度学习是ML的子领域..."}
{"question": "Python的特点？", "answer": "Python简洁且有丰富的库。", "context_v1": "Python语法简洁。"}
```

## 🎨 输出格式

评估结果包含：

```python
result = LLMRAGFaithfulness.eval(data)

# 基本信息
result.score          # 分数 (0-10，整数)
result.error_status   # 是否出错/未通过 (True=未通过, False=通过)
result.type           # 评估类型 (QUALITY_GOOD / QUALITY_BAD_...)
result.name           # 评估名称

# 详细信息
result.reason         # 评估理由（列表）
```

**输出示例**：
```python
# 通过的情况
result.score = 9
result.error_status = False
result.type = "QUALITY_GOOD"
result.name = "FAITHFULNESS_PASS"
result.reason = ["忠实度评估通过 (分数: 9/10)\n答案完全基于上下文，未发现幻觉。"]

# 未通过的情况
result.score = 3
result.error_status = True
result.type = "QUALITY_BAD_FAITHFULNESS"
result.name = "PromptRAGFaithfulness"
result.reason = ["忠实度评估未通过 (分数: 3/10)\n答案中包含未被上下文支持的陈述。"]
```

## 🔧 配置阈值

```python
from dingo.config.input_args import EvaluatorLLMArgs

# 方法1: 直接设置（默认阈值为5）
LLMRAGFaithfulness.dynamic_config = EvaluatorLLMArgs(
    key="YOUR_API_KEY",
    api_url="https://api.openai.com/v1",
    model="deepseek-chat",
    parameters={"threshold": 7}  # 自定义阈值
)

# 方法2: 通过配置文件
config = InputArgs(**{
    "evaluator": {
        "llm_config": {
            "LLMRAGFaithfulness": {
                "model": "deepseek-chat",
                "key": "YOUR_API_KEY",
                "api_url": "https://api.openai.com/v1",
                "parameters": {"threshold": 7}
            }
        }
    }
})
```

## 📊 指标详细说明

### 1️⃣ Faithfulness (忠实度)

**评估目标**: 检测答案中的幻觉和未被上下文支持的陈述

**计算方式**:
1. 将答案分解为独立的陈述
2. 对每个陈述判断是否被上下文支持
3. 忠实度分数 = (被支持的陈述数 / 总陈述数) × 10

**输入要求**:
- `question`: 用户问题
- `answer`: RAG系统生成的答案
- `contexts`: 检索到的上下文列表

**评分标准**:
- `9-10分`: 所有陈述都有上下文支持，无幻觉
- `7-8分`: 大部分陈述有支持，少量细节不够精确
- `5-6分`: 半数陈述有支持，存在一些未支持的陈述
- `3-4分`: 大量陈述缺乏支持，幻觉较多
- `0-2分`: 答案几乎完全是幻觉或编造

**推荐阈值**: 7 (满分10)

**使用场景**:
- 检测RAG系统是否生成了虚假信息
- 验证答案是否基于检索到的事实

---

### 2️⃣ Context Precision (上下文精度)

**评估目标**: 评估检索到的上下文是否精确且排序合理

**计算方式**:
1. 对每个上下文判断是否与答案相关
2. 计算精度 = (相关上下文数 / 总上下文数) × 10
3. 考虑上下文的排序位置（前面的上下文权重更高）

**输入要求**:
- `question`: 用户问题
- `answer`: RAG系统生成的答案
- `contexts`: 检索到的上下文列表（有序）

**评分标准**:
- `9-10分`: 所有上下文都相关，排序合理
- `7-8分`: 大部分上下文相关，排序基本合理
- `5-6分`: 半数上下文相关，存在噪声
- `3-4分`: 大量不相关上下文，排序混乱
- `0-2分`: 上下文几乎全部不相关

**推荐阈值**: 5 (满分10)

**使用场景**:
- 评估检索系统的质量
- 优化检索和排序算法

---

### 3️⃣ Answer Relevancy (答案相关性)

**评估目标**: 判断答案是否直接、完整地回答了问题

**计算方式**:
1. 分析答案是否直接回答了问题
2. 检测答案中是否包含无关信息
3. 相关性分数 = (相关内容占比) × 10

**输入要求**:
- `question`: 用户问题
- `answer`: RAG系统生成的答案

**评分标准**:
- `9-10分`: 答案直接、完整回答问题，无冗余
- `7-8分`: 答案基本回答问题，有少量无关信息
- `5-6分`: 答案部分回答问题，较多无关或冗余内容
- `3-4分`: 答案大量偏题，相关内容很少
- `0-2分`: 答案完全不相关

**推荐阈值**: 5 (满分10)

**使用场景**:
- 检测答案是否跑题或包含不必要的信息
- 优化生成模型的回答质量

---

### 4️⃣ Context Recall (上下文召回)

**评估目标**: 检索到的上下文是否完整地支持了答案

**计算方式**:
1. 从答案（expected_output）中提取独立陈述
2. 对每个陈述判断是否能从上下文中归因
3. 召回率 = (可归因陈述数 / 总陈述数) × 10

**输入要求**:
- `question`: 用户问题
- `expected_output`: 标准答案/ground truth
- `contexts`: 检索到的上下文列表

**评分标准**:
- `9-10分`: 所有关键信息都能从上下文找到
- `7-8分`: 大部分信息被覆盖，少量细节缺失
- `5-6分`: 半数信息被覆盖，存在明显遗漏
- `3-4分`: 大量关键信息缺失
- `0-2分`: 上下文几乎不支持答案

**推荐阈值**: 5 (满分10)

**使用场景**:
- 检测检索系统是否遗漏了重要信息
- 评估检索的完整性

**注意**: Context Recall 需要 ground truth 答案，通常用于评估阶段

---

### 5️⃣ Context Relevancy (上下文相关性)

**评估目标**: 检索到的上下文是否与问题相关（噪声检测）

**计算方式**:
1. 对每个上下文判断是否与问题相关
2. 相关性分数 = (相关上下文数 / 总上下文数) × 10

**输入要求**:
- `question`: 用户问题
- `contexts`: 检索到的上下文列表

**评分标准**:
- `9-10分`: 所有上下文都与问题直接相关
- `7-8分`: 大部分上下文相关，少量不太相关
- `5-6分`: 半数上下文相关，存在明显噪声
- `3-4分`: 大量不相关上下文
- `0-2分`: 上下文几乎完全不相关

**推荐阈值**: 5 (满分10)

**使用场景**:
- 纯粹评估检索系统本身的相关性
- 不依赖答案，只关注问题和上下文的匹配度

**与 Context Precision 的区别**:
- Context Relevancy: 只看问题和上下文的匹配度
- Context Precision: 还要看上下文是否支持最终答案

## 🌟 最佳实践

### 1. 指标组合使用建议

**完整评估** (5个指标):
```python
"prompt_list": [
    "PromptRAGFaithfulness",      # 检测幻觉
    "PromptRAGContextPrecision",  # 评估检索质量
    "PromptRAGAnswerRelevancy",   # 检测答案相关性
    "PromptRAGContextRecall",     # 评估检索完整性（需要ground truth）
    "PromptRAGContextRelevancy"   # 检测噪声上下文
]
```

**生产环境** (不需要ground truth):
```python
"prompt_list": [
    "PromptRAGFaithfulness",      # 最重要：防止幻觉
    "PromptRAGAnswerRelevancy",   # 确保答案相关
    "PromptRAGContextRelevancy"   # 检测噪声
]
```

**评估阶段** (需要ground truth):
```python
"prompt_list": [
    "PromptRAGContextRecall",     # 评估检索完整性
    "PromptRAGContextPrecision"   # 评估检索精确度
]
```

### 2. 阈值调整建议

根据场景调整阈值（默认为5）:

- **严格场景**（金融、医疗）: 阈值 7-8
- **一般场景**（问答系统）: 阈值 5-6
- **宽松场景**（探索性搜索）: 阈值 3-4

### 3. 迭代优化流程

1. **初始评估**: 使用所有5个指标评估当前系统
2. **识别问题**:
   - Faithfulness低 → 答案生成有问题
   - Context Precision/Recall低 → 检索系统有问题
   - Answer Relevancy低 → 生成模型跑题
   - Context Relevancy低 → 检索噪声太多
3. **针对性优化**: 根据问题调整相应组件
4. **重新评估**: 验证优化效果

### 4. 注意事项

- **LLM依赖**: 所有指标都依赖LLM API，需要配置正确
- **成本考虑**: 评估会产生API调用成本，建议抽样评估
- **数据质量**: 输入数据质量会影响评估结果
- **Ground Truth**: Context Recall需要标准答案，主要用于评估阶段

## 💡 示例场景

### 场景1: 检测幻觉 (Faithfulness)

```python
from dingo.io.input import Data
from dingo.model.llm.rag.llm_rag_faithfulness import LLMRAGFaithfulness

# 答案包含上下文中没有的信息
data = Data(
    prompt="Python什么时候发布？",
    content="Python于1991年发布，是第一个面向对象语言。",  # "第一个"是幻觉
    context=["Python由Guido创建，1991年首次发布于1991年。"]
)

result = LLMRAGFaithfulness.eval(data)
print(f"分数: {result.score}/10")
print(f"理由: {result.reason[0]}")
# 预期: 分数较低，reason指出"第一个面向对象语言"未被支持
```

### 场景2: 评估检索质量 (Context Precision)

```python
from dingo.model.llm.rag.llm_rag_context_precision import LLMRAGContextPrecision

# 检索到的上下文质量参差不齐
data = Data(
    prompt="机器学习的应用？",
    content="ML用于图像识别和NLP。",
    context=[
        "机器学习在图像识别中应用广泛。",  # 相关
        "NLP是ML的重要应用。",  # 相关
        "区块链是分布式技术。"  # 不相关
    ]
)

result = LLMRAGContextPrecision.eval(data)
# 预期: 分数约6-7分，反映3个上下文中有1个不相关
```

### 场景3: 发现遗漏信息 (Context Recall)

```python
from dingo.model.llm.rag.llm_rag_context_recall import LLMRAGContextRecall

# 检索遗漏了重要信息
data = Data(
    prompt="深度学习的特点？",
    content="深度学习使用多层神经网络，需要大量数据。",  # expected_output
    context=["深度学习使用神经网络。"]  # 缺少"多层"和"大量数据"
)

result = LLMRAGContextRecall.eval(data)
# 预期: 分数较低，reason指出"大量数据"等信息被遗漏
```

### 场景4: 检测答案跑题 (Answer Relevancy)

```python
from dingo.model.llm.rag.llm_rag_answer_relevancy import LLMRAGAnswerRelevancy

# 答案包含大量无关信息
data = Data(
    prompt="什么是机器学习？",
    content="机器学习是AI的分支。今天天气很好。我喜欢编程。神经网络很复杂。"
)

result = LLMRAGAnswerRelevancy.eval(data)
# 预期: 分数较低，检测出大量无关句子
```

### 场景5: 检测噪声上下文 (Context Relevancy)

```python
from dingo.model.llm.rag.llm_rag_context_relevancy import LLMRAGContextRelevancy

# 检索包含大量噪声
data = Data(
    prompt="深度学习的应用？",
    context=[
        "深度学习用于图像识别。",  # 相关
        "区块链是分布式技术。",  # 不相关
        "天气预报需要气象数据。"  # 不相关
    ]
)

result = LLMRAGContextRelevancy.eval(data)
# 预期: 分数约3-4分，只有1/3的上下文相关
```
