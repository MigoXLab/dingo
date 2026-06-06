"""Unit tests for dingo.retrieval.eval_utils"""

import pytest

from dingo.retrieval.eval_utils import compute_query_metrics, normalize_title, recall_at_k, resolve_hit, strip_d_prefix


class TestNormalizeTitle:
    def test_basic(self):
        assert normalize_title("Hello World") == "helloworld"

    def test_accents(self):
        assert normalize_title("Café Résumé") == "caferesume"

    def test_special_chars(self):
        assert normalize_title("Attention Is All You Need!") == "attentionisallyouneed"

    def test_empty(self):
        assert normalize_title("") == ""

    def test_unicode(self):
        assert normalize_title("über") == "uber"


class TestStripDPrefix:
    def test_with_prefix(self):
        assert strip_d_prefix("d202719327") == "202719327"

    def test_without_prefix(self):
        assert strip_d_prefix("202719327") == "202719327"

    def test_not_numeric(self):
        assert strip_d_prefix("document123") == "document123"

    def test_empty(self):
        assert strip_d_prefix("") == ""


class TestRecallAtK:
    def test_full_recall(self):
        gold = {"a", "b", "c"}
        ranked = ["a", "b", "c", "d", "e"]
        assert recall_at_k(gold, 5, ranked) == 1.0

    def test_partial_recall(self):
        gold = {"a", "b", "c", "d"}
        ranked = ["a", "b", "x", "y", "z"]
        assert recall_at_k(gold, 5, ranked) == 0.5

    def test_zero_recall(self):
        gold = {"a", "b"}
        ranked = ["x", "y", "z"]
        assert recall_at_k(gold, 3, ranked) == 0.0

    def test_empty_gold(self):
        assert recall_at_k(set(), 5, ["a", "b"]) == 0.0

    def test_k_limit(self):
        gold = {"a", "b"}
        ranked = ["x", "a", "b"]
        assert recall_at_k(gold, 1, ranked) == 0.0
        assert recall_at_k(gold, 2, ranked) == 0.5
        assert recall_at_k(gold, 3, ranked) == 1.0


class TestComputeQueryMetrics:
    def test_perfect_retrieval(self):
        retrieved = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        metrics = compute_query_metrics(retrieved, relevant)
        assert metrics["ndcg_at_10"] == 1.0
        assert metrics["mrr_at_10"] == 1.0
        assert metrics["recall_at_5"] == 1.0
        assert metrics["recall_at_10"] == 1.0

    def test_no_relevant(self):
        retrieved = ["x", "y", "z"]
        relevant = {"a", "b"}
        metrics = compute_query_metrics(retrieved, relevant)
        assert metrics["ndcg_at_10"] == 0.0
        assert metrics["mrr_at_10"] == 0.0
        assert metrics["recall_at_5"] == 0.0

    def test_first_relevant_at_position_3(self):
        retrieved = ["x", "y", "a", "b"]
        relevant = {"a", "b"}
        metrics = compute_query_metrics(retrieved, relevant)
        assert metrics["first_relevant_rank_at_10"] == 3
        assert metrics["mrr_at_10"] == pytest.approx(1.0 / 3, abs=1e-4)

    def test_empty_retrieved(self):
        metrics = compute_query_metrics([], {"a", "b"})
        assert metrics["ndcg_at_10"] == 0.0
        assert metrics["mrr_at_10"] == 0.0
        assert metrics["recall_at_10"] == 0.0


class TestResolveHit:
    def setup_method(self):
        self.corpus_ids = {"d123", "d456", "d789"}
        self.title_index = {
            "attentionisallyouneed": ["d123"],
            "bertpretraining": ["d456"],
        }

    def test_exact_match_with_d_prefix(self):
        hit = {"paper_id": "d123", "title": "Something"}
        cid, src = resolve_hit(hit, self.title_index, self.corpus_ids)
        assert cid == "d123"
        assert src == "doc_id_exact"

    def test_exact_match_without_prefix(self):
        hit = {"paper_id": "123", "title": "Something"}
        cid, src = resolve_hit(hit, self.title_index, self.corpus_ids)
        assert cid == "d123"
        assert src == "doc_id_exact"

    def test_title_fallback(self):
        hit = {"paper_id": "999", "title": "Attention Is All You Need"}
        cid, src = resolve_hit(hit, self.title_index, self.corpus_ids)
        assert cid == "d123"
        assert src == "title_fallback"

    def test_unmatched(self):
        hit = {"paper_id": "999", "title": "Unknown Paper"}
        cid, src = resolve_hit(hit, self.title_index, self.corpus_ids)
        assert cid == ""
        assert src == "unmatched"

    def test_empty_hit(self):
        hit = {"paper_id": "", "title": ""}
        cid, src = resolve_hit(hit, self.title_index, self.corpus_ids)
        assert cid == ""
        assert src == "unmatched"
