"""
RetrievalExecutor — Evaluates search APIs against MTEB retrieval benchmarks.

Registered as ``Executor.exec_map["retrieval"]``. Uses the same InputArgs
configuration as other executors, reading retrieval-specific config from
``input_args.executor.retrieval``.

Supports an optional **open eval** phase (Exa-style LLM-as-Judge pointwise
grading) that runs after search and alongside MTEB closed-eval metrics.
"""

from __future__ import annotations
import concurrent.futures
import json
import logging
import os
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from dingo.config.input_args import InputArgs, OpenEvalArgs
from dingo.exec.base import Executor
from dingo.io import SummaryModel
from dingo.model.llm.llm_search_result_relevance import LLMSearchResultRelevance, RelevanceGrade, aggregate_grades
from dingo.retrieval.eval_utils import compute_query_metrics, make_output_dir, save_json
from dingo.retrieval.search_client import SearchResponse, create_client
from dingo.retrieval.tasks import resolve_builtin_task

if TYPE_CHECKING:
    from dingo.retrieval.mteb_adapter import SearchClientModel

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

RAW_API_METRICS_OF_INTEREST = [
    f"raw_api_{key}" for key in METRICS_OF_INTEREST if key != "main_score"
]


def _tqdm_or_none(iterable=None, **kwargs):
    """Return tqdm-wrapped iterable/progress bar if available, else fallback."""
    try:
        from tqdm.auto import tqdm
        return tqdm(iterable, **kwargs)
    except Exception:
        return iterable


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

    def _build_client(self) -> tuple[Any, dict[str, Any]]:
        """Create search client from retrieval args."""
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
        return client, client_kwargs

    def execute(self) -> SummaryModel:
        ra = self.retrieval_args
        if ra.input_queries:
            return self._execute_standalone_open_eval()

        task_names = [
            task.strip() for task in self.input_args.input_path.split(",")
            if task.strip()
        ]
        builtin_tasks = [
            (task_name, resolve_builtin_task(task_name))
            for task_name in task_names
        ]
        builtin_tasks = [item for item in builtin_tasks if item[1] is not None]
        if builtin_tasks:
            if len(task_names) != 1:
                raise ValueError(
                    "A bundled local task cannot currently be combined with other tasks"
                )
            task_name, task_path = builtin_tasks[0]
            return self._execute_builtin_qrels_eval(task_name, str(task_path))
        return self._execute_mteb()

    def _execute_builtin_qrels_eval(
        self,
        task_label: str,
        evalset_path: str,
    ) -> SummaryModel:
        """Evaluate API-ranked document IDs against a bundled labeled task.

        JSON files may contain either a top-level ``queries`` list or a list of
        query objects. JSONL is also accepted. Each query requires ``qid``,
        ``query``, and ``qrels`` (a list of relevant document IDs, or a mapping
        from document ID to binary relevance, 0 or 1).
        """
        ra = self.retrieval_args
        query_items, evalset_metadata = self._load_qrels_file(evalset_path)
        declared_name = evalset_metadata.get("name")
        if declared_name and declared_name != task_label:
            raise ValueError(
                f"Bundled task name mismatch: requested {task_label!r}, "
                f"dataset declares {declared_name!r}"
            )
        started_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if ra.max_queries and len(query_items) > ra.max_queries:
            query_items = query_items[:ra.max_queries]

        client, _ = self._build_client()
        output_dir = make_output_dir(
            explicit_dir=None,
            default_prefix=os.path.join(self.input_args.output_path, ra.backend),
        )

        def _search_item(index_item: tuple[int, dict[str, Any]]):
            index, item = index_item
            response = client.search(item["query"], limit=ra.limit)
            return index, item, response

        completed_rows: list[tuple[dict[str, Any], Any] | None] = [None] * len(query_items)
        with concurrent.futures.ThreadPoolExecutor(max_workers=ra.max_workers) as pool:
            futures = {
                pool.submit(_search_item, pair): pair[0]
                for pair in enumerate(query_items)
            }
            completed = concurrent.futures.as_completed(futures)
            completed = _tqdm_or_none(
                completed,
                total=len(futures),
                desc=f"Searching {task_label}",
                unit="query",
            ) or completed
            for future in completed:
                index = futures[future]
                try:
                    _, item, response = future.result()
                except Exception as exc:
                    item = query_items[index]
                    response = SearchResponse(
                        query=item["query"], results=[], response_time_ms=0.0,
                        status_code=0, error=str(exc),
                    )
                completed_rows[index] = (item, response)

        query_details: list[dict[str, Any]] = []
        errors = 0
        for row in completed_rows:
            if row is None:
                continue
            item, response = row
            gold_doc_ids = set(item["qrels"])
            ranked_doc_ids: list[str] = []
            seen_ids: set[str] = set()
            top_api_results: list[dict[str, Any]] = []
            for rank, paper in enumerate(response.results, start=1):
                paper_id = str(paper.paper_id or "").strip()
                if not paper_id:
                    metric_id = f"__missing_doc_id__{rank}"
                elif paper_id in seen_ids:
                    metric_id = f"__duplicate_doc_id__{rank}"
                else:
                    metric_id = paper_id
                    seen_ids.add(paper_id)
                ranked_doc_ids.append(metric_id)
                top_api_results.append({
                    "rank": rank,
                    "paper_id": paper_id,
                    "title": paper.title,
                    "abstract": paper.abstract,
                    "score": paper.score,
                    "is_relevant": paper_id in gold_doc_ids,
                })

            metrics = compute_query_metrics(ranked_doc_ids, gold_doc_ids)
            if response.error:
                errors += 1
            detail = {
                key: value for key, value in item.items()
                if key not in {"query", "qrels"}
            }
            detail.update({
                "query_text": item["query"],
                "gold_doc_ids": sorted(gold_doc_ids),
                "error": response.error,
                "status_code": response.status_code,
                "response_time_ms": response.response_time_ms,
                "api_results_count": len(response.results),
                "retrieved_doc_ids": ranked_doc_ids,
                "metrics": metrics,
                "top_api_results": top_api_results,
            })
            query_details.append(detail)

        overall_metrics = self._aggregate_custom_metrics(query_details)
        group_metrics: dict[str, dict[str, Any]] = {}
        groups = sorted({str(q.get("group")) for q in query_details if q.get("group")})
        for group in groups:
            group_metrics[group] = self._aggregate_custom_metrics(
                [q for q in query_details if str(q.get("group")) == group]
            )
        task_metrics = {**overall_metrics, "groups": group_metrics}
        all_results = {task_label: task_metrics}

        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        summary = SummaryModel(
            task_id=str(uuid.uuid4())[:8],
            task_name=self.input_args.task_name or "retrieval_eval",
            input_path=task_label,
            output_path=output_dir,
            create_time=started_at,
            finish_time=finished_at,
            score=overall_metrics.get("main_score", 0.0),
            total=len(query_details),
        )
        summary.metrics_score_stats = all_results
        config = {
            "mode": "builtin_qrels",
            "backend": ra.backend,
            "api_url": ra.api_url,
            "limit": ra.limit,
            "max_queries": ra.max_queries,
            "tasks": [task_label],
            "dataset_path": evalset_path,
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
            "evalset_metadata": evalset_metadata,
            "metrics": all_results,
        }
        save_json(summary_dict, output_dir, "summary.json")
        save_json({
            "config": config,
            "evalset_metadata": evalset_metadata,
            "results": all_results,
            "search_traces": [{
                "task": task_label,
                "mode": "builtin_qrels",
                "total_queries": len(query_details),
                "errors": errors,
                "queries": query_details,
            }],
        }, output_dir, "detailed_results.json")
        self.summary = summary
        return summary

    @staticmethod
    def _load_qrels_file(path: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if not os.path.isfile(path):
            raise ValueError(f"qrels file not found: {path}")
        with open(path, "r", encoding="utf-8-sig") as file:
            if path.lower().endswith((".jsonl", ".ndjson")):
                raw_items = [json.loads(line) for line in file if line.strip()]
                metadata: dict[str, Any] = {}
            else:
                payload = json.load(file)
                if isinstance(payload, dict):
                    raw_items = payload.get("queries")
                    metadata = {key: value for key, value in payload.items() if key != "queries"}
                else:
                    raw_items = payload
                    metadata = {}
        if not isinstance(raw_items, list) or not raw_items:
            raise ValueError("qrels file must contain a non-empty query list")

        normalized: list[dict[str, Any]] = []
        seen_qids: set[str] = set()
        for index, item in enumerate(raw_items, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"query item {index} must be an object")
            qid = str(item.get("qid") or "").strip()
            query = str(item.get("query") or "").strip()
            qrels = item.get("qrels")
            if isinstance(qrels, dict):
                # This dataset adapter uses binary judgments; reject graded labels
                # instead of silently computing binary NDCG for graded qrels.
                if any(not isinstance(value, (int, float)) or value not in (0, 1)
                       for value in qrels.values()):
                    raise ValueError("Bundled qrels support binary relevance (0 or 1) only")
                qrels = [doc_id for doc_id, relevance in qrels.items() if relevance == 1]
            if not qid or not query or not isinstance(qrels, list) or not qrels:
                raise ValueError(
                    f"query item {index} requires non-empty qid, query, and qrels"
                )
            if qid in seen_qids:
                raise ValueError(f"duplicate qid in qrels file: {qid}")
            seen_qids.add(qid)
            normalized.append({
                **item,
                "qid": qid,
                "query": query,
                "qrels": list(dict.fromkeys(str(doc_id).strip() for doc_id in qrels
                                            if doc_id is not None and str(doc_id).strip())),
            })
            if not normalized[-1]["qrels"]:
                raise ValueError(f"query item {index} has no valid qrels document IDs")
        return normalized, metadata

    @staticmethod
    def _aggregate_custom_metrics(query_details: list[dict[str, Any]]) -> dict[str, Any]:
        keys = [key for key in METRICS_OF_INTEREST if key != "main_score"]
        aggregated: dict[str, Any] = {"total_queries": len(query_details)}
        for key in keys:
            values = [q.get("metrics", {}).get(key) for q in query_details]
            values = [float(value) for value in values if value is not None]
            if values:
                aggregated[key] = round(sum(values) / len(values), 5)
        aggregated["main_score"] = aggregated.get("ndcg_at_10", 0.0)
        aggregated["errors"] = sum(1 for q in query_details if q.get("error"))
        if query_details:
            aggregated["avg_results_count"] = round(
                sum(float(q.get("api_results_count") or 0) for q in query_details)
                / len(query_details),
                5,
            )
        return aggregated

    def _execute_mteb(self) -> SummaryModel:
        """Standard MTEB closed-eval path, optionally followed by open eval."""
        import mteb

        from dingo.retrieval.mteb_adapter import SearchClientModel

        task_names = [
            t.strip() for t in self.input_args.input_path.split(",") if t.strip()
        ]
        if not task_names:
            raise ValueError("input_path must specify MTEB task name(s), e.g. 'SciFact'")

        ra = self.retrieval_args
        client, _ = self._build_client()
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
            input_args=self.input_args.to_dict(),
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
                task_metrics.update(
                    self._compute_raw_api_metrics_from_search_traces(
                        model.get_search_traces(),
                        task_name,
                    )
                )
                all_results[task_name] = task_metrics
            except Exception as e:
                logger.error(f"Task {task_name!r} failed: {e}", exc_info=True)
                task_metrics = self._compute_metrics_from_search_traces(
                    model.get_search_traces(),
                    task_name,
                )
                if task_metrics:
                    task_metrics.update(
                        self._compute_raw_api_metrics_from_search_traces(
                            model.get_search_traces(),
                            task_name,
                        )
                    )
                    logger.warning(
                        "Using search trace fallback metrics for failed task %r",
                        task_name,
                    )
                    all_results[task_name] = task_metrics
                continue

        oe_args = ra.open_eval
        if oe_args and oe_args.enabled:
            open_eval_metrics = self._run_open_eval(
                model.get_search_traces(), oe_args, task_names,
            )
            for tn, oe_metrics in open_eval_metrics.items():
                all_results.setdefault(tn, {}).update(oe_metrics)

        self._all_results = all_results
        summary.metrics_score_stats = all_results
        summary.total = sum(
            t.get("total_queries", 0)
            for trace in model.get_search_traces()
            for t in [trace]
        )
        summary.score = all_results.get(task_names[0], {}).get("main_score", 0.0) if task_names else 0.0
        summary.finish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        config: dict[str, Any] = {
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
        if oe_args and oe_args.enabled:
            config["open_eval"] = {
                "enabled": True,
                "model": oe_args.model,
                "top_k": oe_args.top_k,
                "aggregate": oe_args.aggregate,
                "prompt_mode": oe_args.prompt_mode,
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
            "input_args": summary.input_args,
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

    def _execute_standalone_open_eval(self) -> SummaryModel:
        """Pure open eval: search custom queries and grade with LLM judge.

        No MTEB corpus or gold labels needed. Reads queries from a JSONL file
        (each line: ``{"query": "...", "expected_criteria": "..."}``).
        """
        import json as _json

        ra = self.retrieval_args
        oe_args = ra.open_eval
        if not oe_args or not oe_args.enabled:
            raise ValueError(
                "open_eval must be enabled for standalone mode. "
                "Use --open-eval together with --input-queries."
            )

        queries_path = ra.input_queries
        with open(queries_path, "r", encoding="utf-8") as f:
            query_items = [_json.loads(line) for line in f if line.strip()]

        if ra.max_queries and len(query_items) > ra.max_queries:
            query_items = query_items[:ra.max_queries]

        logger.info(
            "Standalone open eval: %d queries from %s", len(query_items), queries_path,
        )

        client, _ = self._build_client()
        output_dir = make_output_dir(
            explicit_dir=None,
            default_prefix=os.path.join(self.input_args.output_path, ra.backend),
        )

        task_label = os.path.splitext(os.path.basename(queries_path))[0]

        grader = LLMSearchResultRelevance(
            model=oe_args.model,
            api_key=oe_args.key,
            api_url=oe_args.api_url,
            prompt_mode=oe_args.prompt_mode,
            expected_criteria=oe_args.expected_criteria,
        )

        all_grades: list[RelevanceGrade] = []
        search_traces: list[dict[str, Any]] = []
        query_details: list[dict[str, Any]] = []
        errors = 0

        query_iter = _tqdm_or_none(
            enumerate(query_items),
            total=len(query_items),
            desc="OpenEval queries",
            unit="query",
        ) or enumerate(query_items)

        for idx, item in query_iter:
            q_text = item.get("query", "")
            q_criteria = item.get("expected_criteria") or oe_args.expected_criteria
            if not q_text:
                continue

            try:
                response = client.search(q_text, limit=ra.limit)
            except Exception as e:
                logger.warning("Search failed for query %d: %s", idx, e)
                errors += 1
                continue

            top_results: list[dict[str, Any]] = []
            query_grades: list[RelevanceGrade] = []

            for rank, paper in enumerate(response.results[:oe_args.top_k]):
                grade = grader.grade(
                    query=q_text,
                    title=paper.title,
                    abstract=paper.abstract,
                    expected_criteria=q_criteria,
                )
                all_grades.append(grade)
                query_grades.append(grade)
                top_results.append({
                    "rank": rank + 1,
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "abstract": paper.abstract,
                    "score": paper.score,
                    "llm_grade": grade.to_dict(),
                })

            valid_scores = [g.score for g in query_grades if not g.error]
            q_mean = (
                sum(valid_scores) / len(valid_scores) if valid_scores else 0.0
            )

            query_details.append({
                "qid": str(idx),
                "query_text": q_text,
                "expected_criteria": q_criteria,
                "api_results_count": len(response.results),
                "graded_count": len(query_grades),
                "response_time_ms": response.response_time_ms,
                "open_eval_mean_score": round(q_mean, 5),
                "top_api_results": top_results,
            })

        trace = {
            "task": task_label,
            "mode": "standalone_open_eval",
            "queries_file": queries_path,
            "total_queries": len(query_details),
            "errors": errors,
            "queries": query_details,
        }
        search_traces.append(trace)

        oe_summary = aggregate_grades(all_grades, method=oe_args.aggregate)
        all_results: dict[str, Any] = {task_label: oe_summary.to_dict()}

        summary = SummaryModel(
            task_id=str(uuid.uuid4())[:8],
            task_name=self.input_args.task_name or "open_eval",
            input_path=queries_path,
            output_path=output_dir,
            create_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            input_args=self.input_args.to_dict(),
        )
        summary.metrics_score_stats = all_results
        summary.total = len(query_details)
        summary.score = (
            oe_summary.median_score
            if oe_args.aggregate == "median"
            else oe_summary.mean_score
        )
        summary.finish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        config: dict[str, Any] = {
            "mode": "standalone_open_eval",
            "backend": ra.backend,
            "api_url": ra.api_url,
            "limit": ra.limit,
            "input_queries": queries_path,
            "open_eval": {
                "enabled": True,
                "model": oe_args.model,
                "top_k": oe_args.top_k,
                "aggregate": oe_args.aggregate,
                "prompt_mode": oe_args.prompt_mode,
            },
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
            "input_args": summary.input_args,
        }
        save_json(summary_dict, output_dir, "summary.json")

        detailed = {
            "config": config,
            "results": all_results,
            "search_traces": search_traces,
        }
        save_json(detailed, output_dir, "detailed_results.json")

        logger.info(
            "Standalone open eval complete: mean_score=%.4f (%d queries). "
            "Results saved to: %s",
            oe_summary.mean_score, len(query_details), output_dir,
        )
        self.summary = summary
        return summary

    @staticmethod
    def _attach_relevant_docs(model: "SearchClientModel", tasks: list[Any]) -> None:
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

    @staticmethod
    def _run_open_eval(
        traces: list[dict[str, Any]],
        oe_args: OpenEvalArgs,
        task_names: list[str],
    ) -> dict[str, dict[str, Any]]:
        """Grade (query, result) pairs with an LLM judge.

        Updates trace entries in-place (adds ``llm_grade`` to each result)
        and returns ``{task_name: {open_eval_*: value}}`` metrics.
        """
        grader = LLMSearchResultRelevance(
            model=oe_args.model,
            api_key=oe_args.key,
            api_url=oe_args.api_url,
            prompt_mode=oe_args.prompt_mode,
            expected_criteria=oe_args.expected_criteria,
        )

        work_items: list[tuple[dict, dict, str]] = []
        for trace in traces:
            task = trace.get("task", "")
            for query_detail in trace.get("queries", []):
                q_text = query_detail.get("query_text", "")
                for result in query_detail.get("top_api_results", [])[:oe_args.top_k]:
                    work_items.append((query_detail, result, q_text))

        if not work_items:
            return {}

        logger.info(
            "Open eval: grading %d (query, result) pairs with model=%s",
            len(work_items), oe_args.model,
        )

        def _grade_item(item: tuple[dict, dict, str]):
            _, result, q_text = item
            grade = grader.grade(
                query=q_text,
                title=result.get("title", ""),
                abstract=result.get("abstract", ""),
            )
            result["llm_grade"] = grade.to_dict()
            return grade

        grades: list[RelevanceGrade] = [RelevanceGrade() for _ in range(len(work_items))]

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=oe_args.max_workers
        ) as pool:
            future_to_idx = {
                pool.submit(_grade_item, item): idx
                for idx, item in enumerate(work_items)
            }
            completed = concurrent.futures.as_completed(future_to_idx)
            completed = _tqdm_or_none(
                completed,
                total=len(future_to_idx),
                desc="OpenEval grading",
                unit="pair",
            ) or completed
            for future in completed:
                idx = future_to_idx[future]
                try:
                    grades[idx] = future.result()
                except Exception as e:
                    logger.warning("Open eval grading error: %s", e)
                    grades[idx] = RelevanceGrade(error=str(e))

        task_grades: dict[str, list[RelevanceGrade]] = {}
        idx = 0
        for trace in traces:
            task = trace.get("task", "")
            for query_detail in trace.get("queries", []):
                for _ in query_detail.get("top_api_results", [])[:oe_args.top_k]:
                    task_grades.setdefault(task, []).append(grades[idx])
                    idx += 1

        result_metrics: dict[str, dict[str, Any]] = {}
        for task, task_grade_list in task_grades.items():
            summary = aggregate_grades(task_grade_list, method=oe_args.aggregate)
            result_metrics[task] = summary.to_dict()
            logger.info(
                "Open eval for %s: mean_score=%.4f (%d pairs, %d errors)",
                task, summary.mean_score, summary.graded_pairs, summary.error_count,
            )

        return result_metrics

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

    @staticmethod
    def _compute_raw_api_metrics_from_search_traces(
        traces: list[dict[str, Any]],
        task_name: str,
    ) -> dict[str, float]:
        metric_values: dict[str, list[float]] = {}
        api_results_counts: list[float] = []
        for trace in traces:
            if trace.get("task") != task_name:
                continue
            for query in trace.get("queries", []):
                raw_metrics = query.get("raw_api_metrics") or {}
                for key in RAW_API_METRICS_OF_INTEREST:
                    if key not in raw_metrics:
                        continue
                    metric_values.setdefault(key, []).append(raw_metrics[key])
                if "api_results_count" in query:
                    api_results_counts.append(float(query.get("api_results_count") or 0))

        summary = {
            key: round(sum(values) / len(values), 5)
            for key, values in metric_values.items()
            if values
        }
        if api_results_counts:
            summary["raw_api_avg_results_count"] = round(
                sum(api_results_counts) / len(api_results_counts),
                5,
            )
        return summary

    def load_data(self):
        pass

    def evaluate(self):
        pass

    def summarize(self, summary: SummaryModel) -> SummaryModel:
        return summary
