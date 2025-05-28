# Dingo MCP 服务端

## 概述

`mcp_server.py` 脚本为 Dingo 提供了一个实验性的模型上下文协议 (MCP) 服务端，由 [FastMCP](https://github.com/modelcontextprotocol/fastmcp) 驱动。这允许 MCP 客户端（例如 Cursor）以编程方式与 Dingo 的数据评估功能进行交互。

## 特性

*   通过 MCP 调用 Dingo 的评估逻辑。
*   提供以下工具：
    *   `run_dingo_evaluation`: 对指定数据执行基于规则或基于 LLM 的评估。
    *   `list_dingo_components`: 列出 Dingo 中可用的规则组和已注册的 LLM 模型。
    *   `get_rule_details`: 获取特定规则的详细信息。
    *   `get_llm_details`: 获取特定 LLM 的详细信息。
    *   `get_prompt_details`: 获取特定提示的详细信息。
    *   `run_quick_evaluation`: 基于高级目标运行简化评估。
*   支持通过 MCP 客户端（如 Cursor）进行交互。

## 安装

1.  **前置条件**: 确保你已安装 Git 和 Python 环境（例如 3.8+）。
2.  **克隆仓库**: 将此仓库克隆到本地计算机。
    ```bash
    git clone https://github.com/DataEval/dingo.git
    cd dingo
    ```
3.  **安装依赖**: 安装所需的依赖项，包括 FastMCP 和其他 Dingo 依赖。推荐使用 `requirements.txt` 文件。
    ```bash
    pip install -r requirements.txt
    # 或者，至少安装：pip install fastmcp
    ```
4.  **确保 Dingo 可导入**: 确保在运行服务端脚本时，你的 Python 环境可以找到克隆仓库中的 `dingo` 包。

## 运行服务端

导航到包含 `mcp_server.py` 的目录，并使用 Python 运行它：

```bash
python mcp_server.py
```

### 传输模式

Dingo MCP 服务端支持两种传输模式：

1. **STDIO 传输模式**：
   - 通过设置环境变量 `LOCAL_DEPLOYMENT_MODE=true` 启用
   - 使用标准输入输出流进行通信
   - 适用于直接本地运行或 Smithery 容器化部署
   - 在 mcp.json 中使用 `command` 和 `args` 配置

2. **SSE 传输模式**：
   - 默认模式（当 `LOCAL_DEPLOYMENT_MODE` 未设置或为 false）
   - 通过 HTTP Server-Sent Events 进行网络通信
   - 启动后会监听指定端口，可通过 URL 访问
   - 在 mcp.json 中使用 `url` 配置

根据您的部署需求选择合适的传输模式：
- 如果要在本地直接运行或使用 Smithery 部署，请使用 STDIO 模式
- 如果要部署为网络服务，请使用 SSE 模式

在使用 SSE 模式时，你可以在脚本的 `mcp.run()` 调用中使用参数来自定义其行为：

```python
# mcp_server.py 中的自定义示例
mcp.run(
    transport="sse",      # 通信协议 (sse 是默认值)
    host="127.0.0.1",     # 绑定的网络接口 (默认: 0.0.0.0)
    port=8888,            # 监听的端口 (默认: 8000)
    log_level="debug"     # 日志详细程度 (默认: info)
)
```

**重要**: 请记下服务端运行的 `host` 和 `port`，因为配置 MCP 客户端时需要这些信息。

## 与 Cursor 集成

### 配置

要将 Cursor 连接到你正在运行的 Dingo MCP 服务端，你需要编辑 Cursor 的 MCP 配置文件 (`mcp.json`)。该文件通常位于 Cursor 的用户配置目录中（例如 `~/.cursor/` 或 `%USERPROFILE%\.cursor\`）。

在 `mcpServers` 对象中添加或修改你的 Dingo 服务端条目。

**示例1：SSE 传输模式配置**：

```json
{
  "mcpServers": {
    // ... 其他服务端 ...
    "dingo_evaluator": {
      "url": "http://127.0.0.1:8888/sse" // <-- 必须与你运行的服务端的 host、port 和 transport 匹配
    }
    // ...
  }
}
```

**示例2：STDIO 传输模式配置**：

```json
{
  "mcpServers": {
    "dingo_evaluator": {
      "command": "python",
      "args": ["path/to/mcp_server.py"],
      "env": {
        "LOCAL_DEPLOYMENT_MODE": "true",
        "DEFAULT_OUTPUT_DIR": "/path/to/output",
        "DEFAULT_SAVE_DATA": "true",
        "DEFAULT_SAVE_CORRECT": "true",
        "DEFAULT_DATASET_TYPE": "local",
        "OPENAI_API_KEY": "your-api-key",
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
        "OPENAI_MODEL": "gpt-4",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

*   对于 SSE 模式：确保 `url` 与你的 `mcp_server.py` 配置使用的 `host`、`port` 和 `transport` 完全匹配（目前 URL 方案仅支持 `sse`）。如果你没有自定义 `mcp.run`，默认 URL 可能是 `http://127.0.0.1:8000/sse` 或 `http://0.0.0.0:8000/sse`。
*   对于 STDIO 模式：确保在环境变量中设置 `LOCAL_DEPLOYMENT_MODE` 为 `"true"`。
*   保存对 `mcp.json` 的更改后，重启 Cursor。

### 在 Cursor 中使用

配置完成后，你可以在 Cursor 中调用 Dingo 工具：

*   **列出组件**: "使用 dingo_evaluator 工具列出可用的 Dingo 组件。"
*   **运行评估**: "使用 dingo_evaluator 工具运行规则评估..." 或 "使用 dingo_evaluator 工具运行 LLM 评估..."
*   **获取详情**: "使用 dingo_evaluator 工具获取特定规则/LLM/提示的详细信息..."
*   **快速评估**: "使用 dingo_evaluator 工具快速评估文件的..."

Cursor 将提示你输入必要的参数。

## 工具参考

### `list_dingo_components()`

列出可用的 Dingo 规则组、已注册的 LLM 模型标识符和提示定义。

*   **参数**:
    *   `component_type` (Literal["rule_groups", "llm_models", "prompts", "all"]): 要列出的组件类型。默认值: "all"。
    *   `include_details` (bool): 是否包括每个组件的详细描述和元数据。默认值: false。
*   **返回**: `Dict[str, List[str]]` - 包含 `rule_groups`、`llm_models`、`prompts` 和/或 `llm_prompt_mappings` 的字典（取决于 component_type）。

**Cursor 使用示例**:
> 使用 dingo_evaluator 工具列出 dingo 组件。

### `get_rule_details()`

获取特定 Dingo 规则的详细信息。

*   **参数**:
    *   `rule_name` (str): 要获取详细信息的规则名称。
*   **返回**: 包含规则详细信息的字典，包括其描述、参数和评估特征。

**Cursor 使用示例**:
> 使用 Dingo Evaluator 工具获取"default"规则组的详细信息。

*(Cursor 应提出如下工具调用)*
```xml
<use_mcp_tool>
<server_name>dingo_evaluator</server_name>
<tool_name>get_rule_details</tool_name>
<arguments>
{
  "rule_name": "default"
}
</arguments>
</use_mcp_tool>
```

### `get_llm_details()`

获取特定 Dingo LLM 的详细信息。

*   **参数**:
    *   `llm_name` (str): 要获取详细信息的 LLM 名称。
*   **返回**: 包含 LLM 详细信息的字典，包括其描述、功能和配置参数。

**Cursor 使用示例**:
> 使用 Dingo Evaluator 工具获取"LLMTextQualityModelBase" LLM 的详细信息。

*(Cursor 应提出如下工具调用)*
```xml
<use_mcp_tool>
<server_name>dingo_evaluator</server_name>
<tool_name>get_llm_details</tool_name>
<arguments>
{
  "llm_name": "LLMTextQualityModelBase"
}
</arguments>
</use_mcp_tool>
```

### `get_prompt_details()`

获取特定 Dingo 提示的详细信息。

*   **参数**:
    *   `prompt_name` (str): 要获取详细信息的提示名称。
*   **返回**: 包含提示详细信息的字典，包括其描述、关联的指标类型以及所属的组。

**Cursor 使用示例**:
> 使用 Dingo Evaluator 工具获取"PromptTextQuality"提示的详细信息。

*(Cursor 应提出如下工具调用)*
```xml
<use_mcp_tool>
<server_name>dingo_evaluator</server_name>
<tool_name>get_prompt_details</tool_name>
<arguments>
{
  "prompt_name": "PromptTextQuality"
}
</arguments>
</use_mcp_tool>
```

### `run_quick_evaluation()`

基于高级目标运行简化的 Dingo 评估。

*   **参数**:
    *   `input_path` (str): 要评估的文件路径。
    *   `evaluation_goal` (str): 描述要评估的内容（例如，"检查不当内容"、"评估文本质量"、"评估帮助性"）。
*   **返回**: 评估结果的摘要或详细结果的路径。

**Cursor 使用示例**:
> 使用 Dingo Evaluator 工具快速评估文件"test/data/test_local_jsonl.jsonl"中的文本质量。

*(Cursor 应提出如下工具调用)*
```xml
<use_mcp_tool>
<server_name>dingo_evaluator</server_name>
<tool_name>run_quick_evaluation</tool_name>
<arguments>
{
  "input_path": "test/data/test_local_jsonl.jsonl",
  "evaluation_goal": "评估文本质量并检查任何问题"
}
</arguments>
</use_mcp_tool>
```

### `run_dingo_evaluation(...)`

运行 Dingo 评估（基于规则或基于 LLM）。

*   **参数**:
    *   `input_path` (str): 输入文件或目录的路径（相对于项目根目录或绝对路径）。
    *   `evaluation_type` (Literal["rule", "llm"]): 评估类型。
    *   `eval_group_name` (str): 用于 `rule` 类型的规则组名称（默认：`""`，表示使用 'default'）。服务端逻辑仅验证 'default', 'sft', 'pretrain'。对于 `llm` 类型则忽略此参数。
    *   `output_dir` (Optional[str]): 保存输出的目录。默认为 `input_path` 父目录下的 `dingo_output_*` 子目录。
    *   `task_name` (Optional[str]): 任务名称（用于生成输出路径）。默认为 `mcp_eval_<uuid>`。
    *   `save_data` (bool): 是否保存详细的 JSONL 输出（默认：True）。
    *   `save_correct` (bool): 是否保存正确的数据（默认：True）。
    *   `kwargs` (dict): 用于附加 `dingo.io.InputArgs` 的字典。常见用途：
        *   `dataset` (str): 数据集类型（例如 'local', 'hugging_face'）。如果提供了 `input_path`，则默认为 'local'。
        *   `data_format` (str): 输入数据格式（例如 'json', 'jsonl', 'plaintext'）。如果可能，会从 `input_path` 扩展名推断。
        *   `column_content` (str): **对于 JSON/JSONL 等格式必需** - 指定包含要评估文本的键。
        *   `column_id`, `column_prompt`, `column_image`: 其他列映射。
        *   `custom_config` (str | dict): JSON 配置文件路径、JSON 字符串或用于 LLM 评估或自定义规则设置的字典。LLM 的 API 密钥**必须**在此处提供。
        *   `max_workers`, `batch_size`: Dingo 执行参数（在 MCP 中默认为 1 以确保稳定性）。
*   **返回**: `str` - 主输出文件的绝对路径（例如 `summary.json`）。

**Cursor 使用示例 (基于规则):**

> 使用 Dingo Evaluator 工具对 `test/data/test_local_jsonl.jsonl` 运行默认规则评估。确保使用 'content' 列。

*(Cursor 应提出如下工具调用)*
```xml
<use_mcp_tool>
<server_name>dingo_evaluator</server_name>
<tool_name>run_dingo_evaluation</tool_name>
<arguments>
{
  "input_path": "test/data/test_local_jsonl.jsonl",
  "evaluation_type": "rule",
  "eval_group_name": "default",
  "kwargs": {
    "column_content": "content"
    // data_format="jsonl" 和 dataset="local" 将被推断
  }
}
</arguments>
</use_mcp_tool>
```

**Cursor 使用示例 (基于 LLM):**

> 使用 Dingo Evaluator 工具对 `test/data/test_local_jsonl.jsonl` 执行 LLM 评估。使用 'content' 列。使用文件 `examples/mcp/config_self_deployed_llm.json` 进行配置。

*(Cursor 应提出如下工具调用。注意，当为 LLM 评估使用 `custom_config` 时，可以省略或设置 `eval_group_name`)*
```xml
<use_mcp_tool>
<server_name>dingo_evaluator</server_name>
<tool_name>run_dingo_evaluation</tool_name>
<arguments>
{
  "input_path": "test/data/test_local_jsonl.jsonl",
  "evaluation_type": "llm",
  "kwargs": {
    "column_content": "content",
    "custom_config": "examples/mcp/config_self_deployed_llm.json"
    // data_format="jsonl" 和 dataset="local" 将被推断
  }
}
</arguments>
</use_mcp_tool>
```

请参阅 `examples/mcp/config_api_llm.json`（用于基于 API 的 LLM）和 `examples/mcp/config_self_deployed_llm.json`（用于自托管 LLM）了解 `custom_config` 文件的结构，包括放置 API 密钥或 URL 的位置。
