"""Evaluate repeated tool interactions without an LLM or API key.

Run from the repository root:
    python examples/agent/loop_detection.py C:/path/to/traces.jsonl
"""

import argparse
import json
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--threshold", type=float, default=0.95)
    parser.add_argument("--min-repeats", type=int, default=3)
    args = parser.parse_args()
    options = {
        "input_path": str(args.input_path),
        "dataset": {"source": "local", "format": "ms_swift"},
        "executor": {"result_save": {"good": True, "raw": True, "all_labels": True}},
        "evaluator": [{
            "fields": {"content": "RuleAgentTraceLoopDetection_content"},
            "evals": [{"name": "RuleAgentTraceLoopDetection", "config": {
                "threshold": args.threshold, "min_repeats": args.min_repeats,
            }}],
        }],
    }
    if args.output_dir is not None:
        options["output_path"] = str(args.output_dir)
    executor = Executor.exec_map["local"](InputArgs(**options))
    print(json.dumps(executor.execute().to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
