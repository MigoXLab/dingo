"""Unit tests for dingo.retrieval.eval_utils"""

import pytest

from dingo.retrieval import eval_utils


class TestNormalizeTitle:
    def test_basic(self):
        assert eval_utils.normalize_title("Hello World") == "helloworld"

    def test_accents(self):
        assert eval_utils.normalize_title("Café Résumé") == "caferesume"

    def test_special_chars(self):
        assert eval_utils.normalize_title("Attention Is All You Need!") == "attentionisallyouneed"

    def test_empty(self):
        assert eval_utils.normalize_title("") == ""

    def test_unicode(self):
        assert eval_utils.normalize_title("über") == "uber"


class TestStripDPrefix:
    def test_with_prefix(self):
        assert eval_utils.strip_d_prefix("d202719327") == "202719327"

    def test_without_prefix(self):
        assert eval_utils.strip_d_prefix("202719327") == "202719327"

    def test_not_numeric(self):
        assert eval_utils.strip_d_prefix("document123") == "document123"

    def test_empty(self):
        assert eval_utils.strip_d_prefix("") == ""


class TestRecallAtK:
    def test_full_recall(self):
        gold = {"a", "b", "c"}
        ranked = ["a", "b", "c", "d", "e"]
        assert eval_utils.recall_at_k(gold, 5, ranked) == 1.0

    def test_partial_recall(self):
        gold = {"a", "b", "c", "d"}
        ranked = ["a", "b", "x", "y", "z"]
        assert eval_utils.recall_at_k(gold, 5, ranked) == 0.5

    def test_zero_recall(self):
        gold = {"a", "b"}
        ranked = ["x", "y", "z"]
        assert eval_utils.recall_at_k(gold, 3, ranked) == 0.0

    def test_empty_gold(self):
        assert eval_utils.recall_at_k(set(), 5, ["a", "b"]) == 0.0

    def test_k_limit(self):
        gold = {"a", "b"}
        ranked = ["x", "a", "b"]
        assert eval_utils.recall_at_k(gold, 1, ranked) == 0.0
        assert eval_utils.recall_at_k(gold, 2, ranked) == 0.5
        assert eval_utils.recall_at_k(gold, 3, ranked) == 1.0


class TestComputeQueryMetrics:
    def test_perfect_retrieval(self):
        retrieved = ["a", "b", "c"]
        relevant = {"a", "b", "c"}
        metrics = eval_utils.compute_query_metrics(retrieved, relevant)
        assert metrics["ndcg_at_10"] == 1.0
        assert metrics["mrr_at_10"] == 1.0
        assert metrics["recall_at_5"] == 1.0
        assert metrics["recall_at_10"] == 1.0

    def test_no_relevant(self):
        retrieved = ["x", "y", "z"]
        relevant = {"a", "b"}
        metrics = eval_utils.compute_query_metrics(retrieved, relevant)
        assert metrics["ndcg_at_10"] == 0.0
        assert metrics["mrr_at_10"] == 0.0
        assert metrics["recall_at_5"] == 0.0

    def test_first_relevant_at_position_3(self):
        retrieved = ["x", "y", "a", "b"]
        relevant = {"a", "b"}
        metrics = eval_utils.compute_query_metrics(retrieved, relevant)
        assert metrics["first_relevant_rank_at_10"] == 3
        assert metrics["mrr_at_10"] == pytest.approx(1.0 / 3, abs=1e-4)

    def test_empty_retrieved(self):
        metrics = eval_utils.compute_query_metrics([], {"a", "b"})
        assert metrics["ndcg_at_10"] == 0.0
        assert metrics["mrr_at_10"] == 0.0
        assert metrics["recall_at_10"] == 0.0


class TestBuildRawApiRankedDocIds:
    def test_preserves_unmatched_and_duplicate_positions(self):
        ranked = eval_utils.build_raw_api_ranked_doc_ids(
            [
                {"rank": 1, "resolved_corpus_id": ""},
                {"rank": 2, "resolved_corpus_id": "d1"},
                {"rank": 3, "resolved_corpus_id": "d1"},
                {"rank": 4, "resolved_corpus_id": "d2"},
            ]
        )

        assert ranked[0].startswith("__raw_api_unmatched__")
        assert ranked[1] == "d1"
        assert ranked[2].startswith("__raw_api_duplicate__")
        assert ranked[3] == "d2"


class TestResolveHit:
    def setup_method(self):
        self.corpus_ids = {"d123", "d456", "d789"}
        self.title_index = {
            "attentionisallyouneed": ["d123"],
            "bertpretraining": ["d456"],
        }

    def test_exact_match_with_d_prefix(self):
        hit = {"paper_id": "d123", "title": "Something"}
        cid, src, score = eval_utils.resolve_hit(hit, self.title_index, self.corpus_ids)
        assert cid == "d123"
        assert src == "doc_id_exact"
        assert score is None

    def test_exact_match_without_prefix(self):
        hit = {"paper_id": "123", "title": "Something"}
        cid, src, score = eval_utils.resolve_hit(hit, self.title_index, self.corpus_ids)
        assert cid == "d123"
        assert src == "doc_id_exact"
        assert score is None

    def test_title_fallback(self):
        hit = {"paper_id": "999", "title": "Attention Is All You Need"}
        cid, src, score = eval_utils.resolve_hit(hit, self.title_index, self.corpus_ids)
        assert cid == "d123"
        assert src == "title_fallback"
        assert score is None

    def test_unmatched(self):
        hit = {"paper_id": "999", "title": "Unknown Paper"}
        cid, src, score = eval_utils.resolve_hit(hit, self.title_index, self.corpus_ids)
        assert cid == ""
        assert src == "unmatched"
        assert score is None

    def test_empty_hit(self):
        hit = {"paper_id": "", "title": ""}
        cid, src, score = eval_utils.resolve_hit(hit, self.title_index, self.corpus_ids)
        assert cid == ""
        assert src == "unmatched"
        assert score is None

    def test_title_fuzzy_markup_match(self):
        title_index = {
            "linkagedisequilibriummappingofchek2commonvariationandbreastcancerrisk": ["d999"]
        }
        hit = {
            "paper_id": "not-in-corpus",
            "title": "Linkage disequilibrium mapping of [!i]CHEK2[!/i]:: Common variation and breast cancer risk",
        }
        cid, src, score = eval_utils.resolve_hit(
            hit,
            title_index,
            {"d999"},
            title_fuzzy_enabled=True,
            title_fuzzy_threshold=0.98,
            title_fuzzy_margin=0.001,
            title_fuzzy_min_len=10,
        )
        assert cid == "d999"
        assert src == "title_fuzzy"
        assert score is not None and score >= 0.98

    def test_title_fuzzy_disabled_stays_unmatched(self):
        title_index = {
            "linkagedisequilibriummappingofchek2commonvariationandbreastcancerrisk": ["d999"]
        }
        hit = {
            "paper_id": "not-in-corpus",
            "title": "Linkage disequilibrium mapping of [!i]CHEK2[!/i]:: Common variation and breast cancer risk",
        }
        cid, src, score = eval_utils.resolve_hit(hit, title_index, {"d999"})
        assert cid == ""
        assert src == "unmatched"
        assert score is None


class TestSummarizeLatencies:
    def test_nearest_rank_and_generator(self):
        summary = eval_utils.summarize_latencies(value for value in range(100, 0, -1))
        assert summary == {"count": 100, "mean_ms": 50.5, "p50_ms": 50, "p95_ms": 95, "p99_ms": 99}
        assert eval_utils.summarize_latencies([3, 1, 2, 4])["p50_ms"] == 2

    def test_empty_and_single_zero(self):
        assert eval_utils.summarize_latencies([]) == {
            "count": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None, "p99_ms": None,
        }
        assert eval_utils.summarize_latencies([0]) == {
            "count": 1, "mean_ms": 0, "p50_ms": 0, "p95_ms": 0, "p99_ms": 0,
        }

    @pytest.mark.parametrize("value", [-1, float("inf"), float("-inf"), float("nan"), "1", None, True])
    def test_invalid(self, value):
        with pytest.raises(ValueError, match="finite nonnegative"):
            eval_utils.summarize_latencies([value])


class TestANNResultQuality:
    def test_raw_slot_validity_and_duplicate_types(self):
        hits = [{"id": identifier, "distance": distance} for identifier, distance in [
            (0, 0), (1, 1.0), (1, 2.0), ("1", 0), ("1", 0),
            (-1, 0), (3, 0), (True, 0), (1.0, 0),
            (2, float("nan")), (2, float("inf")), (0, "0"), (0, True),
        ]]
        assert eval_utils.compute_ann_result_quality(hits, base_count=3, top_k=10) == {
            "returned_count": 13, "valid_count": 3, "duplicate_count": 5, "top_k_adherent": False,
        }

    def test_entire_response_including_after_top_ten(self):
        hits = [{"id": i, "distance": float(i)} for i in range(10)]
        hits.extend([{"id": 9, "distance": 0.0}, {"id": 11, "distance": 0.0}])
        assert eval_utils.compute_ann_result_quality(hits, base_count=11, top_k=12) == {
            "returned_count": 12, "valid_count": 11, "duplicate_count": 1, "top_k_adherent": True,
        }

    def test_empty_and_zero_base(self):
        assert eval_utils.compute_ann_result_quality([], base_count=0, top_k=10) == {
            "returned_count": 0, "valid_count": 0, "duplicate_count": 0, "top_k_adherent": False,
        }
        quality = eval_utils.compute_ann_result_quality([{"id": 0, "distance": 0.0}], base_count=0, top_k=1)
        assert quality["valid_count"] == 0

    @pytest.mark.parametrize("base_count,top_k", [(-1, 1), (1, 0), (1, -1), (True, 1), (1, 1.0)])
    def test_invalid_dimensions(self, base_count, top_k):
        with pytest.raises(ValueError, match="integers"):
            eval_utils.compute_ann_result_quality([], base_count=base_count, top_k=top_k)


class TestSummarizeANNMetrics:
    def test_attempt_denominators_and_pooled_slots(self):
        rows = [
            {"query_index": 0, "status": "ok", "elapsed_ms": 10, "recall_at_10": 0.5,
             "quality": {"returned_count": 4, "valid_count": 3, "duplicate_count": 1, "top_k_adherent": True}},
            {"query_index": 0, "status": "ok", "elapsed_ms": 30, "recall_at_10": 1.0,
             "quality": {"returned_count": 2, "valid_count": 2, "duplicate_count": 0, "top_k_adherent": False}},
            {"query_index": 1, "status": "empty", "elapsed_ms": 20, "recall_at_10": 0.0,
             "quality": {"returned_count": 0, "valid_count": 0, "duplicate_count": 0, "top_k_adherent": False}},
            {"query_index": 2, "status": "timeout", "elapsed_ms": 900, "recall_at_10": 0.0,
             "quality": {"returned_count": 0, "valid_count": 0, "duplicate_count": 0, "top_k_adherent": False}},
            {"query_index": 3, "status": "error", "elapsed_ms": 1000, "recall_at_10": 0.0,
             "quality": {"returned_count": 0, "valid_count": 0, "duplicate_count": 0, "top_k_adherent": False}},
        ]
        assert eval_utils.summarize_ann_metrics(iter(rows)) == {
            "attempt_count": 5, "success_count": 3, "timeout_count": 1, "ok_count": 2,
            "recall_at_10": 0.3, "success_rate": 0.6, "timeout_rate": 0.2,
            "has_results_rate": 2 / 3, "valid_hit_rate": 5 / 6, "duplicate_rate": 1 / 6,
            "top_k_adherence_rate": 0.2, "mean_latency_ms": 20, "p50_latency_ms": 20,
            "p95_latency_ms": 30, "p99_latency_ms": 30,
        }

    def test_empty_population(self):
        summary = eval_utils.summarize_ann_metrics([])
        assert {key: value for key, value in summary.items() if key.endswith("_count")} == {
            "attempt_count": 0, "success_count": 0, "timeout_count": 0, "ok_count": 0,
        }
        assert all(value is None for key, value in summary.items() if not key.endswith("_count"))
        assert len(summary) == 15

    @pytest.mark.parametrize("status", ["empty", "timeout", "error"])
    def test_zero_hit_population(self, status):
        summary = eval_utils.summarize_ann_metrics([{
            "status": status, "elapsed_ms": 0, "recall_at_10": 0,
            "quality": {"returned_count": 0, "valid_count": 0, "duplicate_count": 0, "top_k_adherent": False},
        }])
        assert summary["recall_at_10"] == 0
        assert summary["valid_hit_rate"] is None
        assert summary["duplicate_rate"] is None
        assert summary["top_k_adherence_rate"] == 0
        assert summary["success_rate"] == (1 if status == "empty" else 0)
        assert summary["timeout_rate"] == (1 if status == "timeout" else 0)
        assert summary["has_results_rate"] == (0 if status == "empty" else None)
        assert summary["mean_latency_ms"] == (0 if status == "empty" else None)
