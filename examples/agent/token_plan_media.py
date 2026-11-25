"""Run the token-plan image rule on a local single-partition normalized JSONL."""

import argparse
import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--date", required=True, help="Raw partition date (YYYY-MM-DD)")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--raw-base-uri", default="s3://agent-trajectory/lakehouse/token-plan/raw/v001/")
    parser.add_argument("--output", default="outputs")
    args = parser.parse_args()
    config = {
        "s3_config": {
            "s3_endpoint_url": args.endpoint,
            "s3_ak": os.environ["AWS_ACCESS_KEY_ID"],
            "s3_sk": os.environ["AWS_SECRET_ACCESS_KEY"],
        },
        "media_config": {"partition_date": args.date, "raw_base_uri": args.raw_base_uri},
    }
    task = InputArgs(input_path=str(args.input), output_path=args.output,
                     dataset={"source": "local", "format": "ms_swift"},
                     executor={"result_save": {"good": True, "bad": True, "all_labels": True, "merge": True}},
                     evaluator=[{"evals": [{"name": "RuleAgentTrajectoryMediaIntegrity", "config": config}]}])
    Executor.exec_map["local"](task).execute()


if __name__ == "__main__":
    main()
