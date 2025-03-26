<div align="center" xmlns="http://www.w3.org/1999/html">
<!-- logo -->
<p align="center">
  <img src="docs/assets/dingo-logo.png" width="300px" style="vertical-align:middle;">
</p>

<!-- badges -->
<p align="center">
  <a href="https://github.com/pre-commit/pre-commit"><img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white" alt="pre-commit"></a>
  <a href="https://pypi.org/project/dingo-python/"><img src="https://img.shields.io/pypi/v/dingo-python.svg" alt="PyPI 版本"></a>
  <a href="https://pypi.org/project/dingo-python/"><img src="https://img.shields.io/pypi/pyversions/dingo-python.svg" alt="Python 版本"></a>
  <a href="https://github.com/DataEval/dingo/blob/main/LICENSE"><img src="https://img.shields.io/github/license/DataEval/dingo" alt="许可证"></a>
  <a href="https://github.com/DataEval/dingo/stargazers"><img src="https://img.shields.io/github/stars/DataEval/dingo" alt="GitHub 星标"></a>
  <a href="https://github.com/DataEval/dingo/network/members"><img src="https://img.shields.io/github/forks/DataEval/dingo" alt="GitHub 分支"></a>
  <a href="https://github.com/DataEval/dingo/issues"><img src="https://img.shields.io/github/issues/DataEval/dingo" alt="GitHub 问题"></a>
</p>

</div>

# Changelog

- 2024/12/27: Project Initialization

# 一、介绍

Dingo是一款数据质量评估工具，帮助你自动化检测数据集中的数据质量问题。Dingo提供了多种内置的规则和模型评估方法，同时也支持自定义评估方法。Dingo支持常用的文本数据集和多模态数据集，包括预训练数据集、微调数据集和评测数据集。此外，Dingo支持多种使用方式，包括本地CLI和SDK，便于集成到各种评测平台，如[OpenCompass](https://github.com/open-compass/opencompass)等。

## 1. 架构图

![Architecture of dingo](./docs/assets/architeture.png)


# 二、快速启动

## 1. 安装

```shell
pip install dingo-python
```

## 2. 使用示例

### 2.1 评估本地文本文件（纯文本）

```python
from dingo.io import InputArgs
from dingo.exec import Executor

# 评估纯文本文件
input_data = {
    "eval_group": "sft",          # SFT数据的规则集
    "input_path": "data.txt",      # 本地文本文件路径
    "dataset": "local",
    "data_format": "plaintext",    # 格式: plaintext
    "save_data": True              # 保存评估结果
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
```

### 2.2 评估Hugging Face数据集

```python
from dingo.io import InputArgs
from dingo.exec import Executor

# 评估来自Hugging Face的数据集
input_data = {
    "eval_group": "sft",           # SFT数据的规则集
    "input_path": "tatsu-lab/alpaca", # Hugging Face的数据集
    "data_format": "plaintext",    # 格式: plaintext
    "save_data": True              # 保存评估结果
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
```

### 2.3 评估JSON/JSONL格式

```python
from dingo.io import InputArgs
from dingo.exec import Executor

# 评估JSON文件
input_data = {
    "eval_group": "default",       # 默认规则集
    "input_path": "data.json",     # 本地JSON文件路径
    "dataset": "local",
    "data_format": "json",         # 格式: json
    "column_content": "text",      # 包含要评估文本的列
    "save_data": True              # 保存评估结果
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
```

### 2.4 使用LLM进行评估

```python
from dingo.io import InputArgs
from dingo.exec import Executor

# 使用GPT模型评估
input_data = {
    "input_path": "data.jsonl",    # 本地JSONL文件路径
    "dataset": "local",
    "data_format": "jsonl",
    "column_content": "content",
    "custom_config": {
        "prompt_list": ["PromptRepeat"],  # 使用的prompt
        "llm_config": {
            "detect_text_quality": {
                "model": "gpt-4o",
                "key": "您的API密钥",
                "api_url": "https://api.openai.com/v1/chat/completions"
            }
        }
    }
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()
print(result)
```

## 3. 命令行界面

### 3.1 使用规则集评估

```shell
python -m dingo.run.cli --input_path data.txt --dataset local -e sft --data_format plaintext --save_data True
```

### 3.2 使用LLM评估（例如GPT-4o）

```shell
python -m dingo.run.cli --input_path data.json --dataset local -e openai --data_format json --column_content text --custom_config config_gpt.json --save_data True
```

`config_gpt.json`示例:
```json
{
  "llm_config": {
    "openai": {
      "model": "gpt-4o",
      "key": "您的API密钥",
      "api_url": "https://api.openai.com/v1/chat/completions"
    }
  }
}
```

## 4. 图形界面可视化

进行评估后（设置`save_data=True`），系统会自动生成前端页面。若要手动启动前端页面，请运行：

```shell
python -m dingo.run.vsl --input 输出目录
```

其中`输出目录`包含评估结果和`summary.json`文件。

![GUI output](docs/assets/dingo_gui.png)

## 5. 在线演示
尝试我们的在线演示: [(Hugging Face)🤗](https://huggingface.co/spaces/DataEval/dingo)

# 三、数据质量指标

Dingo将数据质量问题分为7个维度的质量指标。每个维度可以通过基于规则的方法和基于LLM的prompt进行评估：

| 质量指标    | 描述 | 规则示例 | LLM Prompt示例 |
|-------------------|-------------|---------------|---------------------|
| **完整性(COMPLETENESS)** | 检查数据是否不完整或缺失 | `RuleColonEnd`, `RuleContentNull` | 评估文本是否突然以冒号或省略号结束，是否有不匹配的括号，或缺少关键组件 |
| **有效性(EFFECTIVENESS)** | 检查数据是否有意义且格式正确 | `RuleAbnormalChar`, `RuleHtmlEntity`, `RuleSpecialCharacter` | 检测乱码文本、没有空格的粘连单词和缺少适当标点的文本 |
| **流畅性(FLUENCY)** | 检查文本是否语法正确且自然易读 | `RuleAbnormalNumber`, `RuleNoPunc`, `RuleWordStuck` | 识别过长的单词、无标点的文本片段或阅读顺序混乱的内容 |
| **相关性(RELEVANCE)** | 检测数据中的不相关内容 | 不同语言的`RuleHeadWord`变体 | 检查引用详情、页眉/页脚、实体标记、HTML标签等不相关信息 |
| **安全性(SECURITY)** | 识别敏感信息或价值冲突 | `RuleIDCard`, `RuleUnsafeWords` | 检查个人信息和与赌博、色情、政治问题相关的内容 |
| **相似性(SIMILARITY)** | 检测重复或高度相似的内容 | `RuleDocRepeat` | 评估文本中连续重复的内容或特殊字符的多次出现 |
| **可理解性(UNDERSTANDABILITY)** | 评估数据解释的容易程度 | `RuleCapitalWords` | 确保LaTeX公式和Markdown格式正确，具有适当的分段和换行 |

## LLM质量评估

Dingo提供了多个基于LLM的模型，用于评估不同维度的文本质量。这些模型使用`llm_register`装饰器注册，可以在您的评估工作流程中使用：

### 文本质量评估模型

| 模型名称 | 描述 | 使用场景 |
|------------|-------------|----------|
| `detect_text_quality` | 基于OpenAI模型的基础文本质量分析 | 通用质量评估 |
| `detect_text_quality_detail` | 带有特定错误类型的详细质量分析 | 提供具体错误类型和原因的细粒度质量反馈 |
| `detect_text_quality_3h` | 基于3H标准的问答对质量评估 | 评估回答是否符合诚实(honest)、有帮助(helpful)、无害(harmless)标准 |

### 专业评估模型

| 模型名称 | 描述 | 使用场景 |
|------------|-------------|----------|
| `classify_topic` | 文本内容的主题分类 | 将文本归类到预定义的主题 |
| `classify_QR` | 二维码和图像内容分析 | 评估基于图像的内容 |
| `detect_image_relevant` | 图像-文本相关性评估 | 检查图像是否与其文本描述匹配 |
| `detect_perspective` | 内容安全和毒性检测 | 使用谷歌的Perspective API识别有毒、有害或不安全的内容 |

### 在评估中使用LLM模型

要在评估中使用这些LLM模型，请在配置中指定它们：

```python
input_data = {
    # 其他参数...
    "custom_config": {
        "prompt_list": ["PromptRepeat"],  # 要使用的特定prompt
        "llm_config": {
            "detect_text_quality": {  # 要使用的LLM模型
                "model": "gpt-4o",
                "key": "您的API密钥",
                "api_url": "https://api.openai.com/v1/chat/completions"
            }
        }
    }
}
```

您可以自定义这些LLM提示和模型，以关注特定的质量维度或适应特定的领域需求。

每条规则都针对文本质量的特定方面进行检查，并映射到这些指标之一。运行评估时，Dingo将提供每个维度的分数并识别触发了哪些规则。

# 四、规则组

Dingo为不同类型的数据集提供预配置的规则组：

| 组名 | 用例 | 示例规则 |
|-------|----------|---------------|
| `default` | 通用文本质量 | `RuleColonEnd`, `RuleContentNull`, `RuleDocRepeat`等 |
| `sft` | 微调数据集 | `default`中的规则加上`RuleLineStartWithBulletpoint` |
| `pretrain` | 预训练数据集 | 包括`RuleAlphaWords`, `RuleCapitalWords`等20多条规则的全面集合 |

使用特定规则组：

```python
input_data = {
    "eval_group": "sft",  # 使用"default"、"sft"或"pretrain"
    # 其他参数...
}
```

# 五、功能亮点

## 1. 多源和多模态支持

- **数据源**：本地文件、Hugging Face数据集、S3存储
- **数据类型**：预训练、微调和评估数据集
- **数据模态**：文本和图像

## 2. 基于规则和模型的评估

- **内置规则**：20多种通用启发式评估规则
- **LLM集成**：OpenAI、Kimi和本地模型（如Llama3）
- **自定义规则**：轻松扩展自己的规则和模型
- **安全评估**：Perspective API集成

## 3. 灵活的使用方式

- **接口**：CLI和SDK选项
- **集成**：易于与其他平台集成
- **执行引擎**：本地和Spark

## 4. 全面报告

- **质量指标**：7维质量评估
- **可追溯性**：异常追踪的详细报告

# 六、使用指南

## 1. 自定义规则、Prompt和模型

如果内置规则不满足您的需求，您可以创建自定义规则：

### 1.1 自定义规则示例

```python
from dingo.model import Model
from dingo.model.rule.base import BaseRule
from dingo.config.config import DynamicRuleConfig
from dingo.io import MetaData
from dingo.model.modelres import ModelRes

@Model.rule_register('QUALITY_BAD_RELEVANCE', ['default'])
class MyCustomRule(BaseRule):
    """检查文本中的自定义模式"""
    
    dynamic_config = DynamicRuleConfig(pattern=r'your_pattern_here')
    
    @classmethod
    def eval(cls, input_data: MetaData) -> ModelRes:
        res = ModelRes()
        # 您的规则实现
        return res
```

### 1.2 自定义LLM集成

```python
from dingo.model import Model
from dingo.model.llm.base_openai import BaseOpenAI

@Model.llm_register('my_custom_model')
class MyCustomModel(BaseOpenAI):
    # 自定义实现
    pass
```

查看更多示例：
- [注册规则](examples/register/sdk_register_rule.py)
- [注册Prompts](examples/register/sdk_register_prompt.py)
- [注册模型](examples/register/sdk_register_llm.py)

## 2. 执行引擎

### 2.1 本地执行

```python
from dingo.io import InputArgs
from dingo.exec import Executor

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()

# 获取结果
summary = executor.get_summary()        # 整体评估摘要
bad_data = executor.get_bad_info_list() # 有问题数据列表
good_data = executor.get_good_info_list() # 高质量数据列表
```

### 2.2 Spark执行

```python
from dingo.io import InputArgs
from dingo.exec import Executor
from pyspark.sql import SparkSession

# 初始化Spark
spark = SparkSession.builder.appName("Dingo").getOrCreate()
spark_rdd = spark.sparkContext.parallelize([...])  # 以MetaData对象形式的数据

input_args = InputArgs(eval_group="default", save_data=True)
executor = Executor.exec_map["spark"](input_args, spark_session=spark, spark_rdd=spark_rdd)
result = executor.execute()
```

## 3. 评估报告

评估后，Dingo生成：

1. **概要报告**（`summary.json`）：总体指标和分数
2. **详细报告**：每个规则违反的具体问题

概要示例：
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

# 七、未来计划

- [ ] 更丰富的图文评测指标
- [ ] 音频和视频数据模态评测
- [ ] 小模型评测（如fasttext、Qurating）
- [ ] 数据多样性评测

# 八、局限性

当前内置的检测规则和模型方法主要关注常见的数据质量问题。对于特殊评估需求，我们建议定制化检测规则。

# 九、致谢

- [RedPajama-Data](https://github.com/togethercomputer/RedPajama-Data)
- [mlflow](https://github.com/mlflow/mlflow)

# 十、贡献

我们感谢所有的贡献者为改进和提升 `Dingo` 所作出的努力。请参考[贡献指南](docs/en/CONTRIBUTING.md)来了解参与项目贡献的相关指引。

# 十一、开源许可证

该项目采用 [Apache 2.0 开源许可证](LICENSE)。

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
