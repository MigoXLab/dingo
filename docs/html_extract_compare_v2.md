# LLMHtmlExtractCompareV2 使用文档

## 概述

`LLMHtmlExtractCompareV2` 是用于对比评估两种 HTML 内容提取工具效果的增强版本。相比 V1 版本，V2 版本采用了更高效的评估策略，大幅减少了 token 消耗。

## 主要特性

### 1. **Diff-Match-Patch 算法优化**
- 在调用 LLM 之前，先使用 `diff-match-patch` 算法计算两段文本的差异
- 将文本分为三部分：
  - `unique_a`: 仅在工具A提取的文本中存在的内容
  - `unique_b`: 仅在工具B提取的文本中存在的内容
  - `common`: 两个工具都提取到的共同内容
- LLM 只需要分析差异部分，而不是完整文本，大幅节省 token

### 2. **中英文双语支持**
- 自动根据输入数据的 `language` 字段选择合适的提示词
- `language="zh"`: 使用中文提示词
- `language="en"`: 使用英文提示词

### 3. **清晰的判断格式**
使用 A/B/C 判断格式，而不是数字评分：
- **A**: Text A (工具A) 包含更多核心信息内容
- **B**: Text A 和 Text B 包含相同量的核心信息内容
- **C**: Text B (工具B) 包含更多核心信息内容

### 4. **聚焦核心信息**
提示词明确定义了什么是"核心信息内容"，排除了以下非核心内容：
- 相关推荐、相关问题
- 推荐文章、"你可能还喜欢"
- 标题、作者信息
- 参考文献、引用列表
- 超链接、导航元素
- 其他自动生成的内容

## 配置参数

使用 `dynamic_config` 设置评估器的配置参数：

```python
evaluator = LLMHtmlExtractCompareV2()
evaluator.dynamic_config.model = 'gpt-4'
evaluator.dynamic_config.key = 'your_api_key'
evaluator.dynamic_config.api_url = 'https://api.openai.com/v1'
```

### 配置参数说明

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `model` | str | 是 | - | LLM 模型名称 |
| `key` | str | 是 | - | API 密钥 |
| `api_url` | str | 是 | - | API 基础URL |

## 输入数据格式

```python
from dingo.io import Data

data = Data(
    data_id="unique_id_001",  # 必需：数据的唯一标识符
    prompt="工具A提取的文本内容",  # 必需
    content="工具B提取的文本内容",  # 必需
    language="zh",  # 可选，默认 "en"；也可放在 raw_data["language"]
)
```

### 数据参数说明

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `data_id` | str | 是 | - | 数据的唯一标识符 |
| `prompt` | str | 是 | - | 工具A提取的文本内容 |
| `content` | str | 是 | - | 工具B提取的文本内容 |
| `language` | str | 否 | "en" | 语言类型，支持 "zh"（中文）和 "en"（英文） |


## 输出结果格式

```python
# result 是 EvalDetail 对象，包含以下字段：
result.metric        # 指标名称: "LLMHtmlExtractCompareV2"
result.label         # 判断标签: ["TOOL_ONE_BETTER.Judgement_A"] 等
result.status        # 错误状态: False (A/B) 或 True (C)
result.reason        # 推理过程: List[str]
```

### 结果映射

| 判断结果 | `result.label` | `result.status` | 含义 |
|----------|----------------|-----------------|------|
| A | ["TOOL_ONE_BETTER.Judgement_A"] | False | 工具A提取的信息更完整 |
| B | ["TOOL_EQUAL.Judgement_B"] | False | 两个工具提取的信息量相同 |
| C | ["TOOL_TWO_BETTER.Judgement_C"] | True | 工具B提取的信息更完整 |

## 使用示例

### 基础用法

```python
import os
from dingo.io import Data
from dingo.model.llm.compare.llm_html_extract_compare_v2 import LLMHtmlExtractCompareV2

# 初始化评估器
evaluator = LLMHtmlExtractCompareV2()
evaluator.dynamic_config.model = 'gpt-4'
evaluator.dynamic_config.key = os.getenv("OPENAI_KEY")
evaluator.dynamic_config.api_url = 'https://api.openai.com/v1'

# 准备数据
data = Data(
    data_id="test_001",
    prompt="工具A提取的内容...",
    content="工具B提取的文本内容",
    language="zh",  # 可选
)

# 执行评估
result = evaluator.eval(data)

# 查看结果
print(f"判断: {result.label}")
print(f"推理: {result.reason[0]}")
```

### 批量评估（使用 Executor）

推荐使用 Executor 进行大规模批量评估，支持并发处理和结果保存。配置需与 `InputArgs` 一致：`evaluator` 为列表，每项包含 `fields`（列名映射到 `Data`）与 `evals`（评估器及 `config`）。

`LLMHtmlExtractCompareV2` 约定：`prompt` = 工具 A 文本，`content` = 工具 B 文本；`language` 可选，缺省为 `"en"`。

```python
import os
from pathlib import Path
from dingo.config.input_args import InputArgs
from dingo.exec.base import Executor

common_config = {
    "model": os.getenv("OPENAI_MODEL", "deepseek-chat"),
    "key": os.getenv("OPENAI_API_KEY"),
    "api_url": os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1"),
}

input_data = {
    "task_name": "html_extract_compare_v2_evaluation",
    "input_path": str(Path("test/data/html_extract_compare_test.jsonl")),
    "output_path": "output/html_extract_compare_evaluation/",
    "dataset": {
        "source": "local",
        "format": "jsonl",
    },
    "executor": {
        "max_workers": 4,
        "batch_size": 1,
        "result_save": {
            "bad": True,   # 保存工具 B 更优的样本（status=True，对应判断 C）
            "good": True,  # 保存工具 A 更好或相当的样本
        },
    },
    "evaluator": [
        {
            # 将 JSONL 列映射到 Data：prompt=工具A，content=工具B
            "fields": {
                "id": "data_id",
                "prompt": "method1",
                "content": "method2",
                "language": "language",
            },
            "evals": [
                {"name": "LLMHtmlExtractCompareV2", "config": common_config},
            ],
        }
    ],
}

input_args = InputArgs(**input_data)
executor = Executor.exec_map["local"](input_args)
result = executor.execute()

print(f"总样本数: {result.total}")
print(f"工具B更好: {result.num_bad}")
print(f"工具A更好或相同: {result.num_good}")
```

若你的数据列名为 `content` / `magic_md`，只需将 `fields` 改为 `"prompt": "content", "content": "magic_md"` 等即可。

#### JSONL 数据格式

与仓库内 `test/data/html_extract_compare_test.jsonl` 对齐：每行一条 JSON，至少包含唯一标识、两种提取结果与可选语言。

```jsonl
{"data_id": "001", "method1": "工具A提取的Markdown文本...", "method2": "工具B提取的Markdown文本...", "language": "zh"}
{"data_id": "002", "method1": "Tool A extracted text...", "method2": "Tool B extracted text...", "language": "en"}
```

`method1` / `method2` 仅为示例列名；实际列名通过 `evaluator[].fields` 中的 `prompt` / `content` 映射指定。

## 与 V1 版本的对比

| 特性 | V1 | V2 |
|------|----|----|
| **Token 消耗** | 高（需要发送完整文本） | 低（只发送差异部分） |
| **评估焦点** | HTML结构化元素识别 | 核心信息内容完整性 |
| **判断格式** | 数字评分 (0/1/2) | 字母判断 (A/B/C) |
| **语言支持** | 仅中文 | 中英文双语 |
| **差异算法** | 无 | diff-match-patch |
| **适用场景** | 结构化内容评估 | 文本内容完整性评估 |

## 技术实现细节

### Diff-Match-Patch 算法

```python
import diff_match_patch as dmp_module

dmp = dmp_module.diff_match_patch()
diff = dmp.diff_main(text_a, text_b)
dmp.diff_cleanupEfficiency(diff)

# diff 结果格式: [(operation, text), ...]
# operation: -1 (删除/仅在A), 0 (相同), 1 (添加/仅在B)
```


## 依赖项

```bash
pip install diff-match-patch
```

## 完整示例

### 单个评估示例
参考: `examples/compare/html_extract_compare_v2_example.py`

### 批量评估示例
参考: `examples/compare/dataset_html_extract_compare_evaluation.py`

### 测试数据
参考: `test/data/html_extract_compare_test.jsonl`
