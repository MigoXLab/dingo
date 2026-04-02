"""
Article Fact-Checking Example using ArticleFactChecker Agent.

Usage:
    python examples/agent/agent_article_fact_checking_example.py

Requirements:
    - OPENAI_API_KEY: For LLM agent and claims extraction
    - TAVILY_API_KEY: (Optional) For web search verification
"""

import os

from dingo.config import InputArgs
from dingo.exec import Executor


def main() -> int:
    """Run article fact-checking example."""

    # Verify API keys
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("ERROR: OPENAI_API_KEY environment variable not set")
        print("\nSet it with:")
        print("  export OPENAI_API_KEY='your-api-key'")
        return 1

    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        print("WARNING: TAVILY_API_KEY not set - web search verification will be limited")
        print("   Set it with: export TAVILY_API_KEY='your-api-key'")

    article_path = "test/data/factcheck_article.jsonl"
    if not os.path.exists(article_path):
        print(f"ERROR: Article file not found: {article_path}")
        return 1

    # Configuration for ArticleFactChecker
    config = {
        "input_path": article_path,
        "dataset": {
            "source": "local",
            "format": "jsonl"
        },
        "executor": {
            "max_workers": 1
        },
        "evaluator": [
            {
                "fields": {
                    "content": "content"
                },
                "evals": [
                    {
                        "name": "ArticleFactChecker",
                        "config": {
                            "key": openai_key,
                            "model": "intern-s1-pro",
                            "api_url": "https://chat.intern-ai.org.cn/api/v1/",
                            "timeout": 600,
                            "temperature": 0,  # deterministic output
                            "agent_config": {
                                "max_concurrent_claims": 10,
                                "max_iterations": 50,
                                # Artifacts auto-saved to outputs/article_factcheck_<timestamp>/
                                # Override with: "output_path": "your/custom/path"
                                "tools": {
                                    "claims_extractor": {
                                        "api_key": openai_key,
                                        "model": "intern-s1-pro",
                                        "base_url": "https://chat.intern-ai.org.cn/api/v1/",
                                        "max_claims": 50,
                                        "claim_types": [
                                            "factual", "statistical", "attribution", "institutional",
                                            "temporal", "comparative", "monetary", "technical"
                                        ]
                                    },
                                    "tavily_search": {
                                        "api_key": tavily_key
                                    } if tavily_key else {},
                                    "arxiv_search": {
                                        "max_results": 5,
                                        "fetch_affiliations": True,
                                    }
                                }
                            }
                        }
                    }
                ]
            }
        ]
    }

    print("Starting Article Fact-Checking")
    print("=" * 70)
    print(f"Article: {article_path}")
    print("Agent: ArticleFactChecker (Agent-First architecture)")
    print(f"Model: {config['evaluator'][0]['evals'][0]['config']['model']}")
    print("Artifact output: outputs/article_factcheck_<timestamp>/")
    print("=" * 70)

    input_args = InputArgs(**config)
    executor = Executor.exec_map["local"](input_args)

    print("\nExecuting agent-based fact-checking...\n")
    result = executor.execute()

    print("\n" + "=" * 70)
    print("FACT-CHECKING RESULTS")
    print("=" * 70)

    if result:
        print(f"\nTotal items evaluated: {result.total}")
        print(f"Passed: {result.num_good}  |  Issues found: {result.num_bad}")
        if result.score:
            print(f"Overall score: {result.score:.2%}")
        if result.type_ratio:
            print("\nIssue breakdown:")
            for field_key, type_counts in result.type_ratio.items():
                for label, count in type_counts.items():
                    print(f"  [{field_key}] {label}: {count}")

    print("\nFact-checking complete!")
    print(f"\nDingo standard output: {input_args.output_path}/")
    print("  |-- summary.json                  (aggregated statistics)")
    print("  +-- content/<LABEL>.jsonl          (results grouped by quality label)")

    print("\nIntermediate artifacts: outputs/article_factcheck_<timestamp>_<uuid>/")
    print("  |-- article_content.md           (original Markdown article)")
    print("  |-- claims_extracted.jsonl        (extracted claims, one per line)")
    print("  |-- claims_verification.jsonl     (per-claim verification details)")
    print("  +-- verification_report.json      (full structured report)")
    print("\nNote: Override artifact path with agent_config.output_path in config")

    return 0


if __name__ == "__main__":
    exit(main())
