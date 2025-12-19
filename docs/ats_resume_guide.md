# Dingo ATS 简历优化工具指南

本指南介绍如何使用 Dingo 的 ATS（Applicant Tracking System）简历优化工具，包括 **LLMKeywordMatcher** 关键词匹配器和 **LLMResumeOptimizer** 简历优化器。

## 🎯 功能概述

ATS 工具套件用于：

- **简历-JD 匹配分析**: 评估简历与职位描述的匹配程度
- **关键词缺失识别**: 识别简历中缺少的必需技能和加分项
- **智能简历优化**: 自动注入缺失关键词，使用 STAR 法则润色经历描述

## 🔧 核心组件

### 1. LLMKeywordMatcher（关键词匹配器）

分析简历与 JD 的匹配度，输出加权匹配分数和详细分析报告。

**输入字段：**
| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `content` | str | ✅ | 简历文本 |
| `prompt` | str | ✅ | 职位描述 (JD) |

**输出字段：**
| 字段 | 类型 | 说明 |
|------|------|------|
| `score` | float | 匹配分数 (0.0-1.0) |
| `error_status` | bool | 是否低于阈值 (默认 0.6) |
| `reason` | List[str] | 详细分析报告 |

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

# Step 2: 简历优化
optimize_data = Data(
    data_id='test_2',
    content=resume,
    prompt='高级Python工程师',
    context='{"match_details": {"missing": [{"skill": "Docker", "importance": "Required"}]}}'
)
opt_result = LLMResumeOptimizer.eval(optimize_data)
print(f"优化结果: {opt_result.reason[0]}")
```

## 📊 匹配分数计算

### 权重分配

| 类别 | 权重 | 说明 |
|------|------|------|
| Required (必需) | 0.7 | 缺失会显著降低分数 |
| Nice-to-have (加分) | 0.3 | 缺失影响较小 |
| Excluded (排除) | -0.1 | 存在会扣分 |

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

结果同样存放在 `result.reason[0]` 中，JSON 格式：

```python
# 访问方式
result = LLMResumeOptimizer.eval(data)
import json
output = json.loads(result.reason[0])
```

**`reason[0]` 内容示例：**
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
```
