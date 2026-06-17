"""
IR ranking metric evaluators for retrieval evaluation.

Each evaluator operates on a single query row (fan-out pattern):
- ``search_results``: list of result dicts with ``resolved_corpus_id``
- ``reference``: list of gold relevant document IDs

Metrics: NDCG@k, MRR@k, Recall@k, Precision@k, MAP@k, HitRate@k.
"""

import math
from typing import Any, List, Set, Tuple

from dingo.io.input import Data
from dingo.io.output.eval_detail import EvalDetail, QualityLabel
from dingo.model.model import Model
from dingo.model.rule.base import BaseRule


class _RetrievalMetricBase(BaseRule):
    """Shared base for retrieval IR metric evaluators."""

    @classmethod
    def _extract_ranked_and_relevant(
        cls, input_data: Data
    ) -> Tuple[List[str], Set[str]]:
        """Extract ranked doc IDs and gold relevant IDs from Data row."""
        search_results = getattr(input_data, "search_results", None) or []
        reference = getattr(input_data, "reference", None) or []

        ranked_ids: List[str] = []
        for r in search_results:
            if isinstance(r, dict):
                doc_id = str(r.get("resolved_corpus_id") or "").strip()
                ranked_ids.append(doc_id)
            else:
                ranked_ids.append("")

        gold_ids = set(str(rid) for rid in reference if rid)
        return ranked_ids, gold_ids

    @classmethod
    def _get_k(cls) -> int:
        k = getattr(cls.dynamic_config, "k", None)
        if k is None:
            k = (cls.dynamic_config.model_extra or {}).get("k", 10)
        return int(k) if k else 10

    @classmethod
    def _make_detail(
        cls, score: float, metric_suffix: str, reason_text: str
    ) -> EvalDetail:
        result = EvalDetail(metric=cls.__name__, score=round(score, 5))
        threshold = (cls.dynamic_config.model_extra or {}).get("threshold", 0.0)
        if score < threshold:
            result.status = True
            result.label = [f"RETRIEVAL_BAD.{metric_suffix}"]
            result.reason = [reason_text]
        else:
            result.status = False
            result.label = [QualityLabel.QUALITY_GOOD]
            result.reason = [reason_text]
        return result


def _dcg(binary_rels: List[int], k: int) -> float:
    s = 0.0
    for i, rel in enumerate(binary_rels[:k], start=1):
        if rel:
            s += 1.0 / math.log2(i + 1)
    return s


@Model.rule_register("RETRIEVAL_NDCG", ["retrieval"])
class RuleNDCG(_RetrievalMetricBase):
    """NDCG@k evaluator. Default k=10, configurable via config.k."""

    _metric_info = {
        "category": "Retrieval Ranking Metrics",
        "metric_name": "RuleNDCG",
        "description": "Normalized Discounted Cumulative Gain at k",
    }

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        ranked_ids, gold_ids = cls._extract_ranked_and_relevant(input_data)
        k = cls._get_k()

        if not gold_ids:
            return cls._make_detail(0.0, "NDCG", f"No gold labels, NDCG@{k}=0")

        top_k = ranked_ids[:k]
        rel_flags = [1 if did in gold_ids else 0 for did in top_k]
        dcg_val = _dcg(rel_flags, k)
        ideal_len = min(len(gold_ids), k)
        idcg_val = _dcg([1] * ideal_len, k) if ideal_len > 0 else 0.0
        ndcg = (dcg_val / idcg_val) if idcg_val > 0 else 0.0

        return cls._make_detail(
            ndcg, "NDCG", f"NDCG@{k}={ndcg:.5f} (relevant={len(gold_ids)})"
        )


@Model.rule_register("RETRIEVAL_MRR", ["retrieval"])
class RuleMRR(_RetrievalMetricBase):
    """MRR@k evaluator. Default k=10."""

    _metric_info = {
        "category": "Retrieval Ranking Metrics",
        "metric_name": "RuleMRR",
        "description": "Mean Reciprocal Rank at k",
    }

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        ranked_ids, gold_ids = cls._extract_ranked_and_relevant(input_data)
        k = cls._get_k()

        if not gold_ids:
            return cls._make_detail(0.0, "MRR", f"No gold labels, MRR@{k}=0")

        mrr = 0.0
        for i, did in enumerate(ranked_ids[:k], start=1):
            if did in gold_ids:
                mrr = 1.0 / i
                break

        return cls._make_detail(
            mrr, "MRR", f"MRR@{k}={mrr:.5f} (relevant={len(gold_ids)})"
        )


@Model.rule_register("RETRIEVAL_RECALL", ["retrieval"])
class RuleRecall(_RetrievalMetricBase):
    """Recall@k evaluator. Default k=10."""

    _metric_info = {
        "category": "Retrieval Ranking Metrics",
        "metric_name": "RuleRecall",
        "description": "Recall at k",
    }

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        ranked_ids, gold_ids = cls._extract_ranked_and_relevant(input_data)
        k = cls._get_k()

        if not gold_ids:
            return cls._make_detail(0.0, "RECALL", f"No gold labels, Recall@{k}=0")

        hits = len(set(ranked_ids[:k]) & gold_ids)
        recall = hits / len(gold_ids)

        return cls._make_detail(
            recall,
            "RECALL",
            f"Recall@{k}={recall:.5f} ({hits}/{len(gold_ids)} relevant found)",
        )


@Model.rule_register("RETRIEVAL_PRECISION", ["retrieval"])
class RulePrecision(_RetrievalMetricBase):
    """Precision@k evaluator. Default k=10."""

    _metric_info = {
        "category": "Retrieval Ranking Metrics",
        "metric_name": "RulePrecision",
        "description": "Precision at k",
    }

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        ranked_ids, gold_ids = cls._extract_ranked_and_relevant(input_data)
        k = cls._get_k()

        if not gold_ids:
            return cls._make_detail(0.0, "PRECISION", f"No gold labels, Precision@{k}=0")

        hits = len(set(ranked_ids[:k]) & gold_ids)
        precision = hits / k if k > 0 else 0.0

        return cls._make_detail(
            precision,
            "PRECISION",
            f"Precision@{k}={precision:.5f} ({hits}/{k} results relevant)",
        )


@Model.rule_register("RETRIEVAL_MAP", ["retrieval"])
class RuleMAP(_RetrievalMetricBase):
    """MAP@k evaluator (Average Precision). Default k=10."""

    _metric_info = {
        "category": "Retrieval Ranking Metrics",
        "metric_name": "RuleMAP",
        "description": "Mean Average Precision at k",
    }

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        ranked_ids, gold_ids = cls._extract_ranked_and_relevant(input_data)
        k = cls._get_k()

        if not gold_ids:
            return cls._make_detail(0.0, "MAP", f"No gold labels, MAP@{k}=0")

        hits = 0
        precision_sum = 0.0
        for rank, did in enumerate(ranked_ids[:k], start=1):
            if did in gold_ids:
                hits += 1
                precision_sum += hits / rank

        denominator = min(len(gold_ids), k)
        ap = (precision_sum / denominator) if denominator > 0 else 0.0

        return cls._make_detail(
            ap, "MAP", f"MAP@{k}={ap:.5f} ({hits} relevant in top-{k})"
        )


@Model.rule_register("RETRIEVAL_HIT_RATE", ["retrieval"])
class RuleHitRate(_RetrievalMetricBase):
    """HitRate@k evaluator. 1.0 if any relevant doc in top-k, else 0.0."""

    _metric_info = {
        "category": "Retrieval Ranking Metrics",
        "metric_name": "RuleHitRate",
        "description": "Hit Rate at k (binary: any relevant doc in top-k)",
    }

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        ranked_ids, gold_ids = cls._extract_ranked_and_relevant(input_data)
        k = cls._get_k()

        if not gold_ids:
            return cls._make_detail(0.0, "HIT_RATE", f"No gold labels, HitRate@{k}=0")

        hit = 1.0 if (set(ranked_ids[:k]) & gold_ids) else 0.0

        return cls._make_detail(
            hit,
            "HIT_RATE",
            f"HitRate@{k}={'hit' if hit else 'miss'} (relevant={len(gold_ids)})",
        )
