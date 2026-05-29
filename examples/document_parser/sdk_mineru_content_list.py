"""Evaluate MinerU content_list.json / content_list_v2.json with Dingo.

Usage:
    # content_list.json (V1)
    python sdk_mineru_content_list.py

    # content_list_v2.json (V2)
    python sdk_mineru_content_list.py --v2

    # Point to your own MinerU output
    python sdk_mineru_content_list.py --input /path/to/content_list.json

    # Only evaluate text and table blocks
    python sdk_mineru_content_list.py --include-types text table
"""

import argparse
from pathlib import Path
from typing import List, Optional

from dingo.config import InputArgs
from dingo.exec import Executor

PROJECT_ROOT = Path(__file__).parent.parent.parent


def run_evaluation(input_path: str, fmt: str, include_types: Optional[List[str]] = None):
    dataset_config = {
        "source": "local",
        "format": fmt,
    }
    if include_types:
        dataset_config["mineru_config"] = {"include_types": include_types}

    input_data = {
        "input_path": input_path,
        "dataset": dataset_config,
        "executor": {
            "result_save": {
                "bad": True,
                "good": True,
            }
        },
        "evaluator": [
            {
                "fields": {"content": "content"},
                "evals": [
                    {"name": "RuleColonEnd"},
                    {"name": "RuleAbnormalChar"},
                ],
            }
        ],
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate MinerU output with Dingo")
    parser.add_argument("--input", type=str, default=None, help="Path to MinerU content_list JSON file")
    parser.add_argument("--v2", action="store_true", help="Use content_list_v2 format (pages x blocks)")
    parser.add_argument("--include-types", nargs="+", default=None,
                        help="Only keep blocks of these types (e.g. text table image)")
    args = parser.parse_args()

    if args.input:
        fmt = "mineru_v2" if args.v2 else "mineru"
        run_evaluation(args.input, fmt, args.include_types)
    else:
        if args.v2:
            path = str(PROJECT_ROOT / "test/data/test_mineru_content_list_v2.json")
            run_evaluation(path, "mineru_v2", args.include_types)
        else:
            path = str(PROJECT_ROOT / "test/data/test_mineru_content_list.json")
            run_evaluation(path, "mineru", args.include_types)
