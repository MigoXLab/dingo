# Dingo MCP Server

## Overview

The `mcp_server.py` script provides an experimental Model Context Protocol (MCP) server for Dingo, powered by [FastMCP](https://github.com/modelcontextprotocol/fastmcp). This allows MCP clients, such as Cursor, to interact with Dingo's data evaluation capabilities programmatically.

## Features

*   Exposes Dingo's evaluation logic via MCP.
*   Provides two primary tools:
    *   `run_dingo_evaluation`: Executes rule-based or LLM-based evaluations on specified data.
    *   `list_dingo_components`: Lists available rule groups and registered LLM models within Dingo.
*   Enables interaction through MCP clients like Cursor.

## Installation

1.  **Prerequisites**: Ensure you have Git and a Python environment (e.g., 3.8+) set up.
2.  **Clone the Repository**: Clone this repository to your local machine.
    ```bash
    git clone https://github.com/DataEval/dingo.git
    cd dingo
    ```
3.  **Install Dependencies**: Install the required dependencies, including FastMCP and other Dingo requirements. It's recommended to use the `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    # Alternatively, at minimum: pip install fastmcp
    ```
4.  **Ensure Dingo is Importable**: Make sure your Python environment can find the `dingo` package within the cloned repository when you run the server script.

## Running the Server

Navigate to the directory containing `mcp_server.py` and run it using Python:

```bash
python mcp_server.py
```

By default, the server starts using the Server-Sent Events (SSE) transport protocol. You can customize its behavior using arguments within the script's `mcp.run()` call:

```python
# Example customization in mcp_server.py
mcp.run(
    transport="sse",      # Communication protocol (sse is default)
    host="127.0.0.1",     # Network interface to bind to (default: 0.0.0.0)
    port=8888,            # Port to listen on (default: 8000)
    log_level="debug"     # Logging verbosity (default: info)
)
```

**Important**: Note the `host` and `port` the server is running on, as you will need these to configure your MCP client.

## Integration with Cursor

### Configuration

To connect Cursor to your running Dingo MCP server, you need to edit Cursor's MCP configuration file (`mcp.json`). This file is typically located in Cursor's user configuration directory (e.g., `~/.cursor/` or `%USERPROFILE%\.cursor\`).

Add or modify the entry for your Dingo server within the `mcpServers` object. Use the `url` property to specify the address of your running server.

**Example `mcp.json` entry:**

```json
{
  "mcpServers": {
    // ... other servers ...
    "dingo_evaluator": {
      "url": "http://127.0.0.1:8888/sse" // <-- MUST match host, port, and transport of your running server
    }
    // ...
  }
}
```

*   Ensure the `url` exactly matches the `host`, `port`, and `transport` (currently only `sse` is supported for the URL scheme) your `mcp_server.py` is configured to use. If you didn't customize `mcp.run`, the default URL is likely `http://127.0.0.1:8000/sse` or `http://0.0.0.0:8000/sse`.
*   Restart Cursor after saving changes to `mcp.json`.

### Usage in Cursor

Once configured, you can invoke the Dingo tools within Cursor:

*   **List Components**: "Use the dingo_evaluator tool to list available Dingo components."
*   **Run Evaluation**: "Use the dingo_evaluator tool to run a rule evaluation..." or "Use the dingo_evaluator tool to run an LLM evaluation..."

Cursor will prompt you for the necessary arguments.

## Tool Reference

### `list_dingo_components()`

Lists available Dingo rule groups and registered LLM model identifiers.

*   **Arguments**: None
*   **Returns**: `Dict[str, List[str]]` - A dictionary containing `rule_groups` and `llm_models`.

**Example Cursor Usage**:
> Use the dingo_evaluator tool to list dingo components.

### `run_dingo_evaluation(...)`

Runs a Dingo evaluation (rule-based or LLM-based).

*   **Arguments**:
    *   `input_path` (str): Path to the input file or directory (relative to the project root or absolute).
    *   `evaluation_type` (Literal["rule", "llm"]): Type of evaluation.
    *   `eval_group_name` (str): Rule group name for `rule` type (default: `""` which uses 'default'). Only 'default', 'sft', 'pretrain' are validated by the server logic. Ignored for `llm` type.
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
