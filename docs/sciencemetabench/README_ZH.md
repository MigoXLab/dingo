# ScienceMetaBench 使用指南

[English](README.md) | [中文](README_ZH.md)

## 📖 简介

ScienceMetaBench 是一个用于评估科学文献 PDF 元数据提取准确性的基准测试数据集。本文档介绍如何使用 Dingo 框架对提取的元数据进行质量评估。

**数据集地址**: 🤗 [HuggingFace - ScienceMetaBench](https://huggingface.co/datasets/opendatalab/ScienceMetaBench)

### 支持的数据类型

- **学术论文 (Paper)**: 主要来自学术期刊和会议论文
- **教科书 (Textbook)**: 正式出版的教科书
- **电子书 (Ebook)**: 数字化的历史文献和书籍

## 🚀 快速开始

### 1. 安装依赖

#### 安装 Dingo

**方式一：安装指定版本**

```bash
pip install dingo-python
```

**方式二：开发模式安装（推荐用于本地开发）**

```bash
git clone https://github.com/MigoXLab/dingo.git
cd dingo
git checkout dev
pip install -e .
```


### 2. 准备数据

数据格式为 JSONL，每条记录包含以下字段：

#### 字段说明

- **`sha256`**: 唯一标识符，用于追溯源文件

每个元数据字段应包含 `standard` 和 `produced` 两个子字段：
- **`standard`**: 标准答案值（基准数据）
  - **来源**: 从 [ScienceMetaBench 数据集](https://huggingface.co/datasets/opendatalab/ScienceMetaBench)获取

- **`produced`**: 待评估的提取结果
  - **来源**: 从 PDF 中提取

**支持的字段**：
- 学术论文 (Paper): `doi`, `title`, `author`, `keyword`, `abstract`, `pub_time`
- 教科书/电子书 (Textbook/Ebook): `isbn`, `title`, `author`, `abstract`, `category`, `pub_time`, `publisher`

**格式示例**：
```json
{
  "sha256": "唯一标识符",
  "doi": {
    "standard": "10.1234/example",
    "produced": "10.1234/example"
  },
  "title": {
    "standard": "示例论文标题",
    "produced": "示例论文标题"
  }
}
```

### 3. 运行评估

完整的示例代码请参考：`examples/sciencemetabench/paper.py`

**配置参数说明**：

- `input_path`: 输入 JSONL 文件路径
- `dataset.source`: 数据源类型，本地文件使用 `"local"`
- `dataset.format`: 数据格式，使用 `"jsonl"`
- `executor.result_save.merge`: 是否将所有结果保存在一个文件中
- `evaluator.fields`: 字段映射，将数据字段映射到评估输入
  - 格式：`{"metadata": "field_name"}` 其中 `field_name` 是要评估的元数据字段（例如 "doi", "title"）
- `evaluator.evals.name`: 评估规则名称：`RuleMetadataSimilarity`
- `evaluator.evals.config.threshold`: 相似度阈值（0-1），默认 0.6

### 4. 运行脚本

```bash
python examples/sciencemetabench/paper.py
```

## 📊 评估规则说明

### 相似度计算规则

`RuleMetadataSimilarity` 规则使用 `calculate_similarity()` 函数，算法如下：

1. **空值处理**: 一个为空另一个不为空 → 相似度为 0
2. **完全匹配**: 二者完全相同（包括全为空）→ 相似度为 1
3. **忽略大小写**: 转换为小写后进行比较
4. **序列匹配**: 使用 `SequenceMatcher`（最长公共子序列）计算相似度（范围: 0-1）

**相似度分数解读**：
- `1.0`: 完全匹配
- `0.8-0.99`: 高度相似（可能有轻微格式差异）
- `0.5-0.79`: 部分匹配（提取了主要信息但不完整）
- `0.0-0.49`: 相似度低（提取结果与标准答案差异较大）

### 评估结果

每个样本的评估结果包含：

- `eval_status`: 整体评估状态（任一字段未通过则为 true）
- `eval_details`: 按字段分组的详细评估信息
  - `metric`: 使用的评估规则名称（`RuleMetadataSimilarity`）
  - `status`: 该字段是否未达到阈值
  - `score`: 相似度分数（0-1）
  - `label`: 质量标签（`QUALITY_GOOD` 或 `QUALITY_BAD_EFFECTIVENESS.RuleMetadataSimilarity`）

**示例输出**：
```json
{
  "sha256": "7d05cfd0101f9443...",
  "doi": {
    "standard": "10.1234/example",
    "produced": "10.1234/example"
  },
  "title": {
    "standard": "示例标题",
    "produced": "示例标题研究"
  },
  "dingo_result": {
    "eval_status": false,
    "eval_details": {
      "doi": [
        {
          "metric": "RuleMetadataSimilarity",
          "status": false,
          "score": 1.0,
          "label": ["QUALITY_GOOD"]
        }
      ],
      "title": [
        {
          "metric": "RuleMetadataSimilarity",
          "status": false,
          "score": 0.941,
          "label": ["QUALITY_GOOD"]
        }
      ]
    }
  }
}
```

## 📈 结果导出与分析

### 分析评估结果

评估完成后，结果以 JSONL 格式保存在输出目录中。每行包含：

- 原始数据字段（例如 `doi`、`title` 等）
- `dingo_result` 字段中的评估结果

### 结果统计

评估框架会自动生成 `summary.json` 文件，包含：

- `task_id`: 任务唯一标识符
- `task_name`: 任务名称
- `input_path`: 输入数据路径
- `output_path`: 输出目录路径
- `create_time`: 任务创建时间
- `finish_time`: 任务完成时间
- `score`: 整体质量得分（百分比，0-100）
- `num_good`: 通过所有质量检查的样本数
- `num_bad`: 至少有一个质量检查未通过的样本数
- `total`: 评估的样本总数
- `type_ratio`: 按字段分组的质量标签分布（比例 0-1）
- `metrics_score`: 每个字段和指标的详细统计数据

**示例 summary.json**：
```json
{
  "task_id": "6f6cadfc-f118-11f0-9e50-8c32235aff7d",
  "task_name": "dingo",
  "input_path": "/path/to/paper.jsonl",
  "output_path": "outputs/20260114_151249_6f6caae6",
  "create_time": "20260114_151249",
  "finish_time": "20260114_151249",
  "score": 0.0,
  "num_good": 0,
  "num_bad": 3,
  "total": 3,
  "type_ratio": {
    "doi": {
      "QUALITY_GOOD": 0.666667,
      "QUALITY_BAD_EFFECTIVENESS.RuleMetadataSimilarity": 0.333333
    },
    "title": {
      "QUALITY_GOOD": 0.666667,
      "QUALITY_BAD_EFFECTIVENESS.RuleMetadataSimilarity": 0.333333
    }
  },
  "metrics_score": {
    "doi": {
      "stats": {
        "RuleMetadataSimilarity": {
          "score_average": 0.67,
          "score_count": 3,
          "score_min": 0.0,
          "score_max": 1.0,
          "score_std_dev": 0.47
        }
      },
      "summary": {
        "RuleMetadataSimilarity": 0.67
      },
      "overall_average": 0.67
    },
    "title": {
      "stats": {
        "RuleMetadataSimilarity": {
          "score_average": 0.87,
          "score_count": 3,
          "score_min": 0.7,
          "score_max": 0.98,
          "score_std_dev": 0.12
        }
      },
      "summary": {
        "RuleMetadataSimilarity": 0.87
      },
      "overall_average": 0.87
    }
  }
}
```

**字段说明**：
- `type_ratio`: 显示每个字段中各质量标签的样本比例
  - `QUALITY_GOOD`: 达到阈值的样本
  - `QUALITY_BAD_EFFECTIVENESS.RuleMetadataSimilarity`: 低于阈值的样本
- `metrics_score`: 包含每个评估字段的详细统计信息
  - `stats`: 统计指标，包括平均值、计数、最小值、最大值和标准差
  - `summary`: 每个指标的汇总分数
  - `overall_average`: 该字段的总体平均分数
