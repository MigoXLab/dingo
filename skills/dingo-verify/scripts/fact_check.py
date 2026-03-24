#!/usr/bin/env python3
"""
Dingo ArticleFactChecker SDK wrapper for dingo-verify skill.

Usage:
    python fact_check.py <article_path> [--model MODEL] [--max-claims N] [--max-concurrent N]

Environment Variables:
    OPENAI_API_KEY (required): API key for LLM calls
    OPENAI_BASE_URL (optional): Custom API endpoint
    TAVILY_API_KEY (optional): For web search verification
    OPENAI_MODEL (optional): Default model name
"""

import argparse
import json
import os
import pathlib
import sys
import tempfile
import time
from typing import Any, Dict, NoReturn, Optional, Tuple

# --- Pure helper functions (no Dingo imports, testable standalone) ---

_ALLOWED_EXTENSIONS: frozenset[str] = frozenset({'.md', '.txt', '.jsonl', '.json'})
_BLOCKED_PATH_PREFIXES: Tuple[str, ...] = ('/proc/', '/sys/', '/dev/')
MAX_ARTICLE_BYTES: int = 10 * 1024 * 1024  # 10 MB


def validate_article_path(path: str) -> str:
    """
    Resolve and validate article path against traversal and special filesystem attacks.

    Args:
        path: User-supplied article file path

    Returns:
        Resolved absolute path string

    Raises:
        ValueError: If path targets a special filesystem, symlink, or unsupported format
    """
    p = pathlib.Path(path)
    resolved = p.resolve()
    path_str = str(resolved)

    if any(path_str.startswith(prefix) for prefix in _BLOCKED_PATH_PREFIXES):
        raise ValueError(f"Refusing to read from special filesystem path: {path_str}")

    if p.is_symlink():
        raise ValueError(f"Refusing to follow symlink: {path}")

    ext = resolved.suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        allowed = ', '.join(sorted(_ALLOWED_EXTENSIONS))
        raise ValueError(f"Unsupported file type: {ext!r}. Supported: {allowed}")

    return path_str


def detect_format(path: str) -> Tuple[str, bool]:
    """
    Detect file format from extension and whether it needs JSONL wrapping.

    Returns:
        (format_name, needs_wrapping) tuple
    """
    ext = os.path.splitext(path)[1].lower()
    format_map = {
        '.jsonl': ('jsonl', False),
        '.json': ('json', False),
        '.md': ('plaintext', True),
        '.txt': ('plaintext', True),
    }
    return format_map.get(ext, ('plaintext', True))


def wrap_plaintext(path: str) -> str:
    """
    Wrap a plaintext/markdown file into a single-line JSONL file.

    Dingo's plaintext format reads line-by-line, creating one Data object per line.
    To treat the entire file as one article, wrap it into a JSONL with one record.

    Args:
        path: Path to the source file

    Returns:
        Path to the temporary JSONL file (caller must clean up)

    Raises:
        ValueError: If the file is empty or too large
    """
    size = os.path.getsize(path)
    if size > MAX_ARTICLE_BYTES:
        raise ValueError(
            f"Article file too large: {size / 1024 / 1024:.1f} MB "
            f"(limit: {MAX_ARTICLE_BYTES // 1024 // 1024} MB)"
        )

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    if not content.strip():
        raise ValueError(f"Article file is empty: {path}")

    # NamedTemporaryFile: uses O_CREAT|O_EXCL (atomic), mode 0o600 (private), full-entropy name
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.jsonl', prefix='dingo_verify_',
        encoding='utf-8', delete=False
    ) as tmp:
        tmp.write(json.dumps({"content": content}, ensure_ascii=False) + '\n')
        return tmp.name


def build_config(
    input_path: str,
    data_format: str,
    model: str,
    api_key: str,
    api_url: str,
    tavily_key: Optional[str],
    max_claims: int,
    max_concurrent: int,
) -> Dict[str, Any]:
    """
    Build Dingo InputArgs configuration dict for ArticleFactChecker.

    Args:
        input_path: Path to input file (original or temp JSONL)
        data_format: Dingo format string ("jsonl", "json", etc.)
        model: LLM model name
        api_key: OpenAI-compatible API key
        api_url: API base URL
        tavily_key: Tavily API key (None to omit tavily_search)
        max_claims: Max claims to extract
        max_concurrent: Max parallel verification slots

    Returns:
        Configuration dict compatible with InputArgs(**config)
    """
    tools_config: Dict[str, Any] = {
        "claims_extractor": {
            "api_key": api_key,
            "model": model,
            "base_url": api_url,
            "max_claims": max_claims,
        },
        "arxiv_search": {"max_results": 5, "fetch_affiliations": True},
    }
    if tavily_key:
        tools_config["tavily_search"] = {"api_key": tavily_key}

    return {
        "input_path": input_path,
        "dataset": {"source": "local", "format": data_format},
        "executor": {"max_workers": 1},
        "evaluator": [{
            "fields": {"content": "content"},
            "evals": [{
                "name": "ArticleFactChecker",
                "config": {
                    "key": api_key,
                    "model": model,
                    "api_url": api_url,
                    "parameters": {
                        "temperature": 0,
                        "agent_config": {
                            "max_concurrent_claims": max_concurrent,
                            "max_iterations": 50,
                            "tools": tools_config,
                        }
                    }
                }
            }]
        }]
    }


def build_report(
    summary_dict: Dict[str, Any],
    detail_report: Optional[Dict[str, Any]],
    duration: float,
) -> Dict[str, Any]:
    """
    Build the final JSON report from SummaryModel data and EvalDetail.reason[1].

    Args:
        summary_dict: SummaryModel fields (total, num_good, num_bad, score, output_path)
        detail_report: Structured report from EvalDetail.reason[1], or None
        duration: Execution time in seconds

    Returns:
        Structured report dict for JSON output
    """
    report: Dict[str, Any] = {
        "success": True,
        "summary": {
            "total_items": summary_dict.get("total", 0),
            "dingo_score": summary_dict.get("score", 0.0),
            "num_good": summary_dict.get("num_good", 0),
            "num_bad": summary_dict.get("num_bad", 0),
        },
        "verification": {},
        "false_claims": [],
        "all_claims": [],
        "output_path": summary_dict.get("output_path", ""),
        "duration_seconds": duration,
    }

    if detail_report:
        vs = detail_report.get("verification_summary", {})
        report["verification"] = {
            "total_claims": vs.get("total_verified", 0),
            "verified_true": vs.get("verified_true", 0),
            "verified_false": vs.get("verified_false", 0),
            "unverifiable": vs.get("unverifiable", 0),
            "accuracy_score": vs.get("accuracy_score", 0.0),
        }

        for fc in detail_report.get("false_claims_comparison", []):
            report["false_claims"].append({
                "claim": fc.get("article_claimed", ""),
                # actual_truth may be absent in async eval path; fall back to evidence
                "truth": fc.get("actual_truth") or fc.get("evidence", ""),
                "evidence": fc.get("evidence", ""),
            })

        for finding in detail_report.get("detailed_findings", []):
            report["all_claims"].append({
                "claim_id": finding.get("claim_id", ""),
                "original_claim": finding.get("original_claim", ""),
                "claim_type": finding.get("claim_type", ""),
                "verification_result": finding.get("verification_result", "UNVERIFIABLE"),
                "evidence": finding.get("evidence", ""),
                "sources": finding.get("sources", []),
            })

    return report


def error_exit(error: str, hint: str = "") -> NoReturn:
    """Print error JSON to stderr and exit with code 1."""
    msg: Dict[str, Any] = {"success": False, "error": error}
    if hint:
        msg["hint"] = hint
    print(json.dumps(msg, ensure_ascii=False), file=sys.stderr)
    sys.exit(1)


def _bounded_int(lo: int, hi: int) -> Any:
    """Return an argparse type function that validates an int within [lo, hi]."""
    def _check(value: str) -> int:
        n = int(value)
        if not lo <= n <= hi:
            raise argparse.ArgumentTypeError(f"must be between {lo} and {hi}, got {n}")
        return n
    return _check


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Dingo ArticleFactChecker Skill Script")
    parser.add_argument("article_path", help="Path to article file (.md, .jsonl, .json, .txt)")
    parser.add_argument("--model", default=None, help="LLM model name (default: env OPENAI_MODEL or gpt-5.4-mini)")
    parser.add_argument("--max-claims", type=_bounded_int(1, 200), default=50,
                        help="Max claims to extract, 1-200 (default: 50)")
    parser.add_argument("--max-concurrent", type=_bounded_int(1, 20), default=5,
                        help="Parallel verification slots, 1-20 (default: 5)")
    return parser.parse_args()


# --- Main execution (requires Dingo SDK) ---

def extract_detail_report(output_path: str) -> Optional[Dict[str, Any]]:
    """
    Extract the structured report from Dingo output JSONL files.

    Reads the first ResultInfo from output_path/content/*.jsonl and
    returns EvalDetail.reason[1] (the structured report dict).

    Args:
        output_path: Dingo output directory path

    Returns:
        Structured report dict, or None if not found
    """
    content_dir = os.path.join(output_path, "content")
    if not os.path.isdir(content_dir):
        return None

    for fname in os.listdir(content_dir):
        if not fname.endswith('.jsonl'):
            continue
        fpath = os.path.join(content_dir, fname)
        with open(fpath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    result_info = json.loads(line)
                    # Navigate: eval_details -> "content" -> [0] -> reason -> [1]
                    eval_details = result_info.get("eval_details", {})
                    for field_key, details_list in eval_details.items():
                        if details_list:
                            detail = details_list[0]
                            reason = detail.get("reason", [])
                            if len(reason) >= 2 and isinstance(reason[1], dict):
                                return reason[1]
                except (json.JSONDecodeError, TypeError, IndexError):
                    continue
    return None


def main() -> int:
    """Main entry point for the Dingo fact-check skill script."""
    args = parse_args()

    # Validate inputs — existence check first, then security validation
    if not os.path.exists(args.article_path):
        error_exit(
            f"File not found: {args.article_path}",
            "Check the file path and try again"
        )

    try:
        article_path = validate_article_path(args.article_path)
    except ValueError as e:
        error_exit(str(e))

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        error_exit(
            "OPENAI_API_KEY environment variable not set",
            "export OPENAI_API_KEY='your-key'"
        )

    # Check dingo is importable
    try:
        from dingo.config import InputArgs
        from dingo.exec import Executor
    except ImportError:
        error_exit(
            "Dingo SDK not installed",
            "pip install -e . or pip install dingo-python"
        )

    # Check LangChain is available (required by ArticleFactChecker agent)
    try:
        import langchain  # noqa: F401
    except ImportError:
        error_exit(
            "LangChain not installed (required by ArticleFactChecker)",
            'pip install "dingo-python[agent]"'
        )

    api_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = args.model or os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    tavily_key = os.getenv("TAVILY_API_KEY")

    if not tavily_key:
        print("Warning: TAVILY_API_KEY not set, web search verification disabled", file=sys.stderr)

    # Format detection and wrapping
    data_format, needs_wrap = detect_format(article_path)
    temp_path = None

    try:
        if needs_wrap:
            temp_path = wrap_plaintext(article_path)
            effective_path = temp_path
            effective_format = "jsonl"
        else:
            effective_path = article_path
            effective_format = data_format

        # Build config and execute
        config = build_config(
            input_path=effective_path,
            data_format=effective_format,
            model=model,
            api_key=api_key,
            api_url=api_url,
            tavily_key=tavily_key,
            max_claims=args.max_claims,
            max_concurrent=args.max_concurrent,
        )

        start_time = time.time()
        input_args = InputArgs(**config)
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute()
        duration = time.time() - start_time

        # Extract structured report from output files
        detail_report = None
        if result.output_path:
            detail_report = extract_detail_report(result.output_path)

        # Build and output report
        summary_dict = {
            "total": result.total,
            "num_good": result.num_good,
            "num_bad": result.num_bad,
            "score": result.score,
            "output_path": result.output_path,
        }

        report = build_report(summary_dict, detail_report, duration)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    except ValueError as e:
        error_exit(str(e))
        return 1  # unreachable
    except Exception:
        # Do not echo exception message to avoid leaking SDK internals or config values
        error_exit("Execution failed. Check Dingo SDK logs in the output directory.")
        return 1  # unreachable

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
