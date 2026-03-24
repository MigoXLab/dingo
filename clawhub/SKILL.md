# Data Quality Evaluation with Dingo

Dingo: A Comprehensive AI Data, Model and Application Quality Evaluation Tool.

* **GitHub**: https://github.com/MigoXLab/dingo
* **SaaS Platform**: https://dingo.openxlab.org.cn/ (free, no install needed)
* **PyPI**: https://pypi.org/project/dingo-python/

## Installation

```bash
pip install dingo-python
```

### Optional extras

```bash
pip install "dingo-python[agent]"    # Agent-based evaluation (fact-checking)
pip install "dingo-python[hhem]"     # HHEM hallucination detection
pip install "dingo-python[all]"      # Everything
```

### Verify installation

```bash
python -c "from dingo.config import InputArgs; print('Dingo OK')"
```

## Two evaluation modes

| | Rule-based | LLM-based |
|---|---|---|
| API key required | No | Yes (any OpenAI-compatible API) |
| Speed | Fast | Slower (API calls) |
| Cost | Zero | Per-token cost |
| Metrics | 50+ deterministic rules | Text quality, RAG, 3H, security |
| Best for | Format checks, PII, completeness | Semantic quality, faithfulness |

## Core workflow

1. **Prepare data**: JSONL, JSON, CSV, plaintext, or Parquet file
2. **Choose evaluators**: Rule-based (free, fast) or LLM-based (semantic understanding)
3. **Run evaluation**: CLI with config file or Python SDK
4. **Review results**: `summary.json` + per-item JSONL reports in output directory

## CLI Usage

Dingo CLI takes a JSON config file as input:

```bash
dingo eval --input config.json
```

### Minimal rule-based config

```json
{
  "input_path": "data.jsonl",
  "dataset": {"source": "local", "format": "jsonl"},
  "evaluator": [
    {
      "fields": {"content": "content"},
      "evals": [
        {"name": "RuleColonEnd"},
        {"name": "RuleSpecialCharacter"},
        {"name": "RuleContentNull"}
      ]
    }
  ]
}
```

### LLM-based config

```json
{
  "input_path": "data.jsonl",
  "dataset": {"source": "local", "format": "jsonl"},
  "evaluator": [
    {
      "fields": {"content": "content"},
      "evals": [
        {
          "name": "LLMTextRepeat",
          "config": {
            "model": "deepseek-chat",
            "key": "${OPENAI_API_KEY}",
            "api_url": "https://api.deepseek.com/v1"
          }
        }
      ]
    }
  ]
}
```

### RAG evaluation config

RAG evaluation requires specific fields mapped from the dataset:

```json
{
  "input_path": "rag_output.jsonl",
  "dataset": {"source": "local", "format": "jsonl"},
  "evaluator": [
    {
      "fields": {
        "user_input": "user_input",
        "response": "response",
        "retrieved_contexts": "retrieved_contexts",
        "reference": "reference"
      },
      "evals": [
        {"name": "Faithfulness", "config": {"model": "deepseek-chat", "key": "${OPENAI_API_KEY}", "api_url": "https://api.deepseek.com/v1"}},
        {"name": "ContextPrecision", "config": {"model": "deepseek-chat", "key": "${OPENAI_API_KEY}", "api_url": "https://api.deepseek.com/v1"}}
      ]
    }
  ]
}
```

### Multi-field evaluation config

Evaluate different columns with different rules:

```json
{
  "input_path": "qa_data.jsonl",
  "dataset": {"source": "local", "format": "jsonl"},
  "evaluator": [
    {
      "fields": {"content": "answer"},
      "evals": [{"name": "RuleColonEnd"}, {"name": "RuleSpecialCharacter"}]
    },
    {
      "fields": {"content": "question"},
      "evals": [{"name": "RuleContentNull"}]
    }
  ]
}
```

## SDK Usage

For programmatic use inside Python scripts:

```python
from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": "data.jsonl",
        "dataset": {"source": "local", "format": "jsonl"},
        "evaluator": [
            {
                "fields": {"content": "content"},
                "evals": [
                    {"name": "RuleColonEnd"},
                    {"name": "RuleSpecialCharacter"}
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
```

## Config reference

### Dataset configuration

| Field | Values | Description |
|---|---|---|
| `source` | `local`, `huggingface`, `s3`, `sql` | Data source type |
| `format` | `jsonl`, `json`, `csv`, `plaintext`, `parquet` | File format |

### Executor configuration

| Field | Default | Description |
|---|---|---|
| `max_workers` | 1 | Parallel evaluation workers |
| `batch_size` | 10 | Items per batch |
| `result_save.bad` | true | Save items that fail evaluation |
| `result_save.good` | false | Save items that pass evaluation |
| `result_save.merge` | false | Merge all results into single file |

### Evaluator configuration

Each evaluator group has:

| Field | Required | Description |
|---|---|---|
| `fields` | Yes | Maps Dingo fields to dataset columns |
| `evals` | Yes | List of evaluators to apply |
| `evals[].name` | Yes | Evaluator class name |
| `evals[].config` | For LLM | LLM config: `model`, `key`, `api_url` |

### Field mapping

The `fields` object maps Dingo's internal field names to your dataset's column names:

| Dingo field | Description | Used by |
|---|---|---|
| `content` | Main text content to evaluate | Most rule/LLM evaluators |
| `prompt` | Instruction/question field | Instruction quality evaluators |
| `image` | Image path or URL | VLM evaluators |
| `user_input` | User query | RAG evaluators |
| `response` | Model response | RAG evaluators |
| `retrieved_contexts` | Retrieved context list | RAG evaluators |
| `reference` | Ground truth reference | RAG evaluators |

## Available evaluators

### Rule-based (no API key needed)

| Category | Examples |
|---|---|
| Content checks | `RuleContentNull`, `RuleContentShort`, `RuleDocRepeat` |
| Format checks | `RuleColonEnd`, `RuleSpecialCharacter`, `RuleAbnormalChar` |
| Quality checks | `RuleLongWord`, `RuleHighPPL`, `RulePunctuation` |
| PII detection | `RulePII`, `RuleUrl`, `RuleEmail` |
| Language | `RuleChineseChaos`, `RuleChineseTraditional` |

### LLM-based (requires API key)

| Category | Evaluators |
|---|---|
| Text quality | `LLMTextRepeat`, `LLMTextQualityV5` |
| RAG metrics | `Faithfulness`, `ContextPrecision`, `ContextRecall`, `AnswerRelevancy`, `ContextRelevancy` |
| Safety | `LLMSecurityProhibition` |
| 3H evaluation | `LLMText3HHelpful`, `LLMText3HHarmless`, `LLMText3HHonest` |

### Agent-based (requires `pip install "dingo-python[agent]"`)

| Evaluator | Description |
|---|---|
| `ArticleFactChecker` | Autonomous fact-checking with ArXiv/web search tools |

## Output structure

Dingo writes results to an output directory:

```
outputs/<timestamp>/
├── summary.json                    # Overall statistics
└── <field_group>/
    ├── QUALITY_BAD/
    │   ├── RULE_COLON_END.jsonl    # Failed items by metric
    │   └── ...
    └── QUALITY_GOOD/
        └── ...                     # Passed items (if result_save.good=true)
```

### summary.json format

```json
{
  "task_name": "...",
  "total_count": 100,
  "good_count": 85,
  "bad_count": 15,
  "good_ratio": 0.85,
  "metric_detail": {
    "RuleColonEnd": {"count": 5, "ratio": 0.05},
    "RuleSpecialCharacter": {"count": 10, "ratio": 0.1}
  }
}
```

## Environment variables

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | API key for LLM-based evaluation |
| `OPENAI_BASE_URL` | Custom API endpoint (default: `https://api.openai.com/v1`) |
| `OPENAI_MODEL` | Model name (default: `gpt-4`) |

## Supported input formats

| Format | Extension | Description |
|---|---|---|
| JSONL | `.jsonl` | One JSON object per line (recommended) |
| JSON | `.json` | Array of objects or single object |
| CSV | `.csv` | Comma-separated values |
| Plaintext | `.txt` | One item per line |
| Parquet | `.parquet` | Apache Parquet columnar format |

## General rules

When using this skill on behalf of the user:

* **Always write a config file** before running CLI evaluation. Don't try to pass complex JSON inline.
* **Quote file paths** with spaces in commands: `dingo eval --input "my config.json"`
* **Wrap main code in `if __name__ == '__main__':`** when writing Python scripts — Dingo uses multiprocessing internally, which fails on macOS without this guard.
* **Infer format from extension**: `.jsonl` → `jsonl`, `.json` → `json`, `.csv` → `csv`, `.txt` → `plaintext`.
* **Default to rule-based** when the user doesn't specify evaluation type — it's free, fast, and needs no API key.
* **Ask for API key** before using LLM-based evaluators. Never hardcode keys in config files; use `${OPENAI_API_KEY}` placeholder or environment variables.
* **Check field names** in the user's data before writing config. The `fields` mapping must match actual column names in the dataset.

### Choosing evaluators

1. **User wants basic quality checks** → Use rule-based evaluators (e.g., `RuleColonEnd`, `RuleContentNull`, `RuleSpecialCharacter`)
2. **User wants semantic quality assessment** → Use LLM-based evaluators (e.g., `LLMTextQualityV5`, `LLMTextRepeat`)
3. **User wants RAG pipeline evaluation** → Use RAG metrics (`Faithfulness`, `ContextPrecision`, `ContextRecall`, `AnswerRelevancy`). Requires `user_input`, `response`, `retrieved_contexts`, `reference` fields.
4. **User wants fact-checking** → Use `ArticleFactChecker` (requires `dingo-python[agent]` extra)
5. **User wants safety/content moderation** → Use `LLMSecurityProhibition`
6. **User doesn't know what to check** → Start with common rule checks, show the summary, then suggest LLM-based evaluators if needed.

### Post-evaluation guidance

After evaluation completes, the agent should:

1. Read `summary.json` and report the key metrics: total items, good/bad counts, good ratio
2. If there are failures, briefly explain what each failing metric means
3. Suggest next steps (e.g., "15% of items have colon-ending issues — you may want to clean those")

## MCP Server (AI Agent Integration)

Dingo includes a built-in MCP (Model Context Protocol) server, allowing AI agents (Cursor, Claude Desktop, etc.) to invoke Dingo's evaluation tools directly.

### Start the server

```bash
# SSE transport (default, for Cursor / remote agents)
dingo serve

# Custom port
dingo serve --port 9000

# stdio transport (for Claude Desktop / local agent spawn)
dingo serve --transport stdio
```

### Configure your AI agent

**Cursor** (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "dingo": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "dingo": {
      "command": "dingo",
      "args": ["serve", "--transport", "stdio"],
      "env": {
        "OPENAI_API_KEY": "your-key",
        "OPENAI_MODEL": "gpt-4o"
      }
    }
  }
}
```

### Available MCP tools

| Tool | Description |
|------|-------------|
| `run_dingo_evaluation` | Run rule or LLM evaluation on a file |
| `list_dingo_components` | List rule groups, LLM models, prompts |
| `get_rule_details` | Get details about a specific rule |
| `get_llm_details` | Get details about a specific LLM evaluator |
| `get_prompt_details` | Get embedded prompt for an LLM |
| `run_quick_evaluation` | Goal-based evaluation (auto-infer settings) |

For detailed MCP documentation, see: https://github.com/MigoXLab/dingo/blob/main/README_mcp.md

## Troubleshooting

* **`ModuleNotFoundError: No module named 'dingo'`**: Run `pip install dingo-python` (note: the package name is `dingo-python`, not `dingo`)
* **`RuntimeError: An attempt has been made to start a new process...`**: Wrap your code in `if __name__ == '__main__':` — required on macOS due to multiprocessing
* **LLM evaluation returns errors**: Check that `OPENAI_API_KEY` is set and `api_url` is correct
* **Empty results**: Verify `fields` mapping matches your dataset's actual column names
* **RAG metrics all fail**: Ensure your data has all required fields: `user_input`, `response`, `retrieved_contexts`, `reference`

## Notes

* Dingo supports any OpenAI-compatible API (OpenAI, DeepSeek, Anthropic via proxy, local vLLM, etc.)
* Rule-based evaluators run locally with zero API cost
* Results are written to the `outputs/` directory by default (timestamped subdirectories)
* The `content` field is the most commonly mapped field — it's the main text that most evaluators check

## Resources

* **GitHub**: https://github.com/MigoXLab/dingo
* **SaaS Platform**: https://dingo.openxlab.org.cn/
* **PyPI**: https://pypi.org/project/dingo-python/
* **Metrics Documentation**: https://github.com/MigoXLab/dingo/blob/main/docs/metrics.md
* **RAG Evaluation Guide**: https://github.com/MigoXLab/dingo/blob/main/docs/rag_evaluation_en.md
* **Discord**: https://discord.gg/Jhgb2eKWh8

---

## Fact-Checking Articles with ArticleFactChecker

ArticleFactChecker extracts all verifiable claims from an article and verifies each one using ArXiv academic search and web search. It runs as an autonomous agent and produces a structured verification report.

### Prerequisites

```bash
pip install "dingo-python[agent]"
python3 -c "from dingo.config import InputArgs; print('Dingo OK')"
```

Required: `OPENAI_API_KEY`
Optional (recommended for web search): `TAVILY_API_KEY`

### Quick start — use the bundled script

The skill includes `scripts/fact_check.py` which handles all input preparation and configuration automatically:

```bash
python3 {baseDir}/scripts/fact_check.py path/to/article.md
```

Supported input formats: `.md`, `.txt` (auto-wrapped), `.jsonl`, `.json`

Optional arguments:
- `--model MODEL` — LLM model (default: env `OPENAI_MODEL` or `gpt-5.4-mini`)
- `--max-claims N` — claims to extract, 1–200 (default: 50)
- `--max-concurrent N` — parallel verification slots, 1–20 (default: 5)

The script outputs structured JSON to stdout. Parse and present:
- **accuracy_score** (0.0–1.0): fraction of claims verified true
- **false_claims**: list of contradicted claims with evidence
- **all_claims**: full breakdown with TRUE/FALSE/UNVERIFIABLE verdicts

### Manual SDK usage

For direct SDK integration without the script:

```python
import json, os, tempfile
from dingo.config import InputArgs
from dingo.exec import Executor

# IMPORTANT: wrap article into JSONL — plaintext is read line-by-line otherwise
article_text = open("article.md", encoding="utf-8").read()
tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
tmp.write(json.dumps({"content": article_text}, ensure_ascii=False) + "\n")
tmp.close()

config = {
    "input_path": tmp.name,
    "dataset": {"source": "local", "format": "jsonl"},
    "executor": {"max_workers": 1},
    "evaluator": [{
        "fields": {"content": "content"},
        "evals": [{
            "name": "ArticleFactChecker",
            "config": {
                "key": os.environ["OPENAI_API_KEY"],
                "model": os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
                "api_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                "parameters": {
                    "temperature": 0,
                    "agent_config": {
                        "max_concurrent_claims": 5,
                        "max_iterations": 50,
                        "tools": {
                            "claims_extractor": {
                                "api_key": os.environ["OPENAI_API_KEY"],
                                "model": os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
                                "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                                "max_claims": 50
                            },
                            "arxiv_search": {"max_results": 5},
                            **({"tavily_search": {"api_key": os.environ["TAVILY_API_KEY"]}}
                               if os.getenv("TAVILY_API_KEY") else {})
                        }
                    }
                }
            }
        }]
    }]
}

if __name__ == "__main__":
    result = Executor.exec_map["local"](InputArgs(**config)).execute()
    print(f"Score: {result.score:.1f}%  |  Output: {result.output_path}")
    os.unlink(tmp.name)
```

> **Key requirement**: Always use `if __name__ == "__main__":` when running Dingo with multiprocessing — required on macOS, recommended everywhere.

### Interpreting the output

The `summary.json` in the output directory contains overall stats. Detailed per-claim results are in `content/QUALITY_BAD_*.jsonl` (for articles with false claims).

Each result item's `eval_details.content[0]` has:
- `score`: accuracy_score (0.0–1.0, ratio of verified-true claims)
- `reason[0]`: human-readable text summary
- `reason[1]`: full structured report dict with `detailed_findings` and `false_claims_comparison`

For advanced configuration (model selection, claim types, tuning), see [references/advanced-config.md](references/advanced-config.md).
