# Advanced Configuration

## Model Selection

### OpenAI Models (recommended)

| Model | Speed | Quality | Cost (per 1M tokens) | Notes |
|-------|-------|---------|---------------------|-------|
| `gpt-5.4-mini` | Fast | Very Good | $0.75 / $4.50 | **Default**, best balance for fact-checking |
| `gpt-5.4` | Medium | Excellent | $2.50 / $15.00 | Flagship, 33% fewer factual errors vs 5.2 |
| `gpt-5.4-nano` | Very Fast | Good | $0.20 / $1.25 | Budget option for simple claims |
| `o3` | Slow | Best reasoning | $2.00 / $8.00 | Best for complex multi-step verification |
| `o4-mini` | Medium | Good reasoning | $1.10 / $4.40 | Budget reasoning model |

### Alternative Providers (via OPENAI_BASE_URL)

| Model | Provider | Cost (per 1M tokens) | Notes |
|-------|----------|---------------------|-------|
| `deepseek-chat` | DeepSeek | $0.14 / $0.28 | Very cheap, good quality, tool use supported |
| `gemini-2.5-flash` | Google (via proxy) | $0.30 / $2.50 | Fast, 1M context, requires OpenAI-compatible proxy |
| Custom model | Self-hosted | Varies | Set via `OPENAI_BASE_URL` |

Override model: `--model gpt-5.4` or `export OPENAI_MODEL=gpt-5.4`

### Model Selection Guide

- **Quick demo**: `gpt-5.4-nano` or `deepseek-chat` (fastest, cheapest)
- **Standard use**: `gpt-5.4-mini` (default, best balance)
- **High accuracy**: `gpt-5.4` (flagship, fewer factual errors)
- **Complex reasoning**: `o3` (best for institutional/attribution claims)

## Claim Types

ArticleFactChecker recognizes 8 claim types:

| Type | Description | Example |
|------|-------------|---------|
| `factual` | General factual statements | "Python was created in 1991" |
| `statistical` | Numbers, percentages, metrics | "GPT-4 achieves 86.4% on MMLU" |
| `attribution` | Who said/did what | "Elon Musk announced..." |
| `institutional` | Organization affiliations | "Released by Tsinghua University" |
| `temporal` | Dates and timelines | "Launched on December 5, 2024" |
| `comparative` | Comparisons between entities | "Faster than GPT-3.5" |
| `monetary` | Financial figures | "Raised $100M in Series B" |
| `technical` | Technical specs and capabilities | "Supports 128K context window" |

## Tuning Parameters

### `--max-claims N` (default: 50)

Controls how many claims are extracted from the article.

- **10-20**: Quick scan, good for short articles or demos
- **30-50**: Standard, covers most article claims
- **50+**: Thorough, may increase execution time significantly

### `--max-concurrent N` (default: 5)

Controls parallel claim verification.

- **1-3**: Conservative, avoids API rate limits
- **5**: Default balance of speed and reliability
- **10**: Fast but may hit rate limits on some APIs

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | Yes | - | API key for LLM calls |
| `OPENAI_BASE_URL` | No | `https://api.openai.com/v1` | Custom API endpoint |
| `OPENAI_MODEL` | No | `gpt-5.4-mini` | Default model |
| `TAVILY_API_KEY` | No | - | Enables web search verification |

## Output Artifacts

Dingo saves detailed output to `outputs/<timestamp>/`:

| File | Content |
|------|---------|
| `summary.json` | Overall evaluation statistics |
| `content/QUALITY_BAD_*.jsonl` | Per-item results grouped by error type |

ArticleFactChecker also saves intermediate artifacts:

| File | Content |
|------|---------|
| `article_content.md` | Original article text |
| `claims_extracted.jsonl` | Extracted claims (one per line) |
| `claims_verification.jsonl` | Per-claim verification details |
| `verification_report.json` | Full structured verification report |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Dingo SDK not installed" | `pip install -e .` from project root |
| "LangChain not installed" | `pip install -r requirements/agent.txt` |
| Timeout errors | Use `--model gpt-5.4-mini` and `--max-claims 20` |
| Rate limit errors | Reduce `--max-concurrent` to 2-3 |
| Empty results | Check that article has verifiable factual claims |
