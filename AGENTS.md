# Dingo — Agent Instructions

## Project Overview

Dingo is a comprehensive AI data quality evaluation tool for ML practitioners, data engineers, and AI researchers. It systematically assesses training data, fine-tuning datasets, and production AI systems using rule-based, LLM-based, and agent-based evaluation methods.

**Repository**: https://github.com/MigoXLab/dingo
**PyPI**: `pip install dingo-python`
**License**: Apache 2.0

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.10+ |
| Data Models | Pydantic (BaseModel, extra="allow") |
| LLM Integration | OpenAI SDK (supports any compatible API) |
| MCP Server | FastMCP + SSE transport |
| Distributed | PySpark (optional) |

## Directory Structure

```
dingo/
├── AGENTS.md                ← this file (agent instructions)
├── setup.py                 ← package config (extras_require for optional deps)
├── mcp_server.py            ← MCP server entry point (legacy, use `dingo serve` instead)
├── requirements/
│   ├── runtime.txt          ← core dependencies (minimal)
│   ├── datasource.txt       ← optional datasource deps (S3, SQL, Parquet, etc.)
│   ├── optional.txt         ← heavy optional deps (torch, pyspark, etc.)
│   └── agent.txt            ← agent evaluation deps (langchain, tavily)
│
├── SKILL.md                 ← AI agent skill definition (symlink → clawhub/SKILL.md)
├── dingo/                   ← core Python package
│   ├── config/
│   │   └── input_args.py    ← InputArgs, EvalPiplineConfig, EvaluatorGroupConfig
│   ├── io/
│   │   ├── input/data.py    ← Data model (Pydantic, extra="allow")
│   │   └── output/          ← ResultInfo, EvalDetail, SummaryModel (+ cross-layer analysis)
│   ├── data/
│   │   ├── datasource/      ← LocalDataSource, SQLDataSource, S3DataSource, HFDataSource
│   │   ├── dataset/         ← Dataset implementations per source
│   │   └── converter/       ← Format converters (JSON, JSONL, CSV, Parquet, etc.)
│   ├── model/
│   │   ├── model.py         ← Model registry (rule_register, llm_register)
│   │   ├── rule/            ← Rule-based evaluators (80+ built-in)
│   │   │   ├── base.py      ← BaseRule
│   │   │   ├── rule_common.py ← Common rules (text quality, format, PII, etc.)
│   │   │   └── utils/       ← Shared utilities (normalize, ngrams, etc.)
│   │   └── llm/             ← LLM-based evaluators
│   │       ├── base_openai.py ← BaseOpenAI (base class for all LLM evaluators)
│   │       ├── text_quality/  ← Text quality evaluators (V4, V5)
│   │       ├── rag/          ← RAG metrics (Faithfulness, Precision, Recall, etc.)
│   │       ├── hhh/          ← 3H evaluators (Honest, Helpful, Harmless)
│   │       ├── compare/      ← Document comparison evaluators
│   │       └── agent/        ← Agent-based evaluators
│   │           ├── base_agent.py  ← BaseAgent
│   │           ├── tools/         ← Tool registry + implementations
│   │           ├── agent_fact_check.py
│   │           └── agent_hallucination.py
│   ├── exec/
│   │   ├── local.py         ← LocalExecutor (single machine, cross-layer conflict detection)
│   │   └── spark.py         ← SparkExecutor (distributed)
│   └── run/
│       └── cli.py           ← CLI entry point (subcommands: eval, info)
│
├── examples/                ← Usage examples (SDK, CLI, various scenarios)
├── test/                    ← Test suite
│   ├── data/                ← Test data files
│   ├── env/                 ← Test environment configs
│   └── scripts/             ← Test scripts (pytest)
└── docs/                    ← Documentation
```

## Core Concepts

### Data Flow

```
Data Input → Interface (SDK/CLI/MCP) → Datasource → Dataset → Converter → Evaluator → Executor → Report
```

### Registration System

All evaluators use decorator-based registration:

```python
# Rule evaluator
@Model.rule_register('QUALITY_BAD_COMPLETENESS', ['default', 'pretrain'])
class MyRule(BaseRule):
    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail: ...

# LLM evaluator
@Model.llm_register('MyLLMEvaluator')
class MyLLMEvaluator(BaseOpenAI):
    prompt = "..."
    @classmethod
    def build_messages(cls, input_data: Data) -> List: ...

# Agent evaluator
@Model.llm_register('MyAgent')
class MyAgent(BaseAgent):
    available_tools = ["tavily_search"]
    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail: ...
```

### Data Model

`Data` uses `extra = "allow"` — any field can be set dynamically:

```python
class Data(BaseModel):
    class Config:
        extra = "allow"
```

Common fields: `data_id`, `prompt`, `content`, `image`, `context`, `raw_data`, `reference`, `user_input`, `response`, `retrieved_contexts`.

### InputArgs Configuration

```python
input_data = {
    "input_path": "data.jsonl",
    "dataset": {"source": "local", "format": "jsonl"},
    "executor": {"max_workers": 4, "batch_size": 10, "result_save": {"bad": True, "good": True}},
    "evaluator": [
        {
            "fields": {"content": "text_field", "prompt": "question_field"},
            "evals": [
                {"name": "RuleAbnormalChar"},
                {"name": "LLMTextQualityV5", "config": {"key": "...", "model": "gpt-4o", "api_url": "..."}}
            ]
        }
    ]
}
```

### Execution Modes

| Mode | Class | Use Case |
|------|-------|----------|
| Local | `Executor.exec_map["local"]` | Development, < 100K rows |
| Spark | `Executor.exec_map["spark"]` | Production, > 1M rows |

### Optional Dependencies (extras_require)

```bash
pip install dingo-python                # Core (includes all datasource support)
pip install "dingo-python[hhem]"        # + HHEM hallucination detection (transformers + torch)
pip install "dingo-python[agent]"       # + Agent-based evaluation (langchain)
pip install "dingo-python[all]"         # + Everything
```

## Development Conventions

### General

- Python 3.10+ required
- Code comments in English or Chinese (both acceptable)
- All evaluators must return `EvalDetail` with `metric`, `status`, `label`, `reason`
- Use lazy imports for optional heavy dependencies (torch, transformers, pyarrow, etc.)
- Never hardcode API keys; use environment variables or config parameters

### Adding a New Rule Evaluator

1. Create class in `dingo/model/rule/rule_common.py` (or a new file under `dingo/model/rule/`)
2. Inherit from `BaseRule`
3. Decorate with `@Model.rule_register(metric_type, groups)`
4. Implement `eval(cls, input_data: Data) -> EvalDetail` as classmethod
5. Set `_required_fields` to declare needed input fields

### Adding a New LLM Evaluator

1. Create class in `dingo/model/llm/` (appropriate subdirectory)
2. Inherit from `BaseOpenAI`
3. Decorate with `@Model.llm_register('EvaluatorName')`
4. Set `prompt` attribute or override `build_messages()`
5. Override `parse_result()` if custom response parsing needed

### Adding a New Datasource

1. Create datasource class in `dingo/data/datasource/`
2. Create dataset class in `dingo/data/dataset/`
3. Register in the respective `__init__.py`
4. Use lazy imports if new dependencies required
5. Add dependency to `requirements/runtime.txt` (core) or `setup.py` extras (heavy/optional)

### Testing

```bash
# Run all tests
pytest test/scripts --ignore=test/scripts/data

# Run specific test
pytest test/scripts/model/llm/test_rag.py -v

# Integration tests (CLI)
dingo eval --input .github/env/local_plaintext.json
dingo eval --input .github/env/local_json.json --json
```

### CLI Reference

Dingo provides a `dingo` CLI command (installed via `pip install dingo-python`):

```bash
# Run evaluation (primary command)
dingo eval --input config.json            # Human-readable output
dingo eval --input config.json --json     # JSON output (for agents/automation)

# List available evaluators, groups
dingo info                                # Show all (rules, LLM, groups)
dingo info --rules                        # Rule evaluators only
dingo info --llm                          # LLM evaluators only
dingo info --groups                       # Rule groups only
dingo info --json                         # JSON output

# Start MCP server (for AI agent integration)
dingo serve                               # SSE transport on 0.0.0.0:8000
dingo serve --port 9000                   # Custom port
dingo serve --transport stdio             # stdio transport (for local agent)

# Backward compatibility (no subcommand)
dingo --input config.json                 # Same as `dingo eval --input config.json`
python -m dingo.run.cli --input config.json
```


### Version Conventions

- Version defined in `setup.py` (`version="2.0.0"`)
- Follow semantic versioning (MAJOR.MINOR.PATCH)

## MCP Server

Start via CLI: `dingo serve` (SSE default) or `dingo serve --transport stdio`
Legacy entry point: `mcp_server.py`
Framework: FastMCP

### Available MCP Tools

| Tool | Purpose |
|------|---------|
| `run_dingo_evaluation` | Run rule or LLM evaluation on a file |
| `list_dingo_components` | List rule groups, LLM models, prompts |
| `get_rule_details` | Get details about a specific rule |
| `get_llm_details` | Get details about a specific LLM evaluator |
| `get_prompt_details` | Get embedded prompt for an LLM |
| `run_quick_evaluation` | Goal-based evaluation (auto-infer settings) |

### MCP Environment Variables

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | OpenAI API key for LLM evaluation |
| `OPENAI_BASE_URL` | Custom API base URL |
| `OPENAI_MODEL` | Model name (default: gpt-4) |
| `DEFAULT_OUTPUT_DIR` | Default output directory |
| `LOG_LEVEL` | Logging level (default: info) |

## Config Maintenance Rules

When these events occur, update the corresponding files:

| Event | Update |
|-------|--------|
| New evaluator added | Ensure registration decorator is correct; update `docs/metrics.md` |
| New datasource added | Update `requirements/runtime.txt`, `setup.py` extras if heavy, README install section |
| New dependency added | Decide: `runtime.txt` (core) vs `setup.py` extras (heavy/optional); use lazy import for optional |
| New MCP tool added | Update MCP Tools table in this file |
| New CLI subcommand added | Update CLI Reference section in this file |
| Directory structure change | Update this file |
| Version bump | Update `setup.py` version field |

After completing a feature, check if any of the above need updating.
