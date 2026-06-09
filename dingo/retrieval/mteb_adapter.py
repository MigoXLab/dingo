"""
MTEB SearchProtocol adapter for SearchClient backends.

Wraps any SearchClient as an MTEB-compatible search model, bridging external
search APIs to MTEB's metric computation pipeline.

Usage:
    from dingo.retrieval import create_client
    from dingo.retrieval.mteb_adapter import SearchClientModel

    client = create_client("agentic", api_url="http://...")
    model = SearchClientModel(client, search_limit=100)

    import mteb
    tasks = mteb.get_tasks(tasks=["SciFact"])
    results = mteb.evaluate(model, tasks=tasks)
"""

from __future__ import annotations
import concurrent.futures
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from mteb.models.model_meta import ModelMeta
from tqdm import tqdm

from dingo.retrieval.eval_utils import normalize_title, resolve_hit
from dingo.retrieval.search_client import SearchClient, SearchResponse

if TYPE_CHECKING:
    from mteb.abstasks.task_metadata import TaskMetadata
    from mteb.types import CorpusDatasetType, EncodeKwargs, QueryDatasetType, RetrievalOutputType, TopRankedDocumentsType

logger = logging.getLogger(__name__)

IFIR_INSTRUCTION_TASKS = {"IFIRScifact", "IFIRNFCorpus"}
INSTRUCTION_COLUMNS = ("instruction", "instructions", "prompt")


def _task_uses_query_instructions(task_name: str) -> bool:
    return task_name in IFIR_INSTRUCTION_TASKS


def _get_query_column_values(queries: Any, column_name: str, total: int) -> list[Any]:
    try:
        values = queries[column_name]
    except Exception:
        return [None] * total

    values_list = list(values)
    if len(values_list) < total:
        values_list.extend([None] * (total - len(values_list)))
    return values_list[:total]


def _extract_query_instructions(queries: Any, total: int) -> list[str | None]:
    for column_name in INSTRUCTION_COLUMNS:
        values = _get_query_column_values(queries, column_name, total)
        if any(value not in (None, "") for value in values):
            return [
                str(value).strip() if value not in (None, "") else None
                for value in values
            ]
    return [None] * total


def _build_effective_query_text(
    task_name: str, query_text: str, instruction: str | None
) -> str:
    if not _task_uses_query_instructions(task_name) or not instruction:
        return query_text
    return f"Instruction: {instruction}\nQuery: {query_text}"


def _instruction_trace_fields(
    task_name: str,
    query_text: str,
    instruction: str | None,
    effective_query_text: str,
) -> dict[str, str]:
    if not instruction and effective_query_text == query_text:
        return {}

    fields: dict[str, str] = {"effective_query_text": effective_query_text}
    if instruction:
        fields["instruction"] = instruction
    return fields


# Workaround for mteb versions where confidence_scores crashes on empty input.
try:
    from mteb._evaluators import retrieval_metrics as _rm

    _orig_confidence_scores = _rm.confidence_scores

    def _safe_confidence_scores(sim_scores):
        if not sim_scores:
            return {"max": 0.0, "std": 0.0, "diff1": 0.0}
        return _orig_confidence_scores(sim_scores)

    _rm.confidence_scores = _safe_confidence_scores
except Exception:
    pass


class SearchClientModel:
    """MTEB SearchProtocol adapter for SearchClient backends."""

    def __init__(
        self,
        client: SearchClient,
        search_limit: int = 100,
        max_queries: int | None = None,
        max_workers: int = 1,
    ):
        self.client = client
        self.search_limit = search_limit
        self.max_queries = max_queries
        self.max_workers = max_workers

        self._title_to_ids: dict[str, list[str]] = defaultdict(list)
        self._corpus_ids: set[str] = set()
        self._corpus_size = 0
        self._collisions = 0
        self._search_traces: list[dict[str, Any]] = []
        self._relevant_docs_by_context: dict[
            tuple[str, str, str], dict[str, set[str]]
        ] = {}

        safe_name = client.name.replace(" ", "-")
        self._mteb_model_meta = ModelMeta(
            loader=lambda name, **kw: self,
            name=f"custom/{safe_name}",
            model_type=["dense"],
            languages=None,
            open_weights=False,
            revision=None,
            release_date=None,
            n_parameters=None,
            n_embedding_parameters=None,
            memory_usage_mb=None,
            embed_dim=None,
            license=None,
            max_tokens=None,
            reference=None,
            similarity_fn_name=None,
            framework=[],
            use_instructions=True,
            public_training_code=None,
            public_training_data=None,
            training_datasets=None,
        )

    @property
    def mteb_model_meta(self) -> ModelMeta:
        return self._mteb_model_meta

    def set_relevant_docs(
        self,
        task_name: str,
        hf_split: str,
        hf_subset: str,
        relevant_docs: dict[str, Any],
    ) -> None:
        """Attach qrels for richer debug traces.

        MTEB's SearchProtocol does not pass qrels into ``search()``, but Dingo's
        detailed traces are easier to inspect when mapped hits are annotated as
        relevant or not.
        """
        normalized: dict[str, set[str]] = {}
        for qid, docs in (relevant_docs or {}).items():
            if isinstance(docs, dict):
                normalized[str(qid)] = {
                    str(doc_id) for doc_id, score in docs.items() if score
                }
            else:
                normalized[str(qid)] = {str(doc_id) for doc_id in docs}
        self._relevant_docs_by_context[
            (task_name, hf_split, hf_subset)
        ] = normalized

    def index(
        self,
        corpus: "CorpusDatasetType",
        *,
        task_metadata: "TaskMetadata",
        hf_split: str,
        hf_subset: str,
        encode_kwargs: "EncodeKwargs",
        num_proc: int | None = None,
    ) -> None:
        self._title_to_ids.clear()
        self._corpus_ids.clear()
        count = 0
        for row in corpus:
            doc_id = str(row["id"])
            self._corpus_ids.add(doc_id)
            title = row.get("title", "")
            if not title:
                continue
            normalized = normalize_title(title)
            if normalized:
                self._title_to_ids[normalized].append(doc_id)
                count += 1

        self._corpus_size = count
        self._collisions = sum(
            1 for ids in self._title_to_ids.values() if len(ids) > 1
        )
        logger.info(
            f"TitleIndex built: {len(self._title_to_ids)} unique titles "
            f"from {count} docs ({self._collisions} collisions) "
            f"[task={task_metadata.name}]"
        )

    def search(
        self,
        queries: "QueryDatasetType",
        *,
        task_metadata: "TaskMetadata",
        hf_split: str,
        hf_subset: str,
        top_k: int,
        encode_kwargs: "EncodeKwargs",
        top_ranked: "TopRankedDocumentsType | None" = None,
        num_proc: int | None = None,
    ) -> "RetrievalOutputType":
        query_ids = list(queries["id"])
        query_texts = list(queries["text"])
        query_instructions = _extract_query_instructions(queries, len(query_ids))
        total = len(query_ids)

        if self.max_queries and total > self.max_queries:
            query_ids = query_ids[: self.max_queries]
            query_texts = query_texts[: self.max_queries]
            query_instructions = query_instructions[: self.max_queries]
            total = len(query_ids)

        results: dict[str, dict[str, float]] = {}
        errors = 0
        total_matched = 0
        query_details: list[dict[str, Any]] = []
        relevant_docs_by_qid = self._relevant_docs_by_context.get(
            (task_metadata.name, hf_split, hf_subset)
        )

        def _process_query(idx_qid_text):
            idx, qid, q_text, instruction = idx_qid_text
            effective_query_text = _build_effective_query_text(
                task_metadata.name, q_text, instruction
            )
            try:
                response = self.client.search(
                    effective_query_text, limit=self.search_limit
                )
            except Exception as e:
                error_resp = SearchResponse(
                    query=effective_query_text, results=[], response_time_ms=0.0,
                    status_code=0, error=str(e),
                )
                return (
                    idx,
                    qid,
                    q_text,
                    instruction,
                    effective_query_text,
                    error_resp,
                    None,
                    None,
                    None,
                    None,
                )

            if response.error:
                return (
                    idx,
                    qid,
                    q_text,
                    instruction,
                    effective_query_text,
                    response,
                    None,
                    None,
                    None,
                    None,
                )

            doc_scores: dict[str, float] = {}
            top_api_results: list[dict[str, Any]] = []
            relevant_doc_ids = (
                relevant_docs_by_qid.get(str(qid))
                if relevant_docs_by_qid is not None
                else None
            )
            mapping_stats: dict[str, int] = {
                "doc_id_exact": 0,
                "title_fallback": 0,
                "unmatched": 0,
            }

            for rank, paper in enumerate(response.results):
                hit = {"paper_id": paper.paper_id, "title": paper.title}
                resolved_id, src = resolve_hit(
                    hit, self._title_to_ids, self._corpus_ids
                )
                mapping_stats[src] = mapping_stats.get(src, 0) + 1
                top_api_results.append(
                    {
                        "rank": rank + 1,
                        "paper_id": paper.paper_id,
                        "title": paper.title,
                        "score": paper.score,
                        "resolved_corpus_id": resolved_id,
                        "mapping_source": src,
                        "is_relevant": (
                            bool(resolved_id and resolved_id in relevant_doc_ids)
                            if relevant_doc_ids is not None
                            else None
                        ),
                    }
                )
                if not resolved_id or resolved_id in doc_scores:
                    continue
                doc_scores[resolved_id] = 1.0 / (rank + 1)

            relevant_matched_count = (
                sum(1 for doc_id in doc_scores if doc_id in relevant_doc_ids)
                if relevant_doc_ids is not None
                else None
            )

            return (
                idx,
                qid,
                q_text,
                instruction,
                effective_query_text,
                response,
                doc_scores,
                top_api_results,
                mapping_stats,
                relevant_matched_count,
            )

        items = [
            (i, qid, qt, instruction)
            for i, (qid, qt, instruction) in enumerate(
                zip(query_ids, query_texts, query_instructions)
            )
        ]

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers
        ) as pool:
            futures = {pool.submit(_process_query, item): item for item in items}
            pbar = tqdm(
                total=total,
                desc=f"Searching {task_metadata.name}",
                unit="query",
            )
            for future in concurrent.futures.as_completed(futures):
                (
                    idx,
                    qid,
                    q_text,
                    instruction,
                    effective_query_text,
                    response,
                    doc_scores,
                    top_api_results,
                    mapping_stats,
                    relevant_matched_count,
                ) = future.result()

                if doc_scores is None:
                    errors += 1
                    logger.warning(
                        f"[{idx + 1}/{total}] {qid} ERROR: {response.error}"
                    )
                    results[qid] = {}
                    query_details.append(
                        {
                            "qid": qid,
                            "query_text": q_text,
                            **_instruction_trace_fields(
                                task_metadata.name,
                                q_text,
                                instruction,
                                effective_query_text,
                            ),
                            "error": response.error,
                            "response_time_ms": response.response_time_ms,
                            "api_results_count": 0,
                            "matched_count": 0,
                            "mapped_count": 0,
                            "relevant_matched_count": 0,
                            "relevant_total": 0,
                        }
                    )
                else:
                    results[qid] = doc_scores
                    total_matched += len(doc_scores)
                    matched_count = (
                        relevant_matched_count
                        if relevant_matched_count is not None
                        else len(doc_scores)
                    )
                    relevant_doc_ids = (
                        relevant_docs_by_qid.get(str(qid))
                        if relevant_docs_by_qid is not None
                        else None
                    )
                    query_details.append(
                        {
                            "qid": qid,
                            "query_text": q_text,
                            **_instruction_trace_fields(
                                task_metadata.name,
                                q_text,
                                instruction,
                                effective_query_text,
                            ),
                            "error": "",
                            "response_time_ms": response.response_time_ms,
                            "api_results_count": len(response.results),
                            "matched_count": matched_count,
                            "mapped_count": len(doc_scores),
                            "relevant_matched_count": relevant_matched_count,
                            "relevant_total": (
                                len(relevant_doc_ids)
                                if relevant_doc_ids is not None
                                else None
                            ),
                            "gold_doc_ids": (
                                sorted(relevant_doc_ids)
                                if relevant_doc_ids is not None
                                else None
                            ),
                            "top_api_results": top_api_results,
                            "retrieved_doc_ids": list(doc_scores.keys()),
                            "mapping_stats": mapping_stats,
                        }
                    )

                pbar.update(1)
            pbar.close()

        avg_matched = total_matched / total if total > 0 else 0
        logger.info(
            f"Search complete: {total} queries, {errors} errors, "
            f"avg {avg_matched:.1f} matched docs/query"
        )
        self._search_traces.append(
            {
                "task": task_metadata.name,
                "split": hf_split,
                "subset": hf_subset,
                "search_limit": self.search_limit,
                "max_queries": self.max_queries,
                "total_queries": total,
                "errors": errors,
                "avg_matched_docs_per_query": round(avg_matched, 4),
                "queries": query_details,
            }
        )

        return results

    def get_search_traces(self) -> list[dict[str, Any]]:
        return list(self._search_traces)
