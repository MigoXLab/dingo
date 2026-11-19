"""Count all empty assistant turns without an LLM or converter preparer.

Run from the repository root (complete standardized samples are included):
    python examples/agent/empty_assistant_turn.py
    python examples/agent/empty_assistant_turn.py C:/path/to/traces.jsonl

The rule ignores loss flags. An empty turn has neither text nor reasoning nor
tool calls. Any match sets status=True after the full scan and counts toward
Dingo's num_bad summary. Keep all results to inspect passes and N/A as well.
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
        default=Path(__file__).resolve().parents[2] / "test" / "data" / "agent" / "empty_assistant_turn.jsonl",
    )
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    options = {
        "input_path": str(args.input_path),
        "dataset": {"source": "local", "format": "ms_swift"},
        "executor": {"result_save": {
            "bad": True, "good": True, "raw": True, "all_labels": True, "merge": True,
        }},
        "evaluator": [{
            "fields": {"messages": "messages"},
            "evals": [{"name": "RuleAgentTraceEmptyAssistantTurn"}],
        }],
    }
    if args.output_dir is not None:
        options["output_path"] = str(args.output_dir)
    executor = Executor.exec_map["local"](InputArgs(**options))
    print(json.dumps(executor.execute().to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
