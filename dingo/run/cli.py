import argparse
import json
import os
import sys

import prettytable as pt

from dingo.config import InputArgs
from dingo.exec import Executor
from dingo.model import Model
from dingo.utils import log


def parse_args():
    parser = argparse.ArgumentParser(
        prog="dingo",
        description="Dingo: A Comprehensive AI Data, Model and Application Quality Evaluation Tool",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # --- dingo eval ---
    eval_parser = subparsers.add_parser("eval", help="Run data quality evaluation")
    eval_parser.add_argument(
        "-i", "--input",
        type=str,
        required=True,
        help="Path to JSON config file",
    )
    eval_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output result as JSON to stdout (for agent/automation consumption)",
    )

    # --- dingo info ---
    info_parser = subparsers.add_parser("info", help="List available evaluators and rule groups")
    info_parser.add_argument(
        "--rules", action="store_true", help="List rule-based evaluators",
    )
    info_parser.add_argument(
        "--llm", action="store_true", help="List LLM-based evaluators",
    )
    info_parser.add_argument(
        "--groups", action="store_true", help="List rule groups",
    )
    info_parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        help="Output as JSON",
    )

    # Backward compatibility: bare `dingo --input config.json`
    parser.add_argument(
        "-i", "--input",
        type=str,
        default=None,
        help=argparse.SUPPRESS,
    )

    return parser.parse_args(), parser


def get_config(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


def cmd_eval(args):
    """Run evaluation from a config file."""
    input_data = get_config(args.input)
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()

    if args.json:
        json.dump(result.to_dict(), sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        print(result)


def cmd_info(args):
    """List available evaluators and groups."""
    Model.load_model()

    show_all = not (args.rules or args.llm or args.groups)

    info = {}

    if show_all or args.rules:
        rules = {}
        for name, cls in sorted(Model.rule_name_map.items()):
            metric_type = getattr(cls, 'metric_type', '')
            groups = getattr(cls, 'group', [])
            required = [f.value for f in getattr(cls, '_required_fields', [])]
            rules[name] = {
                "metric_type": metric_type,
                "groups": groups,
                "required_fields": required,
            }
        info["rules"] = rules

    if show_all or args.llm:
        llm_evals = {}
        for name, cls in sorted(Model.llm_name_map.items()):
            required = [f.value for f in getattr(cls, '_required_fields', [])]
            llm_evals[name] = {
                "required_fields": required,
            }
        info["llm_evaluators"] = llm_evals

    if show_all or args.groups:
        groups = {}
        for group_name, rule_list in sorted(Model.rule_groups.items()):
            groups[group_name] = [cls.__name__ for cls in rule_list]
        info["groups"] = groups

    if args.json:
        json.dump(info, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    else:
        _print_info_table(info)


def _print_info_table(info):
    """Pretty-print evaluator info as tables."""
    if "rules" in info:
        table = pt.PrettyTable()
        table.field_names = ["Rule", "Metric Type", "Groups", "Required Fields"]
        table.align = "l"
        for name, meta in info["rules"].items():
            table.add_row([
                name,
                meta["metric_type"],
                ", ".join(meta["groups"]) if meta["groups"] else "-",
                ", ".join(meta["required_fields"]) if meta["required_fields"] else "-",
            ])
        print(f"\n=== Rule Evaluators ({len(info['rules'])}) ===")
        print(table)

    if "llm_evaluators" in info:
        table = pt.PrettyTable()
        table.field_names = ["LLM Evaluator", "Required Fields"]
        table.align = "l"
        for name, meta in info["llm_evaluators"].items():
            table.add_row([
                name,
                ", ".join(meta["required_fields"]) if meta["required_fields"] else "-",
            ])
        print(f"\n=== LLM Evaluators ({len(info['llm_evaluators'])}) ===")
        print(table)

    if "groups" in info:
        table = pt.PrettyTable()
        table.field_names = ["Group", "Rules"]
        table.align = "l"
        table.max_width["Rules"] = 80
        for group_name, rule_names in info["groups"].items():
            table.add_row([group_name, ", ".join(rule_names)])
        print(f"\n=== Rule Groups ({len(info['groups'])}) ===")
        print(table)


def main():
    args, parser = parse_args()

    # Backward compatibility: `dingo --input config.json` (no subcommand)
    if args.command is None and args.input:
        input_data = get_config(args.input)
        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute()
        print(result)
        return

    if args.command == "eval":
        cmd_eval(args)
    elif args.command == "info":
        cmd_info(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
