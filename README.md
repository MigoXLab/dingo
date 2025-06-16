<div align="center" xmlns="http://www.w3.org/1999/html">
<!-- logo -->
<p align="center">
  <img src="docs/assets/dingo-logo.png" width="300px" style="vertical-align:middle;">
</p>

<!-- badges -->
<p align="center">
  <a href="https://github.com/pre-commit/pre-commit"><img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white" alt="pre-commit"></a>
  <a href="https://pypi.org/project/dingo-python/"><img src="https://img.shields.io/pypi/v/dingo-python.svg" alt="PyPI version"></a>
  <a href="https://pypi.org/project/dingo-python/"><img src="https://img.shields.io/pypi/pyversions/dingo-python.svg" alt="Python versions"></a>
  <a href="https://github.com/DataEval/dingo/blob/main/LICENSE"><img src="https://img.shields.io/github/license/DataEval/dingo" alt="License"></a>
  <a href="https://github.com/DataEval/dingo/stargazers"><img src="https://img.shields.io/github/stars/DataEval/dingo" alt="GitHub stars"></a>
  <a href="https://github.com/DataEval/dingo/network/members"><img src="https://img.shields.io/github/forks/DataEval/dingo" alt="GitHub forks"></a>
  <a href="https://github.com/DataEval/dingo/issues"><img src="https://img.shields.io/github/issues/DataEval/dingo" alt="GitHub issues"></a>
  <a href="https://mseep.ai/app/dataeval-dingo"><img src="https://mseep.net/pr/dataeval-dingo-badge.png" alt="MseeP.ai Security Assessment Badge" height="20"></a>
</p>

</div>


<div align="center">

[English](README.md) · [简体中文](README_zh-CN.md) · [日本語](README_ja.md)

</div>


<!-- join us -->

<p align="center">
    👋 join us on <a href="https://discord.gg/Jhgb2eKWh8" target="_blank">Discord</a> and <a href="./docs/assets/wechat.jpg" target="_blank">WeChat</a>
</p>


# Changelog

- 2024/12/27: Project Initialization

# Introduction

Dingo is a data quality evaluation tool that helps you automatically detect data quality issues in your datasets. Dingo provides a variety of built-in rules and model evaluation methods, and also supports custom evaluation methods. Dingo supports commonly used text datasets and multimodal datasets, including pre-training datasets, fine-tuning datasets, and evaluation datasets. In addition, Dingo supports multiple usage methods, including local CLI and SDK, making it easy to integrate into various evaluation platforms, such as [OpenCompass](https://github.com/open-compass/opencompass).

## Architecture Diagram

![Architecture of dingo](./docs/assets/architeture.png)

# Quick Start

## Installation

```shell
pip install dingo-python
```

## Example Use Cases

### 1. Evaluate LLM chat data

```python
from dingo.config.config import DynamicLLMConfig
from dingo.io.input.Data import Data
from dingo.model.llm.llm_text_quality_model_base import LLMTextQualityModelBase
from dingo.model.rule.rule_common import RuleEnterAndSpace

data = Data(
    data_id='123',
    prompt="hello, introduce the world",
    content="Hello! The world is a vast and diverse place, full of wonders, cultures, and incredible natural beauty."
)

def llm():
    LLMTextQualityModelBase.dynamic_config = DynamicLLMConfig(
        key='YOUR_API_KEY',
        api_url='https://api.openai.com/v1/chat/completions',
        model='gpt-4o',
    )
    res = LLMTextQualityModelBase.eval(data)
    print(res)


def rule():
    res = RuleEnterAndSpace().eval(data)
    print(res)
```

### 2. Evaluate Dataset

```python
from dingo.io import InputArgs
from dingo.exec import Executor

# Evaluate a dataset from Hugging Face
input_data = {
    "eval_group": "sft",           # Rule set for SFT data
    "input_path": "tatsu-lab/alpaca", # Dataset from Hugging Face
    "data_format": "plaintext",    # Format: plaintext
    "save_data": True              # Save evaluation results
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
```

## Command Line Interface

### Evaluate with Rule Sets

```shell
python -m dingo.run.cli --input_path data.txt --dataset local -e sft --data_format plaintext --save_data True
```

### Evaluate with LLM (e.g., GPT-4o)

```shell
python -m dingo.run.cli --input_path data.json --dataset local -e openai --data_format json --column_content text --custom_config config_gpt.json --save_data True
```

Example `config_gpt.json`:
```json
{
  "llm_config": {
    "openai": {
      "model": "gpt-4o",
      "key": "YOUR_API_KEY",
      "api_url": "https://api.openai.com/v1/chat/completions"
    }
  }
}
```

## GUI Visualization

After evaluation (with `save_data=True`), a frontend page will be automatically generated. To manually start the frontend:

```shell
python -m dingo.run.vsl --input output_directory
```

Where `output_directory` contains the evaluation results with a `summary.json` file.

![GUI output](docs/assets/dingo_gui.png)

## Online Demo
Try Dingo on our online demo: [(Hugging Face)🤗](https://huggingface.co/spaces/DataEval/dingo)

## Local Demo
Try Dingo in local:

```shell
cd app_gradio
python app.py
```

![Gradio demo](docs/assets/gradio_demo.png)


## Google Colab Demo
Experience Dingo interactively with Google Colab notebook: [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/DataEval/dingo/blob/dev/examples/colab/dingo_colab_demo.ipynb)



# MCP Server

Dingo includes an experimental Model Context Protocol (MCP) server. For details on running the server and integrating it with clients like Cursor, please see the dedicated documentation:

[English](README_mcp.md) · [简体中文](README_mcp_zh-CN.md) · [日本語](README_mcp_ja.md)

## Video Demonstration

To help you get started quickly with Dingo MCP, we've created a video walkthrough:

https://github.com/user-attachments/assets/aca26f4c-3f2e-445e-9ef9-9331c4d7a37b

This video demonstrates step-by-step how to use Dingo MCP server with Cursor.


# Data Quality Metrics

Dingo classifies data quality issues into 7 dimensions of Quality Metrics. Each dimension can be evaluated using both rule-based methods and LLM-based prompts:

| Quality Metric    | Description | Rule Examples | LLM Prompt Examples |
|-------------------|-------------|---------------|---------------------|
| **COMPLETENESS** | Checks if data is incomplete or missing | `RuleColonEnd`, `RuleContentNull` | Evaluates if text abruptly ends with a colon or ellipsis, has mismatched parentheses, or missing critical components |
| **EFFECTIVENESS** | Checks if data is meaningful and properly formatted | `RuleAbnormalChar`, `RuleHtmlEntity`, `RuleSpecialCharacter` | Detects garbled text, words stuck together without spaces, and text lacking proper punctuation |
| **FLUENCY** | Checks if text is grammatically correct and reads naturally | `RuleAbnormalNumber`, `RuleNoPunc`, `RuleWordStuck` | Identifies excessively long words, text fragments without punctuation, or content with chaotic reading order |
| **RELEVANCE** | Detects irrelevant content within the data | `RuleHeadWord` variants for different languages | Examines for irrelevant information like citation details, headers/footers, entity markers, HTML tags |
| **SECURITY** | Identifies sensitive information or value conflicts | `RuleIDCard`, `RuleUnsafeWords` | Checks for personal information, and content related to gambling, pornography, political issues |
| **SIMILARITY** | Detects repetitive or highly similar content | `RuleDocRepeat` | Evaluates text for consecutive repeated content or multiple occurrences of special characters |
| **UNDERSTANDABILITY** | Assesses how easily data can be interpreted | `RuleCapitalWords` | Ensures LaTeX formulas and Markdown are correctly formatted, with proper segmentation and line breaks |

## LLM Quality Assessment

Dingo provides several LLM-based assessment methods defined by prompts in the `dingo/model/prompt` directory. These prompts are registered using the `prompt_register` decorator and can be combined with LLM models for quality evaluation:

### Text Quality Assessment Prompts

| Prompt Type | Metric | Description |
|-------------|--------|-------------|
| `TEXT_QUALITY_V2`, `TEXT_QUALITY_V3` | Various quality dimensions | Comprehensive text quality evaluation covering effectiveness, relevance, completeness, understandability, similarity, fluency, and security |
| `QUALITY_BAD_EFFECTIVENESS` | Effectiveness | Detects garbled text and anti-crawling content |
| `QUALITY_BAD_SIMILARITY` | Similarity | Identifies text repetition issues |
| `WORD_STICK` | Fluency | Checks for words stuck together without proper spacing |
| `CODE_LIST_ISSUE` | Completeness | Evaluates code blocks and list formatting issues |
| `UNREAD_ISSUE` | Effectiveness | Detects unreadable characters due to encoding issues |

### 3H Assessment Prompts (Honest, Helpful, Harmless)

| Prompt Type | Metric | Description |
|-------------|--------|-------------|
| `QUALITY_HONEST` | Honesty | Evaluates if responses provide accurate information without fabrication or deception |
| `QUALITY_HELPFUL` | Helpfulness | Assesses if responses address questions directly and follow instructions appropriately |
| `QUALITY_HARMLESS` | Harmlessness | Checks if responses avoid harmful content, discriminatory language, and dangerous assistance |

### Domain-Specific Assessment Prompts

| Prompt Type | Metric | Description |
|-------------|--------|-------------|
| `TEXT_QUALITY_KAOTI` | Exam question quality | Specialized assessment for evaluating the quality of exam questions, focusing on formula rendering, table formatting, paragraph structure, and answer formatting |
| `Html_Abstract` | HTML extraction quality | Compares different methods of extracting Markdown from HTML, evaluating completeness, formatting accuracy, and semantic coherence |
| `DATAMAN_ASSESSMENT` | Data Quality & Domain | Evaluates pre-training data quality using the DataMan methodology (14 standards, 15 domains). Assigns a score (0/1), domain type, quality status, and reason. |

### Classification Prompts

| Prompt Type | Metric | Description |
|-------------|--------|-------------|
| `CLASSIFY_TOPIC` | Topic Categorization | Classifies text into categories like language processing, writing, code, mathematics, role-play, or knowledge Q&A |
| `CLASSIFY_QR` | Image Classification | Identifies images as CAPTCHA, QR code, or normal images |

### Image Assessment Prompts

| Prompt Type | Metric | Description |
|-------------|--------|-------------|
| `IMAGE_RELEVANCE` | Image Relevance | Evaluates if an image matches reference image in terms of face count, feature details, and visual elements |

### Using LLM Assessment in Evaluation

To use these assessment prompts in your evaluations, specify them in your configuration:

```python
input_data = {
    # Other parameters...
    "custom_config": {
        "prompt_list": ["QUALITY_BAD_SIMILARITY"],  # Specific prompt to use
        "llm_config": {
            "detect_text_quality": {  # LLM model to use
                "model": "gpt-4o",
                "key": "YOUR_API_KEY",
                "api_url": "https://api.openai.com/v1/chat/completions"
            }
        }
    }
}
```

You can customize these prompts to focus on specific quality dimensions or to adapt to particular domain requirements. When combined with appropriate LLM models, these prompts enable comprehensive evaluation of data quality across multiple dimensions.

# Rule Groups

Dingo provides pre-configured rule groups for different types of datasets:

| Group | Use Case | Example Rules |
|-------|----------|---------------|
| `default` | General text quality | `RuleColonEnd`, `RuleContentNull`, `RuleDocRepeat`, etc. |
| `sft` | Fine-tuning datasets | Rules from `default` plus `RuleLineStartWithBulletpoint` |
| `pretrain` | Pre-training datasets | Comprehensive set of 20+ rules including `RuleAlphaWords`, `RuleCapitalWords`, etc. |

To use a specific rule group:

```python
input_data = {
    "eval_group": "sft",  # Use "default", "sft", or "pretrain"
    # other parameters...
}
```

# Feature Highlights

## Multi-source & Multi-modal Support

- **Data Sources**: Local files, Hugging Face datasets, S3 storage
- **Data Types**: Pre-training, fine-tuning, and evaluation datasets
- **Data Modalities**: Text and image

## Rule-based & Model-based Evaluation

- **Built-in Rules**: 20+ general heuristic evaluation rules
- **LLM Integration**: OpenAI, Kimi, and local models (e.g., Llama3)
- **Custom Rules**: Easily extend with your own rules and models
- **Security Evaluation**: Perspective API integration

## Flexible Usage

- **Interfaces**: CLI and SDK options
- **Integration**: Easy integration with other platforms
- **Execution Engines**: Local and Spark

## Comprehensive Reporting

- **Quality Metrics**: 7-dimensional quality assessment
- **Traceability**: Detailed reports for anomaly tracking

# User Guide

## Custom Rules, Prompts, and Models

If the built-in rules don't meet your requirements, you can create custom ones:

### Custom Rule Example

```python
from dingo.model import Model
from dingo.model.rule.base import BaseRule
from dingo.config.config import DynamicRuleConfig
from dingo.io import Data
from dingo.model.modelres import ModelRes

@Model.rule_register('QUALITY_BAD_RELEVANCE', ['default'])
class MyCustomRule(BaseRule):
    """Check for custom pattern in text"""

    dynamic_config = DynamicRuleConfig(pattern=r'your_pattern_here')

    @classmethod
    def eval(cls, input_data: Data) -> ModelRes:
        res = ModelRes()
        # Your rule implementation here
        return res
```

### Custom LLM Integration

```python
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI

@Model.llm_register('my_custom_model')
class MyCustomModel(BaseOpenAI):
    # Custom implementation here
    pass
```

See more examples in:
- [Register Rules](examples/register/sdk_register_rule.py)
- [Register Prompts](examples/register/sdk_register_prompt.py)
- [Register Models](examples/register/sdk_register_llm.py)

## Execution Engines

### Local Execution

```python
from dingo.io import InputArgs
from dingo.exec import Executor

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()

# Get results
summary = executor.get_summary()        # Overall evaluation summary
bad_data = executor.get_bad_info_list() # List of problematic data
good_data = executor.get_good_info_list() # List of high-quality data
```

### Spark Execution

```python
from dingo.io import InputArgs
from dingo.exec import Executor
from pyspark.sql import SparkSession

# Initialize Spark
spark = SparkSession.builder.appName("Dingo").getOrCreate()
spark_rdd = spark.sparkContext.parallelize([...])  # Your data as Data objects

input_args = InputArgs(eval_group="default", save_data=True)
executor = Executor.exec_map["spark"](input_args, spark_session=spark, spark_rdd=spark_rdd)
result = executor.execute()
```

## Evaluation Reports

After evaluation, Dingo generates:

1. **Summary Report** (`summary.json`): Overall metrics and scores
2. **Detailed Reports**: Specific issues for each rule violation

Report Description:
1. **score**: `num_good` / `total`
2. **type_ratio**: The count of type / total, such as: `QUALITY_BAD_COMPLETENESS` / `total`
3. **name_ratio**: The count of name / total, such as: `QUALITY_BAD_COMPLETENESS-RuleColonEnd` / `total`

Example summary:
```json
{
    "task_id": "d6c922ec-981c-11ef-b723-7c10c9512fac",
    "task_name": "dingo",
    "eval_group": "default",
    "input_path": "test/data/test_local_jsonl.jsonl",
    "output_path": "outputs/d6c921ac-981c-11ef-b723-7c10c9512fac",
    "create_time": "20241101_144510",
    "score": 50.0,
    "num_good": 1,
    "num_bad": 1,
    "total": 2,
    "type_ratio": {
        "QUALITY_BAD_COMPLETENESS": 0.5,
        "QUALITY_BAD_RELEVANCE": 0.5
    },
    "name_ratio": {
        "QUALITY_BAD_COMPLETENESS-RuleColonEnd": 0.5,
        "QUALITY_BAD_RELEVANCE-RuleSpecialCharacter": 0.5
    }
}
```


# Research & Publications

## Research Powered by Dingo
- **WanJuanSiLu**: [A High-Quality Open-Source Webtext Dataset for Low-Resource Languages](https://arxiv.org/pdf/2501.14506)
  *Uses Dingo for comprehensive data quality assessment of multilingual web data*

## Methodologies Implemented in Dingo
- **DataMan Methodology**: [DataMan: Data Manager for Pre-training Large Language Models](https://openreview.net/pdf?id=eNbA8Fqir4)
  *Dingo implements the DataMan methodology for pre-training data quality assessment*
- **RedPajama-Data-v2**: [RedPajama-Data](https://github.com/togethercomputer/RedPajama-Data)
  *Dingo implements parts of the RedPajama-Data-v2 methodology for web text quality assessment and filtering*

# Future Plans

- [ ] Richer graphic and text evaluation indicators
- [ ] Audio and video data modality evaluation
- [ ] Small model evaluation (fasttext, Qurating)
- [ ] Data diversity evaluation

# Limitations

The current built-in detection rules and model methods focus on common data quality problems. For specialized evaluation needs, we recommend customizing detection rules.

# Acknowledgments

- [RedPajama-Data](https://github.com/togethercomputer/RedPajama-Data)
- [mlflow](https://github.com/mlflow/mlflow)

# Contribution

We appreciate all the contributors for their efforts to improve and enhance `Dingo`. Please refer to the [Contribution Guide](docs/en/CONTRIBUTING.md) for guidance on contributing to the project.

# License

This project uses the [Apache 2.0 Open Source License](LICENSE).

This project uses fasttext for some functionality including language detection. fasttext is licensed under the MIT License, which is compatible with our Apache 2.0 license and provides flexibility for various usage scenarios.

# Citation

If you find this project useful, please consider citing our tool:

```
@misc{dingo,
  title={Dingo: A Comprehensive Data Quality Evaluation Tool for Large Models},
  author={Dingo Contributors},
  howpublished={\url{https://github.com/DataEval/dingo}},
  year={2024}
}
```
