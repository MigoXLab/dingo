"""
RetrievalExecutor — Evaluates search APIs against MTEB retrieval benchmarks.

Registered as ``Executor.exec_map["retrieval"]``. Uses the same InputArgs
configuration as other executors, reading retrieval-specific config from
``input_args.executor.retrieval``.

Architecture (unified with standard Dingo pipeline):
1. Search Phase: call SearchClient to produce search traces
2. Data Conversion: convert traces to standard Data rows (one per query)
3. Evaluation Phase: call registered evaluators (rule + LLM) via Model registry
4. Output: standard ResultInfo / SummaryModel + search_traces for audit
"""

from __future__ import annotations
import logging
import os
import uuid
from datetime import datetime
from typing import Any

from dingo.config.input_args import EvalPiplineConfig, EvaluatorLLMArgs, InputArgs
from dingo.exec.base import Executor
from dingo.io import Data, ResultInfo, SummaryModel
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
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

RAW_API_METRICS_OF_INTEREST = [
    f"raw_api_{key}" for key in METRICS_OF_INTEREST if key != "main_score"
]

_RULE_EVALUATOR_NAMES = [
    "RuleNDCG", "RuleMRR", "RuleRecall", "RulePrecision", "RuleMAP", "RuleHitRate",
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
    """Evaluates search APIs against MTEB retrieval benchmarks.

    Uses registered evaluators (rule + LLM) from the Dingo model registry
    for all metric computation.
    """

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

    # ------------------------------------------------------------------
    # Data conversion: search traces -> standard Data rows
    # ------------------------------------------------------------------

    @staticmethod
    def _traces_to_data_rows(
        traces: list[dict[str, Any]],
        task_name: str = "",
    ) -> list[Data]:
        """Convert search traces to standard Data rows (one per query).

        Each Data row contains:
        - data_id: {task_name}_{qid}
        - prompt: the query text
        - search_results: list of result dicts from the trace
        - reference: list of gold doc IDs (from trace's gold_doc_ids)
        - expected_criteria: from query-level if present
        """
        data_rows: list[Data] = []
        for trace in traces:
            t_name = trace.get("task", task_name)
            for query_detail in trace.get("queries", []):
                if query_detail.get("error"):
                    continue

                qid = query_detail.get("qid", "")
                data_id = f"{t_name}_{qid}" if t_name else str(qid)

                search_results = query_detail.get("top_api_results", [])
                gold_doc_ids = query_detail.get("gold_doc_ids", []) or []
                expected_criteria = query_detail.get("expected_criteria")

                row = Data(
                    data_id=data_id,
                    prompt=query_detail.get("query_text", ""),
                    search_results=search_results,
                    reference=gold_doc_ids,
                )
                if expected_criteria:
                    row.expected_criteria = expected_criteria

                data_rows.append(row)

        return data_rows

    # ------------------------------------------------------------------
    # Evaluator auto-configuration
    # ------------------------------------------------------------------

    def _build_evaluator_configs(self) -> list[EvalPiplineConfig]:
        """Auto-configure evaluators based on retrieval mode.

        - If gold labels are available (MTEB closed eval): add rule IR evaluators
        - If open_eval is enabled: add LLMSearchResultRelevance
        """
        configs: list[EvalPiplineConfig] = []
        ra = self.retrieval_args
        oe_args = ra.open_eval

        # Rule evaluators for IR metrics (always added for MTEB mode)
        if not ra.input_queries:
            for name in _RULE_EVALUATOR_NAMES:
                if name in Model.rule_name_map:
                    configs.append(EvalPiplineConfig(name=name))

        # LLM evaluator for open eval
        if oe_args and oe_args.enabled:
            extra_kwargs: dict[str, Any] = {
                "prompt_mode": oe_args.prompt_mode,
                "top_k": oe_args.top_k,
            }
            if oe_args.expected_criteria:
                extra_kwargs["expected_criteria"] = oe_args.expected_criteria
            llm_config = EvaluatorLLMArgs(
                model=oe_args.model,
                key=oe_args.key,
                api_url=oe_args.api_url,
                **extra_kwargs,
            )
            configs.append(EvalPiplineConfig(
                name="LLMSearchResultRelevance",
                config=llm_config,
            ))

        return configs

    # ------------------------------------------------------------------
    # Evaluation loop (uses registered evaluators)
    # ------------------------------------------------------------------

    def _evaluate_data_rows(
        self,
        data_rows: list[Data],
        eval_configs: list[EvalPiplineConfig],
    ) -> list[ResultInfo]:
        """Run registered evaluators on each Data row, producing ResultInfo list."""
        Model.load_model()
        results: list[ResultInfo] = []

        rule_configs = [c for c in eval_configs if c.name in Model.rule_name_map]
        llm_configs = [c for c in eval_configs if c.name in Model.llm_name_map]

        progress = _tqdm_or_none(
            data_rows, total=len(data_rows), desc="Evaluating queries", unit="query"
        ) or data_rows

        for data in progress:
            result_info = ResultInfo(
                dingo_id=str(getattr(data, "data_id", "")),
                raw_data=data.to_dict(),
            )
            eval_details: list[EvalDetail] = []

            # Run rule evaluators
            for ec in rule_configs:
                model_cls = Model.rule_name_map[ec.name]
                model = model_cls()
                if ec.config:
                    Model.set_config_rule(model, ec.config)
                    Model.set_config_rule(model_cls, ec.config)
                detail = model.eval(data)
                eval_details.append(detail)
                if detail.status:
                    result_info.eval_status = True

            # Run LLM evaluators
            for ec in llm_configs:
                model_cls = Model.llm_name_map[ec.name]
                model = model_cls()
                if ec.config:
                    Model.set_config_llm(model, ec.config)
                    Model.set_config_llm(model_cls, ec.config)
                detail = model.eval(data)
                eval_details.append(detail)
                if detail.status:
                    result_info.eval_status = True

            result_info.eval_details = {"retrieval": eval_details}
            results.append(result_info)

        return results

    def _aggregate_results(
        self, results: list[ResultInfo], summary: SummaryModel
    ) -> SummaryModel:
        """Aggregate ResultInfo list into SummaryModel using standard methods."""
        for result_info in results:
            for field_key, eval_details in result_info.eval_details.items():
                if field_key not in summary.type_ratio:
                    summary.type_ratio[field_key] = {}

                label_set = set()
                for eval_detail in eval_details:
                    if eval_detail.score is not None and eval_detail.metric:
                        summary.add_metric_score(
                            field_key, eval_detail.metric, eval_detail.score
                        )
                    label_list = eval_detail.label if eval_detail.label else []
                    for label in label_list:
                        label_set.add(label)

                for label in label_set:
                    summary.type_ratio[field_key].setdefault(label, 0)
                    summary.type_ratio[field_key][label] += 1

            if result_info.eval_status:
                summary.num_bad += 1
            else:
                summary.num_good += 1
            summary.total += 1

        summary.calculate_metrics_score_averages()
        return summary

    # ------------------------------------------------------------------
    # Main execution paths
    # ------------------------------------------------------------------

    def execute(self) -> SummaryModel:
        ra = self.retrieval_args
        if ra.input_queries:
            return self._execute_standalone_open_eval()
        return self._execute_mteb()

    def _execute_mteb(self) -> SummaryModel:
        """Standard MTEB closed-eval path, optionally followed by open eval."""
        import mteb

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
        )

        # --- Search Phase ---
        for task_name in task_names:
            logger.info(f"Starting evaluation on task: {task_name}")
            tasks = mteb.get_tasks(tasks=[task_name])
            if not tasks:
                logger.warning(f"Task {task_name!r} not found in MTEB, skipping")
                continue

            try:
                self._attach_relevant_docs(model, tasks)
                mteb.evaluate(
                    model,
                    tasks=tasks,
                    overwrite_strategy="always",
                )
            except Exception as e:
                logger.error(f"Task {task_name!r} search phase failed: {e}", exc_info=True)
                continue

        # --- Data Conversion ---
        traces = model.get_search_traces()
        data_rows = self._traces_to_data_rows(traces)

        if not data_rows:
            logger.warning("No data rows produced from search traces")
            summary.finish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.summary = summary
            return summary

        # --- Evaluation Phase (via registered evaluators) ---
        eval_configs = self._build_evaluator_configs()
        results = self._evaluate_data_rows(data_rows, eval_configs)
        summary = self._aggregate_results(results, summary)

        # Compute supplementary raw API metrics (pre-corpus-resolution, for debugging)
        raw_api_metrics = {}
        for task_name in task_names:
            raw = self._compute_raw_api_metrics_from_search_traces(traces, task_name)
            if raw:
                raw_api_metrics[task_name] = raw

        # --- Output ---
        summary.score = self._compute_primary_score(summary)
        summary.finish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        oe_args = ra.open_eval
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
            "metrics": summary.metrics_score_stats,
            "raw_api_metrics": raw_api_metrics,
        }
        save_json(summary_dict, output_dir, "summary.json")

        detailed = {
            "config": config,
            "metrics": summary.metrics_score_stats,
            "raw_api_metrics": raw_api_metrics,
            "search_traces": traces,
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

        # --- Search Phase ---
        search_traces: list[dict[str, Any]] = []
        query_details: list[dict[str, Any]] = []
        errors = 0

        query_iter = _tqdm_or_none(
            enumerate(query_items),
            total=len(query_items),
            desc="Searching queries",
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
            for rank, paper in enumerate(response.results[:oe_args.top_k]):
                top_results.append({
                    "rank": rank + 1,
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "abstract": paper.abstract,
                    "score": paper.score,
                })

            query_details.append({
                "qid": str(idx),
                "query_text": q_text,
                "expected_criteria": q_criteria,
                "api_results_count": len(response.results),
                "response_time_ms": response.response_time_ms,
                "top_api_results": top_results,
                "gold_doc_ids": [],
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

        # --- Data Conversion ---
        data_rows = self._traces_to_data_rows(search_traces, task_name=task_label)

        if not data_rows:
            logger.warning("No data rows from standalone open eval search")
            summary = SummaryModel(
                task_id=str(uuid.uuid4())[:8],
                task_name=self.input_args.task_name or "open_eval",
                input_path=queries_path,
                output_path=output_dir,
            )
            summary.finish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.summary = summary
            return summary

        # --- Evaluation Phase ---
        eval_configs = self._build_evaluator_configs()
        results = self._evaluate_data_rows(data_rows, eval_configs)

        summary = SummaryModel(
            task_id=str(uuid.uuid4())[:8],
            task_name=self.input_args.task_name or "open_eval",
            input_path=queries_path,
            output_path=output_dir,
            create_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        summary = self._aggregate_results(results, summary)
        summary.score = self._compute_primary_score(summary)
        summary.finish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # --- Output ---
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
            "metrics": summary.metrics_score_stats,
        }
        save_json(summary_dict, output_dir, "summary.json")

        detailed = {
            "config": config,
            "metrics": summary.metrics_score_stats,
            "search_traces": search_traces,
        }
        save_json(detailed, output_dir, "detailed_results.json")

        logger.info(
            "Standalone open eval complete: %d queries evaluated. "
            "Results saved to: %s",
            len(data_rows), output_dir,
        )
        self.summary = summary
        return summary

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_primary_score(summary: SummaryModel) -> float:
        """Pick the primary score from metrics for the summary."""
        for field_key, metrics in summary.metrics_score_stats.items():
            # Prefer NDCG if available (closed eval)
            if "RuleNDCG" in metrics:
                return metrics["RuleNDCG"].get("score_average", 0.0)
            # Fall back to LLM relevance score (open eval)
            if "LLMSearchResultRelevance" in metrics:
                return metrics["LLMSearchResultRelevance"].get("score_average", 0.0)
        return 0.0

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

    @staticmethod
    def _compute_raw_api_metrics_from_search_traces(
        traces: list[dict[str, Any]],
        task_name: str,
    ) -> dict[str, float]:
        """Compute supplementary metrics from raw API results (pre-corpus-resolution)."""
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
