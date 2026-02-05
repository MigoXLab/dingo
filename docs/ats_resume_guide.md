# Dingo ATS 简历优化工具指南

本指南介绍如何使用 Dingo 的 ATS（Applicant Tracking System）简历优化工具，包括 **LLMKeywordMatcher** 关键词匹配器、**LLMResumeOptimizer** 简历优化器和 **LLMScout** 求职战略分析器。

## 🎯 功能概述

ATS 工具套件用于：

- **简历-JD 匹配分析**: 评估简历与职位描述的匹配程度
- **关键词缺失识别**: 识别简历中缺少的必需技能和加分项
- **智能简历优化**: 自动注入缺失关键词，使用 STAR 法则润色经历描述
- **求职战略分析**: 基于行业报告和用户画像生成精准求职策略

## 🔧 核心组件

### 1. LLMKeywordMatcher（关键词匹配器）

分析简历与 JD 的匹配度，输出加权匹配分数和详细分析报告。

**核心功能：**
- 语义匹配（不仅是字符串匹配）
- 同义词自动识别（如 k8s → Kubernetes）
- 负向约束识别（Excluded 技能警告）
- 基于证据的匹配（引用简历原文）

**输入字段：**
| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `content` | str | ✅ | 简历文本 |
| `prompt` | str | ✅ | 职位描述 (JD) |

**输出字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| `score` | float | 匹配分数 (0.0-1.0) |
| `status` | bool | 是否低于阈值 (True=低于，False=通过) |
| `reason` | List[str] | 详细分析报告（文本格式） |

**内置同义词映射 (SYNONYM_MAP)：**
```
k8s → Kubernetes, js → JavaScript, ts → TypeScript
py → Python, tf → TensorFlow, pt → PyTorch
nodejs → Node.js, postgres → PostgreSQL
aws → Amazon Web Services, gcp → Google Cloud Platform
ml → Machine Learning, dl → Deep Learning, nlp → NLP
```

### 2. LLMResumeOptimizer（简历优化器）

基于匹配分析结果优化简历，支持两种模式：

**模式对比：**
| 模式 | 触发条件 | 功能 |
|------|----------|------|
| 通用润色 | `context` 为空 | STAR 法则润色、格式统一 |
| 针对性优化 | `context` 包含匹配报告 | 关键词注入、弱化负面技能 |

**输入字段：**
| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `content` | str | ✅ | 简历文本 |
| `prompt` | str | ❌ | 目标岗位 |
| `context` | str/dict | ❌ | 匹配报告 JSON (触发针对性模式) |

### 3. LLMScout（求职战略分析器）

基于行业报告和用户画像，生成精准求职策略。

**核心功能：**
- 行业报告解析（公司提取、财务信号识别）
- 用户画像解析（学历、技能、风险偏好）
- 人岗匹配评分（5维度加权打分）
- 搜索策略生成（关键词、平台推荐）
- 面试风格预测

**输入字段：**
| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `content` | str | ✅ | 行业报告文本 |
| `prompt` | str | ✅ | 用户画像（自然语言描述） |
| `context` | str | ❌ | 个人简历文本（提升技能匹配精度） |

**输出字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| `score` | float | 综合匹配分数 (0.0-1.0) |
| `status` | bool | 是否通过阈值检查 |
| `reason` | List[str] | 分析摘要（目标公司、Tier分类等） |
| `strategy_context` | dict | 完整策略上下文（公司列表、搜索关键词等） |

**评分权重 (SCORE_WEIGHTS)：**
| 维度 | 权重 | 说明 |
|------|------|------|
| skill_match | 40% | 技能匹配度 |
| risk_alignment | 20% | 风险偏好匹配 |
| career_stage_fit | 15% | 职业阶段匹配 |
| location_match | 10% | 地点匹配 |
| financial_health | 15% | 公司财务健康度 |

**Tier 分类阈值 (TIER_THRESHOLDS)：**
| Tier | 分数要求 | 说明 |
|------|----------|------|
| Tier 1 | ≥ 0.75 | 强烈推荐 |
| Tier 2 | ≥ 0.50 | 可以考虑 |
| Not Recommended | < 0.50 | 不推荐 |

**财务信号分类：**
- `expansion`: 扩张期（ROE上升、融资完成、扩招）
- `stable`: 稳定期（ROE平稳、正常招聘）
- `contraction`: 收缩期（裁员、ROE下降）
- `uncertain`: 不确定（信号混合）
- `unknown`: 未知（信息不足）

## 🚀 快速开始

### 基本使用

```python
from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.llm_keyword_matcher import LLMKeywordMatcher
from dingo.model.llm.llm_resume_optimizer import LLMResumeOptimizer

# 配置 LLM
config = EvaluatorLLMArgs(
    key='YOUR_API_KEY',
    api_url='https://api.deepseek.com',
    model='deepseek-chat',
)
LLMKeywordMatcher.dynamic_config = config
LLMResumeOptimizer.dynamic_config = config

# 准备数据
resume = """
张三 | Python开发工程师 | 5年经验
技能：Python, Django, MySQL
"""

jd = """
高级Python工程师
要求：Python（必需）、Docker（必需）、Kubernetes（加分）
"""

# Step 1: 匹配分析
match_data = Data(data_id='test_1', content=resume, prompt=jd)
match_result = LLMKeywordMatcher.eval(match_data)
print(f"匹配分数: {match_result.score}")
print(f"是否通过: {'通过' if not match_result.status else '未通过'}")
print(f"分析报告: {match_result.reason[0]}")

# Step 2: 简历优化
optimize_data = Data(
    data_id='test_2',
    content=resume,
    prompt='高级Python工程师',
    context='{"match_details": {"missing": [{"skill": "Docker", "importance": "Required"}]}}'
)
opt_result = LLMResumeOptimizer.eval(optimize_data)
print(f"优化摘要: {opt_result.reason[0]}")
print(f"完整结果: {opt_result.optimized_content}")
```

### Scout 使用示例

```python
from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.llm_scout import LLMScout

# 配置 LLM
LLMScout.dynamic_config = EvaluatorLLMArgs(
    key='YOUR_API_KEY',
    api_url='https://api.deepseek.com',
    model='deepseek-chat',
)

# 行业报告
industry_report = """
2024年Q3科技行业报告
1. 字节跳动 - ROE上升，计划扩招2000人
2. 阿里巴巴 - ROE平稳，技术岗位保持招聘
"""

# 用户画像
user_profile = """
我是2024届CS硕士，会Python和PyTorch，想找大厂，偏好稳定
"""

data = Data(
    data_id='scout_1',
    content=industry_report,
    prompt=user_profile,
    context="简历文本（可选）"  # 提供简历可提升技能匹配精度
)

result = LLMScout.eval(data)
print(f"综合分数: {result.score}")
print(f"策略分析: {result.reason[0]}")

# 访问完整策略上下文
if hasattr(result, 'strategy_context'):
    ctx = result.strategy_context
    for company in ctx.get('target_companies', []):
        print(f"- {company['name']}: {company['tier']} ({company['match_score']:.0%})")
```

## 📊 匹配分数计算

### 权重公式

```
score = (Required_Matched × 2 + Nice_Matched × 1) / (Required_Total × 2 + Nice_Total × 1)
```

| 类别 | 权重 | 说明 |
|------|------|------|
| Required (必需) | ×2 | 缺失会显著降低分数 |
| Nice-to-have (加分) | ×1 | 缺失影响较小 |
| Excluded (排除) | 不计分 | 仅生成警告，不影响分数 |

### 阈值配置

```python
# 调整匹配阈值 (默认 0.6)
LLMKeywordMatcher.threshold = 0.7  # 更严格
```

## 📝 针对性优化策略

### P1 - 强制注入 (Required)
必需技能必须出现在简历中，添加到技能列表或自然融入工作经历。

### P2 - 关联注入 (Nice-to-have)
使用关联提及：`MySQL (熟悉 PostgreSQL 概念)`

### P3 - 隐含推断
- 有 LoRA/SFT 经验 → 可推断 PyTorch
- 有 RAG 项目 → 可推断向量数据库

### P4 - 弱化处理 (Excluded)
不删除历史事实，仅移到技能列表末尾。

### 禁止造假规则
- ❌ 禁止发明不存在的公司、项目或经历
- ✅ 无法融入的关键词放入 `keywords_unused` 列表

## 📁 输出格式

### KeywordMatcher 输出

结果存放在 `result.reason[0]` 中，格式化的文本报告：

```python
# 访问方式
result = LLMKeywordMatcher.eval(data)
print(result.reason[0])  # 完整分析报告
print(result.score)      # 匹配分数 (0.0-1.0)
```

**`reason[0]` 内容示例：**
```
JD Analysis: 高级Python工程师
Keywords: Python, Docker, Kubernetes, MySQL

Match Score: 0.65 (Threshold: 0.60)

Required (Matched): Python
Required (Missing): Docker
Nice-to-have (Matched): MySQL
Nice-to-have (Missing): Kubernetes
```

### ResumeOptimizer 输出

**`reason[0]`**: 人类可读的摘要文本
**`optimized_content`**: 完整的 JSON 优化结果

```python
# 访问方式
result = LLMResumeOptimizer.eval(data)

# 摘要文本
print(result.reason[0])

# 完整 JSON 结果
opt = result.optimized_content
print(opt.get('optimization_summary'))
print(opt.get('section_changes'))
```

**`reason[0]` 内容示例：**
```
Overall: 优化了专业技能板块
Keywords Added: Docker
Associative: Kubernetes (了解概念)
Sections Modified: 专业技能
```

**`optimized_content` 结构：**
```json
{
  "optimization_summary": {
    "keywords_added": ["Docker"],
    "keywords_associative": ["Kubernetes (了解概念)"],
    "keywords_unused": []
  },
  "section_changes": [
    {
      "section_name": "专业技能",
      "before": "Python, Django, MySQL",
      "after": "Python, Django, MySQL, Docker, Kubernetes (了解概念)",
      "changes": ["添加 Docker", "关联提及 Kubernetes"]
    }
  ]
}
```

## 🌐 语言支持

工具自动检测简历语言并使用对应的 Prompt：
- 中文简历 → 中文 Prompt
- 英文简历 → 英文 Prompt

检测规则：中文字符占比 > 10% 判定为中文。

## 📂 示例脚本

```bash
# 运行关键词匹配示例
python examples/ats_resume/sdk_keyword_matcher.py

# 运行简历优化示例
python examples/ats_resume/sdk_resume_optimizer.py

# 运行求职战略分析示例
python examples/ats_resume/sdk_scout.py
```
