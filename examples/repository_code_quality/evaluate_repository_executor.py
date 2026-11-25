"""Run repository-code quality checks through Dingo's LocalExecutor.

The input must be JSONL and each record must contain a string ``content``.
Keep evaluator fields empty so repository metadata such as language, file_name,
path, and track_id remains available to cross-record checks.

Pick the pipeline version with ``--evaluator``: ``LLMRepositoryCodeQualityPipeline``
(V1, default) or ``LLMRepositoryCodeQualityPipelineV2`` (adds contextual-character,
artifact, language-consistency, placeholder, ClamAV, and model-confirmed license and
reverse-shell checks).
"""

import argparse
import json
import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec.local import LocalExecutor

PIPELINE_VERSIONS = (
    "LLMRepositoryCodeQualityPipeline",
    "LLMRepositoryCodeQualityPipelineV2",
)


def make_config(
    input_path: Path,
    output_path: Path,
    workers: int,
    batch_size: int,
    start_index: int,
    end_index: int,
    evaluator_name: str = PIPELINE_VERSIONS[0],
) -> InputArgs:
    return InputArgs(
        task_name="repository_code_quality_executor",
        input_path=str(input_path.resolve()),
        output_path=str(output_path.resolve()),
        dataset={"source": "local", "format": "repository_code_jsonl"},
        executor={
            "start_index": start_index,
            "end_index": end_index,
            "max_workers": workers,
            "batch_size": batch_size,
            "result_save": {
                "bad": True,
                "good": True,
                "all_labels": True,
            },
        },
        evaluator=[
            {
                "fields": {},
                "evals": [
                    {
                        "name": evaluator_name,
                        "config": {
                            "key": os.environ["OPENAI_API_KEY"],
                            "api_url": os.environ["OPENAI_BASE_URL"],
                            "model": os.environ["OPENAI_MODEL"],
                            "request_timeout": 120,
                            "max_retries": 1,
                            "max_tokens": 4096,
                        },
                    }
                ],
            }
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--start-index", type=int, default=0)
    parser.add_argument("--end-index", type=int, default=-1)
    parser.add_argument("--evaluator", choices=PIPELINE_VERSIONS, default=PIPELINE_VERSIONS[0])
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error("--input must point to an existing JSONL file")
    if args.workers <= 0 or args.batch_size <= 0 or args.start_index < 0:
        parser.error("workers and batch-size must be positive; start-index must be nonnegative")
    if args.end_index >= 0 and args.end_index < args.start_index:
        parser.error("end-index must be -1 or greater than or equal to start-index")
    missing = [
        name
        for name in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL")
        if not os.environ.get(name)
    ]
    if missing:
        parser.error("Set required environment variables: " + ", ".join(missing))

    os.environ["LOCAL_DEPLOYMENT_MODE"] = "true"
    config = make_config(
        args.input,
        args.output,
        args.workers,
        args.batch_size,
        args.start_index,
        args.end_index,
        args.evaluator,
    )
    summary = LocalExecutor(config).execute()
    print(
        json.dumps(
            {
                "total": summary.total,
                "good": summary.num_good,
                "bad": summary.num_bad,
                "score": summary.score,
                "type_count": summary.type_count,
                "output_path": summary.output_path,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
