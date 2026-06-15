"""
Shared utilities for retrieval evaluation.

Provides:
  - Title normalization and doc-ID format conversion
  - Recall / nDCG / MRR metric helpers
  - Hit resolution (API doc_id -> corpus ID)
  - Output directory management
"""

from __future__ import annotations
import json
import logging
import math
import os
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)


def normalize_title(title: str) -> str:
    """Lower-case, strip accents and non-alphanumeric chars for fuzzy matching."""
    title = unicodedata.normalize("NFKD", title)
    title = title.lower()
    return re.sub(r"[^a-z0-9]", "", title)


def strip_d_prefix(doc_id: str) -> str:
    """``d202719327`` -> ``202719327``; pass-through if no ``d`` prefix."""
    s = (doc_id or "").strip()
    if s.startswith("d") and s[1:].isdigit():
        return s[1:]
    return s


def recall_at_k(gold_ids: set[str], k: int, ranked_list: list[str]) -> float:
    if not gold_ids:
        return 0.0
    return len(set(ranked_list[:k]) & gold_ids) / len(gold_ids)


def dcg(binary_rels: list[int], k: int) -> float:
    s = 0.0
    for i, rel in enumerate(binary_rels[:k], start=1):
        if rel:
            s += 1.0 / math.log2(i + 1)
    return s


def compute_query_metrics(
    retrieved_doc_ids: list[str],
    relevant_doc_ids: set[str],
) -> dict[str, Any]:
    """Compute standard retrieval metrics for a single query."""
    top5 = retrieved_doc_ids[:5]
    top10 = retrieved_doc_ids[:10]
    top20 = retrieved_doc_ids[:20]
    top100 = retrieved_doc_ids[:100]
    top1000 = retrieved_doc_ids[:1000]

    rel_flags_5 = [1 if did in relevant_doc_ids else 0 for did in top5]
    rel_in_5 = sum(rel_flags_5)
    rel_flags_10 = [1 if did in relevant_doc_ids else 0 for did in top10]
    rel_in_10 = sum(rel_flags_10)
    rel_flags_100 = [1 if did in relevant_doc_ids else 0 for did in top100]
    rel_total = len(relevant_doc_ids)

    first_rel_rank = -1
    for i, did in enumerate(top10, start=1):
        if did in relevant_doc_ids:
            first_rel_rank = i
            break
    mrr10 = 1.0 / first_rel_rank if first_rel_rank > 0 else 0.0

    ideal_len_10 = min(rel_total, 10)
    idcg10 = dcg([1] * ideal_len_10, 10) if ideal_len_10 > 0 else 0.0
    ndcg10 = (dcg(rel_flags_10, 10) / idcg10) if idcg10 > 0 else 0.0

    ideal_len_100 = min(rel_total, 100)
    idcg100 = dcg([1] * ideal_len_100, 100) if ideal_len_100 > 0 else 0.0
    ndcg100 = (dcg(rel_flags_100, 100) / idcg100) if idcg100 > 0 else 0.0

    recall5 = (rel_in_5 / rel_total) if rel_total > 0 else 0.0
    recall10 = (rel_in_10 / rel_total) if rel_total > 0 else 0.0
    recall20 = (
        sum(1 for did in top20 if did in relevant_doc_ids) / rel_total
        if rel_total > 0
        else 0.0
    )
    recall100 = (
        sum(1 for did in top100 if did in relevant_doc_ids) / rel_total
        if rel_total > 0
        else 0.0
    )
    recall1000 = (
        sum(1 for did in top1000 if did in relevant_doc_ids) / rel_total
        if rel_total > 0
        else 0.0
    )

    hits = 0
    precision_sum = 0.0
    for rank, did in enumerate(top10, start=1):
        if did in relevant_doc_ids:
            hits += 1
            precision_sum += hits / rank
    map10 = (
        precision_sum / min(rel_total, 10)
        if rel_total > 0
        else 0.0
    )

    return {
        "first_relevant_rank_at_10": first_rel_rank,
        "relevant_in_top10": rel_in_10,
        "relevant_total": rel_total,
        "ndcg_at_10": round(ndcg10, 5),
        "ndcg_at_100": round(ndcg100, 5),
        "mrr_at_10": round(mrr10, 5),
        "recall_at_5": round(recall5, 5),
        "recall_at_10": round(recall10, 5),
        "recall_at_20": round(recall20, 5),
        "recall_at_100": round(recall100, 5),
        "recall_at_1000": round(recall1000, 5),
        "precision_at_10": round(rel_in_10 / 10, 5),
        "map_at_10": round(map10, 5),
    }


def resolve_hit(
    hit: dict[str, Any],
    title_index: dict[str, list[str]],
    corpus_id_set: set[str],
    *,
    title_fuzzy_enabled: bool = False,
    title_fuzzy_threshold: float = 0.95,
    title_fuzzy_margin: float = 0.01,
    title_fuzzy_min_len: int = 20,
    title_norm_candidates: list[tuple[str, list[str]]] | None = None,
) -> tuple[str, str, float | None]:
    """Resolve a search hit to a corpus ID.

    Returns ``(corpus_id, mapping_source, fuzzy_similarity)`` where
    *mapping_source* is one of ``"doc_id_exact"``, ``"title_fallback"``,
    ``"title_fuzzy"``, or ``"unmatched"``.
    """
    raw_id = str(hit.get("doc_id") or hit.get("paper_id") or "").strip()
    if raw_id:
        stripped = strip_d_prefix(raw_id)
        for candidate in (raw_id, stripped, f"d{stripped}"):
            if candidate in corpus_id_set:
                return candidate, "doc_id_exact", None
    title = str(hit.get("title") or "")
    norm = normalize_title(title)
    if norm:
        candidates = title_index.get(norm)
        if candidates:
            return candidates[0], "title_fallback", None

    if title_fuzzy_enabled and norm and len(norm) >= title_fuzzy_min_len:
        iterable_candidates = (
            title_norm_candidates
            if title_norm_candidates is not None
            else list(title_index.items())
        )
        best_ids: list[str] | None = None
        best_score = -1.0
        second_score = -1.0
        for candidate_norm, candidate_ids in iterable_candidates:
            score = SequenceMatcher(None, norm, candidate_norm).ratio()
            if score > best_score:
                second_score = best_score
                best_score = score
                best_ids = candidate_ids
            elif score > second_score:
                second_score = score

        if (
            best_ids
            and best_score >= title_fuzzy_threshold
            and (best_score - second_score) >= title_fuzzy_margin
        ):
            return best_ids[0], "title_fuzzy", round(best_score, 6)

    return "", "unmatched", None


def make_output_dir(explicit_dir: str | None, default_prefix: str) -> str:
    """Return (and create) a timestamped output directory."""
    if explicit_dir:
        d = explicit_dir
    else:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        d = f"{default_prefix}/{stamp}"
    os.makedirs(d, exist_ok=True)
    return d


def save_json(data: Any, directory: str, filename: str) -> str:
    """Write *data* as indented JSON to ``directory/filename``, return path."""
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Saved %s", path)
    return path
