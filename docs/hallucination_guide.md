# Dingo 幻觉检测功能完整指南

本指南介绍如何在 Dingo 中使用集成的幻觉检测功能，支持两种检测方案：**HHEM-2.1-Open 本地模型**（推荐）和 **GPT-based 云端检测**。

## 🎯 功能概述

幻觉检测功能用于评估 LLM 生成的回答是否与提供的参考上下文存在事实性矛盾。特别适用于：

- **RAG 系统评估**: 检测生成回答与检索文档的一致性
- **SFT 数据质量评估**: 验证训练数据中回答的事实准确性
- **LLM 输出验证**: 实时检测模型输出中的幻觉问题

## 🔧 核心原理

### 评估流程

1. **数据准备**: 提供待检测回答和参考上下文
2. **一致性分析**: 判断回答是否与每个上下文一致
3. **分数计算**: 计算整体幻觉分数
4. **阈值判断**: 根据设定阈值决定是否标记为有问题

### 评分机制

- **分数范围**: 0.0 - 1.0
- **分数含义**:
  - 0.0 = 完全无幻觉
  - 1.0 = 完全幻觉
- **默认阈值**: 0.5 （可配置）


## 📋 使用要求

### 数据格式要求

```python
from dingo.io.input import Data

data = Data(
    data_id="test_1",
    prompt="用户的问题",  # 原始问题（可选）
    content="LLM的回答",  # 需要检测的回答
    context=["参考上下文1", "参考上下文2"]  # 参考上下文（必需）
)
```

### 支持的上下文格式

```python
# 方式1: 字符串列表
context = ["上下文1", "上下文2", "上下文3"]

# 方式2: JSON字符串
context = '["上下文1", "上下文2", "上下文3"]'

# 方式3: 单个字符串
context = "单个参考上下文"
```

## 🚀 快速开始

### 方法一：HHEM-2.1-Open 本地模型（推荐）

#### 安装依赖
```bash
pip install transformers torch
# 或使用专门的依赖文件
pip install -r requirements/hhem_integration.txt
```

#### 基本使用

```python
from dingo.io.input import Data
from dingo.model.rule.rule_hallucination_hhem import RuleHallucinationHHEM

# 准备测试数据
data = Data(
    data_id='test_1',
    prompt="爱因斯坦什么时候获得诺贝尔奖？",
    content="爱因斯坦在1969年因发现光电效应获得诺贝尔奖。",
    context=[
        "爱因斯坦因发现光电效应获得诺贝尔奖。",
        "爱因斯坦在1921年获得诺贝尔奖。"
    ]
)

# 执行检测（无需API密钥，本地推理）
result = RuleHallucinationHHEM.eval(data)

# 查看结果
print(f"是否检测到幻觉: {result.eval_status}")
print(f"HHEM 分数: {getattr(result, 'score', 'N/A')}")
print(f"详细分析: {result.reason[0]}")
```

### 方法二：GPT-based 云端检测

```python
from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.llm_hallucination import LLMHallucination

# 配置 LLM
LLMHallucination.dynamic_config = EvaluatorLLMArgs(
    key='YOUR_OPENAI_API_KEY',
    api_url='https://api.openai.com/v1/chat/completions',
    model='gpt-4o',
)

# 准备测试数据（同上）
data = Data(
    data_id='test_1',
    prompt="爱因斯坦什么时候获得诺贝尔奖？",
    content="爱因斯坦在1969年因发现光电效应获得诺贝尔奖。",
    context=[
        "爱因斯坦因发现光电效应获得诺贝尔奖。",
        "爱因斯坦在1921年获得诺贝尔奖。"
    ]
)

# 执行检测
result = LLMHallucination.eval(data)

# 查看结果
print(f"是否检测到幻觉: {result.eval_status}")
print(f"幻觉分数: {getattr(result, 'score', 'N/A')}")
print(f"详细原因: {result.reason[0]}")
```

## 📊 批量数据集评估

### 使用 HHEM-2.1-Open（本地，免费）

```python
from dingo.config import InputArgs
from dingo.exec import Executor

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
                "threshold": 0.5  # Default threshold (0.0-1.0, higher = more strict)
            }
        }
    }
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()

print(f"HHEM 幻觉检测完成: 发现 {result.bad_count}/{result.total_count} 个问题")
```

### 使用 GPT（在线，需要 API）

```python
from dingo.config import InputArgs
from dingo.exec import Executor

input_data = {
    "input_path": "test/data/hallucination_test.jsonl",  # Your JSONL file path
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

print(f"GPT 幻觉检测完成: 发现 {result.bad_count}/{result.total_count} 个问题")
```

## 🎛️ 高级配置

### 自定义阈值

```python
# 方式1: 直接设置类属性
RuleHallucinationHHEM.dynamic_config.threshold = 0.3  # HHEM 更严格的检测
LLMHallucination.threshold = 0.3      # GPT 更严格的检测

# 方式2: 通过配置文件
{
    "rule_config": {
        "RuleHallucinationHHEM": {
            "threshold": 0.7  # 更宽松的检测
        }
        },
    "llm_config": {
        "LLMHallucination": {
            "model": "gpt-4o",
            "key": "YOUR_API_KEY",
            "api_url": "https://api.openai.com/v1/chat/completions",
            "threshold": 0.7  # 更宽松的检测
        }
    }
}
```

### 阈值建议

- **严格检测** (0.2-0.3): 用于高质量要求的生产环境
- **平衡检测** (0.4-0.6): 用于一般质量控制
- **宽松检测** (0.7-0.8): 用于初步筛选或宽容场景

### 性能优化配置

```python
# HHEM 批量处理优化
RuleHallucinationHHEM.load_model()  # 预加载模型
results = RuleHallucinationHHEM.batch_evaluate(data_list)  # 批量更高效

# GPT 多模型配置
{
    "custom_config": {
        "prompt_list": [
            "QUALITY_BAD_HALLUCINATION",
            "QUALITY_HELPFUL",
            "QUALITY_HARMLESS"
        ],
        "llm_config": {
            "LLMHallucination": {
                "model": "gpt-4o",
                "key": "YOUR_API_KEY",
                "api_url": "https://api.openai.com/v1/chat/completions"
            },
            "LLMText3HHelpful": {
                "model": "gpt-4o-mini",  # 使用不同模型
                "key": "YOUR_API_KEY",
                "api_url": "https://api.openai.com/v1/chat/completions"
            }
        }
    }
}
```

## 📊 输出结果解析

### ModelRes 字段说明

```python
result = RuleHallucinationHHEM.eval(data)  # 或 LLMHallucination.eval(data)

# 标准字段
result.eval_status      # bool: 是否检测到幻觉
result.type             # str: 质量类型标识
result.name             # str: 检测结果名称
result.reason           # List[str]: 详细分析原因

# 扩展字段
result.score            # float: 幻觉分数 (0.0-1.0)
result.verdict_details  # List[str]: 每个上下文的判断详情（GPT 模式）
result.consistency_scores # List[float]: HHEM 原始一致性分数（HHEM 模式）
```

### 典型输出示例

#### HHEM 输出示例
```
HHEM 幻觉分数: 0.650 (阈值: 0.500)
处理了 2 个上下文对：
  1. 上下文: "爱因斯坦因发现光电效应获得诺贝尔奖。"
     一致性: 0.95 → 幻觉分数: 0.05
  2. 上下文: "爱因斯坦在1921年获得诺贝尔奖。"
     一致性: 0.35 → 幻觉分数: 0.65
平均幻觉分数: 0.350
❌ 检测到幻觉: 超过阈值 0.500
```

#### GPT 输出示例
```
幻觉分数: 0.500 (阈值: 0.500)
发现 1 个矛盾:
  1. 实际输出与提供的上下文矛盾，上下文说爱因斯坦在1921年获得诺贝尔奖，而不是1969年。
发现 1 个事实一致:
  1. 实际输出与提供的上下文一致，都说爱因斯坦因发现光电效应获得诺贝尔奖。
❌ 检测到幻觉: 回答包含事实性矛盾
```

## 📁 数据集格式要求

### JSONL 格式示例

```jsonl
{"data_id": "1", "prompt": "问题", "content": "回答", "context": ["上下文1", "上下文2"]}
{"data_id": "2", "prompt": "问题", "content": "回答", "context": "单个上下文"}
```

### 自定义列名

```python
{
    "column_content": "generated_response",  # LLM生成的回答
    "column_prompt": "user_question",       # 用户问题
    "column_context": "retrieved_docs",     # 检索到的文档
    "column_id": "question_id"              # 数据ID
}
```

## 🔍 典型应用场景

### 1. RAG 系统质量监控

```python
# 实时基于RAG监控回答质量（使用本地HHEM）
def monitor_rag_response(question, generated_answer, retrieved_docs):
    data = Data(
        data_id=f"rag_{timestamp}",
        prompt=question,
        content=generated_answer,
        context=retrieved_docs
    )

    result = RuleHallucinationHHEM.eval(data)  # 本地、快速、免费

    if result.eval_status:
        logger.warning(f"检测到幻觉: {result.reason[0]}")
        # 触发人工审核或回答重生成
```

### 2. SFT 数据集预处理

```python
# 训练前检查SFT数据质量（批量处理使用HHEM）
input_data = {
    "input_path": "sft_training_data.jsonl",
    "custom_config": {
        "rule_config": {"RuleHallucinationHHEM": {"threshold": 0.4}}
    },
    "save_correct": True,  # 保存通过检测的数据用于训练
}
```

### 3. 模型输出后处理

```python
# 生产环境中过滤有问题的回答
def filter_hallucinated_responses(responses_with_context):
    clean_responses = []

    for item in responses_with_context:
        data = Data(**item)
        # 使用本地HHEM进行快速检测
        result = RuleHallucinationHHEM.eval(data)

        if not result.eval_status:  # 无幻觉
            clean_responses.append(item)
        else:
            log_quality_issue(item, result.reason[0])

    return clean_responses
```

### 4. 企业级部署

```python
# 完整的企业级RAG系统（集成检索+生成+幻觉检测）
class RAGWithHallucinationDetection:
    def __init__(self, retriever, llm, hallucination_detector):
        self.retriever = retriever
        self.llm = llm
        self.detector = hallucination_detector
        # 预加载HHEM模型以提高性能
        self.detector.load_model()

    def generate_answer(self, question):
        # 1. 检索相关文档
        retrieved_docs = self.retriever.search(question, top_k=3)

        # 2. 生成回答
        context = "\n".join(retrieved_docs)
        prompt = f"基于以下文档回答问题:\n{context}\n\n问题: {question}\n回答:"
        generated_answer = self.llm.generate(prompt)

        # 3. 幻觉检测
        data = Data(
            data_id=generate_id(),
            prompt=question,
            content=generated_answer,
            context=retrieved_docs  # 检索到的原始文档
        )

        hallucination_result = self.detector.eval(data)

        # 4. 根据检测结果决定是否返回答案
        if hallucination_result.eval_status:
            self.log_hallucination(question, generated_answer, hallucination_result)
            return {
                "answer": None,
                "warning": "检测到潜在幻觉，请人工审核",
                "retrieved_docs": retrieved_docs,
                "hallucination_score": getattr(hallucination_result, 'score', 'N/A')
            }
        else:
            return {
                "answer": generated_answer,
                "retrieved_docs": retrieved_docs,
                "confidence": "high"
            }

    def log_hallucination(self, question, answer, result):
        # 记录幻觉检测结果用于系统优化
        logger.warning(f"幻觉检测警告: {result.reason[0]}")

# 使用示例
rag_system = RAGWithHallucinationDetection(
    retriever=VectorRetriever("knowledge_base"),
    llm=OpenAILLM("gpt-4"),
    detector=RuleHallucinationHHEM
)

result = rag_system.generate_answer("什么是深度学习？")
```

## 🏗️ 架构设计

### 核心组件结构

```
dingo/
├── model/
│   ├── llm/
│   │   └── llm_hallucination.py            # GPT-based 检测（DeepEval风格）
│   ├── rule/
│   │   └── rule_hallucination_hhem.py      # HHEM-2.1-Open 集成
│   ├── prompt/prompt_hallucination.py       # GPT 提示词模板
│   └── response/response_hallucination.py   # 响应数据结构
├── io/input/Data.py                         # 扩展Data类支持context
├── examples/hallucination/                  # 使用示例
│   ├── sdk_rule_hhem_detection.py          # Rule-based HHEM 使用示例
│   ├── sdk_hallucination_detection.py      # GPT 使用示例
│   └── dataset_hallucination_evaluation.py # 批量评估示例
└── requirements/hhem_integration.txt        # HHEM 依赖
```
