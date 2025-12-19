# RAG评估指标 - 完整指南

## 🎯 概述

dingo 的 RAG 评估指标系统基于 [RAGAS 论文](https://arxiv.org/abs/2309.15217)、DeepEval 和 TruLens 的最佳实践，提供完整的 RAG 系统评估能力。

### ✅ 支持的指标 (5/5)

| 指标 | 评估维度 | 需要字段 | 论文来源 |
|------|---------|---------|---------|
| **Faithfulness** | 答案忠实度 | user_input, response, retrieved_contexts | RAGAS |
| **Answer Relevancy** | 答案相关性 | user_input, response | RAGAS |
| **Context Relevancy** | 上下文相关性 | user_input, retrieved_contexts | RAGAS + DeepEval + TruLens |
| **Context Recall** | 上下文召回 | user_input, retrieved_contexts, reference | RAGAS |
| **Context Precision** | 上下文精度 | user_input, retrieved_contexts, reference | RAGAS |


## 🚀 快速开始

### 1. 运行示例

```bash
# Dataset方式 - 批量评估baseline（推荐）
python examples/rag/dataset_rag_eval_baseline.py

# SDK方式 - 单个评估
python examples/rag/sdk_rag_eval.py

# 模拟RAG系统并评估
python examples/rag/e2e_RAG_eval_with_mockRAG_fiqa.py
```

### 2. SDK方式 - 单个评估

```python
import os
from dingo.config.input_args import EvaluatorLLMArgs, EmbeddingConfigArgs
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
print(f"通过: {not result.status}")  # status=False 表示通过
print(f"理由: {result.reason[0]}")
```

### 3. Dataset方式 - 批量评估

```python
from dingo.config import InputArgs
from dingo.exec import Executor
from pathlib import Path
import os

# 配置
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "YOUR_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-large")

input_data = {
    "task_name": "rag_evaluation",
    "input_path": str(Path("test/data/fiqa.jsonl")),
    "output_path": "outputs/rag_results/",
    "dataset": {
        "source": "local",
        "format": "jsonl"
    },
    "executor": {
        "max_workers": 1,
        "result_save": {
            "good": True,
            "bad": True,
            "all_labels": True
        }
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
                {
                    "name": "LLMRAGFaithfulness",
                    "config": {
                        "model": OPENAI_MODEL,
                        "key": OPENAI_KEY,
                        "api_url": OPENAI_URL
                    }
                },
                {
                    "name": "LLMRAGAnswerRelevancy",
                    "config": {
                        "model": OPENAI_MODEL,
                        "key": OPENAI_KEY,
                        "api_url": OPENAI_URL,
                        "embedding_config": {  # ⭐ 必需配置
                            "model": EMBEDDING_MODEL,
                            "api_url": OPENAI_URL,
                            "key": OPENAI_KEY
                        },
                        "parameters": {
                            "strictness": 3,
                            "threshold": 5
                        }
                    }
                },
                {
                    "name": "LLMRAGContextRelevancy",
                    "config": {
                        "model": OPENAI_MODEL,
                        "key": OPENAI_KEY,
                        "api_url": OPENAI_URL
                    }
                },
                {
                    "name": "LLMRAGContextRecall",
                    "config": {
                        "model": OPENAI_MODEL,
                        "key": OPENAI_KEY,
                        "api_url": OPENAI_URL
                    }
                },
                {
                    "name": "LLMRAGContextPrecision",
                    "config": {
                        "model": OPENAI_MODEL,
                        "key": OPENAI_KEY,
                        "api_url": OPENAI_URL
                    }
                }
            ]
        }
    ]
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
summary = executor.execute()

# 查看结果（需要指定字段组）
field_key = "user_input,response,retrieved_contexts,reference"
print(f"总平均分: {summary.get_metrics_score_overall_average(field_key)}")
print(f"各指标平均分: {summary.get_metrics_score_summary(field_key)}")
```

## 📋 数据格式

### 必需字段

每个指标需要不同的字段（使用 Dingo 框架的字段名）：

| 指标 | user_input (问题) | response (答案) | retrieved_contexts (上下文) | reference (参考答案) | 说明 |
|------|------------------|----------------|---------------------------|---------------------|------|
| **Faithfulness** | ✅ | ✅ | ✅ | - | 衡量答案是否完全基于检索到的上下文，避免幻觉 |
| **Answer Relevancy** | ✅ | ✅ | - | - | 衡量答案是否直接回答用户问题，不需要上下文 |
| **Context Relevancy** | ✅ | - | ✅ | - | 衡量检索到的上下文是否与问题相关 |
| **Context Recall** | ✅ | - | ✅ | ✅ | 衡量是否检索到了所有需要的信息（需要参考答案） |
| **Context Precision** | ✅ | - | ✅ | ✅ | 衡量检索结果的排序质量，相关文档是否在前面（需要参考答案） |

**字段映射说明**：
- `user_input` = `prompt` = `question`：用户问题
- `response` = `content` = `answer`：RAG 系统生成的答案
- `retrieved_contexts` = `context` = `contexts`：检索到的上下文列表
- `reference` = `expected_output` = `ground_truth`：标准答案/参考答案

### 数据示例 (SDK方式)

SDK 方式使用 `Data` 对象，字段名为：`prompt`, `content`, `context`, `reference`

```python
from dingo.io.input import Data

# Faithfulness (需要: prompt, content, context)
data = Data(
    data_id="example_1",
    prompt="什么是深度学习？",  # user_input
    content="深度学习是机器学习的子领域，使用多层神经网络。",  # response
    context=[  # retrieved_contexts
        "深度学习使用多层神经网络...",
        "深度学习在图像识别中很有用..."
    ]
)

# Answer Relevancy (需要: prompt, content)
data = Data(
    data_id="example_2",
    prompt="什么是机器学习？",
    content="机器学习是AI的分支，让计算机从数据中学习。"
    # 不需要 context
)

# Context Relevancy (需要: prompt, context)
data = Data(
    data_id="example_3",
    prompt="机器学习有哪些应用？",
    context=[
        "机器学习用于图像识别。",  # 相关
        "区块链是分布式技术。",  # 不相关
    ]
    # 不需要 content
)

# Context Recall (需要: prompt, context, reference)
data = Data(
    data_id="example_4",
    prompt="Python的特点？",
    context=[
        "Python以其简洁的语法著称。",
        # 缺少关于库的信息，召回率会低
    ],
    reference="Python简洁且有丰富的库。"  # 参考答案
)

# Context Precision (需要: prompt, context, reference)
data = Data(
    data_id="example_5",
    prompt="深度学习的应用？",
    context=[
        "深度学习用于图像识别。",  # 相关，排序第1
        "区块链是分布式技术。",  # 不相关，排序第2
        "深度学习用于NLP。"  # 相关，排序第3（应该排前面）
    ],
    reference="深度学习在图像识别和NLP中广泛应用。"
)
```

### 数据示例 (Dataset方式 - JSONL)

Dataset 方式使用 JSONL 文件，推荐字段名为：`user_input`, `response`, `retrieved_contexts`, `reference`

```jsonl
{"user_input": "什么是深度学习？", "response": "深度学习使用神经网络...", "retrieved_contexts": ["深度学习是ML的子领域...", "深度学习用于图像识别..."]}
{"user_input": "Python的特点？", "response": "Python简洁且有丰富的库。", "retrieved_contexts": ["Python语法简洁。", "Python有NumPy等库。"], "reference": "Python语法简洁，生态系统丰富。"}
```

**字段映射配置**：

```python
"fields": {
    "prompt": "user_input",           # 问题
    "content": "response",            # RAG生成的答案
    "context": "retrieved_contexts",  # 检索的上下文
    "reference": "reference"          # 标准答案（可选）
}
```

## 🎨 输出格式

### SDK 方式输出

评估结果包含：

```python
result = LLMRAGFaithfulness.eval(data)

# 基本信息 (EvalDetail 对象)
result.metric                    # 指标名称 (如 "LLMRAGFaithfulness")
result.score                     # 分数 (0-10，浮点数)
result.status                    # 是否未通过 (True=未通过, False=通过)
result.label                     # 标签列表 (如 ["QUALITY_GOOD.FAITHFULNESS_PASS"])
result.reason                    # 评估理由列表 (如 ["答案完全基于上下文..."])

# 示例
print(f"指标: {result.metric}")
print(f"分数: {result.score}/10")
print(f"通过: {not result.status}")  # status=False 表示通过
print(f"标签: {result.label}")
print(f"理由: {result.reason}")
```

**输出示例**：
```python
# 通过的情况
result.metric = "LLMRAGFaithfulness"
result.score = 9.2
result.status = False  # False 表示通过
result.label = ["QUALITY_GOOD.FAITHFULNESS_PASS"]
result.reason = ["答案完全基于上下文，未发现幻觉。所有陈述都有支持。"]

# 未通过的情况
result.metric = "LLMRAGFaithfulness"
result.score = 3.5
result.status = True  # True 表示未通过
result.label = ["QUALITY_BAD.FAITHFULNESS_FAIL"]
result.reason = ["答案中包含未被上下文支持的陈述：'Python是第一个面向对象语言'"]
```

### Dataset 方式输出

执行完成后会生成 `summary.json`，包含：

> **注意**：指标分数统计功能支持 `local` 和 `spark` 两种执行器。

```json
{
  "task_name": "rag_evaluation",
  "total": 30,
  "num_good": 28,
  "num_bad": 2,
  "score": 93.3,
  "type_ratio": {
    "user_input,response,retrieved_contexts,reference": {
      "good": 0.933333,
      "bad": 0.066667
    }
  },
  "metrics_score": {
    "user_input,response,retrieved_contexts,reference": {
      "stats": {
        "LLMRAGFaithfulness": {
          "score_average": 8.36,
          "score_count": 30,
          "score_min": 1.67,
          "score_max": 10.0,
          "score_std_dev": 2.53
        },
        "LLMRAGContextPrecision": {
          "score_average": 9.67,
          "score_count": 30,
          "score_min": 0.0,
          "score_max": 10.0,
          "score_std_dev": 1.8
        },
        "LLMRAGContextRecall": {
          "score_average": 8.42,
          "score_count": 30,
          "score_min": 2.5,
          "score_max": 10.0,
          "score_std_dev": 2.61
        },
        "LLMRAGContextRelevancy": {
          "score_average": 9.0,
          "score_count": 30,
          "score_min": 0.0,
          "score_max": 10.0,
          "score_std_dev": 2.38
        },
        "LLMRAGAnswerRelevancy": {
          "score_average": 5.77,
          "score_count": 30,
          "score_min": 0.0,
          "score_max": 7.82,
          "score_std_dev": 2.09
        }
      },
      "summary": {
        "LLMRAGFaithfulness": 8.36,
        "LLMRAGContextPrecision": 9.67,
        "LLMRAGContextRecall": 8.42,
        "LLMRAGContextRelevancy": 9.0,
        "LLMRAGAnswerRelevancy": 5.77
      },
      "overall_average": 8.24
    }
  }
}
```

### 多字段组示例

```json
{
  "metrics_score": {
    "user_input,response": {
      "stats": {...},
      "summary": {...},
      "overall_average": 7.8
    },
    "retrieved_contexts,reference": {
      "stats": {...},
      "summary": {...},
      "overall_average": 9.1
    }
  }
}
```

## ⚙️ 执行器支持

### 支持的执行器

指标分数统计功能支持以下执行器：

| 执行器 | 类型 | 指标统计 | 适用场景 |
|--------|------|---------|---------|
| **Local** | 单机 | ✅ 支持 | 小规模数据集，开发测试 |
| **Spark** | 分布式 | ✅ 支持 | 大规模数据集，生产环境 |

### Spark 执行器示例

```python
from pyspark import SparkConf
from pyspark.sql import SparkSession
from dingo.config import InputArgs
from dingo.exec import Executor

# 初始化 Spark
spark_conf = SparkConf().setAppName("RAG_Evaluation").setMaster("local[*]")
spark = SparkSession.builder.config(conf=spark_conf).getOrCreate()

# 配置评估参数（与 Local 相同）
input_args = InputArgs.from_dict({
    "task_name": "rag_spark_evaluation",
    "input_path": "test/data/fiqa.jsonl",
    "evaluator": [...]  # 与 Local 相同的配置
})

# 创建 RDD
data_rdd = spark.sparkContext.parallelize(data_list)

# 使用 Spark 执行器
executor = Executor.exec_map["spark"](
    input_args=input_args,
    spark_rdd=data_rdd,
    spark_session=spark
)

# 执行评估
summary = executor.execute()

# 获取指标统计（输出格式与 Local 完全一致）
field_key = "user_input,response,retrieved_contexts,reference"
print(f"总平均分: {summary.get_metrics_score_overall_average(field_key)}")
print(f"各指标汇总: {summary.get_metrics_score_summary(field_key)}")

# to_dict() 也包含完整的 metrics_score 层级结构
result = summary.to_dict()
print(result['metrics_score'][field_key]['overall_average'])
print(result['metrics_score'][field_key]['summary'])
```

## 🔧 配置阈值和参数

### SDK 方式配置

```python
from dingo.config.input_args import EvaluatorLLMArgs

# 配置阈值（默认阈值为5）
LLMRAGFaithfulness.dynamic_config = EvaluatorLLMArgs(
    key="YOUR_API_KEY",
    api_url="https://api.openai.com/v1",
    model="gpt-4o-mini",
    parameters={"threshold": 7}  # 自定义阈值
)

# Answer Relevancy 特殊配置（需要 embedding）⭐
# 注意：必须配置 embedding_config
LLMRAGAnswerRelevancy.dynamic_config = EvaluatorLLMArgs(
    key="YOUR_API_KEY",
    api_url="https://api.openai.com/v1",
    model="gpt-4o-mini",
    embedding_config=EmbeddingConfigArgs(  # ⭐ 必需
        model="text-embedding-3-large",
        api_url="https://api.openai.com/v1",
        key="YOUR_API_KEY"
    ),
    parameters={
        "strictness": 3,  # 生成问题数量
        "threshold": 5    # 通过阈值
    }
)
```

### Dataset 方式配置

```python
"evaluator": [
    {
        "evals": [
            {
                "name": "LLMRAGFaithfulness",
                "config": {
                    "model": "gpt-4o-mini",
                    "key": "YOUR_API_KEY",
                    "api_url": "https://api.openai.com/v1",
                    "parameters": {"threshold": 7}
                }
            },
            {
                "name": "LLMRAGAnswerRelevancy",
                "config": {
                    "model": "gpt-4o-mini",
                    "key": "YOUR_API_KEY",
                    "api_url": "https://api.openai.com/v1",
                    "embedding_config": {  # ⭐ 必需配置
                        "model": "text-embedding-3-large",
                        "api_url": "https://api.openai.com/v1",
                        "key": "YOUR_API_KEY"
                    },
                    "parameters": {
                        "strictness": 3,
                        "threshold": 5
                    }
                }
            }
        ]
    }
]
```

### 可配置参数

| 参数 | 适用指标 | 默认值 | 说明 |
|------|---------|--------|------|
| `threshold` | 所有指标 | 5.0 | 通过阈值（0-10），在 `parameters` 中配置 |
| `strictness` | Answer Relevancy | 3 | 生成问题数量（1-5），在 `parameters` 中配置 |
| `embedding_config` | Answer Relevancy | - | **必需配置**，包含 `model`（模型名）、`api_url`（服务地址）、`key`（API密钥） |

## 📊 指标详细说明

### 1️⃣ Faithfulness (答案忠实度)

**评估目标**: 衡量答案是否完全基于检索到的上下文，避免幻觉

**计算方式**:
1. 将答案分解为独立的陈述（claims）
2. 对每个陈述判断是否被上下文支持
3. 忠实度分数 = (上下文支持的陈述数 / 总陈述数) × 10

**计算公式**：
```
Faithfulness = (上下文支持的声明数 / 总声明数) × 10
```

**输入要求**:
- `user_input`: 用户问题（生成答案时需要）
- `response`: RAG系统生成的答案
- `retrieved_contexts`: 检索到的上下文列表

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
- 生产环境中最关键的指标，防止幻觉

---

### 2️⃣ Answer Relevancy (答案相关性)

**评估目标**: 衡量答案是否直接回答用户问题，不需要上下文

**计算方式**:
1. 基于答案生成 N 个反向问题（由 LLM 从答案推断出的问题）
2. 计算生成问题的 embedding 与原始问题 embedding 的余弦相似度
3. 答案相关性 = 所有相似度的平均值

**计算公式**：
```
Answer Relevancy = (1/N) × Σ cosine_sim(E_gi, E_o)

其中：
- N: 生成的问题数量，默认为 3（可通过 strictness 参数调整）
- E_gi: 第 i 个生成问题的 embedding（从 response 反推生成的问题的向量表示）
- E_o: 原始问题的 embedding
- 分子: 所有余弦相似度的总和，\sum 符号表示累加
- 分母: 生成的问题数量 N，用于计算平均值
```

**输入要求**:
- `user_input`: 用户问题
- `response`: RAG系统生成的答案

**⚠️ 重要**: 此指标**必须配置 `embedding_config`**，包含：
- `model`: Embedding 模型名（如 `text-embedding-3-large`、`BAAI/bge-m3`）
- `api_url`: Embedding 服务地址
- `key`: API 密钥（可选，本地服务可用任意值）

**评分标准**:
- `9-10分`: 生成的问题与原始问题高度相似，答案完全切题
- `7-8分`: 生成的问题基本匹配，答案相关性好
- `5-6分`: 部分生成问题相关，答案有一定相关性
- `3-4分`: 生成问题相关性较低，答案偏题明显
- `0-2分`: 答案完全不相关或跑题严重

**推荐阈值**: 5 (满分10)

**使用场景**:
- 检测答案是否跑题或包含不必要的信息
- 优化生成模型的回答质量
- 确保答案直接回答用户问题

**技术细节**:
- 使用 `strictness` 参数控制生成问题数量（默认3个）
- 使用 `threshold` 参数设置通过阈值（默认5.0）
- **必须**在 `embedding_config` 中配置 embedding 服务：
  - 云端选项：OpenAI、DeepSeek 等
  - 本地选项：vLLM、Xinference 部署的 bge-m3、multilingual-e5 等

---

### 3️⃣ Context Relevancy (上下文相关性)

**评估目标**: 衡量检索到的上下文是否与问题相关

**计算方式**:
采用**双评判系统（Dual-Judge）** 来评估上下文与问题的相关性，这个方法来自 NVIDIA 的研究：

**评判员1 评分（Judge 1）**：
- **任务**: 判断上下文是否包含回答问题所需的信息
- **0** = 上下文完全不相关
- **1** = 上下文部分相关
- **2** = 上下文完全相关

**评判员2 评分（Judge 2）**：
- **使用不同的提示词表述，从另一个角度评估**
- **同样使用 0-2 的评分标准**
- **目的**: 减少单一提示词的偏差

**最终分数计算**：
```
Context Relevancy = (相关上下文数 / 总上下文数) × 10

其中：
- 相关上下文：两个评判员的平均分 ≥ 阈值（默认1.0）
- 不相关上下文：平均分 < 阈值
```

**输入要求**:
- `user_input`: 用户问题
- `retrieved_contexts`: 检索到的上下文列表

**注意**: 此指标不需要答案，纯粹评估检索系统的相关性

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
- 检测检索系统是否引入了噪声上下文

**与 Context Precision 的区别**:
- **Context Relevancy**: 只看问题和上下文的匹配度，不需要答案
- **Context Precision**: 需要参考答案，评估排序质量

---

### 4️⃣ Context Recall (上下文召回)

**评估目标**: 衡量是否检索到了所有需要的信息（需要参考答案）

**计算方式**:
1. 从参考答案（reference）中提取独立陈述
2. 对每个陈述判断是否能从检索到的上下文中归因
3. 召回率 = (上下文支持的参考陈述数 / 参考中总陈述数) × 10

**计算公式**：
```
Context Recall = (上下文支持的参考声明数 / 参考中总声明数) × 10

分子：retrieved_contexts 能支持的参考答案中的陈述数
分母：reference 中总声明数
```

**输入要求**:
- `user_input`: 用户问题
- `retrieved_contexts`: 检索到的上下文列表
- `reference`: 参考答案/ground truth（必需）

**评分标准**:
- `9-10分`: 所有关键信息都能从上下文找到
- `7-8分`: 大部分信息被覆盖，少量细节缺失
- `5-6分`: 半数信息被覆盖，存在明显遗漏
- `3-4分`: 大量关键信息缺失
- `0-2分`: 上下文几乎不支持参考答案

**推荐阈值**: 5 (满分10)

**使用场景**:
- 检测检索系统是否遗漏了重要信息
- 评估检索的完整性
- 评估阶段使用，需要标注的参考答案

**注意**:
- **必须有参考答案（reference）**，通常用于评估阶段
- 与 Faithfulness 相反：Faithfulness 防止多说（幻觉），Context Recall 防止少说（遗漏）

---

### 5️⃣ Context Precision (上下文精度)

**评估目标**: 衡量检索结果的排序质量，相关文档是否在前面（需要参考答案）

**计算方式**:
1. 对每个位置 k 判断该上下文是否相关（是否支持参考答案）
2. 计算每个位置的精度（Precision@k）
3. 使用相关性指示器（v_k）加权求和

**计算公式**：
```
Context Precision = Σ(Precision@k × v_k) / top K 中相关项总数

其中：
- K: 检索返回的总文档数，例如：5个文档
- k: 当前位置（第几个），1, 2, 3, ..., K
- v_k: 相关性指示器，0（不相关）或 1（相关）
- Precision@k: 前k个文档中的精确率，0.0 到 1.0
- Precision@k = 前k个文档中相关的数量 / k
```

**输入要求**:
- `user_input`: 用户问题
- `retrieved_contexts`: 检索到的上下文列表（有序）
- `reference`: 参考答案（必需）

**评分标准**:
- `9-10分`: 所有相关上下文都排在前面，排序完美
- `7-8分`: 大部分相关上下文靠前，排序较好
- `5-6分`: 相关上下文分布不均，排序一般
- `3-4分`: 相关上下文靠后，排序较差
- `0-2分`: 排序完全混乱，不相关的排在前面

**推荐阈值**: 5 (满分10)

**使用场景**:
- 评估检索系统的排序质量
- 优化检索和排序算法
- 确保相关文档排在前面（Top-K 优化）
- 评估阶段使用，需要标注的参考答案

**注意**:
- **必须有参考答案（reference）**，通过对比参考答案判断哪些上下文相关
- 关注排序：相关的文档越靠前，分数越高
- 与 Context Relevancy 的区别：Context Precision 关注排序，Context Relevancy 只关注相关性

## 🌟 最佳实践

### 1. 指标组合使用建议

**完整评估** (5个指标):
```python
"evals": [
    {"name": "LLMRAGFaithfulness"},       # 检测幻觉（答案是否忠实于上下文）
    {"name": "LLMRAGAnswerRelevancy"},    # 检测答案相关性（是否回答问题）
    {"name": "LLMRAGContextRelevancy"},   # 检测噪声上下文（上下文是否相关）
    {"name": "LLMRAGContextRecall"},      # 评估检索完整性（需要reference）
    {"name": "LLMRAGContextPrecision"}    # 评估检索排序质量（需要reference）
]
```

**生产环境** (不需要 reference):
```python
"evals": [
    {"name": "LLMRAGFaithfulness"},       # ⭐ 最重要：防止幻觉
    {"name": "LLMRAGAnswerRelevancy"},    # 确保答案直接回答问题
    {"name": "LLMRAGContextRelevancy"}    # 检测检索噪声
]
```

**评估阶段** (需要 reference):
```python
"evals": [
    {"name": "LLMRAGContextRecall"},      # 评估检索完整性（是否遗漏信息）
    {"name": "LLMRAGContextPrecision"}    # 评估检索排序质量（相关的是否靠前）
]
```

**检索系统优化**:
```python
"evals": [
    {"name": "LLMRAGContextRelevancy"},   # 评估相关性（减少噪声）
    {"name": "LLMRAGContextRecall"},      # 评估完整性（减少遗漏）
    {"name": "LLMRAGContextPrecision"}    # 评估排序质量（优化Top-K）
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
   - **Faithfulness 低** → 生成模型产生幻觉，答案不基于上下文
     - 优化方向：调整生成 prompt、使用更强的模型、增强事实检查
   - **Answer Relevancy 低** → 答案跑题或包含无关信息
     - 优化方向：优化生成 prompt、限制答案长度、增强问题理解
   - **Context Relevancy 低** → 检索引入了大量噪声
     - 优化方向：优化检索算法、调整相似度阈值、改进 embedding 模型
   - **Context Recall 低** → 检索遗漏了重要信息
     - 优化方向：增加检索数量（Top-K）、改进查询重写、扩展知识库
   - **Context Precision 低** → 相关文档排序靠后
     - 优化方向：优化排序算法、调整 reranker、改进相关性计算
3. **针对性优化**: 根据问题调整相应组件
4. **重新评估**: 验证优化效果
5. **持续监控**: 在生产环境持续监控关键指标（Faithfulness, Answer Relevancy, Context Relevancy）

### 4. 注意事项

- **字段分组**:
  - `metrics_score` 按字段组（field_key）组织，访问时需指定字段组名
  - 字段组名由评估器配置中的 `fields` 值拼接生成，如 `"user_input,response"`
  - 如果不确定字段组名，可遍历 `summary.metrics_score_stats.items()` 获取所有字段组
- **LLM依赖**: 所有指标都依赖 LLM API，需要配置正确的 API key 和 endpoint
- **Embedding 依赖**:
  - Answer Relevancy **必须配置 `embedding_config`**，包含 `model`、`api_url`、`key`
  - 可使用云端服务（OpenAI、DeepSeek）或本地部署（vLLM、Xinference）
  - 如不配置会抛出异常：`ValueError: Embedding model not initialized...`
- **成本考虑**: 评估会产生 API 调用成本，建议：
  - 开发阶段：小样本抽样评估（如 50-100 条）
  - 生产阶段：只使用关键指标（Faithfulness, Answer Relevancy, Context Relevancy）
  - 评估阶段：全量评估所有指标
- **数据质量**: 输入数据质量会影响评估结果，确保：
  - 问题清晰明确
  - 上下文列表格式正确（字符串数组）
  - 参考答案准确（Context Recall/Precision 需要）
- **Reference 要求**:
  - Context Recall 和 Context Precision **必须**有 reference
  - 其他三个指标不需要 reference
  - Reference 主要用于评估阶段，生产环境通常不需要

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
