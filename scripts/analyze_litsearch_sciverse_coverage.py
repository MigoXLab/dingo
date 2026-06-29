#!/usr/bin/env python
"""Check retrieval benchmark gold-document coverage in Sciverse meta-search.

The script loads local MTEB retrieval dataset files, searches each unique gold
corpus document by its title through the Sciverse meta-search API, and writes
detailed per-document/per-qrel coverage reports.

Example:
  SCIVERSE_API_TOKEN=... python scripts/analyze_litsearch_sciverse_coverage.py \
    --dataset LitSearchRetrieval \
    --api-url https://api.sciverse.space \
    --page-size 25 \
    --output-dir outputs/litsearch_sciverse_coverage

  SCIVERSE_API_TOKEN=... python scripts/analyze_litsearch_sciverse_coverage.py \
    --dataset SciFact \
    --api-url https://api.sciverse.space \
    --page-size 25 \
    --max-workers 4 \
    --rate-limit 0.25 \
    --output-dir outputs/scifact_sciverse_coverage
"""

from __future__ import annotations
import argparse
import csv
import json
import os
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd
from datasets import Dataset

from dingo.retrieval.backends.agentic import MetaSearchClient
from dingo.retrieval.eval_utils import normalize_title

DEFAULT_LITSEARCH_CACHE = (
    Path.home()
    / ".cache/huggingface/datasets/mteb___lit_search_retrieval/default/0.0.0/data"
)
DEFAULT_SCIFACT_CACHE = (
    Path.home()
    / ".cache/huggingface/datasets/mteb___scifact"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze retrieval benchmark gold-document coverage in Sciverse meta-search."
    )
    parser.add_argument(
        "--dataset",
        default="LitSearchRetrieval",
        choices=["LitSearchRetrieval", "SciFact"],
        help="Dataset to analyze.",
    )
    parser.add_argument("--api-url", default="https://api.sciverse.space")
    parser.add_argument(
        "--api-token",
        default=os.environ.get("SCIVERSE_API_TOKEN"),
        help="Sciverse API token. Prefer SCIVERSE_API_TOKEN to avoid shell history leaks.",
    )
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--rate-limit", type=float, default=1.0)
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Concurrent meta-search requests. Default 1 keeps the old serial behavior.",
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--max-docs", type=int, default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--cache-file", default=None)
    parser.add_argument(
        "--title-similarity-threshold",
        type=float,
        default=1.0,
        help=(
            "Use best_title_similarity >= threshold as covered. "
            "Default 1.0 keeps strict exact-title behavior."
        ),
    )
    parser.add_argument(
        "--mteb-data-dir",
        default=None,
        help="Override local dataset cache path.",
    )
    parser.add_argument("--fresh", action="store_true", help="Ignore existing cache file.")
    return parser.parse_args()


def load_litsearch(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    queries_path = data_dir / "queries/test-00000-of-00001.parquet"
    qrels_path = data_dir / "qrels/test-00000-of-00001.parquet"
    corpus_path = data_dir / "corpus/test-00000-of-00001.parquet"
    missing = [
        str(path)
        for path in (queries_path, qrels_path, corpus_path)
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError(f"Missing LitSearch parquet files: {missing}")
    return (
        pd.read_parquet(queries_path),
        pd.read_parquet(qrels_path),
        pd.read_parquet(corpus_path),
    )


def _latest_cache_revision(base: Path, config: str) -> Path:
    config_dir = base / config / "0.0.0"
    if not config_dir.exists():
        raise FileNotFoundError(f"Missing dataset cache directory: {config_dir}")
    revisions = [path for path in config_dir.iterdir() if path.is_dir()]
    if not revisions:
        raise FileNotFoundError(f"No cached revisions under: {config_dir}")
    return max(revisions, key=lambda path: path.stat().st_mtime)


def _read_arrow_df(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing Arrow file: {path}")
    return Dataset.from_file(str(path)).to_pandas()


def load_scifact(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    corpus_dir = _latest_cache_revision(data_dir, "corpus")
    queries_dir = _latest_cache_revision(data_dir, "queries")
    default_dir = _latest_cache_revision(data_dir, "default")
    corpus_path = corpus_dir / "scifact-corpus.arrow"
    queries_path = queries_dir / "scifact-queries.arrow"
    qrels_path = default_dir / "scifact-test.arrow"
    return (
        _read_arrow_df(queries_path),
        _read_arrow_df(qrels_path),
        _read_arrow_df(corpus_path),
    )


def default_data_dir(dataset: str) -> Path:
    if dataset == "SciFact":
        return DEFAULT_SCIFACT_CACHE
    return DEFAULT_LITSEARCH_CACHE


def load_dataset_files(dataset: str, data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if dataset == "SciFact":
        return load_scifact(data_dir)
    return load_litsearch(data_dir)


def result_to_dict(result: Any, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "paper_id": result.paper_id,
        "title": result.title,
        "score": result.score,
        "raw": result.raw,
    }


def analyze_hit(gold_title: str, results: list[Any]) -> dict[str, Any]:
    gold_norm = normalize_title(gold_title)
    exact_matches: list[dict[str, Any]] = []
    best: dict[str, Any] = {
        "rank": None,
        "paper_id": "",
        "title": "",
        "score": None,
        "similarity": 0.0,
    }

    for rank, result in enumerate(results, start=1):
        title = result.title or ""
        title_norm = normalize_title(title)
        similarity = (
            SequenceMatcher(None, gold_norm, title_norm).ratio()
            if gold_norm and title_norm
            else 0.0
        )
        if similarity > best["similarity"]:
            best = {
                "rank": rank,
                "paper_id": result.paper_id,
                "title": title,
                "score": result.score,
                "similarity": similarity,
            }
        if gold_norm and title_norm == gold_norm:
            exact_matches.append(result_to_dict(result, rank))

    first_exact = exact_matches[0] if exact_matches else None
    return {
        "covered_exact_title": bool(first_exact),
        "exact_match_rank": first_exact["rank"] if first_exact else None,
        "exact_match_paper_id": first_exact["paper_id"] if first_exact else "",
        "exact_match_title": first_exact["title"] if first_exact else "",
        "best_title_similarity": best["similarity"],
        "best_match_rank": best["rank"],
        "best_match_paper_id": best["paper_id"],
        "best_match_title": best["title"],
        "top_results": [result_to_dict(result, i) for i, result in enumerate(results, start=1)],
    }


def load_cache(path: Path, fresh: bool) -> dict[str, Any]:
    if fresh or not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class ThreadSafeRateLimiter:
    def __init__(self, interval_seconds: float) -> None:
        self.interval_seconds = max(0.0, float(interval_seconds))
        self._lock = threading.Lock()
        self._last_request_time = 0.0

    def wait(self) -> None:
        if self.interval_seconds <= 0:
            return
        with self._lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.interval_seconds:
                time.sleep(self.interval_seconds - elapsed)
            self._last_request_time = time.monotonic()


def search_gold_title(
    *,
    api_url: str,
    api_token: str,
    timeout: float,
    page_size: int,
    corpus_id: str,
    gold_title: str,
    rate_limiter: ThreadSafeRateLimiter,
) -> dict[str, Any]:
    client = MetaSearchClient(
        api_url=api_url,
        api_token=api_token,
        timeout=timeout,
        rate_limit=0,
    )
    rate_limiter.wait()
    response = client.search(gold_title, limit=page_size)
    hit_info = analyze_hit(gold_title, response.results)
    return {
        "corpus_id": corpus_id,
        "gold_title": gold_title,
        "error": response.error or "",
        "response_time_ms": response.response_time_ms,
        "api_results_count": len(response.results),
        "page_size": page_size,
        **hit_info,
    }


def summarize(
    doc_rows: list[dict[str, Any]],
    qrel_rows: list[dict[str, Any]],
    queries_df: pd.DataFrame,
    title_similarity_threshold: float = 1.0,
) -> dict[str, Any]:
    rank_counter = Counter()
    fuzzy_counter = Counter()
    for row in doc_rows:
        if row["covered_exact_title"]:
            rank = row["exact_match_rank"]
            if rank <= 1:
                rank_counter["at_1"] += 1
            if rank <= 3:
                rank_counter["at_3"] += 1
            if rank <= 5:
                rank_counter["at_5"] += 1
            if rank <= 10:
                rank_counter["at_10"] += 1
            if rank <= 25:
                rank_counter["at_25"] += 1
        sim = row["best_title_similarity"]
        if sim >= 0.99:
            fuzzy_counter["gte_0.99"] += 1
        if sim >= 0.95:
            fuzzy_counter["gte_0.95"] += 1
        if sim >= 0.90:
            fuzzy_counter["gte_0.90"] += 1

    covered_by_doc_exact = {
        row["corpus_id"]: bool(row["covered_exact_title"]) for row in doc_rows
    }
    covered_by_doc_threshold = {
        row["corpus_id"]: (
            bool(row["covered_exact_title"])
            or float(row.get("best_title_similarity", 0.0)) >= title_similarity_threshold
        )
        for row in doc_rows
    }
    qid_to_doc_covered_exact: dict[str, list[bool]] = {}
    qid_to_doc_covered_threshold: dict[str, list[bool]] = {}
    for row in qrel_rows:
        qid_to_doc_covered_exact.setdefault(row["qid"], []).append(
            covered_by_doc_exact.get(row["corpus_id"], False)
        )
        qid_to_doc_covered_threshold.setdefault(row["qid"], []).append(
            covered_by_doc_threshold.get(row["corpus_id"], False)
        )

    query_any_exact = sum(
        1 for values in qid_to_doc_covered_exact.values() if any(values)
    )
    query_all_exact = sum(
        1 for values in qid_to_doc_covered_exact.values() if all(values)
    )
    query_any_threshold = sum(
        1 for values in qid_to_doc_covered_threshold.values() if any(values)
    )
    query_all_threshold = sum(
        1 for values in qid_to_doc_covered_threshold.values() if all(values)
    )
    empty_gold_title = sum(1 for row in doc_rows if row["error"] == "empty_gold_title")
    errored = sum(
        1
        for row in doc_rows
        if row["error"] and row["error"] not in {"empty_gold_title", "missing_from_local_corpus"}
    )
    verifiable_docs = [row for row in doc_rows if row["error"] != "empty_gold_title"]
    verifiable_doc_ids = {row["corpus_id"] for row in verifiable_docs}
    total_docs = len(doc_rows)
    total_qrels = len(qrel_rows)
    total_queries = len(queries_df)
    covered_docs_exact = sum(1 for row in doc_rows if row["covered_exact_title"])
    covered_docs_threshold = sum(
        1 for row in doc_rows if covered_by_doc_threshold.get(row["corpus_id"], False)
    )
    covered_qrels_exact = sum(
        1
        for row in qrel_rows
        if covered_by_doc_exact.get(row["corpus_id"], False)
    )
    covered_qrels_threshold = sum(
        1
        for row in qrel_rows
        if covered_by_doc_threshold.get(row["corpus_id"], False)
    )
    verifiable_qrels = sum(1 for row in qrel_rows if row["corpus_id"] in verifiable_doc_ids)

    return {
        "total_queries": total_queries,
        "total_qrels": total_qrels,
        "unique_gold_docs": total_docs,
        "api_errors": errored,
        "empty_gold_title_docs": empty_gold_title,
        "verifiable_unique_gold_docs": len(verifiable_docs),
        "title_similarity_threshold": title_similarity_threshold,
        "covered_unique_gold_docs_exact_title": covered_docs_exact,
        "covered_unique_gold_docs_exact_title_rate": (
            covered_docs_exact / total_docs if total_docs else 0
        ),
        "covered_verifiable_unique_gold_docs_exact_title_rate": (
            covered_docs_exact / len(verifiable_docs) if verifiable_docs else 0
        ),
        "covered_qrels_exact_title": covered_qrels_exact,
        "covered_qrels_exact_title_rate": (
            covered_qrels_exact / total_qrels if total_qrels else 0
        ),
        "covered_verifiable_qrels_exact_title_rate": (
            covered_qrels_exact / verifiable_qrels if verifiable_qrels else 0
        ),
        # Backward compatible aliases (exact-title coverage semantics).
        "queries_with_any_gold_doc_covered": query_any_exact,
        "queries_with_any_gold_doc_covered_rate": (
            query_any_exact / total_queries if total_queries else 0
        ),
        "queries_with_all_gold_docs_covered": query_all_exact,
        "queries_with_all_gold_docs_covered_rate": (
            query_all_exact / total_queries if total_queries else 0
        ),
        "queries_with_any_gold_doc_covered_exact_title": query_any_exact,
        "queries_with_any_gold_doc_covered_exact_title_rate": (
            query_any_exact / total_queries if total_queries else 0
        ),
        "queries_with_all_gold_docs_covered_exact_title": query_all_exact,
        "queries_with_all_gold_docs_covered_exact_title_rate": (
            query_all_exact / total_queries if total_queries else 0
        ),
        "covered_unique_gold_docs_at_similarity_threshold": covered_docs_threshold,
        "covered_unique_gold_docs_at_similarity_threshold_rate": (
            covered_docs_threshold / total_docs if total_docs else 0
        ),
        "missing_unique_gold_docs_at_similarity_threshold": (
            total_docs - covered_docs_threshold
        ),
        "covered_qrels_at_similarity_threshold": covered_qrels_threshold,
        "covered_qrels_at_similarity_threshold_rate": (
            covered_qrels_threshold / total_qrels if total_qrels else 0
        ),
        "missing_qrels_at_similarity_threshold": (
            total_qrels - covered_qrels_threshold
        ),
        "queries_with_any_gold_doc_covered_at_similarity_threshold": query_any_threshold,
        "queries_with_any_gold_doc_covered_at_similarity_threshold_rate": (
            query_any_threshold / total_queries if total_queries else 0
        ),
        "queries_with_all_gold_docs_covered_at_similarity_threshold": query_all_threshold,
        "queries_with_all_gold_docs_covered_at_similarity_threshold_rate": (
            query_all_threshold / total_queries if total_queries else 0
        ),
        "exact_title_rank_counts": dict(rank_counter),
        "best_title_similarity_counts": dict(fuzzy_counter),
        "page_size": doc_rows[0]["page_size"] if doc_rows else None,
    }


def main() -> None:
    args = parse_args()
    if not args.api_token:
        raise SystemExit(
            "Missing API token. Set SCIVERSE_API_TOKEN or pass --api-token."
        )

    dataset_slug = args.dataset.lower()
    output_dir = args.output_dir or f"outputs/{dataset_slug}_sciverse_coverage"
    run_dir = Path(output_dir) / datetime.now().strftime("%Y%m%d-%H%M%S")
    cache_path = (
        Path(args.cache_file)
        if args.cache_file
        else Path(output_dir) / f"{dataset_slug}_gold_meta_search_cache.json"
    )

    data_dir = Path(args.mteb_data_dir) if args.mteb_data_dir else default_data_dir(args.dataset)
    queries_df, qrels_df, corpus_df = load_dataset_files(args.dataset, data_dir)
    query_text_by_id = dict(zip(queries_df["_id"].astype(str), queries_df["text"].astype(str)))
    corpus = corpus_df.set_index(corpus_df["_id"].astype(str), drop=False)

    unique_gold_ids = list(dict.fromkeys(qrels_df["corpus-id"].astype(str).tolist()))
    if args.max_docs:
        unique_gold_ids = unique_gold_ids[: args.max_docs]

    cache = load_cache(cache_path, args.fresh)
    doc_by_id: dict[str, dict[str, Any]] = {}
    pending: list[tuple[str, str]] = []

    for corpus_id in unique_gold_ids:
        if corpus_id not in corpus.index:
            doc_by_id[corpus_id] = {
                "corpus_id": corpus_id,
                "gold_title": "",
                "error": "missing_from_local_corpus",
                "response_time_ms": 0.0,
                "api_results_count": 0,
                "page_size": args.page_size,
                "covered_exact_title": False,
                "exact_match_rank": None,
                "exact_match_paper_id": "",
                "exact_match_title": "",
                "best_title_similarity": 0.0,
                "best_match_rank": None,
                "best_match_paper_id": "",
                "best_match_title": "",
            }
            continue

        gold_title = str(corpus.loc[corpus_id]["title"] or "").strip()
        if not gold_title:
            cached = {
                "corpus_id": corpus_id,
                "gold_title": gold_title,
                "error": "empty_gold_title",
                "response_time_ms": 0.0,
                "api_results_count": 0,
                "page_size": args.page_size,
                "covered_exact_title": False,
                "exact_match_rank": None,
                "exact_match_paper_id": "",
                "exact_match_title": "",
                "best_title_similarity": 0.0,
                "best_match_rank": None,
                "best_match_paper_id": "",
                "best_match_title": "",
                "top_results": [],
            }
            cache[corpus_id] = cached
            save_json(cache_path, cache)
        else:
            cached = cache.get(corpus_id)
            if cached is None:
                pending.append((corpus_id, gold_title))
                continue

        doc_by_id[corpus_id] = (
            {key: value for key, value in cached.items() if key != "top_results"}
        )

    if pending:
        max_workers = max(1, int(args.max_workers))
        rate_limiter = ThreadSafeRateLimiter(args.rate_limit)
        print(
            f"searching {len(pending)} uncached gold docs "
            f"(max_workers={max_workers}, rate_limit={args.rate_limit}s)"
        )
        completed = len(unique_gold_ids) - len(pending)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    search_gold_title,
                    api_url=args.api_url,
                    api_token=args.api_token,
                    timeout=args.timeout,
                    page_size=args.page_size,
                    corpus_id=corpus_id,
                    gold_title=gold_title,
                    rate_limiter=rate_limiter,
                ): corpus_id
                for corpus_id, gold_title in pending
            }
            for future in as_completed(futures):
                corpus_id = futures[future]
                try:
                    cached = future.result()
                except Exception as e:
                    cached = {
                        "corpus_id": corpus_id,
                        "gold_title": dict(pending).get(corpus_id, ""),
                        "error": str(e),
                        "response_time_ms": 0.0,
                        "api_results_count": 0,
                        "page_size": args.page_size,
                        "covered_exact_title": False,
                        "exact_match_rank": None,
                        "exact_match_paper_id": "",
                        "exact_match_title": "",
                        "best_title_similarity": 0.0,
                        "best_match_rank": None,
                        "best_match_paper_id": "",
                        "best_match_title": "",
                        "top_results": [],
                    }
                cache[corpus_id] = cached
                save_json(cache_path, cache)
                doc_by_id[corpus_id] = {
                    key: value for key, value in cached.items() if key != "top_results"
                }
                completed += 1
                if completed % 25 == 0 or completed == len(unique_gold_ids):
                    print(f"processed {completed}/{len(unique_gold_ids)} gold docs")
    else:
        print(f"processed {len(unique_gold_ids)}/{len(unique_gold_ids)} gold docs")

    doc_rows = [doc_by_id[corpus_id] for corpus_id in unique_gold_ids]
    qrel_rows: list[dict[str, Any]] = []
    for row in qrels_df.to_dict("records"):
        qid = str(row["query-id"])
        corpus_id = str(row["corpus-id"])
        doc = doc_by_id.get(corpus_id, {})
        qrel_rows.append(
            {
                "qid": qid,
                "query_text": query_text_by_id.get(qid, ""),
                "corpus_id": corpus_id,
                "score": row["score"],
                "gold_title": doc.get("gold_title", ""),
                "covered_exact_title": doc.get("covered_exact_title", False),
                "covered_at_similarity_threshold": (
                    doc.get("covered_exact_title", False)
                    or float(doc.get("best_title_similarity", 0.0))
                    >= args.title_similarity_threshold
                ),
                "exact_match_rank": doc.get("exact_match_rank"),
                "exact_match_paper_id": doc.get("exact_match_paper_id", ""),
                "best_title_similarity": doc.get("best_title_similarity", 0.0),
                "best_match_rank": doc.get("best_match_rank"),
                "best_match_title": doc.get("best_match_title", ""),
                "error": doc.get("error", ""),
            }
        )

    summary = summarize(
        doc_rows,
        qrel_rows,
        queries_df,
        title_similarity_threshold=args.title_similarity_threshold,
    )
    summary.update(
        {
            "dataset": args.dataset,
            "api_url": args.api_url,
            "mteb_data_dir": str(data_dir),
            "cache_file": str(cache_path),
        }
    )

    save_json(run_dir / "summary.json", summary)
    save_json(run_dir / "gold_doc_coverage.json", doc_rows)
    save_json(run_dir / "qrel_coverage.json", qrel_rows)
    write_csv(run_dir / "gold_doc_coverage.csv", doc_rows)
    write_csv(run_dir / "qrel_coverage.csv", qrel_rows)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {run_dir}")


if __name__ == "__main__":
    main()
