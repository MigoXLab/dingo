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
            use_instructions=False,
            public_training_code=None,
            public_training_data=None,
            training_datasets=None,
        )

    @property
    def mteb_model_meta(self) -> ModelMeta:
        return self._mteb_model_meta

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
        total = len(query_ids)

        if self.max_queries and total > self.max_queries:
            query_ids = query_ids[: self.max_queries]
            query_texts = query_texts[: self.max_queries]
            total = len(query_ids)

        results: dict[str, dict[str, float]] = {}
        errors = 0
        total_matched = 0
        query_details: list[dict[str, Any]] = []

        def _process_query(idx_qid_text):
            idx, qid, q_text = idx_qid_text
            try:
                response = self.client.search(q_text, limit=self.search_limit)
            except Exception as e:
                error_resp = SearchResponse(
                    query=q_text, results=[], response_time_ms=0.0,
                    status_code=0, error=str(e),
                )
                return idx, qid, q_text, error_resp, None, None, None

            if response.error:
                return idx, qid, q_text, response, None, None, None

            doc_scores: dict[str, float] = {}
            top_api_results: list[dict[str, Any]] = []
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
                    }
                )
                if not resolved_id or resolved_id in doc_scores:
                    continue
                doc_scores[resolved_id] = 1.0 / (rank + 1)

            return idx, qid, q_text, response, doc_scores, top_api_results, mapping_stats

        items = [(i, qid, qt) for i, (qid, qt) in enumerate(zip(query_ids, query_texts))]

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
                idx, qid, q_text, response, doc_scores, top_api_results, mapping_stats = future.result()

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
                            "error": response.error,
                            "response_time_ms": response.response_time_ms,
                            "api_results_count": 0,
                            "matched_count": 0,
                        }
                    )
                else:
                    results[qid] = doc_scores
                    total_matched += len(doc_scores)
                    query_details.append(
                        {
                            "qid": qid,
                            "query_text": q_text,
                            "error": "",
                            "response_time_ms": response.response_time_ms,
                            "api_results_count": len(response.results),
                            "matched_count": len(doc_scores),
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
