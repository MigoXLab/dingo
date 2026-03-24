# Dingo MCP Server

## Overview

Dingo provides a built-in Model Context Protocol (MCP) server, powered by [FastMCP](https://github.com/modelcontextprotocol/fastmcp). This allows MCP clients, such as Cursor, to interact with Dingo's data evaluation capabilities programmatically.

## Features

*   Exposes Dingo's evaluation logic via MCP.
*   Provides tools for:
    *   `run_dingo_evaluation`: Executes rule-based or LLM-based evaluations on specified data.
    *   `list_dingo_components`: Lists available rule groups and registered LLM models within Dingo.
    *   `get_rule_details`: Gets detailed information about a specific rule.
    *   `get_llm_details`: Gets detailed information about a specific LLM.
    *   `get_prompt_details`: Gets detailed information about a specific prompt.
    *   `run_quick_evaluation`: Runs a simplified evaluation based on a high-level goal.
*   Enables interaction through MCP clients like Cursor.

## Installation

```bash
pip install dingo-python
```

This installs the `dingo` CLI command which includes the MCP server. No need to clone the repository.

For development or to customize `mcp_server.py` directly:

```bash
git clone https://github.com/MigoXLab/dingo.git
cd dingo
pip install -e .
```

## Running the Server

### Using the CLI (recommended)

```bash
# SSE transport (default) on port 8000
dingo serve

# Custom host and port
dingo serve --host 127.0.0.1 --port 9000

# stdio transport (for Claude Desktop or local agent spawn)
dingo serve --transport stdio
```

### Using mcp_server.py directly (legacy)

If you cloned the repository, you can also run the server script directly:

```bash
python mcp_server.py
```

### Transmission Modes

| Mode | Use Case | How to Start |
|------|----------|-------------|
| **SSE** (default) | Network service, Cursor integration | `dingo serve` or `dingo serve --port 9000` |
| **stdio** | Claude Desktop, local agent spawn | `dingo serve --transport stdio` |

## Integration with Cursor

### Configuration

To connect Cursor to your running Dingo MCP server, you need to edit Cursor's MCP configuration file (`mcp.json`). This file is typically located in Cursor's user configuration directory (e.g., `~/.cursor/` or `%USERPROFILE%\.cursor\`).

Add or modify the entry for your Dingo server within the `mcpServers` object.

**Example 1: SSE Mode** (run `dingo serve` first, then configure):

```json
{
  "mcpServers": {
    "dingo": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

**Example 2: stdio Mode** (Cursor spawns the process automatically):

```json
{
  "mcpServers": {
    "dingo": {
      "command": "dingo",
      "args": ["serve", "--transport", "stdio"],
      "env": {
        "OPENAI_API_KEY": "your-api-key",
        "OPENAI_BASE_URL": "https://api.openai.com/v1",
        "OPENAI_MODEL": "gpt-4"
      }
    }
  }
}
```

*   For SSE mode: Start `dingo serve` first, then the `url` must match the host and port. Default is `http://localhost:8000/sse`.
*   For stdio mode: Cursor spawns the `dingo serve --transport stdio` process automatically. No need to start the server manually.
*   Restart Cursor after saving changes to `mcp.json`.

### Usage in Cursor

Once configured, you can invoke the Dingo tools within Cursor:

*   **List Components**: "Use the dingo_evaluator tool to list available Dingo components."
*   **Run Evaluation**: "Use the dingo_evaluator tool to run a rule evaluation..." or "Use the dingo_evaluator tool to run an LLM evaluation..."
*   **Get Details**: "Use the dingo_evaluator tool to get details about a specific rule/LLM/prompt..."
*   **Quick Evaluation**: "Use the dingo_evaluator tool to quickly evaluate a file for..."

Cursor will prompt you for the necessary arguments.

## Tool Reference

### `list_dingo_components()`

Lists available Dingo rule groups, registered LLM model identifiers, and prompt definitions.

*   **Arguments**:
    *   `component_type` (Literal["rule_groups", "llm_models", "prompts", "all"]): Type of components to list. Default: "all".
    *   `include_details` (bool): Whether to include detailed descriptions and metadata for each component. Default: false.
*   **Returns**: `Dict[str, List[str]]` - A dictionary containing `rule_groups`, `llm_models`, `prompts`, and/or `llm_prompt_mappings` based on component_type.

**Example Cursor Usage**:
> Use the dingo_evaluator tool to list dingo components.

### `get_rule_details()`

Get detailed information about a specific Dingo rule.

*   **Arguments**:
    *   `rule_name` (str): The name of the rule to get details for.
*   **Returns**: A dictionary containing details about the rule, including its description, parameters, and evaluation characteristics.

**Example Cursor Usage**:
> Use the Dingo Evaluator tool to get details about the 'default' rule group.

*(Cursor should propose a tool call like below)*
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

Get detailed information about a specific Dingo LLM.

*   **Arguments**:
    *   `llm_name` (str): The name of the LLM to get details for.
*   **Returns**: A dictionary containing details about the LLM, including its description, capabilities, and configuration parameters.

**Example Cursor Usage**:
> Use the Dingo Evaluator tool to get details about the 'LLMTextQualityModelBase' LLM.

*(Cursor should propose a tool call like below)*
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

Get detailed information about a specific Dingo prompt.

*   **Arguments**:
    *   `prompt_name` (str): The name of the prompt to get details for.
*   **Returns**: A dictionary containing details about the prompt, including its description, associated metric type, and which groups it belongs to.

**Example Cursor Usage**:
> Use the Dingo Evaluator tool to get details about the 'PromptTextQuality' prompt.

*(Cursor should propose a tool call like below)*
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

Run a simplified Dingo evaluation based on a high-level goal.

*   **Arguments**:
    *   `input_path` (str): Path to the file to evaluate.
    *   `evaluation_goal` (str): Description of what to evaluate (e.g., 'check for inappropriate content', 'evaluate text quality', 'assess helpfulness').
*   **Returns**: A summary of the evaluation results or a path to the detailed results.

**Example Cursor Usage**:
> Use the Dingo Evaluator tool to quickly evaluate text quality in the file 'test/data/test_local_jsonl.jsonl'.

*(Cursor should propose a tool call like below)*
```xml
<use_mcp_tool>
<server_name>dingo_evaluator</server_name>
<tool_name>run_quick_evaluation</tool_name>
<arguments>
{
  "input_path": "test/data/test_local_jsonl.jsonl",
  "evaluation_goal": "evaluate text quality and check for any issues"
}
</arguments>
</use_mcp_tool>
```

### `run_dingo_evaluation(...)`

Runs a Dingo evaluation (rule-based or LLM-based).

*   **Arguments**:
    *   `input_path` (str): Path to the input file or directory. Supports:
        *   **Relative paths** (recommended): Resolved relative to the current working directory (CWD), e.g., `test_data.jsonl`
        *   **Absolute paths**: Used directly if the file exists
        *   **Project-relative paths** (legacy): Falls back to project root if not found in CWD
    *   `evaluation_type` (Literal["rule", "llm"]): Type of evaluation.
    *   `eval_group_name` (str): Rule group name for `rule` type (default: `""` which uses 'default'). Valid rule groups are dynamically loaded from Dingo's Model registry. Use `list_dingo_components(component_type="rule_groups")` to see available groups. Ignored for `llm` type.
    *   `output_dir` (Optional[str]): Directory to save outputs. Defaults to a `dingo_output_*` subdirectory within the parent directory of `input_path`.
    *   `task_name` (Optional[str]): Name for the task (used in output path generation). Defaults to `mcp_eval_<uuid>`.
    *   `save_data` (bool): Whether to save detailed JSONL output (default: True).
    *   `save_correct` (bool): Whether to save correct data (default: True).
    *   `kwargs` (dict): Dictionary for additional `dingo.io.InputArgs`. Common uses:
        *   `dataset` (str): Dataset type (e.g., 'local', 'hugging_face'). Defaults to 'local' if `input_path` is given.
        *   `data_format` (str): Input data format (e.g., 'json', 'jsonl', 'plaintext'). Inferred from `input_path` extension if possible.
        *   `column_content` (str): **Required** for formats like JSON/JSONL - specifies the key containing the text to evaluate.
        *   `column_id`, `column_prompt`, `column_image`: Other column mappings.
        *   `custom_config` (str | dict): Path to a JSON config file, a JSON string, or a dictionary for LLM evaluation or custom rule settings. API keys for LLMs **must** be provided here.
        *   `max_workers`, `batch_size`: Dingo execution parameters (default to 1 in MCP for stability).
*   **Returns**: `str` - The absolute path to the primary output file (e.g., `summary.json`).

**Example Cursor Usage (Rule-based):**

> Use the Dingo Evaluator tool to run the default rule evaluation on `test/data/test_local_jsonl.jsonl`. Make sure to use the 'content' column.

*(Cursor should propose a tool call like below)*
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
    // data_format="jsonl" and dataset="local" will be inferred
  }
}
</arguments>
</use_mcp_tool>
```

**Example Cursor Usage (LLM-based):**

> Use the Dingo Evaluator tool to perform an LLM evaluation on `test/data/test_local_jsonl.jsonl`. Use the 'content' column. Configure it using the file `examples/mcp/config_self_deployed_llm.json`.

*(Cursor should propose a tool call like below. Note `eval_group_name` can be omitted or set when using `custom_config` for LLM evals)*
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
    // data_format="jsonl" and dataset="local" will be inferred
  }
}
</arguments>
</use_mcp_tool>
```

Refer to `examples/mcp/config_api_llm.json` (for API-based LLMs) and `examples/mcp/config_self_deployed_llm.json` (for self-hosted LLMs) for the structure of the `custom_config` file, including where to place API keys or URLs.
