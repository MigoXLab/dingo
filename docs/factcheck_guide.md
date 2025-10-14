# 事实性评估指南

Dingo 提供了基于 GPT-5 System Card 的两阶段事实性评估能力，可以帮助您：
- 评估 LLM 输出的事实准确性
- 检测 RAG 系统的检索-生成质量
- 验证训练数据的事实性
- 监控多轮对话的事实一致性

## 评估方法

### 两阶段评估流程

LLMFactCheckPublic 采用两阶段评估流程：

1. **声明提取阶段**：
   - 将文本分解为独立的事实性声明
   - 过滤掉主观、推测性的内容
   - 标准化指代（如将代词替换为具体对象）

2. **事实验证阶段**：
   - 对每个声明进行网络搜索验证
   - 收集支持或反驳的证据
   - 给出 true/false/unsure 的判断

### 评分机制

```python
factual_ratio = true_claims / total_claims
```

- true：有充分证据支持的声明
- false：有证据明确反驳的声明
- unsure：证据不足或存在争议的声明

默认阈值为 0.8（80% 真实率）。

### 评估结果

每个声明的验证结果包含：
- 判断（true/false/unsure）
- 推理说明
- 支持证据（URL、相关片段、总结）

## 使用场景

### 场景一：评估单条回复

```python
from dingo.io import Data
from dingo.model.llm.llm_factcheck_public import LLMFactCheckPublic

# 配置评估器
LLMFactCheckPublic.dynamic_config.key = 'your-api-key'
LLMFactCheckPublic.dynamic_config.api_url = 'https://api.deepseek.com/v1'
LLMFactCheckPublic.dynamic_config.model = 'deepseek-chat'

# 创建数据对象
data = Data(
    data_id="test_1",
    prompt="Who is Albert Einstein?",
    content="Albert Einstein was a German-born theoretical physicist..."
)

# 执行评估
result = LLMFactCheckPublic.eval(data)

# 查看结果
print(f"Factual ratio: {result.score:.2%}")
print(f"Reason: {result.reason}")
print("\nDetailed results:")
for claim in result.raw_resp["results"]:
    print(f"\nClaim: {claim.claim}")
    print(f"Answer: {claim.answer}")
    print(f"Reasoning: {claim.reasoning}")
```

### 场景二：评估数据集

```python
from dingo.config import InputArgs
from dingo.exec import Executor

# 准备配置
input_data = {
    "input_path": "test/data/your_test.jsonl",
    "output_path": "output/factcheck_evaluation/",
    "dataset": {
        "source": "local",
        "format": "jsonl",
        "field": {
            "prompt": "question",
            "content": "response"
        }
    },
    "executor": {
        "eval_group": "factuality",
        "result_save": {
            "bad": True,  # 保存不实信息
            "good": True  # 保存真实信息
        }
    },
    "evaluator": {
        "llm_config": {
            "LLMFactCheckPublic": {
                "model": "deepseek-chat",
                "key": "your-api-key",
                "api_url": "https://api.deepseek.com/v1",
                "parameters": {
                    "temperature": 0.1
                }
            }
        }
    }
}

# 执行评估
input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()

# 查看结果
print(f"Total processed: {result.total}")
print(f"Factual responses: {result.num_good}")
print(f"Non-factual responses: {result.num_bad}")
print(f"Overall factuality score: {result.score:.2%}")
```

### 场景三：RAG 系统评估

```python
# 准备 RAG 输出数据
rag_data = {
    "data_id": "rag_1",
    "prompt": "What is quantum entanglement?",
    "content": "Quantum entanglement is a phenomenon...",
    "context": [  # 检索到的文档
        "doc1: Quantum entanglement occurs when...",
        "doc2: In quantum physics, entanglement is..."
    ]
}

# 评估生成内容与检索文档的一致性
data = Data(**rag_data)
result = LLMFactCheckPublic.eval(data)

# 分析结果
print(f"Factual consistency: {result.score:.2%}")
for claim in result.raw_resp["results"]:
    if claim.answer != "true":
        print(f"\nPotential hallucination:")
        print(f"Claim: {claim.claim}")
        print(f"Evidence: {claim.reasoning}")
```

### 场景四：多轮对话监控

```python
conversation = [
    {
        "data_id": "turn_1",
        "prompt": "Tell me about the solar system.",
        "content": "The solar system consists of..."
    },
    {
        "data_id": "turn_2",
        "prompt": "What about Mars?",
        "content": "Mars is the fourth planet..."
    }
]

# 逐轮评估事实性
for turn in conversation:
    data = Data(**turn)
    result = LLMFactCheckPublic.eval(data)
    print(f"\nTurn {turn['data_id']}:")
    print(f"Factual ratio: {result.score:.2%}")
    if result.score < LLMFactCheckPublic.threshold:
        print("Warning: Potential misinformation detected!")
```

## 最佳实践

1. **阈值调整**：
   - 严格场景（如医疗、金融）：提高阈值（>0.9）
   - 一般场景：使用默认阈值（0.8）
   - 创意场景：可适当降低阈值（0.6-0.7）

2. **批处理优化**：
   - 使用 `batch_size` 参数控制批量大小
   - 默认为 10，可根据需要调整
   - 较大的批量可提高处理速度，但会增加单次请求的复杂度

3. **网络搜索控制**：
   - 默认启用网络搜索（`web_enabled=True`）
   - 如果只需验证特定上下文，可以禁用网络搜索
   - 禁用网络搜索可以加快评估速度

4. **结果分析**：
   - 检查 `raw_resp` 中的详细验证过程
   - 关注 `unsure` 的声明，可能需要人工复核
   - 对于 `false` 声明，查看具体的反驳证据

5. **集成建议**：
   - 在生产环境中设置事实性分数阈值
   - 对于低于阈值的回复，可以：
     * 要求 LLM 重新生成
     * 添加事实性警告
     * 引导用户查看源文档
     * 记录问题案例以改进系统

## 技术细节

### 文件结构

```
dingo/
  ├── model/
  │   ├── llm/
  │   │   └── llm_factcheck_public.py  # 评估器实现
  │   └── prompt/
  │       └── prompt_factcheck.py      # 评估提示词
  └── examples/
      └── factcheck/
          └── dataset_factcheck_evaluation.py  # 数据集评估示例
```

### 评估提示词

评估器使用两个核心提示词：

1. `CLAIM_LISTING`：用于提取事实性声明
   - 将文本分解为独立声明
   - 标准化指代和表述
   - 过滤非事实性内容

2. `FACT_CHECKING`：用于验证声明
   - 搜索相关证据
   - 分析证据可靠性
   - 给出判断和理由

### 评估结果格式

```python
ModelRes(
    score=0.85,  # 事实性得分
    threshold=0.8,  # 判断阈值
    reason=["Found 10 claims: 8 true, 1 false, 1 unsure..."],
    raw_resp={
        "claims": ["claim1", "claim2", ...],
        "results": [
            FactCheckResult(
                claim="...",
                answer="true",
                reasoning="...",
                supporting_evidence=[...]
            ),
            ...
        ],
        "metrics": {
            "factual_ratio": 0.85,
            "true_count": 8,
            "false_count": 1,
            "unsure_count": 1,
            "total_claims": 10
        }
    }
)
```

## 参考资料

1. [GPT-5 System Card](https://cdn.openai.com/pdf/8124a3ce-ab78-4f06-96eb-49ea29ffb52f/gpt5-system-card-aug7.pdf) - 两阶段事实性评估方法
2. [Dingo 文档](https://deepwiki.com/MigoXLab/dingo) - 完整的 API 文档和更多示例
