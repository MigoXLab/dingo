"""Report per-trajectory empty reasoning frequency without an LLM or API key.

Run from the repository root (bundled standardized sample is the default):
    python examples/agent/reasoning_sparsity.py
    python examples/agent/reasoning_sparsity.py C:/path/to/traces.jsonl --threshold 0.7

Feature matches remain status=False. Save all labels and good records so the
feature labels and descriptive reasons are retained in all_results.jsonl.
"""

import argparse
import json
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_path", type=Path, nargs="?",
        default=Path(__file__).resolve().parents[2] / "test" / "data" / "agent" / "reasoning_sparsity.jsonl",
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--threshold", type=float, default=0.7)
    args = parser.parse_args()
    options = {
        "input_path": str(args.input_path),
        "dataset": {"source": "local", "format": "ms_swift"},
        "executor": {"result_save": {
            "bad": True, "good": True, "raw": True, "all_labels": True, "merge": True,
        }},
        "evaluator": [{
            "fields": {"messages": "messages"},
            "evals": [{"name": "RuleAgentTraceReasoningSparsity", "config": {
                "threshold": args.threshold,
            }}],
        }],
    }
    if args.output_dir is not None:
        options["output_path"] = str(args.output_dir)
    executor = Executor.exec_map["local"](InputArgs(**options))
    print(json.dumps(executor.execute().to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
