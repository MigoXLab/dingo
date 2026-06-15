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
from dingo.retrieval.eval_utils import compute_query_metrics, make_output_dir, save_json
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
        self.summary = SummaryModel()

    def get_summary(self):
        return self.summary

    def execute(self) -> SummaryModel:
        task_names = [
            t.strip() for t in self.input_args.input_path.split(",") if t.strip()
        ]
        if not task_names:
            raise ValueError("input_path must specify MTEB task name(s), e.g. 'SciFact'")

        ra = self.retrieval_args
        client_kwargs: dict[str, Any] = {
            "api_token": ra.api_token,
            "timeout": ra.timeout,
            "max_retries": ra.max_retries,
            "retrieval_mode": ra.retrieval_mode,
            "sub_queries": ra.sub_queries,
            "search_type": ra.search_type,
            "sort_by": ra.sort_by,
            "freshness_boost": ra.freshness_boost,
            "filters": ra.filters,
        }
        if ra.api_url:
            client_kwargs["api_url"] = ra.api_url
        if ra.rate_limit is not None:
            client_kwargs["rate_limit"] = ra.rate_limit
        client = create_client(ra.backend, **client_kwargs)
        model = SearchClientModel(
            client,
            search_limit=ra.limit,
            max_queries=ra.max_queries,
            max_workers=ra.max_workers,
            title_fuzzy_enabled=ra.title_fuzzy_enabled,
            title_fuzzy_threshold=ra.title_fuzzy_threshold,
            title_fuzzy_margin=ra.title_fuzzy_margin,
            title_fuzzy_min_len=ra.title_fuzzy_min_len,
            title_fuzzy_max_candidates=ra.title_fuzzy_max_candidates,
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
                self._attach_relevant_docs(model, tasks)
                results = mteb.evaluate(
                    model,
                    tasks=tasks,
                    overwrite_strategy="always",
                )
                task_metrics = self._extract_metrics(results)
                if not task_metrics:
                    logger.warning(
                        "MTEB returned empty metrics for task %r; "
                        "falling back to search trace metrics",
                        task_name,
                    )
                    task_metrics = self._compute_metrics_from_search_traces(
                        model.get_search_traces(),
                        task_name,
                    )
                all_results[task_name] = task_metrics
            except Exception as e:
                logger.error(f"Task {task_name!r} failed: {e}", exc_info=True)
                task_metrics = self._compute_metrics_from_search_traces(
                    model.get_search_traces(),
                    task_name,
                )
                if task_metrics:
                    logger.warning(
                        "Using search trace fallback metrics for failed task %r",
                        task_name,
                    )
                    all_results[task_name] = task_metrics
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
            "title_fuzzy_enabled": ra.title_fuzzy_enabled,
            "title_fuzzy_threshold": ra.title_fuzzy_threshold,
            "title_fuzzy_margin": ra.title_fuzzy_margin,
            "title_fuzzy_min_len": ra.title_fuzzy_min_len,
            "title_fuzzy_max_candidates": ra.title_fuzzy_max_candidates,
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
        self.summary = summary
        return summary

    @staticmethod
    def _attach_relevant_docs(model: SearchClientModel, tasks: list[Any]) -> None:
        """Load task qrels into the search adapter for detailed trace annotation."""
        for task in tasks:
            task.load_data()
            if hasattr(task, "convert_v1_dataset_format_to_v2"):
                task.convert_v1_dataset_format_to_v2(num_proc=None)

            task_name = task.metadata.name
            attached = False
            for hf_subset, splits in getattr(task, "dataset", {}).items():
                if not isinstance(splits, dict):
                    continue
                for hf_split, data_split in splits.items():
                    if not isinstance(data_split, dict):
                        continue
                    relevant_docs = data_split.get("relevant_docs")
                    if relevant_docs is None:
                        continue
                    model.set_relevant_docs(
                        task_name,
                        hf_split,
                        hf_subset,
                        relevant_docs,
                    )
                    attached = True

            if attached:
                continue

            hf_subset = getattr(task, "hf_subset", "default")
            relevant_docs_dict = getattr(task, "relevant_docs", {})
            for (
                hf_subset,
                hf_split,
                relevant_docs,
            ) in RetrievalExecutor._iter_legacy_qrels(relevant_docs_dict, hf_subset):
                model.set_relevant_docs(
                    task_name,
                    hf_split,
                    hf_subset,
                    relevant_docs,
                )

    @staticmethod
    def _iter_legacy_qrels(
        relevant_docs_dict: Any,
        default_subset: str,
    ):
        """Yield qrels from older MTEB task.relevant_docs layouts."""
        if not isinstance(relevant_docs_dict, dict):
            return

        for key, value in relevant_docs_dict.items():
            if RetrievalExecutor._looks_like_qrels(value):
                yield default_subset, key, value
            elif isinstance(value, dict):
                for split, qrels in value.items():
                    if RetrievalExecutor._looks_like_qrels(qrels):
                        yield key, split, qrels

    @staticmethod
    def _looks_like_qrels(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        if not value:
            return True
        sample = next(iter(value.values()))
        if isinstance(sample, dict):
            if not sample:
                return True
            nested_sample = next(iter(sample.values()))
            return not isinstance(nested_sample, (dict, list, tuple, set))
        return isinstance(sample, (list, tuple, set))

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

    @staticmethod
    def _compute_metrics_from_search_traces(
        traces: list[dict[str, Any]],
        task_name: str,
    ) -> dict[str, float]:
        """Compute fallback retrieval metrics from stored trace qrels/results."""
        metric_values: dict[str, list[float]] = {}
        for trace in traces:
            if trace.get("task") != task_name:
                continue
            for query in trace.get("queries", []):
                retrieved_doc_ids = query.get("retrieved_doc_ids") or []
                gold_doc_ids = set(query.get("gold_doc_ids") or [])
                if not gold_doc_ids:
                    continue

                query_metrics = compute_query_metrics(
                    retrieved_doc_ids,
                    gold_doc_ids,
                )
                query_metrics["main_score"] = query_metrics.get("ndcg_at_10", 0.0)

                for key in METRICS_OF_INTEREST:
                    if key not in query_metrics:
                        continue
                    metric_values.setdefault(key, []).append(query_metrics[key])

        return {
            key: round(sum(values) / len(values), 5)
            for key, values in metric_values.items()
            if values
        }

    def load_data(self):
        pass

    def evaluate(self):
        pass

    def summarize(self, summary: SummaryModel) -> SummaryModel:
        return summary
