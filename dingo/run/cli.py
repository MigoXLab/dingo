import argparse
import os

import prettytable as pt

from dingo.exec import Executor
from dingo.io import InputArgs
from dingo.model import Model
from dingo.utils import log


def parse_args():
    parser = argparse.ArgumentParser("dingo run with local script. (CLI)")
    parser.add_argument(
        "-n", "--task_name", type=str, default=None, help="Input task name"
    )
    parser.add_argument(
        "-e",
        "--eval_group",
        type=str,
        default=None,
        help="Eval models, can be specified multiple times like '-e default' or '-e pretrain'",
    )
    parser.add_argument(
        "-i",
        "--input_path",
        type=str,
        default=None,
        help="Input file or directory path",
    )
    parser.add_argument(
        "--output_path", type=str, default=None, help="Output file or directory path"
    )
    parser.add_argument(
        "--save_data",
        nargs='?',
        const=True,
        default=False,
        type=lambda x: (
            True if x.lower() in ('true', '1') else
            False if x.lower() in ('false', '0') else
            argparse.ArgumentTypeError(f"Invalid boolean value: {x}")
        ),
        help="Save data in output path (default: False, use --save_data or --save_data True to enable)"
    )
    parser.add_argument(
        "--save_correct",
        nargs='?',
        const=True,
        default=False,
        type=lambda x: (
            True if x.lower() in ('true', '1') else
            False if x.lower() in ('false', '0') else
            argparse.ArgumentTypeError(f"Invalid boolean value: {x}")
        ),
        help="Save correct data in output path (default: False, use --save_correct or --save_correct True to enable)",
    )
    parser.add_argument(
        "--save_raw",
        nargs='?',
        const=True,
        default=False,
        type=lambda x: (
            True if x.lower() in ('true', '1') else
            False if x.lower() in ('false', '0') else
            argparse.ArgumentTypeError(f"Invalid boolean value: {x}")
        ),
        help="Save raw data in output path (default: False, use --save_raw or --save_raw True to enable)",
    )
    parser.add_argument(
        "--start_index",
        type=int,
        default=None,
        help="The number of data start to check.",
    )
    parser.add_argument(
        "--end_index", type=int, default=None, help="The number of data end to check."
    )
    parser.add_argument(
        "--max_workers",
        type=int,
        default=None,
        help="The number of max workers to concurrent check. ",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=None,
        help="the number of max data for concurrent check. ",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        choices=["hugging_face", "local"],
        help="Dataset type (in ['hugging_face', 'local']), default is 'hugging_face'",
    )
    parser.add_argument(
        "--data_format",
        type=str,
        default=None,
        choices=["json", "jsonl", "listjson", "plaintext", "image", "s3_image"],
        help="Dataset format (in ['json', 'jsonl', 'listjson', 'plaintext', 'image', 's3_image']), default is 'json'",
    )
    parser.add_argument(
        "--huggingface_split",
        type=str,
        default=None,
        help="Huggingface split, default is 'train'",
    )
    parser.add_argument(
        "--huggingface_config_name",
        type=str,
        default=None,
        help="Huggingface config name",
    )
    parser.add_argument(
        "--column_id",
        type=str,
        default=None,
        help="Column name of id in the input file. If exists multiple levels, use '.' separate",
    )
    parser.add_argument(
        "--column_prompt",
        type=str,
        default=None,
        help="Column name of prompt in the input file. If exists multiple levels, use '.' separate",
    )
    parser.add_argument(
        "--column_content",
        type=str,
        default=None,
        help="Column name of content in the input file. If exists multiple levels, use '.' separate",
    )
    parser.add_argument(
        "--column_image",
        type=str,
        default=None,
        action="append",
        help="Column name of image in the input file. If exists multiple levels, use '.' separate",
    )
    parser.add_argument(
        "--custom_config", type=str, default=None, help="Custom config file path"
    )

    # Warning: arguments bellow are not associated with inner abilities.
    parser.add_argument(
        "--log_level",
        type=str,
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help='Choose the logging level in ["DEBUG", "INFO", '
        + '"WARNING", "ERROR"], default is \'WARNING\'',
    )
    parser.add_argument(
        "--use_browser",
        nargs='?',
        const=True,
        default=False,
        type=lambda x: (
            True if x.lower() in ('true', '1') else
            False if x.lower() in ('false', '0') else
            argparse.ArgumentTypeError(f"Invalid boolean value: {x}")
        ),
        help="Open browser to display result (default: False, use --use_browser or --use_browser True to enable)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    log.setLevel(args.log_level)

    if not args.eval_group:
        print("\n=========+++ Help +++==========")
        print("Eval models not specified")
        print("\n========= Rule Model ==========")
        print("You can use '-e default' or '-e pretrain' to run all eval models\n")
        print([i for i in Model.get_rule_groups().keys()])
        print("=================================")
        print("Rule Model details are as follows: \n")
        for i in Model.get_rule_groups():
            tb = pt.PrettyTable()
            tb.field_names = ["ModelName", "Rules"]
            tb.add_row(
                [
                    i,
                    ",\n".join(
                        [
                            str(j.__name__).split(".")[-1]
                            for j in Model.get_rule_groups()[i]
                        ]
                    ),
                ]
            )
            print(tb)
        print("=================================")
        print("Or combine them with a json file select from this list\n")
        Model.print_rule_list()
        print("=================================")
        print("\n")
        print("=========== LLM Model ===========")
        print(",".join([i for i in Model.llm_name_map.keys()]))
        print("=================================")
        print("\n")

    else:
        # parse input
        input_data = {}
        if args.task_name:
            input_data["task_name"] = args.task_name
        if args.eval_group:
            input_data["eval_group"] = args.eval_group
        if args.input_path:
            input_data["input_path"] = args.input_path
        if args.output_path:
            input_data["output_path"] = args.output_path
        if args.save_data:
            input_data["save_data"] = args.save_data
        if args.save_correct:
            input_data["save_correct"] = args.save_correct
        if args.save_raw:
            input_data["save_raw"] = args.save_raw
        if args.start_index:
            input_data["start_index"] = args.start_index
        if args.end_index:
            input_data["end_index"] = args.end_index
        if args.max_workers:
            input_data["max_workers"] = args.max_workers
        if args.batch_size:
            input_data["batch_size"] = args.batch_size
        if args.dataset:
            input_data["dataset"] = args.dataset
        if args.data_format:
            input_data["data_format"] = args.data_format
        if args.huggingface_split:
            input_data["huggingface_split"] = args.huggingface_split
        if args.huggingface_config_name:
            input_data["huggingface_config_name"] = args.huggingface_config_name
        if args.column_id:
            input_data["column_id"] = args.column_id
        if args.column_prompt:
            input_data["column_prompt"] = args.column_prompt
        if args.column_content:
            input_data["column_content"] = args.column_content
        if args.column_image:
            input_data["column_image"] = args.column_image
        if args.custom_config:
            input_data["custom_config"] = args.custom_config
        if args.log_level:
            input_data["log_level"] = args.log_level
        if args.use_browser:
            input_data["use_browser"] = args.use_browser

        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute()
        print(result)

        if input_args.use_browser and input_args.save_data:
            os.system("python -m dingo.run.vsl --input " + result.output_path)
