# Dingo MCPサーバー

## 概要

`mcp_server.py`スクリプトは、[FastMCP](https://github.com/modelcontextprotocol/fastmcp)を使用してDingo用の実験的なModel Context Protocol（MCP）サーバーを提供します。これにより、CursorなどのMCPクライアントがDingoのデータ評価機能とプログラム的に対話できるようになります。

## 機能

*   MCPを通じてDingoの評価ロジックを公開
*   以下のツールを提供：
    *   `run_dingo_evaluation`: 指定されたデータに対してルールベースまたはLLMベースの評価を実行
    *   `list_dingo_components`: Dingo内で利用可能なルールグループと登録されたLLMモデルをリスト表示
    *   `get_rule_details`: 特定のルールの詳細情報を取得
    *   `get_llm_details`: 特定のLLMの詳細情報を取得
    *   `get_prompt_details`: 特定のプロンプトの詳細情報を取得
    *   `run_quick_evaluation`: 高レベルな目標に基づいて簡略化された評価を実行
*   CursorなどのMCPクライアントを通じた対話を可能にする

## インストール

1.  **前提条件**: GitとPython環境（例：3.8+）がセットアップされていることを確認してください。
2.  **リポジトリのクローン**: このリポジトリをローカルマシンにクローンします。
    ```bash
    git clone https://github.com/DataEval/dingo.git
    cd dingo
    ```
3.  **依存関係のインストール**: FastMCPやその他のDingo要件を含む必要な依存関係をインストールします。`requirements.txt`ファイルの使用を推奨します。
    ```bash
    pip install -r requirements.txt
    # または、最低限：pip install fastmcp
    ```
4.  **Dingoがインポート可能であることを確認**: サーバースクリプトを実行する際に、Python環境がクローンしたリポジトリ内の`dingo`パッケージを見つけられることを確認してください。

## サーバーの実行

`mcp_server.py`が含まれているディレクトリに移動し、Pythonを使用して実行します：

```bash
python mcp_server.py
```

### 伝送モード

Dingo MCPサーバーは2つの伝送モードをサポートしています：

1. **STDIO伝送モード**：
   - 環境変数`LOCAL_DEPLOYMENT_MODE=true`を設定することで有効化
   - 標準入出力ストリームを使用して通信
   - 直接的なローカル実行やSmitheryコンテナ化デプロイメントに適している
   - mcp.jsonで`command`と`args`を使用して設定

2. **SSE伝送モード**：
   - デフォルトモード（`LOCAL_DEPLOYMENT_MODE`が設定されていないか、falseの場合）
   - ネットワーク通信にHTTP Server-Sent Eventsを使用
   - 起動後に指定されたポートでリッスンし、URL経由でアクセス可能
   - mcp.jsonで`url`を使用して設定

デプロイメントのニーズに応じて適切な伝送モードを選択してください：
- ローカル実行やSmitheryデプロイメントにはSTDIOモードを使用
- ネットワークサービスデプロイメントにはSSEモードを使用

SSEモードを使用する場合、スクリプトの`mcp.run()`呼び出しで引数を使用してサーバーの動作をカスタマイズできます：

```python
# mcp_server.pyでのカスタマイズ例
mcp.run(
    transport="sse",      # 通信プロトコル（sseがデフォルト）
    host="127.0.0.1",     # バインドするネットワークインターフェース（デフォルト：0.0.0.0）
    port=8888,            # リッスンするポート（デフォルト：8000）
    log_level="debug"     # ログの詳細レベル（デフォルト：info）
)
```

**重要**: MCPクライアントを設定する際に必要となるため、サーバーが実行されている`host`と`port`をメモしてください。

## Cursorとの統合

### 設定

実行中のDingo MCPサーバーにCursorを接続するには、CursorのMCP設定ファイル（`mcp.json`）を編集する必要があります。このファイルは通常、Cursorのユーザー設定ディレクトリ（例：`~/.cursor/`または`%USERPROFILE%\.cursor\`）にあります。

`mcpServers`オブジェクト内でDingoサーバーのエントリを追加または変更します。

**例1：SSE伝送モード設定**：

```json
{
  "mcpServers": {
    // ... その他のサーバー ...
    "dingo_evaluator": {
      "url": "http://127.0.0.1:8888/sse" // <-- 実行中のサーバーのhost、port、transportと一致する必要があります
    }
    // ...
  }
}
```

**例2：STDIO伝送モード設定**：

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

*   SSEモードの場合：`url`が`mcp_server.py`が使用するように設定された`host`、`port`、`transport`（現在URLスキームでは`sse`のみサポート）と正確に一致することを確認してください。`mcp.run`をカスタマイズしていない場合、デフォルトのURLは`http://127.0.0.1:8000/sse`または`http://0.0.0.0:8000/sse`の可能性があります。
*   STDIOモードの場合：環境変数で`LOCAL_DEPLOYMENT_MODE`が`"true"`に設定されていることを確認してください。
*   `mcp.json`への変更を保存した後、Cursorを再起動してください。

### Cursorでの使用

設定が完了すると、Cursor内でDingoツールを呼び出すことができます：

*   **コンポーネントのリスト表示**: "dingo_evaluatorツールを使用して利用可能なDingoコンポーネントをリストしてください。"
*   **評価の実行**: "dingo_evaluatorツールを使用してルール評価を実行してください..." または "dingo_evaluatorツールを使用してLLM評価を実行してください..."
*   **詳細の取得**: "dingo_evaluatorツールを使用して特定のルール/LLM/プロンプトの詳細を取得してください..."
*   **クイック評価**: "dingo_evaluatorツールを使用してファイルを迅速に評価してください..."

Cursorが必要な引数の入力を促します。

## ツールリファレンス

### `list_dingo_components()`

利用可能なDingoルールグループ、登録されたLLMモデル識別子、およびプロンプト定義をリストします。

*   **引数**:
    *   `component_type` (Literal["rule_groups", "llm_models", "prompts", "all"]): リストするコンポーネントのタイプ。デフォルト："all"。
    *   `include_details` (bool): 各コンポーネントの詳細な説明とメタデータを含めるかどうか。デフォルト：false。
*   **戻り値**: `Dict[str, List[str]]` - component_typeに基づいて`rule_groups`、`llm_models`、`prompts`、および/または`llm_prompt_mappings`を含む辞書。

**Cursor使用例**:
> dingo_evaluatorツールを使用してdingoコンポーネントをリストしてください。

### `get_rule_details()`

特定のDingoルールの詳細情報を取得します。

*   **引数**:
    *   `rule_name` (str): 詳細を取得するルールの名前。
*   **戻り値**: ルールの詳細を含む辞書（説明、パラメータ、評価特性を含む）。

**Cursor使用例**:
> Dingo Evaluatorツールを使用して'default'ルールグループの詳細を取得してください。

*(Cursorは以下のようなツール呼び出しを提案するはずです)*
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

特定のDingo LLMの詳細情報を取得します。

*   **引数**:
    *   `llm_name` (str): 詳細を取得するLLMの名前。
*   **戻り値**: LLMの詳細を含む辞書（説明、機能、設定パラメータを含む）。

**Cursor使用例**:
> Dingo Evaluatorツールを使用して'LLMTextQualityModelBase' LLMの詳細を取得してください。

*(Cursorは以下のようなツール呼び出しを提案するはずです)*
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

特定のDingoプロンプトの詳細情報を取得します。

*   **引数**:
    *   `prompt_name` (str): 詳細を取得するプロンプトの名前。
*   **戻り値**: プロンプトの詳細を含む辞書（説明、関連するメトリックタイプ、所属するグループを含む）。

**Cursor使用例**:
> Dingo Evaluatorツールを使用して'PromptTextQuality'プロンプトの詳細を取得してください。

*(Cursorは以下のようなツール呼び出しを提案するはずです)*
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

高レベルな目標に基づいて簡略化されたDingo評価を実行します。

*   **引数**:
    *   `input_path` (str): 評価するファイルのパス。
    *   `evaluation_goal` (str): 評価する内容の説明（例：'不適切なコンテンツをチェック'、'テキスト品質を評価'、'有用性を評価'）。
*   **戻り値**: 評価結果の要約または詳細結果へのパス。

**Cursor使用例**:
> Dingo Evaluatorツールを使用してファイル'test/data/test_local_jsonl.jsonl'のテキスト品質を迅速に評価してください。

*(Cursorは以下のようなツール呼び出しを提案するはずです)*
```xml
<use_mcp_tool>
<server_name>dingo_evaluator</server_name>
<tool_name>run_quick_evaluation</tool_name>
<arguments>
{
  "input_path": "test/data/test_local_jsonl.jsonl",
  "evaluation_goal": "テキスト品質を評価し、問題をチェックする"
}
</arguments>
</use_mcp_tool>
```

### `run_dingo_evaluation(...)`

Dingo評価（ルールベースまたはLLMベース）を実行します。

*   **引数**:
    *   `input_path` (str): 入力ファイルまたはディレクトリのパス（プロジェクトルートからの相対パスまたは絶対パス）。
    *   `evaluation_type` (Literal["rule", "llm"]): 評価のタイプ。
    *   `eval_group_name` (str): `rule`タイプのルールグループ名（デフォルト：`""`、'default'を使用）。サーバーロジックでは'default'、'sft'、'pretrain'のみが検証されます。`llm`タイプでは無視されます。
    *   `output_dir` (Optional[str]): 出力を保存するディレクトリ。デフォルトは`input_path`の親ディレクトリ内の`dingo_output_*`サブディレクトリ。
    *   `task_name` (Optional[str]): タスクの名前（出力パス生成に使用）。デフォルトは`mcp_eval_<uuid>`。
    *   `save_data` (bool): 詳細なJSONL出力を保存するかどうか（デフォルト：True）。
    *   `save_correct` (bool): 正しいデータを保存するかどうか（デフォルト：True）。
    *   `kwargs` (dict): 追加の`dingo.io.InputArgs`用の辞書。一般的な用途：
        *   `dataset` (str): データセットタイプ（例：'local'、'hugging_face'）。`input_path`が指定されている場合、デフォルトは'local'。
        *   `data_format` (str): 入力データ形式（例：'json'、'jsonl'、'plaintext'）。可能であれば`input_path`の拡張子から推測されます。
        *   `column_content` (str): **JSON/JSONLなどの形式では必須** - 評価するテキストを含むキーを指定。
        *   `column_id`、`column_prompt`、`column_image`: その他の列マッピング。
        *   `custom_config` (str | dict): JSONコンフィグファイルのパス、JSON文字列、またはLLM評価やカスタムルール設定用の辞書。LLMのAPIキーは**ここで**提供する必要があります。
        *   `max_workers`、`batch_size`: Dingo実行パラメータ（安定性のためMCPではデフォルトで1）。
*   **戻り値**: `str` - 主要出力ファイルの絶対パス（例：`summary.json`）。

**Cursor使用例（ルールベース）:**

> Dingo Evaluatorツールを使用して`test/data/test_local_jsonl.jsonl`でデフォルトルール評価を実行してください。'content'列を使用することを確認してください。

*(Cursorは以下のようなツール呼び出しを提案するはずです)*
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
    // data_format="jsonl"とdataset="local"は推測されます
  }
}
</arguments>
</use_mcp_tool>
```

**Cursor使用例（LLMベース）:**

> Dingo Evaluatorツールを使用して`test/data/test_local_jsonl.jsonl`でLLM評価を実行してください。'content'列を使用してください。ファイル`examples/mcp/config_self_deployed_llm.json`を使用して設定してください。

*(Cursorは以下のようなツール呼び出しを提案するはずです。LLM評価で`custom_config`を使用する場合、`eval_group_name`は省略または設定可能です)*
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
    // data_format="jsonl"とdataset="local"は推測されます
  }
}
</arguments>
</use_mcp_tool>
```

APIキーやURLの配置場所を含む`custom_config`ファイルの構造については、`examples/mcp/config_api_llm.json`（APIベースLLM用）と`examples/mcp/config_self_deployed_llm.json`（セルフホストLLM用）を参照してください。
