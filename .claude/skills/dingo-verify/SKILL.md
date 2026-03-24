---
name: dingo-verify
description: >
  Use when the user wants to fact-check an article or verify factual claims
  in a document. Triggers on: "fact-check", "verify article", "check facts",
  "文章事实核查", "验证文章". Runs Dingo's ArticleFactChecker via SDK
  to extract and verify all factual claims with web search evidence.
argument-hint: [article-path]
allowed-tools: Bash Read Glob
---

# Dingo Article Fact-Checker

Verify factual claims in articles using Dingo's ArticleFactChecker agent.

## Prerequisites

Before running, verify:
1. Dingo is installed: `python -c "from dingo.config import InputArgs; print('OK')"`
2. `OPENAI_API_KEY` is set (required)
3. `TAVILY_API_KEY` is set (optional, enables web search verification)

If prerequisites fail, help the user fix them:
- Missing dingo: `pip install -e .` (from project root) or `pip install dingo-python`
- Missing LangChain: `pip install -r requirements/agent.txt`
- Missing API key: `export OPENAI_API_KEY='your-key'`

## Usage

Run the fact-check script with the article path:

```bash
python ${CLAUDE_SKILL_DIR}/scripts/fact_check.py $ARGUMENTS
```

### Optional arguments

- `--model MODEL`: Override LLM model (default: env `OPENAI_MODEL` or `gpt-5.4-mini`)
- `--max-claims N`: Max claims to extract (default: 50, reduce for faster runs)
- `--max-concurrent N`: Parallel verification slots (default: 5)

### Supported file formats

- `.md`, `.txt`: Markdown/plaintext articles (auto-wrapped for Dingo)
- `.jsonl`: JSONL with `{"content": "..."}` per line
- `.json`: JSON array format

## Presenting Results

The script outputs JSON to stdout. Parse it and present to the user:

### Success output

Present a formatted report with these sections:

1. **Summary**: total claims, accuracy score, false/unverifiable counts
2. **False Claims Table**: if any false claims found, show claim vs truth vs evidence
3. **All Claims Overview**: list all claims with their verdicts (TRUE/FALSE/UNVERIFIABLE)
4. **Output Path**: where the full Dingo report is saved

Example presentation:

```
## Article Fact-Check Report

**Accuracy**: 73.3% (11/15 claims verified true)
- Verified True: 11
- Verified False: 2
- Unverifiable: 2

### False Claims Found

| # | Article Claimed | Actual Truth | Evidence |
|---|----------------|-------------|----------|
| 1 | "released in Nov 2024" | Released Dec 5, 2024 | Official announcement |

### Full Report
Saved to: outputs/20260318_143022_abc123/
```

### Error output

If the script exits with code 1, it prints error JSON to stderr.
Read the `error` and `hint` fields and help the user resolve the issue.

## Performance Notes

- Single article: typically 2-5 minutes depending on claim count and model speed
- Progress is printed to stderr during execution
- For faster runs: use `--max-claims 10 --model gpt-5.4-mini`

## Advanced Configuration

For model selection, claim types, and tuning options, see:
[references/advanced-config.md](references/advanced-config.md)
