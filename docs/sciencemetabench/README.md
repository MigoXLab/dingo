# ScienceMetaBench Usage Guide

[English](README.md) | [中文](README_ZH.md)

## 📖 Introduction

ScienceMetaBench is a benchmark dataset for evaluating the accuracy of metadata extraction from scientific literature PDFs. This document introduces how to use the Dingo framework to assess the quality of extracted metadata.

**Dataset**: 🤗 [HuggingFace - ScienceMetaBench](https://huggingface.co/datasets/opendatalab/ScienceMetaBench)

### Supported Data Types

- **Academic Papers (Paper)**: Primarily from academic journals and conference papers
- **Textbooks (Textbook)**: Formally published textbooks
- **Ebooks (Ebook)**: Digitized historical documents and books

## 🚀 Quick Start

### 1. Install Dependencies

#### Install Dingo

**Option 1: Install Specific Version**

```bash
pip install dingo-python
```

**Option 2: Development Mode Installation (Recommended for Local Development)**

```bash
git clone https://github.com/MigoXLab/dingo.git
cd dingo
git checkout dev
pip install -e .
```


### 2. Prepare Data

Data format is JSONL, with each record containing the following fields:

#### Field Description

- **`sha256`**: Unique identifier for tracing source files

Each metadata field should contain `standard` and `produced` subfields:
- **`standard`**: Ground truth value (benchmark)
  - **Source**: Obtained from [ScienceMetaBench Dataset](https://huggingface.co/datasets/opendatalab/ScienceMetaBench)

- **`produced`**: Extraction result to be evaluated
  - **Source**: Extracted from PDF

**Supported Fields**:
- Academic Papers (Paper): `doi`, `title`, `author`, `keyword`, `abstract`, `pub_time`
- Textbooks/Ebooks (Textbook/Ebook): `isbn`, `title`, `author`, `abstract`, `category`, `pub_time`, `publisher`

**Example Format**:
```json
{
  "sha256": "unique_identifier",
  "doi": {
    "standard": "10.1234/example",
    "produced": "10.1234/example"
  },
  "title": {
    "standard": "Example Paper Title",
    "produced": "Example Paper Title"
  }
}
```

### 3. Run Evaluation

For complete example code, please refer to: `examples/sciencemetabench/paper.py`

**Configuration Parameters**:

- `input_path`: Input JSONL file path
- `dataset.source`: Data source type, use `"local"` for local files
- `dataset.format`: Data format, use `"jsonl"`
- `executor.result_save.merge`: Whether to save all results in one file
- `evaluator.fields`: Field mapping, maps data fields to evaluation input
  - Format: `{"metadata": "field_name"}` where `field_name` is the metadata field to evaluate (e.g., "doi", "title")
- `evaluator.evals.name`: Evaluation rule name: `RuleMetadataSimilarity`
- `evaluator.evals.config.threshold`: Similarity threshold (0-1), default 0.6

### 4. Run Script

```bash
python examples/sciencemetabench/paper.py
```

## 📊 Evaluation Rules

### Similarity Calculation Rules

The `RuleMetadataSimilarity` rule uses `calculate_similarity()` function with the following algorithm:

1. **Null Value Handling**: One is empty while the other is not → similarity is 0
2. **Exact Match**: Both are identical (including both empty) → similarity is 1
3. **Case Insensitive**: Converted to lowercase before comparison
4. **Sequence Matching**: Uses `SequenceMatcher` (longest common subsequence) to calculate similarity (range: 0-1)

**Similarity Score Interpretation**:
- `1.0`: Exact match
- `0.8-0.99`: Highly similar (may have slight formatting differences)
- `0.5-0.79`: Partial match (extracted main information but incomplete)
- `0.0-0.49`: Low similarity (significant difference between extraction result and ground truth)

### Evaluation Results

Each sample's evaluation result includes:

- `eval_status`: Overall evaluation status (true if any field failed)
- `eval_details`: Detailed evaluation information by field
  - `metric`: Name of the evaluation rule used (`RuleMetadataSimilarity`)
  - `status`: Whether the field failed to meet the threshold
  - `score`: Similarity score (0-1)
  - `label`: Quality label (`QUALITY_GOOD` or `QUALITY_BAD_EFFECTIVENESS.RuleMetadataSimilarity`)

**Example Output**:
```json
{
  "sha256": "7d05cfd0101f9443...",
  "doi": {
    "standard": "10.1234/example",
    "produced": "10.1234/example"
  },
  "title": {
    "standard": "Example Title",
    "produced": "Example Title Study"
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

## 📈 Result Export and Analysis

### Analyzing Evaluation Results

After evaluation is complete, results are saved in JSONL format in the output directory. Each line contains:

- Original data fields (e.g., `doi`, `title`, etc.)
- Evaluation results in `dingo_result` field

### Result Statistics

The evaluation framework automatically generates a `summary.json` file containing:

- `task_id`: Unique task identifier
- `task_name`: Task name
- `input_path`: Input data path
- `output_path`: Output directory path
- `create_time`: Task creation time
- `finish_time`: Task completion time
- `score`: Overall quality score (percentage, 0-100)
- `num_good`: Number of samples passing all quality checks
- `num_bad`: Number of samples failing at least one quality check
- `total`: Total number of samples evaluated
- `type_ratio`: Distribution of quality labels by field (as ratio 0-1)
- `metrics_score`: Detailed statistics for each field and metric

**Example summary.json**:
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

**Field Descriptions**:
- `type_ratio`: Shows the proportion of samples with each quality label for each field
  - `QUALITY_GOOD`: Samples meeting the threshold
  - `QUALITY_BAD_EFFECTIVENESS.RuleMetadataSimilarity`: Samples below the threshold
- `metrics_score`: Contains detailed statistics for each evaluated field
  - `stats`: Statistical metrics including average, count, min, max, and standard deviation
  - `summary`: Summary score for each metric
  - `overall_average`: Overall average score for the field
