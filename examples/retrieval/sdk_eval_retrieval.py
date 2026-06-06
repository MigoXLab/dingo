"""
Example: Evaluate a retrieval API against SciFact benchmark.

Usage (SDK):
    python examples/retrieval/sdk_eval_retrieval.py

Usage (CLI equivalent):
    dingo eval-retrieval --backend agentic --tasks SciFact \
        --api-url https://api.sciverse.space \
        --api-token YOUR_TOKEN --limit 100 --max-queries 5
"""

import os

from dingo.config import InputArgs
from dingo.exec import Executor

YOUR_API_TOKEN = os.getenv("SCIVERSE_API_TOKEN")


def eval_retrieval_api():
    """Evaluate agentic-search API against SciFact benchmark."""
    input_data = {
        "task_name": "retrieval_eval",
        "input_path": "SciFact",
        "output_path": "outputs/retrieval_eval",
        "executor": {
            "retrieval": {
                "backend": "agentic",
                "api_url": "https://api.sciverse.space",
                "api_token": YOUR_API_TOKEN,
                "limit": 100,
                "retrieval_mode": "hybrid",
            }
        },
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["retrieval"](input_args)
    result = executor.execute()
    print(result)


def eval_retrieval_api_quick():
    """Quick test with only 5 queries (for debugging)."""
    input_data = {
        "task_name": "retrieval_eval_quick",
        "input_path": "SciFact",
        "output_path": "outputs/retrieval_eval",
        "executor": {
            "retrieval": {
                "backend": "agentic",
                "api_url": "https://api.sciverse.space",
                "limit": 50,
                "api_token": YOUR_API_TOKEN,
                "retrieval_mode": "hybrid",
                "max_queries": 5,
            }
        },
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["retrieval"](input_args)
    result = executor.execute()
    print(result)


def eval_multiple_tasks():
    """Evaluate against multiple MTEB tasks at once."""
    input_data = {
        "task_name": "multi_task_eval",
        "input_path": "SciFact,SCIDOCS",
        "output_path": "outputs/retrieval_eval",
        "executor": {
            "retrieval": {
                "backend": "agentic",
                "api_url": "https://api.sciverse.space",
                "api_token": YOUR_API_TOKEN,
                "limit": 100,
                "retrieval_mode": "hybrid",
            }
        },
    }

    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["retrieval"](input_args)
    result = executor.execute()
    print(result)


if __name__ == "__main__":
    eval_retrieval_api_quick()
