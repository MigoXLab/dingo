# Config

`Dingo` 为不同模块设置了各自的配置，让用户可以更加自由地使用项目完成自身的质检需求。

## CLI Config

用户在命令行输入指令启动项目时只需要指定配置文件路径：

| Parameter | Type | Default | Required | Description           |
|-----------|------|---------|----------|-----------------------|
| --input / -i | str  | None    | Yes      | 配置文件路径           |

## 配置文件结构

配置文件采用 JSON 格式，包含以下主要结构：

### InputArgs 根配置

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| task_name | str | "dingo" | No | 任务名称 |
| input_path | str | "test/data/test_local_json.json" | Yes | 要检查的文件或目录路径 |
| output_path | str | "outputs/" | No | 结果输出路径 |
| log_level | str | "WARNING" | No | 日志级别，可选值：['DEBUG', 'INFO', 'WARNING', 'ERROR'] |

### Dataset 配置 (dataset)

数据集相关配置：

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| source | str | "hugging_face" | Yes | 数据源类型，可选值：['hugging_face', 'local'] |
| format | str | "json" | Yes | 数据格式，可选值：['json', 'jsonl', 'plaintext', 'listjson', 'csv', 'parquet', 'mineru', 'mineru_v2'] |
| field | object | - | Yes | 字段映射配置 |
| hf_config | object | - | No | HuggingFace 特定配置 |
| mineru_config | object | - | No | MinerU 格式特定配置（仅 mineru / mineru_v2 格式使用） |

#### DatasetMinerUConfig 配置 (dataset.mineru_config)

MinerU 格式特定配置，用于过滤 block 类型：

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| include_types | list[str] | null | No | 只保留指定的 block 类型（如 `["text", "table", "image"]`），null 表示保留全部类型 |

MinerU 支持的 block 类型包括：`text`, `title`, `image`, `table`, `equation`, `code`, `list`, `header`, `page_footer`, `page_footnote`, `chart` 等。

**格式说明：**
- `mineru`：对应 MinerU 的 `content_list.json`，顶层为 block 数组
- `mineru_v2`：对应 MinerU 的 `content_list_v2.json`，顶层为页面数组，每页包含 block 数组

每个 block 会被转换为一条 `Data` 记录。block 的 `type`、`bbox`、`page_idx` 等原始字段会通过 Pydantic `extra="allow"` 保留在 Data 对象上。

#### DatasetField 配置 (dataset.field)

字段映射配置：

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| id | str | "" | Depends | ID 字段名，多级用 '.' 分隔 |
| prompt | str | "" | Depends | prompt 字段名，多级用 '.' 分隔 |
| content | str | "" | Yes | 内容字段名，多级用 '.' 分隔 |
| context | str | "" | Depends | 上下文字段名，多级用 '.' 分隔 |
| image | str | "" | Depends | 图像字段名，多级用 '.' 分隔 |

#### DatasetHFConfig 配置 (dataset.hf_config)

HuggingFace 特定配置：

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| huggingface_split | str | "" | No | HuggingFace 数据集分割 |
| huggingface_config_name | str | null | No | HuggingFace 配置名称 |

### Executor 配置 (executor)

执行器相关配置：

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| eval_group | str | "" | Yes | 评估模型组 |
| rule_list | list | [] | Depends | 规则函数列表 |
| prompt_list | list | [] | Depends | prompt 列表 |
| start_index | int | 0 | No | 开始检查的数据索引 |
| end_index | int | -1 | No | 结束检查的数据索引 |
| max_workers | int | 1 | No | 最大并发工作线程数 |
| batch_size | int | 1 | No | 并发检查的最大数据量 |
| multi_turn_mode | str | null | No | 多轮对话解析模式 |
| result_save | object | - | No | 结果保存配置 |

#### ExecutorResultSave 配置 (executor.result_save)

结果保存配置：

| Parameter  | Type | Default | Required | Description |
|------------|------|---------|----------|-------------|
| bad        | bool | false   | No       | 是否保存错误结果    |
| good       | bool | false   | No       | 是否保存正确结果    |
| all_labels | bool | false   | No       | 是否保存所有标签    |
| raw        | bool | false   | No       | 是否保存原始数据    |

### Evaluator 配置 (evaluator)

评估器相关配置：

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| rule_config | object | {} | Depends | 规则配置 |
| llm_config | object | {} | Depends | LLM 配置 |

#### EvaluatorRuleArgs 配置 (evaluator.rule_config.[rule_name])

规则配置：

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| threshold | float | null | No | 规则决策阈值 |
| pattern | str | null | No | 匹配模式字符串 |
| key_list | list | null | No | 匹配关键词列表 |
| refer_path | list | null | No | 参考文件路径或小模型路径 |

#### EvaluatorLLMArgs 配置 (evaluator.llm_config.[llm_name])

LLM 配置（支持额外字段，所有额外字段会直接透传给 LLM API）：

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| model | str | null | No | 使用的模型名称 |
| key | str | null | No | API 密钥 |
| api_url | str | null | No | API URL |
| embedding_config | object | null | No | Embedding 模型独立配置（RAG 评估器使用） |
| *其他字段* | any | - | No | 所有额外字段直接透传给 LLM API |

## 配置文件示例

```json
{
  "task_name": "dingo",
  "input_path": "test/data/test_local_json.json",
  "output_path": "outputs/",
  "log_level": "WARNING",
  "use_browser": false,

  "dataset": {
    "source": "hugging_face",
    "format": "json",
    "field": {
      "id": "",
      "prompt": "",
      "content": "",
      "context": "",
      "image": ""
    },
    "hf_config": {
      "huggingface_split": "",
      "huggingface_config_name": null
    }
  },

  "executor": {
    "eval_group": "",
    "rule_list": [],
    "prompt_list": [],
    "start_index": 0,
    "end_index": -1,
    "max_workers": 1,
    "batch_size": 1,
    "multi_turn_mode": null,
    "result_save": {
      "bad": false,
      "good": false,
      "raw": false
    }
  },

  "evaluator": {
    "rule_config": {
      "rule_name": {
        "threshold": 0.5,
        "pattern": ".*",
        "key_list": ["key1", "key2"],
        "refer_path": ["path/to/reference"]
      }
    },
    "llm_config": {
      "openai": {
        "model": "gpt-3.5-turbo",
        "key": "your-api-key",
        "api_url": "https://api.openai.com/v1/chat/completions",
        "temperature": 1,
        "top_p": 1,
        "max_tokens": 4000,
        "presence_penalty": 0,
        "frequency_penalty": 0
      }
    }
  }
}
```

## 使用方式

### CLI 方式
```bash
dingo --input config.json
```

### SDK 方式
```python
from dingo import InputArgs, run

# 从文件加载配置
config = InputArgs.parse_file("config.json")
run(config)

# 或从字典创建配置
config_dict = {
    "task_name": "my_task",
    "input_path": "data.json",
    # ... 其他配置
}
config = InputArgs(**config_dict)
run(config)
```

## MinerU 文档解析数据评估

Dingo 原生支持 MinerU 的输出格式（`content_list.json` 和 `content_list_v2.json`），可直接对文档解析结果进行质量评估。

### MinerU V1 配置示例

```json
{
  "input_path": "/path/to/content_list.json",
  "dataset": {
    "source": "local",
    "format": "mineru"
  },
  "evaluator": [
    {
      "fields": {"content": "content"},
      "evals": [
        {"name": "RuleColonEnd"},
        {"name": "RuleAbnormalChar"}
      ]
    }
  ]
}
```

### MinerU V2 配置示例（带类型过滤）

```json
{
  "input_path": "/path/to/content_list_v2.json",
  "dataset": {
    "source": "local",
    "format": "mineru_v2",
    "mineru_config": {
      "include_types": ["text", "title", "table"]
    }
  },
  "evaluator": [
    {
      "fields": {"content": "content"},
      "evals": [
        {"name": "RuleContentNull"},
        {"name": "RuleDocRepeat"}
      ]
    }
  ]
}
```

更多示例参考: `examples/document_parser/sdk_mineru_content_list.py`

## 多轮对话模式

`Dingo` 支持多轮对话数据质检，如MT-Bench、MT-Bench++和MT-Bench101：

| Mode | Description |
|------|-------------|
| all | 拼接多轮对话中的所有回合 |

具体使用方法请参考相关示例文件:
[sdk_mtbench101_rule_all.py](../examples/multi_turn_dialogues/sdk_mtbench101_rule_all.py)、[sdk_mtbench101_llm.py](../examples/multi_turn_dialogues/sdk_mtbench101_llm.py)、
[sdk_mtbench_rule_all.py](../examples/multi_turn_dialogues/sdk_mtbench_rule_all.py)、[sdk_mtbench_llm.py](../examples/multi_turn_dialogues/sdk_mtbench_llm.py)。
