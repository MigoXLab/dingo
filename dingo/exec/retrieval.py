"""
RetrievalExecutor — Evaluates search APIs against MTEB retrieval benchmarks.

Registered as ``Executor.exec_map["retrieval"]``. Uses the same InputArgs
configuration as other executors, reading retrieval-specific config from
``input_args.executor.retrieval``.
"""

from __future__ import annotations
import logging
import os
import uuid
from datetime import datetime
from typing import Any

import mteb

from dingo.config.input_args import InputArgs
from dingo.exec.base import Executor
from dingo.io import SummaryModel
from dingo.retrieval.eval_utils import make_output_dir, save_json
from dingo.retrieval.mteb_adapter import SearchClientModel
from dingo.retrieval.search_client import create_client

logger = logging.getLogger(__name__)

METRICS_OF_INTEREST = [
    "main_score",
    "ndcg_at_10",
    "ndcg_at_100",
    "mrr_at_10",
    "recall_at_5",
    "recall_at_10",
    "recall_at_20",
    "recall_at_100",
    "precision_at_10",
    "map_at_10",
]


@Executor.register("retrieval")
class RetrievalExecutor:
    """Evaluates search APIs against MTEB retrieval benchmarks."""

    def __init__(self, input_args: InputArgs):
        self.input_args = input_args
        if not input_args.executor.retrieval:
            raise ValueError(
                "executor.retrieval config is required for RetrievalExecutor. "
                "Please set executor.retrieval with backend, api_url, etc."
            )
        self.retrieval_args = input_args.executor.retrieval

    def execute(self) -> SummaryModel:
        task_names = [
            t.strip() for t in self.input_args.input_path.split(",") if t.strip()
        ]
        if not task_names:
            raise ValueError("input_path must specify MTEB task name(s), e.g. 'SciFact'")

        ra = self.retrieval_args
        client = create_client(
            ra.backend,
            api_url=ra.api_url,
            api_token=ra.api_token,
            timeout=ra.timeout,
            max_retries=ra.max_retries,
            rate_limit=ra.rate_limit or 0.0,
            retrieval_mode=ra.retrieval_mode,
            sub_queries=ra.sub_queries,
        )
        model = SearchClientModel(
            client,
            search_limit=ra.limit,
            max_queries=ra.max_queries,
            max_workers=ra.max_workers,
        )

        output_dir = make_output_dir(
            explicit_dir=None,
            default_prefix=os.path.join(
                self.input_args.output_path, ra.backend
            ),
        )

        summary = SummaryModel(
            task_id=str(uuid.uuid4())[:8],
            task_name=self.input_args.task_name or "retrieval_eval",
            input_path=self.input_args.input_path,
            output_path=output_dir,
            create_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

        all_results: dict[str, Any] = {}

        for task_name in task_names:
            logger.info(f"Starting evaluation on task: {task_name}")
            tasks = mteb.get_tasks(tasks=[task_name])
            if not tasks:
                logger.warning(f"Task {task_name!r} not found in MTEB, skipping")
                continue

            try:
                results = mteb.evaluate(
                    model,
                    tasks=tasks,
                    overwrite_strategy="always",
                )
                task_metrics = self._extract_metrics(results)
                all_results[task_name] = task_metrics
            except Exception as e:
                logger.error(f"Task {task_name!r} failed: {e}")
                continue

        self._all_results = all_results
        summary.metrics_score_stats = all_results
        summary.total = sum(
            t.get("total_queries", 0)
            for trace in model.get_search_traces()
            for t in [trace]
        )
        summary.score = all_results.get(task_names[0], {}).get("main_score", 0.0) if task_names else 0.0
        summary.finish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        config = {
            "backend": ra.backend,
            "api_url": ra.api_url,
            "limit": ra.limit,
            "retrieval_mode": ra.retrieval_mode,
            "sub_queries": ra.sub_queries,
            "max_queries": ra.max_queries,
            "tasks": task_names,
        }

        summary_dict = {
            "task_id": summary.task_id,
            "task_name": summary.task_name,
            "input_path": summary.input_path,
            "output_path": summary.output_path,
            "create_time": summary.create_time,
            "finish_time": summary.finish_time,
            "score": summary.score,
            "total": summary.total,
            "config": config,
            "metrics": all_results,
        }
        save_json(summary_dict, output_dir, "summary.json")

        detailed = {
            "config": config,
            "results": all_results,
            "search_traces": model.get_search_traces(),
        }
        save_json(detailed, output_dir, "detailed_results.json")

        logger.info(f"Evaluation complete. Results saved to: {output_dir}")
        return summary

    def _extract_metrics(self, model_result) -> dict[str, float]:
        """Extract metrics of interest from MTEB ModelResult."""
        metrics: dict[str, float] = {}
        for task_result in model_result.task_results:
            scores = task_result.scores
            if not scores:
                continue
            for split_scores in scores.values():
                for score_entry in split_scores:
                    for key in METRICS_OF_INTEREST:
                        if key in score_entry:
                            metrics[key] = round(score_entry[key], 5)
        return metrics

    def load_data(self):
        pass

    def evaluate(self):
        pass

    def summarize(self, summary: SummaryModel) -> SummaryModel:
        return summary
