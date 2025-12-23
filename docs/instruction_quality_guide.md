# Instruction Quality Evaluation Guide - 指令质量评估指南

## 🎯 概述

本指南介绍如何使用 Dingo 的指令质量评估功能，用于评估 SFT（Supervised Fine-Tuning）数据集中 query/instruction 的质量。这对于知识蒸馏、指令微调数据准备至关重要。

### ✨ 新增评估指标

基于最新研究成果，我们提供了两个核心评估指标：

| 指标 | 评估内容 | 研究基础 | 评分范围 |
|------|---------|---------|---------|
| **Instruction Clarity<br/>指令清晰度** | 自描述性、一致性、具体性、完整性 | IFEval (Google, 2023)<br/>Self-Instruct (UW, 2023) | 0-10 |
| **Task Difficulty<br/>任务难度** | 认知复杂度、步骤复杂度、领域知识、约束密度 | Task Complexity (DeepMind, 2023)<br/>OpenAI Math Problem Difficulty (2024) | 0-10 |

---

## 📊 指标详解

### 1️⃣ Instruction Clarity（指令清晰度）

**评估目标**：衡量指令是否清晰、明确、易于理解和执行。

#### 评估维度（总分 10 分）

| 维度 | 分值 | 评估内容 |
|------|------|---------|
| **Self-Descriptiveness<br/>自描述性** | 2.5 | 指令是否包含足够信息，无需额外上下文 |
| **Consistency<br/>一致性** | 2.5 | 指令内部是否一致，无矛盾 |
| **Specificity<br/>具体性** | 2.5 | 指令是否具体明确，避免歧义 |
| **Completeness<br/>完整性** | 2.5 | 指令是否包含所有必要信息（输入、输出、约束、格式） |

#### 评分标准

**优秀 (8-10 分)**：
- ✅ 自包含，无需额外说明
- ✅ 内部完全一致
- ✅ 非常具体，有明确成功标准
- ✅ 包含所有必要元素

**良好 (6-8 分)**：
- ⚠️ 大部分清晰，个别细节需推断
- ✅ 基本一致，有轻微模糊
- ⚠️ 较具体但允许一定解释空间
- ⚠️ 大部分信息齐全，个别细节缺失

**及格 (4-6 分)**：
- ⚠️ 需要一定上下文理解
- ⚠️ 有一些不一致之处
- ⚠️ 比较模糊，解释空间较大
- ⚠️ 缺少重要信息

**不合格 (0-4 分)**：
- ❌ 严重依赖外部上下文
- ❌ 内部矛盾
- ❌ 过于模糊，难以理解意图
- ❌ 关键信息缺失

#### 示例

**优秀示例（9.5 分）**：
```
编写一个 Python 函数 calculate_discount，接受参数：
- original_price (float): 原价
- discount_percentage (float, 0-100): 折扣百分比
返回应用折扣后的最终价格，保留 2 位小数。
包含输入验证：价格必须为正，折扣在 0-100 之间。
添加详细 docstring 和使用示例。
```

**不合格示例（2.0 分）**：
```
写个代码
```

---

### 2️⃣ Task Difficulty（任务难度）

**评估目标**：衡量任务的复杂度和挑战性，用于数据集平衡和质量控制。

#### 评估维度（总分 10 分）

| 维度 | 权重 | 分值 | 评估内容 |
|------|------|------|---------|
| **Cognitive Complexity<br/>认知复杂度** | 30% | 3.0 | 基于 Bloom 分类法的认知层次（记忆→理解→应用→分析→评估→创造） |
| **Step Complexity<br/>步骤复杂度** | 30% | 3.0 | 任务步骤数量及依赖关系（单步 vs 多步 vs 递归/分支） |
| **Domain Knowledge<br/>领域知识** | 20% | 2.0 | 所需专业知识程度（常识 vs 专业知识 vs 专家知识） |
| **Constraint Density<br/>约束密度** | 20% | 2.0 | 约束条件的数量和严格程度 |

#### 难度级别

| 级别 | 分数范围 | 特征 | 适用场景 |
|------|---------|------|---------|
| **Easy<br/>简单** | 0-3 | 单步、常识、少约束 | 快速知识蒸馏、基础训练 |
| **Moderate<br/>中等** | 4-6 | 多步、专业知识、中等约束 | 标准 SFT 训练 |
| **Hard<br/>困难** | 7-8 | 复杂推理、专家知识、严格约束 | 高质量模型训练 |
| **Expert<br/>专家** | 9-10 | 深度推理、前沿知识、多重约束 | 专家能力评估 |

#### 示例

**简单任务（2.5 分）**：
```
将 'Hello World' 翻译成法语
```
- 认知：记忆级别
- 步骤：单步
- 知识：基础语言知识
- 约束：无

**中等任务（5.5 分）**：
```
编写 Python 函数求列表中所有质数的和，包含错误处理和单元测试
```
- 认知：应用+分析
- 步骤：多步（质数判断 + 求和 + 错误处理 + 测试）
- 知识：算法基础
- 约束：多个组件要求

**困难任务（8.0 分）**：
```
设计分布式系统架构，支持 10万 QPS，99.99% 可用性。
包括服务拆分、数据一致性、故障恢复、监控方案。
考虑 CAP 定理权衡，画出架构图并详细说明。
```
- 认知：评估+创造
- 步骤：复杂多步，相互依赖
- 知识：深度专业知识
- 约束：多个严格性能指标

**专家任务（9.5 分）**：
```
证明或反驳：对于任意满足 ∫₀¹ f(x)² dx < ∞ 的连续函数 f: [0,1] → ℝ，
存在多项式序列 {pₙ} 使得 ||f - pₙ||₂ → 0。
使用测度论和泛函分析提供严格证明。
```
- 认知：创造（构造证明）
- 步骤：高度复杂的逻辑链
- 知识：研究生级数学
- 约束：严格的数学证明要求

---

## 🚀 使用方法

### 安装

确保已安装 Dingo：

```bash
pip install dingo-python
```

### 环境配置

```bash
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="https://api.deepseek.com"  # 可选
export OPENAI_MODEL="deepseek-chat"  # 可选
```

### 基础使用

#### 1. 准备数据

创建 JSONL 文件（`instructions.jsonl`）：

```jsonl
{"instruction": "Write a Python function to calculate factorial"}
{"instruction": "写个代码"}
{"instruction": "Design a microservices architecture..."}
```

#### 2. 评估指令清晰度

```python
from dingo.config import InputArgs
from dingo.exec import Executor
from dingo.model.llm.instruction_quality import LLMInstructionClarity

input_data = {
    "task_name": "clarity_check",
    "input_path": "instructions.jsonl",
    "output_path": "outputs/",
    "dataset": {"source": "local", "format": "jsonl"},
    "executor": {
        "max_workers": 5,
        "result_save": {"bad": True, "good": True}
    },
    "evaluator": [
        {
            "fields": {"content": "instruction"},
            "evals": [
                {
                    "name": "LLMInstructionClarity",
                    "config": {
                        "model": "deepseek-chat",
                        "key": "your-api-key",
                        "api_url": "https://api.deepseek.com",
                        "parameters": {"threshold": 6.0}
                    }
                }
            ]
        }
    ]
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
summary = executor.execute()

print(f"清晰指令: {summary.num_good}/{summary.total}")
```

#### 3. 评估任务难度

```python
{
    "evals": [
        {
            "name": "LLMTaskDifficulty",
            "config": {
                "model": "deepseek-chat",
                "key": "your-api-key",
                "api_url": "https://api.deepseek.com",
                "parameters": {
                    "min_difficulty": 3.0,  # 可选：过滤太简单的
                    "max_difficulty": 8.0,  # 可选：过滤太难的
                }
            }
        }
    ]
}
```

#### 4. 综合评估

```python
{
    "evals": [
        {
            "name": "LLMInstructionClarity",
            "config": {...}
        },
        {
            "name": "LLMTaskDifficulty",
            "config": {...}
        }
    ]
}
```

### 快速开始脚本

我们提供了完整的示例脚本：

```bash
# 只评估清晰度
python examples/custom/evaluate_instruction_quality.py clarity

# 只评估难度
python examples/custom/evaluate_instruction_quality.py difficulty

# 综合评估（推荐）
python examples/custom/evaluate_instruction_quality.py both

# 分析难度分布（用于数据集平衡）
python examples/custom/evaluate_instruction_quality.py distribution
```

---

## 📈 实践建议

### 1. SFT 数据准备流程

```
原始指令
    ↓
① 清晰度筛选 (threshold=6.0)
    ↓
清晰的指令
    ↓
② 难度评估
    ↓
③ 难度分布平衡
    ↓
高质量 SFT 数据集
```

### 2. 数据集质量标准

**优秀 SFT 数据集**：
- ✅ 95%+ 指令清晰度 ≥ 6.0
- ✅ 难度分布合理：
  - Easy (0-3): 15-20%
  - Moderate (4-6): 50-60%
  - Hard (7-8): 20-25%
  - Expert (9-10): 5-10%

### 3. 常见问题处理

**问题1: 过多简单指令**
```python
# 设置最低难度阈值
"parameters": {"min_difficulty": 3.0}
```

**问题2: 指令模糊不清**
```python
# 提高清晰度要求
"parameters": {"threshold": 7.0}
```

**问题3: 难度分布不均**
- 使用 `distribution` 模式分析当前分布
- 针对性补充缺失难度级别的数据
- 移除过多的某一难度级别数据

### 4. 成本优化

**大规模数据（> 10万条）**：
```python
# 方案1: 先用规则快速筛选基础质量
"evals": [
    {"name": "RuleContentNull"},      # 过滤空指令
    {"name": "RuleSpecialCharacter"}, # 过滤异常字符
]

# 方案2: 对筛选后的数据进行深度评估
"evals": [
    {"name": "LLMInstructionClarity"},
    {"name": "LLMTaskDifficulty"}
]
```

**中等规模（1万-10万条）**：
```python
# 降低并发，避免 API 限流
"max_workers": 5,
```

**小规模（< 1万条）**：
```python
# 可以更高并发
"max_workers": 10,
```

---

## 🔬 研究基础

### 学术参考

1. **IFEval: Instruction Following Evaluation**
   - Google Research, 2023
   - 提出了系统化的指令遵循评估框架

2. **Self-Instruct: Aligning Language Models with Self-Generated Instructions**
   - University of Washington, 2023
   - 指令质量对模型性能的影响研究

3. **Task Complexity in Instruction Following**
   - Google DeepMind, 2023
   - 任务复杂度的多维度分析框架

4. **Measuring Difficulty of Math Problems**
   - OpenAI, 2024
   - 任务难度的量化评估方法

### 评估原则

1. **基于 Bloom 认知分类法**：从记忆到创造的六个层次
2. **考虑实际 LLM 能力**：难度评估要符合当前模型水平
3. **多维度综合评分**：避免单一维度的片面性
4. **严格但公允**：现实世界的指令不会完美

---

## 📊 输出格式

### 清晰度评估输出

```json
{
    "score": 8.5,
    "dimensions": {
        "self_descriptiveness": 2.5,
        "consistency": 2.0,
        "specificity": 2.0,
        "completeness": 2.0
    },
    "issues": [],
    "strengths": ["Clear task definition", "Well-specified output format"],
    "suggestions": ["Could specify tone/style more explicitly"],
    "reason": "High-quality instruction..."
}
```

### 难度评估输出

```json
{
    "difficulty_score": 7.5,
    "difficulty_level": "Hard",
    "dimensions": {
        "cognitive_complexity": 2.5,
        "step_complexity": 2.0,
        "domain_knowledge": 1.5,
        "constraint_density": 1.5
    },
    "estimated_time": "10-20 minutes",
    "suitable_for": ["Advanced fine-tuning"],
    "key_challenges": ["Requires multi-step reasoning"],
    "reason": "This is a hard task..."
}
```

---

## 💡 常见问题

### Q1: 如何确定清晰度阈值？

**建议**：
- 基础训练：threshold = 5.0（宽松）
- 标准 SFT：threshold = 6.0（平衡）
- 高质量数据：threshold = 7.0（严格）

### Q2: 难度分布应该如何设置？

**推荐分布**：
- 知识蒸馏：Easy 30%, Moderate 50%, Hard 20%
- 通用 SFT：Easy 20%, Moderate 50%, Hard 25%, Expert 5%
- 专家训练：Moderate 30%, Hard 50%, Expert 20%

### Q3: 评估速度慢怎么办？

1. 降低并发数（避免限流）
2. 使用更快的 LLM（如 GPT-4o-mini）
3. 对关键数据进行抽样评估
4. 先用规则筛选再用 LLM 深度评估

### Q4: 如何处理非英文指令？

两个评估器都支持多语言（中文、英文等），LLM 会根据指令语言进行评估。

### Q5: 评估结果如何应用到数据筛选？

```python
# 读取评估结果
bad_clarity = "outputs/instruction_clarity/bad/bad.jsonl"  # 不清晰的
good_difficulty = "outputs/task_difficulty/good/good.jsonl"  # 所有难度评估

# 根据结果筛选：
# - 移除 clarity < 6.0 的指令
# - 平衡各难度级别的数量
# - 优先保留 clarity ≥ 7.0 且 difficulty 在目标范围的指令
```

---

## 📚 相关文档

- [RAG Evaluation Metrics Guide](rag_evaluation_metrics.md)
- [Hallucination Detection Guide](hallucination_detection_guide.md)
- [Text Quality Evaluation](../README.md#evaluation-metrics)

---

## 🤝 贡献

如果您有改进建议或发现问题，欢迎：
- 提交 Issue
- 发起 Pull Request
- 加入我们的 Discord/WeChat 讨论

**Happy Evaluating! 🎉**
