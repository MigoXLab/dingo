"""
Open Eval Example — Exa-style LLM-as-Judge search result grading.

Demonstrates two usage modes:

1. **Standalone open eval**: grade search results on custom queries
   (no MTEB corpus, no gold labels needed).

2. **MTEB + open eval**: run standard closed eval and additionally
   grade top results with an LLM judge.

Usage:

    # Mode 1: Standalone open eval with custom queries
    python sdk_open_eval.py --mode standalone \
        --queries sample_queries.jsonl \
        --api-url https://api.example.com \
        --api-token YOUR_TOKEN \
        --llm-model gpt-4o \
        --llm-key YOUR_OPENAI_KEY

    # Mode 2: MTEB closed eval + open eval
    python sdk_open_eval.py --mode mteb \
        --tasks SciFact \
        --api-url https://api.example.com \
        --api-token YOUR_TOKEN \
        --llm-model gpt-4o \
        --llm-key YOUR_OPENAI_KEY

    # Equivalent CLI commands:

    # Standalone:
    dingo eval-retrieval --backend agentic \
        --input-queries sample_queries.jsonl \
        --api-url https://api.example.com \
        --api-token YOUR_TOKEN \
        --open-eval --open-eval-model gpt-4o --open-eval-key YOUR_KEY

    # MTEB + open eval:
    dingo eval-retrieval --backend agentic --tasks SciFact \
        --api-url https://api.example.com \
        --api-token YOUR_TOKEN \
        --open-eval --open-eval-model gpt-4o --open-eval-key YOUR_KEY
"""

import argparse
import json

from dingo.config.input_args import InputArgs, OpenEvalArgs, RetrievalArgs
from dingo.exec import Executor


def main():
    parser = argparse.ArgumentParser(description="Open Eval Example")
    parser.add_argument("--mode", choices=["standalone", "mteb"], default="standalone")
    parser.add_argument("--queries", type=str, default="sample_queries.jsonl")
    parser.add_argument("--tasks", nargs="+", default=["SciFact"])
    parser.add_argument("--backend", type=str, default="agentic")
    parser.add_argument("--api-url", type=str, required=True)
    parser.add_argument("--api-token", type=str, default=None)
    parser.add_argument("--llm-model", type=str, default="gpt-4o")
    parser.add_argument("--llm-key", type=str, required=True)
    parser.add_argument("--llm-api-url", type=str, default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--prompt-mode", choices=["standard", "detailed"], default="standard")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--max-queries", type=int, default=None)
    parser.add_argument("-o", "--output", type=str, default="outputs/open_eval")
    args = parser.parse_args()

    open_eval = OpenEvalArgs(
        enabled=True,
        model=args.llm_model,
        key=args.llm_key,
        api_url=args.llm_api_url,
        top_k=args.top_k,
        prompt_mode=args.prompt_mode,
    )

    retrieval_config = RetrievalArgs(
        backend=args.backend,
        api_url=args.api_url,
        api_token=args.api_token,
        limit=args.limit,
        max_queries=args.max_queries,
        open_eval=open_eval,
        input_queries=args.queries if args.mode == "standalone" else None,
    )

    input_path = (
        "__open_eval__" if args.mode == "standalone"
        else ",".join(args.tasks)
    )

    input_args = InputArgs(
        task_name="open_eval_demo",
        input_path=input_path,
        output_path=args.output,
        executor={"retrieval": retrieval_config.model_dump()},
    )

    executor = Executor.exec_map["retrieval"](input_args)
    summary = executor.execute()

    print("\n=== Open Eval Results ===")
    print(json.dumps(summary.metrics_score_stats, indent=2, ensure_ascii=False))
    print(f"\nResults saved to: {summary.output_path}")


if __name__ == "__main__":
    main()
