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
| task_id | str | "" | No | 用户指定的任务唯一标识；为空时由执行器自动生成 |
| task_name | str | "dingo" | No | 任务名称 |
| input_path | str | "test/data/test_local_json.json" | Yes | 数据位置；具体含义由 `dataset.source` 决定 |
| output_path | str | "outputs/" | No | 结果输出路径 |
| log_level | str | "WARNING" | No | 日志级别，可选值：['DEBUG', 'INFO', 'WARNING', 'ERROR'] |

执行结束后，Dingo 会将本次执行参数记录到 `summary.json` 的 `input_args` 字段中，便于后续追溯任务的执行方式。该快照采用安全字段白名单，不会写入 S3 AK/SK、SQL 密码、LLM API Key 或 retrieval token。

### Dataset 配置 (dataset)

`dataset` 决定数据从哪里读取、按什么格式转换，以及是否启用数据源或格式专属选项。

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| source | str | `"hugging_face"` | Yes | 数据源，可选 `local`、`hugging_face`、`s3`、`sql` |
| format | str | `"json"` | Yes | 数据转换格式，完整列表见下文 |
| hf_config | object | `{}` | Depends | Hugging Face 数据源配置，仅 `source="hugging_face"` 使用 |
| s3_config | object | `{}` | Depends | S3/Ceph/MinIO 连接配置，仅 `source="s3"` 使用 |
| sql_config | object | `{}` | Depends | SQLAlchemy 连接配置，仅 `source="sql"` 使用 |
| excel_config | object | `{}` | Depends | Excel 读取配置，仅 `format="excel"` 使用 |
| csv_config | object | `{}` | Depends | CSV 读取配置，仅 `format="csv"` 使用 |
| parquet_config | object | `{}` | Depends | Parquet 读取配置，仅 `format="parquet"` 使用 |
| mineru_config | object | `{}` | Depends | MinerU block 过滤配置，仅 `mineru` / `mineru_v2` 使用 |

`dataset` 中没有 `field` 字段。评估字段映射应配置在 `evaluator[].fields` 中，例如：

```json
{
  "fields": {
    "content": "answer",
    "prompt": "question"
  },
  "evals": [{"name": "RuleColonEnd"}]
}
```

#### 数据源与 input_path

`input_path` 的含义由 `dataset.source` 决定：

| source | input_path 含义 | 示例 | 主要配置 |
|--------|-----------------|------|----------|
| `local` | 本地文件或目录路径 | `data/train.jsonl` | 按格式使用 `csv_config`、`excel_config` 等 |
| `hugging_face` | Hugging Face Hub 数据集名称 | `tatsu-lab/alpaca` | `hf_config` |
| `s3` | 包含 Bucket 的完整 S3 URI | `s3://bucket/path/train.jsonl` | `s3_config` |
| `sql` | 要执行的 SQL 查询 | `SELECT id, content FROM samples` | `sql_config` |

#### 支持的数据格式

| format | 输入结构 | 说明 |
|--------|----------|------|
| `json` | 顶层对象，value 为样本对象 | 本地 JSON 或 Hugging Face 数据转换 |
| `listjson` | 顶层样本数组 | 本地 JSON 数组；Hugging Face 使用时按 JSONL 样本处理 |
| `jsonl` | 每行一个 JSON 对象 | 本地、S3、SQL 的常用格式 |
| `plaintext` | 每行一条文本 | 每行转换为 `{"content": "..."}` |
| `md` | UTF-8 Markdown 文件 | 每个文件转换为一条包含 `id` 和 `content` 的记录 |
| `csv` | CSV 文件 | 使用 `csv_config` 控制表头、编码、方言和分隔符 |
| `excel` | `.xlsx` 或 `.xls` | 使用 `excel_config` 选择工作表和表头 |
| `parquet` | Parquet 文件 | 使用 `parquet_config` 控制批大小和读取列 |
| `mineru` | MinerU `content_list.json` | 顶层 block 数组 |
| `mineru_v2` | MinerU `content_list_v2.json` | 页面数组，每页包含 block 数组 |
| `ms_swift` | Agent 轨迹 JSONL | 按所选 Agent 指标生成派生字段 |
| `multi_turn_dialog` | 多轮对话 JSON/JSONL | 配合 `executor.multi_turn_mode` 解析多轮内容 |
| `image` | 含图像字段的 JSON/JSONL | 用于图像类评估器 |
| `repository_code_jsonl` | 仓库代码 JSONL | 支持跨记录重复标注 |

数据源还会施加额外限制：S3 当前支持 `jsonl`、`ms_swift` 和 `plaintext`；SQL 推荐使用 `jsonl`；CSV、Excel、Parquet、Markdown、MinerU 和仓库代码格式由本地数据源读取。

#### DatasetHFConfig 配置 (dataset.hf_config)

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| huggingface_split | str | `""` | No | 数据集 split；空字符串等价于 `train` |
| huggingface_config_name | str \| null | `null` | No | Hugging Face 数据集子配置名称，对应 `load_dataset(name=...)` |

#### DatasetS3Config 配置 (dataset.s3_config)

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| s3_ak | str | `""` | Yes | Access Key，运行时不能为空 |
| s3_sk | str | `""` | Yes | Secret Key，运行时不能为空 |
| s3_endpoint_url | str | `""` | Yes | AWS S3 或 S3 兼容服务 endpoint |
| s3_addressing_style | str | `"path"` | No | 可选 `auto`、`path`、`virtual`；Ceph/MinIO 通常使用 `path` |

S3 的 Bucket 从完整 `input_path` URI 中解析，不存在单独的 `s3_bucket` 配置。完整说明见 [S3 数据集使用指南](dataset/s3.md)。

#### DatasetSqlConfig 配置 (dataset.sql_config)

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| dialect | str | `""` | Yes | SQLAlchemy dialect，例如 `sqlite`、`mysql`、`postgresql` |
| driver | str | `""` | No | 驱动名称，例如 `pymysql`、`psycopg2` |
| username | str | `""` | Depends | 非 SQLite 数据库必填 |
| password | str | `""` | No | 数据库密码 |
| host | str | `""` | Depends | 非 SQLite 数据库必填 |
| port | str | `""` | No | 数据库端口，非空时必须能转换为整数 |
| database | str | `""` | Yes | 数据库名；SQLite 使用数据库文件路径 |
| connect_args | str | `""` | No | URL 查询参数，例如 `charset=utf8mb4&connect_timeout=10` |
| engine_args | str | `""` | No | 引擎参数，支持 `pool_pre_ping`、`pool_recycle`、`pool_size`、`max_overflow`、`pool_timeout` |

完整说明见 [SQL Dataset 使用指南](dataset/sql.md)。

#### DatasetExcelConfig 配置 (dataset.excel_config)

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| sheet_name | str \| int | `0` | No | 工作表名称或从 0 开始的索引 |
| has_header | bool | `true` | No | 第一行是否作为列名 |

完整说明见 [Excel 数据集读取功能说明](dataset/excel.md)。

#### DatasetCsvConfig 配置 (dataset.csv_config)

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| has_header | bool | `true` | No | 第一行是否作为列名；否则生成 `column_0` 等列名 |
| encoding | str | `"utf-8"` | No | 文件编码，例如 `utf-8`、`gbk`、`latin1` |
| dialect | str | `"excel"` | No | Python CSV 方言，例如 `excel`、`excel-tab`、`unix` |
| delimiter | str \| null | `null` | No | 自定义分隔符；设置后覆盖方言默认分隔符 |
| quotechar | str | `"\""` | No | 引号字符 |

完整说明见 [CSV 数据集读取功能说明](dataset/csv.md)。

#### DatasetParquetConfig 配置 (dataset.parquet_config)

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| batch_size | int | `10000` | No | PyArrow 每批读取的行数 |
| columns | list[str] \| null | `null` | No | 指定读取列；`null` 表示全部列 |

完整说明见 [Parquet 数据集读取功能说明](dataset/parquet.md)。

#### DatasetMinerUConfig 配置 (dataset.mineru_config)

MinerU 格式特定配置，用于过滤 block 类型：

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| include_types | list[str] | null | No | 只保留指定的 block 类型（如 `["text", "table", "image"]`），null 表示保留全部类型 |

MinerU 支持的 block 类型包括：`text`, `title`, `image`, `table`, `equation`, `code`, `list`, `header`, `page_footer`, `page_footnote`, `chart` 等。

**格式说明：**
- `md`：读取单个 `.md` 文件或目录下全部 `.md` 文件；每个文件构造成一条 `Data`，包含 `id`（文件名）和 `content`（全文字符串）
- `mineru`：对应 MinerU 的 `content_list.json`，顶层为 block 数组
- `mineru_v2`：对应 MinerU 的 `content_list_v2.json`，顶层为页面数组，每页包含 block 数组

每个 block 会被转换为一条 `Data` 记录。block 的 `type`、`bbox`、`page_idx` 等原始字段会通过 Pydantic `extra="allow"` 保留在 Data 对象上。

#### ms-swift 格式 (dataset.format = "ms_swift")

读取 Agent 轨迹 JSONL，每行一个包含 `messages` 数组的对象。保留原始字段，
只为 `evaluator[].evals` 中选中的已支持指标生成 `<指标名>_<字段名>` 字段。
每个指标使用独立的 `fields` 映射配置块。当前支持 9 个确定性规则和 7 个 LLM 指标，
映射及配置示例见 [ms-swift converter 用户说明](agent_trace/ms_swift.md)。

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
| raw        | bool | true    | No       | 是否将原始字段直接保存在结果记录中；设为 false 时保存在 `raw_data` 字段中 |

### LLM Token 使用量输出

当 LLM 服务返回 token usage 时，Dingo 会在对应的 `EvalDetail` 中写入 `usage` 字段，并在 `summary.json` 中按字段组合和 evaluator 汇总到 `token_usage`。该统计来自模型服务商返回的 `usage`，不会本地估算；如果兼容 API 不返回 usage，则对应字段为空。

单条结果示例：

```json
{
  "metric": "LLMTextQualityV5",
  "status": false,
  "label": ["QUALITY_GOOD"],
  "reason": ["pass"],
  "usage": {
    "prompt_tokens": 812,
    "completion_tokens": 96,
    "total_tokens": 908,
    "reasoning_tokens": null,
    "cached_tokens": null,
    "model": "gpt-4o-mini",
    "provider": "openai",
    "calls": 1,
    "source": "provider"
  }
}
```

汇总结果示例：

```json
{
  "token_usage": {
    "content": {
      "LLMTextQualityV5": {
        "prompt_tokens": 81200,
        "completion_tokens": 9600,
        "total_tokens": 90800,
        "reasoning_tokens": 0,
        "cached_tokens": 12000,
        "calls": 100,
        "records": 100,
        "models": {"gpt-4o-mini": 100},
        "providers": {"openai": 100},
        "sources": {"provider": 100}
      }
    }
  }
}
```

### Evaluator 配置 (evaluator)

评估器相关配置：

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| rule_config | object | {} | Depends | 规则配置 |
| llm_config | object | {} | Depends | LLM 配置 |

#### EvaluatorRuleArgs 配置 (evaluator.rule_config.[rule_name])

规则配置（支持额外字段，规则可按需读取自定义参数）：

| Parameter | Type | Default | Required | Description |
|-----------|------|---------|----------|-------------|
| threshold | float | null | No | 规则决策阈值 |
| pattern | str | null | No | 匹配模式字符串 |
| key_list | list | null | No | 匹配关键词列表 |
| refer_path | list | null | No | 参考文件路径或小模型路径 |
| *其他字段* | any | - | No | 规则自定义扩展字段（如 `ignore_order`） |

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
  "task_id": "my-task-001",
  "task_name": "dingo",
  "input_path": "data/train.jsonl",
  "output_path": "outputs/",
  "log_level": "WARNING",
  "dataset": {
    "source": "local",
    "format": "jsonl"
  },
  "executor": {
    "start_index": 0,
    "end_index": -1,
    "max_workers": 1,
    "batch_size": 1,
    "multi_turn_mode": null,
    "result_save": {
      "bad": false,
      "good": false,
      "all_labels": false,
      "raw": true
    }
  },
  "evaluator": [
    {
      "fields": {
        "content": "answer",
        "prompt": "question"
      },
      "evals": [
        {"name": "RuleColonEnd"}
      ]
    }
  ]
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
    "task_id": "my-task-001",
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
