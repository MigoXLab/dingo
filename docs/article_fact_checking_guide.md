# Article Fact-Checking Guide

This guide explains how to use the `ArticleFactChecker` agent for comprehensive article fact-checking.

## Overview

The `ArticleFactChecker` is an Agent-First architecture implementation that autonomously:
1. Extracts verifiable claims from long-form articles
2. Selects appropriate verification tools based on claim types
3. Verifies institutional attributions and factual statements
4. Generates structured verification reports with evidence

**Implementation Pattern:** Agent-First (LangChain 1.0 ReAct)

## Quick Start

### Basic Usage (Direct Evaluation)

```python
import os
from dingo.io.input import Data
from dingo.model.llm.agent import ArticleFactChecker

# Set API keys (use environment variables)
os.environ["OPENAI_API_KEY"] = "your-openai-api-key"
os.environ["TAVILY_API_KEY"] = "your-tavily-api-key"  # Optional

# Fact-check article
article_text = """
Your article content here...
"""

data = Data(content=article_text)
result = ArticleFactChecker.eval(data)

# View results
print(f"Accuracy: {result.score:.1%}")
print(f"Issues Found: {result.status}")

# reason[0]: Human-readable text summary (always present)
if result.reason:
    print(result.reason[0] if isinstance(result.reason[0], str) else str(result.reason[0]))

    # reason[1]: Structured report dict (always present after evaluation)
    if len(result.reason) > 1 and isinstance(result.reason[1], dict):
        report = result.reason[1]
        print(f"Report Version: {report.get('report_version', 'N/A')}")
```

### Advanced Usage (Full Configuration)

> **Note**: Executor requires `input_path` pointing to a file. The `plaintext` format reads
> line-by-line, splitting the article into separate Data objects per line. Use `jsonl` format
> instead: `json.dumps` encodes newlines as `\n`, keeping the entire article as one Data object.

```python
import json
import os
import tempfile

from dingo.config import InputArgs
from dingo.exec import Executor

# Read article and convert to JSONL (entire article as one Data object)
with open("article.md", "r") as f:
    article_text = f.read()

temp_jsonl = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8')
temp_jsonl.write(json.dumps({"content": article_text}, ensure_ascii=False) + '\n')
temp_jsonl.close()

# Configure ArticleFactChecker with full options
config = {
    "input_path": temp_jsonl.name,
    "dataset": {"source": "local", "format": "jsonl"},
    "executor": {"max_workers": 1},
    "evaluator": [{
        "fields": {"content": "content"},
        "evals": [{
            "name": "ArticleFactChecker",
            "config": {
                "key": os.getenv("OPENAI_API_KEY"),
                "model": "deepseek-chat",  # or "gpt-4o-mini" for OpenAI
                "agent_config": {
                    "max_iterations": 15,
                    "output_path": "outputs/article_factcheck/",  # Optional: save intermediate artifacts
                    "tools": {
                        "claims_extractor": {
                            "api_key": os.getenv("OPENAI_API_KEY"),
                            "max_claims": 50,
                            "claim_types": [
                                "factual", "statistical", "attribution", "institutional",
                                "temporal", "comparative", "monetary", "technical"
                            ]
                        },
                        "tavily_search": {
                            "api_key": os.getenv("TAVILY_API_KEY")
                        },
                        "arxiv_search": {"max_results": 5}
                    }
                }
            }
        }]
    }]
}

# Execute
input_args = InputArgs(**config)
result = Executor.exec_map["local"](input_args).execute()

print(f"Total: {result.total_count}, Good: {result.good_count}, Bad: {result.bad_count}")

# Cleanup
os.unlink(temp_jsonl.name)
```

### CLI Usage

```bash
# 1. Convert article to JSONL format (entire article as one line)
python -c "
import json
with open('path/to/article.md', 'r') as f:
    text = f.read()
with open('article_input.jsonl', 'w') as f:
    f.write(json.dumps({'content': text}, ensure_ascii=False) + '\n')
"

# 2. Create configuration file
cat > article_check_config.json << EOF
{
  "input_path": "article_input.jsonl",
  "dataset": {
    "source": "local",
    "format": "jsonl"
  },
  "evaluator": [{
    "fields": {"content": "content"},
    "evals": [{
      "name": "ArticleFactChecker",
      "config": {
        "key": "${OPENAI_API_KEY}",
        "model": "deepseek-chat",
        "agent_config": {
          "max_iterations": 15,
          "tools": {
            "claims_extractor": {
              "api_key": "${OPENAI_API_KEY}",
              "max_claims": 50
            },
            "tavily_search": {
              "api_key": "${TAVILY_API_KEY}"
            },
            "arxiv_search": {}
          }
        }
      }
    }]
  }]
}
EOF

# 3. Run fact-checking
dingo eval --input article_check_config.json
```

## Supported Article Types

`ArticleFactChecker` is designed to handle various article types with adaptive verification strategies:

### 1. Academic Articles

**Characteristics:** Research paper announcements, academic news, conference proceedings

**Claim Types:** institutional, attribution, statistical, factual

**Verification Strategy:**
- Use `arxiv_search` for paper metadata (title, authors, abstract)
- Use `tavily_search` for institutional affiliations verification
- Combine both tools for comprehensive verification

**Example:**
```python
academic_article = """
百度刚刚发布的PaddleOCR-VL模型登顶了由清华大学、阿里达摩院等联合发布的OmniDocBench榜单。
"""

data = Data(content=academic_article)
result = ArticleFactChecker.eval(data)
```

**Expected Claims:**
- Attribution: "PaddleOCR-VL released by Baidu"
- Institutional: "OmniDocBench jointly released by Tsinghua and Alibaba DAMO"
- Factual: "PaddleOCR-VL topped OmniDocBench leaderboard"

---

### 2. News Articles

**Characteristics:** Tech news, product launches, current events, announcements

**Claim Types:** temporal, attribution, factual, statistical, monetary

**Verification Strategy:**
- Use `tavily_search` with date filters for temporal claims
- Verify attributions through official announcements
- Cross-check statistics with authoritative sources

**Example:**
```python
news_article = """
OpenAI于2024年12月5日正式发布o1推理模型。CEO Sam Altman表示这是AGI道路上的里程碑。
根据技术报告,o1在数学推理任务上的准确率达到89.3%。ChatGPT Plus月费保持20美元。
"""

data = Data(content=news_article)
result = ArticleFactChecker.eval(data)
```

**Expected Claims:**
- Temporal: "Released on December 5, 2024"
- Attribution: "Sam Altman stated o1 is a milestone"
- Statistical: "89.3% accuracy on math reasoning"
- Monetary: "ChatGPT Plus remains $20/month"

---

### 3. Product Reviews

**Characteristics:** Gadget reviews, product comparisons, specifications

**Claim Types:** technical, comparative, monetary, statistical, factual

**Verification Strategy:**
- Use `tavily_search` for official specifications
- Verify comparative claims with benchmark databases
- Check pricing against official sources

**Example:**
```python
product_review = """
iPhone 15 Pro搭载A17 Pro芯片,采用3纳米工艺。
GPU性能相比A16提升20%。国行128GB版售价7999元。
在Geekbench 6测试中,单核跑分达到2920。
"""

data = Data(content=product_review)
result = ArticleFactChecker.eval(data)
```

**Expected Claims:**
- Technical: "A17 Pro chip with 3nm process"
- Comparative: "GPU improved 20% vs A16"
- Monetary: "128GB priced at 7999 yuan"
- Statistical: "Geekbench single-core: 2920"

---

### 4. Technical Blogs

**Characteristics:** Engineering blogs, tutorials, technical analysis

**Claim Types:** factual, attribution, technical, comparative

**Verification Strategy:**
- Use `tavily_search` for technical documentation
- Verify code examples and API usage
- Cross-check with official docs and benchmarks

**Example:**
```python
tech_blog = """
React 18引入了并发渲染特性,性能提升了3倍。
根据Dan Abramov的博客,新的Suspense API简化了异步数据加载。
"""

data = Data(content=tech_blog)
result = ArticleFactChecker.eval(data)
```

**Expected Claims:**
- Factual: "React 18 introduced concurrent rendering"
- Comparative: "Performance improved 3x"
- Attribution: "Dan Abramov stated Suspense simplifies async loading"

---

### Claim Types Reference

The agent supports **8 claim types** (expanded from original 4):

| Claim Type | Description | Example |
|------------|-------------|---------|
| **factual** | General facts | "The tower is 330 meters tall" |
| **statistical** | Numbers, percentages, metrics | "Model has 0.9B parameters" |
| **attribution** | Who said/did/published what | "Vaswani et al. proposed Transformer" |
| **institutional** | Organizations, affiliations | "Released by MIT and Stanford" |
| **temporal** | Time-related claims | "Released on Dec 5, 2024" |
| **comparative** | Comparisons between entities | "GPU improved 20% vs A16" |
| **monetary** | Financial figures, prices | "Priced at $999" |
| **technical** | Technical specifications | "A17 Pro chip with 3nm process" |

Note: temporal, comparative, monetary, technical types were added in v0.3.0 for multi-type article support

---

## How It Works

### Agent-First Architecture

The `ArticleFactChecker` uses **Agent-First** design with `use_agent_executor = True`:

```
┌─────────────────────────────────────────────────┐
│   ArticleFactChecker (LangChain Agent)          │
│   [Autonomous Decision-Making]                  │
└─────────────────────────────────────────────────┘
           ↓ Autonomous Decision
    ┌──────────────────────────────┐
    │   Available Tools            │
    └──────────────────────────────┘
     ↓         ↓             ↓
┌──────────┐ ┌─────────┐ ┌──────────┐
│claims_   │ │arxiv_   │ │tavily_   │
│extractor │ │search   │ │search    │
└──────────┘ └─────────┘ └──────────┘
```

**Key Advantages:**
- **Intelligent Tool Selection**: Agent chooses tools based on claim semantics
- **Multi-Step Reasoning**: Builds evidence chains across multiple verifications
- **Adaptive Strategies**: Adjusts approach based on intermediate results
- **Fallback Mechanisms**: Tries alternative tools if initial verification fails

### Workflow

**Step 0: Article Type Analysis**
   - Agent first identifies the article type: academic, news, product, blog, policy, opinion
   - This classification guides claim extraction and verification strategy
   - Different article types emphasize different claim types:
     - Academic → institutional, attribution, statistical
     - News → temporal, attribution, factual
     - Product → technical, comparative, monetary
     - Blog → factual, technical, attribution

**Step 1: Claims Extraction**
   - Agent calls `claims_extractor` tool on full article
   - Extracts atomic, verifiable claims with 8 types: factual, statistical, attribution,
     institutional, temporal, comparative, monetary, technical
   - Claims are decontextualized (stand-alone) for independent verification

**Step 2: Autonomous Tool Selection**
   - Agent analyzes each claim type and article context
   - Selects best verification tool based on principles (not rigid IF-THEN rules):
     - **Academic papers** → `arxiv_search` (metadata) + `tavily_search` (institutions)
     - **Institutional/organizational claims** → `tavily_search` (primary)
     - **Current events/news** → `tavily_search` with date filters
     - **Product specs/pricing** → `tavily_search` for official sources
     - **Technical documentation** → `tavily_search` for docs
   - **Adaptive Strategy:** Combines tools, uses fallbacks, cross-verifies with multiple sources

3. **Verification**
   - Agent calls selected tools to verify each claim
   - Collects evidence and sources
   - Adapts if initial verification fails

4. **Report Generation**
   - Synthesizes verification results
   - Generates structured report with:
     - Summary statistics
     - False claims comparison table
     - Evidence and sources
     - Severity ratings

## Claim Types

### Institutional Claims

Claims about organizational affiliations:

```
Example: "OmniDocBench was released by Tsinghua University"

Agent Decision:
1. Recognizes institutional claim
2. Checks if paper mentioned → Yes (OmniDocBench)
3. Selects arxiv_search tool
4. Searches for paper metadata and author affiliations
5. Compares claimed vs actual institutions via LLM reasoning
```

### Statistical Claims

Claims with numbers or percentages:

```
Example: "The model has 0.9B parameters"

Agent Decision:
1. Recognizes statistical claim
2. Selects tavily_search for general verification
3. Searches for official sources
4. Verifies number accuracy
```

### Factual Claims

General factual statements:

```
Example: "PaddleOCR-VL topped the OmniDocBench leaderboard"

Agent Decision:
1. Recognizes factual claim
2. Selects tavily_search
3. Searches for leaderboard information
4. Verifies ranking claim
```

## Configuration

### Agent Configuration

```python
{
  "agent_config": {
    "max_iterations": 15,       # Maximum reasoning steps

    # Artifact output path (three options, evaluated in priority order):
    # 1. "output_path": "path/to/dir"  → use explicit path (backward-compatible)
    # 2. "save_artifacts": false        → disable artifact saving entirely
    # 3. (default)                      → auto-generate outputs/article_factcheck_<timestamp>_<uuid>/
    #    Override base dir with "base_output_path": "custom/base/"

    "tools": {
      "claims_extractor": {
        "api_key": "...",
        "max_claims": 50,           # Max claims to extract
        "claim_types": [            # Types to extract
          "factual",
          "statistical",
          "attribution",
          "institutional"
        ],
        "chunk_size": 2000,         # Text chunk size
        "include_context": true,    # Include surrounding context
        "temperature": 0.1          # LLM temperature
      },
      "arxiv_search": {
        "max_results": 5,           # Max search results
        "sort_by": "relevance",
        "rate_limit_delay": 3.0     # Delay between requests
      },
      "tavily_search": {
        "api_key": "...",
        "max_results": 5,
        "search_depth": "advanced"  # or "basic"
      }
    },
    "max_concurrent_claims": 5       # Max parallel claim verifications (asyncio Semaphore)
  }
}
```

### Output Format

The `EvalDetail` returned by `ArticleFactChecker` uses a **dual-layer reason** structure:

- `reason[0]`: Human-readable text summary (always present, `str`)
- `reason[1]`: Structured report dictionary (always present after evaluation, `dict`)

```python
{
  "metric": "ArticleFactChecker",
  "status": true,  # true = issues found, false = all good
  "score": 0.75,   # Overall accuracy (0.0-1.0)
  "label": ["QUALITY_BAD_ARTICLE_FACTUAL_ERROR"],  # or QUALITY_BAD_ARTICLE_UNVERIFIED_CLAIMS / QUALITY_GOOD
  "reason": [
    # reason[0]: Human-readable text summary (str)
    "Article Fact-Checking Report\n"
    "======================================================================\n"
    "Total Claims Analyzed: 20\n"
    "Verified Claims: 15\n"
    "False Claims: 5\n"
    "Unverifiable Claims: 0\n"
    "Overall Accuracy: 75.0%\n"
    "\n"
    "Agent Performance:\n"
    "   Tool Calls: 8\n"
    "   Reasoning Steps: 10\n"
    "\n"
    "FALSE CLAIMS DETAILED COMPARISON:\n"
    "======================================================================\n"
    "\n"
    "#1 FALSE CLAIM\n"
    "   Article Claimed:\n"
    "      OmniDocBench was released by Tsinghua University...\n"
    "   Actual Truth:\n"
    "      OmniDocBench was released by Shanghai AI Lab, Abaka AI, 2077AI\n"
    "   Evidence:\n"
    "      Verified via arXiv paper 2412.07626 author list",

    # reason[1]: Structured report dict (always present)
    {
      "report_version": "2.0",
      "generated_at": "2026-02-06T15:30:00",
      "article_info": {"content_source": "markdown", "content_length": 5432},
      "claims_extraction": {
        "total_extracted": 20,
        "verifiable": 18,
        "claim_types_distribution": {"factual": 5, "institutional": 3, "...": "..."}
      },
      "verification_summary": {
        "total_verified": 20,
        "verified_true": 15,
        "verified_false": 5,
        "unverifiable": 0,
        "accuracy_score": 0.75
      },
      "detailed_findings": ["..."],
      "false_claims_comparison": ["..."],
      "agent_metadata": {
        "model": "deepseek-chat",
        "tool_calls_count": 8,
        "reasoning_steps": 10,
        "execution_time_seconds": 45.2
      }
    }
  ]
}
```

### Output Files

ArticleFactChecker auto-saves intermediate artifacts to a timestamped directory by default.

**Dingo standard output** (saved to executor output_path):

Default mode (`merge=false`, the default):
- `summary.json` - Aggregated statistics
- `content/<LABEL>.jsonl` - Results grouped by quality label

Merge mode (`executor.result_save.merge=true`):
- `all_results.jsonl` - All EvalDetail records in single file
- `summary.json` - Aggregated statistics

**Intermediate artifacts** (auto-saved by default; path: `outputs/article_factcheck_<timestamp>_<uuid>/`):
```
{output_path}/
  |-- article_content.md           # Original Markdown article
  |-- claims_extracted.jsonl       # Extracted claims (from claims_extractor tool or agent reasoning fallback)
  |-- claims_verification.jsonl    # Per-claim verification details
  +-- verification_report.json     # Full structured report (v2.0)
```

#### claims_extracted.jsonl format

Each line contains one extracted claim:
```json
{"claim_id":"claim_001","claim":"OmniDocBench was jointly released by Tsinghua University","claim_type":"institutional","confidence":0.95,"verifiable":true,"context":"..."}
```

#### claims_verification.jsonl format

Each line contains a complete verification record:
```json
{"claim_id":"claim_001","original_claim":"...","claim_type":"institutional","confidence":0.95,"verification_result":"FALSE","evidence":"...","sources":["https://arxiv.org/abs/2412.07626"],"verification_method":"arxiv_search","search_queries_used":["OmniDocBench"],"reasoning":"..."}
```

## Real-World Example

### Case Study: OmniDocBench Attribution Error

**Article Claim:**
> "它经清华大学、阿里达摩院、上海人工智能实验室等联合发布"
>
> Translation: "It was jointly released by Tsinghua University, Alibaba DAMO Academy, Shanghai AI Laboratory"

**Agent Workflow:**

1. **Claim Extraction**
   ```
   Extracted: "OmniDocBench was jointly released by Tsinghua University,
               Alibaba DAMO Academy, Shanghai AI Laboratory"
   Type: institutional
   ```

2. **Tool Selection**
   ```
   Agent Analysis: This is an institutional affiliation claim
   Decision: Use arxiv_search to verify author institutions
   Reasoning: Academic paper mentioned, can verify via arXiv
   ```

3. **Verification**
   ```
   Tool: arxiv_search
   Query: "OmniDocBench 2412.07626"

   Paper Found: arXiv:2412.07626
   Authors/Affiliations from arXiv metadata:
   - Shanghai AI Laboratory ✅
   - Abaka AI
   - 2077AI

   LLM Reasoning:
   - 清华大学 (Tsinghua): ❌ NOT found in paper metadata
   - 阿里达摩院 (Alibaba DAMO): ❌ NOT found in paper metadata
   - 上海人工智能实验室 (Shanghai AI Lab): ✅ VERIFIED
   ```

4. **Report**
   ```
   FALSE CLAIM DETECTED:

   Article Claimed: Released by Tsinghua, Alibaba DAMO, Shanghai AI Lab
   Actual Truth: Released ONLY by Shanghai AI Lab, Abaka AI, 2077AI
   Evidence: arXiv:2412.07626 author list verification
   ```

## Best Practices

### 1. Choose Appropriate max_iterations

```python
# For short articles (<1000 words):
"max_iterations": 10

# For long articles (>2000 words):
"max_iterations": 15-20

# For comprehensive verification:
"max_iterations": 25-30
```

### 2. Configure Claim Types Based on Content

```python
# Technical/Academic articles:
"claim_types": ["factual", "institutional", "attribution", "statistical"]

# News articles:
"claim_types": ["factual", "attribution", "statistical"]

# Product announcements:
"claim_types": ["factual", "statistical"]
```

### 3. Use Both Search Tools

```python
# Recommended: Enable both for comprehensive coverage
"tools": {
    "arxiv_search": {},        # Academic verification
    "tavily_search": {         # General web search
        "api_key": "..."
    }
}
```

### 4. Monitor Agent Performance

```python
result = ArticleFactChecker.eval(data)

# Check agent metrics via structured report (reason[1])
if len(result.reason) > 1 and isinstance(result.reason[1], dict):
    report = result.reason[1]
    meta = report.get('agent_metadata', {})
    print(f"Tool Calls: {meta.get('tool_calls_count', 'N/A')}")
    print(f"Reasoning Steps: {meta.get('reasoning_steps', 'N/A')}")
    print(f"Execution Time: {meta.get('execution_time_seconds', 'N/A')}s")

    v_summary = report.get('verification_summary', {})
    print(f"Verified True: {v_summary.get('verified_true', 'N/A')}")
    print(f"Verified False: {v_summary.get('verified_false', 'N/A')}")
else:
    # Fallback: parse from text summary (reason[0])
    reason_text = result.reason[0] if result.reason else ''
    import re
    match = re.search(r'Tool Calls: (\d+)', reason_text)
    if match:
        print(f"Agent made {match.group(1)} tool calls")
```

## Troubleshooting

### Issue: Agent Exceeds max_iterations

**Symptom:** Error message "Agent returned empty output"

**Solutions:**
1. Increase `max_iterations`
2. Reduce article length
3. Reduce `max_claims` in claims_extractor

### Issue: Missing Institutional Claims

**Symptom:** Agent doesn't detect institutional misattributions

**Solutions:**
1. Verify `claim_types` includes "institutional"
2. Increase `max_claims`
3. For academic papers: Use `arxiv_search` for paper metadata + `tavily_search` for institution verification
4. The agent will combine tools automatically for comprehensive verification

### Issue: API Rate Limits

**Symptom:** "Rate limit exceeded" errors

**Solutions:**
1. Increase `rate_limit_delay` for arxiv_search (default: 3.0s)
2. Process articles in smaller batches
3. Use caching if available
4. `tavily_search` has built-in retry logic with exponential backoff (default: 3 retries)

### Issue: Network Errors / Timeouts

**Symptom:** "Network connection error" or "timeout" messages

**Solutions:**
1. `tavily_search` automatically retries transient errors (timeout, network, 5xx)
2. Configure `max_retries` (default: 3) and `retry_base_delay` (default: 1.0s)
3. Non-retryable errors (authentication, rate limit) fail immediately

## Testing

### Unit Tests

```bash
# Test claims extractor (requires OPENAI_API_KEY)
pytest test/scripts/model/llm/agent/tools/test_claims_extractor.py -v

# Test arXiv search tool
pytest test/scripts/model/llm/agent/tools/test_arxiv_search.py -v

# Test Tavily search tool (includes retry logic tests)
pytest test/scripts/model/llm/agent/tools/test_tavily_search.py -v
```

### Integration Tests

```bash
# Test full article fact-checking (requires API keys)
pytest test/scripts/model/llm/agent/test_article_fact_checker.py -v -s

# Run specific test
pytest test/scripts/model/llm/agent/test_article_fact_checker.py::TestArticleFactChecker::test_real_blog_article_fact_check -v -s
```

### Example Script

```bash
# Run example
python examples/agent/agent_article_fact_checking_example.py
```

## API Reference

### ArticleFactChecker

**Class:** `dingo.model.llm.agent.ArticleFactChecker`

**Attributes:**
- `use_agent_executor`: `True` (Agent-First mode)
- `available_tools`: `["claims_extractor", "arxiv_search", "tavily_search"]`
- `max_iterations`: `10` (default)

**Methods:**
- `eval(input_data: Data) -> EvalDetail`: Main evaluation method

### ClaimsExtractor

**Class:** `dingo.model.llm.agent.tools.ClaimsExtractor`

**Methods:**
- `execute(text: str, claim_types: List[str] = None, **kwargs) -> Dict`

**Returns:**
```python
{
    'success': bool,
    'claims': List[{
        'claim_id': str,
        'claim': str,
        'claim_type': str,
        'context': str,
        'verifiable': bool,
        'confidence': float
    }],
    'metadata': Dict
}
```

### ArxivSearch

**Class:** `dingo.model.llm.agent.tools.ArxivSearch`

**Methods:**
- `execute(query: str, search_type: str = "auto", **kwargs) -> Dict`

**Parameters:**
- `query`: Search query (arXiv ID, DOI, title, or keywords)
- `search_type`: `"auto"`, `"id"`, `"doi"`, `"title"`, or `"author"`

**Returns:**
```python
{
    'success': bool,
    'query': str,
    'search_type': str,  # Detected type
    'results': List[{
        'arxiv_id': str,
        'title': str,
        'authors': List[str],
        'summary': str,
        'published': str,
        'pdf_url': str,
        'doi': str
    }],
    'count': int
}
```

**Note:** For institutional verification, use `arxiv_search` to get paper metadata,
then use `tavily_search` to verify institutional affiliations via web search.

### TavilySearch

**Class:** `dingo.model.llm.agent.tools.TavilySearch`

**Methods:**
- `execute(query: str, **kwargs) -> Dict`

**Configuration:**
```python
{
    'api_key': str,          # Required
    'max_results': int,      # Default: 5
    'search_depth': str,     # "basic" or "advanced"
    'max_retries': int,      # Default: 3 (for transient errors)
    'retry_base_delay': float  # Default: 1.0 seconds
}
```

**Retry Behavior:**
- Automatically retries on timeout, network, and 5xx errors
- Does NOT retry on authentication or rate limit errors
- Uses exponential backoff: delay = base_delay * (2 ^ attempt)

## Further Reading

- [Agent Development Guide](./agent_development_guide.md)
- [Fact-Checking Guide](./factcheck_guide.md)
- [Agent Architecture Documentation](./agent_architecture.md)
