"""Unit tests for rule-based IR retrieval metric evaluators."""

import pytest

from dingo.io.input import Data
from dingo.model.rule.rule_search_ranking import RuleHitRate, RuleMAP, RuleMRR, RuleNDCG, RulePrecision, RuleRecall


def _make_data(ranked_corpus_ids: list, gold_ids: list) -> Data:
    """Helper to create a Data row for retrieval evaluation."""
    search_results = [
        {"rank": i + 1, "resolved_corpus_id": cid, "title": f"T{i}", "abstract": f"A{i}"}
        for i, cid in enumerate(ranked_corpus_ids)
    ]
    return Data(
        data_id="test_q",
        prompt="test query",
        search_results=search_results,
        reference=gold_ids,
    )


class TestRuleNDCG:
    def test_perfect_ranking(self):
        data = _make_data(["doc1", "doc2", "doc3"], ["doc1", "doc2", "doc3"])
        detail = RuleNDCG.eval(data)
        assert detail.score == pytest.approx(1.0, abs=0.001)
        assert detail.status is False

    def test_single_relevant_at_top(self):
        data = _make_data(["doc1", "doc2", "doc3"], ["doc1"])
        detail = RuleNDCG.eval(data)
        assert detail.score == pytest.approx(1.0, abs=0.001)

    def test_single_relevant_at_position_3(self):
        data = _make_data(["doc1", "doc2", "doc3"], ["doc3"])
        detail = RuleNDCG.eval(data)
        assert 0.0 < detail.score < 1.0

    def test_no_relevant_docs(self):
        data = _make_data(["doc1", "doc2"], ["doc99"])
        detail = RuleNDCG.eval(data)
        assert detail.score == 0.0

    def test_no_gold_labels(self):
        data = _make_data(["doc1", "doc2"], [])
        detail = RuleNDCG.eval(data)
        assert detail.score == 0.0

    def test_empty_results(self):
        data = Data(data_id="q", prompt="q", search_results=[], reference=["doc1"])
        detail = RuleNDCG.eval(data)
        assert detail.score == 0.0


class TestRuleMRR:
    def test_relevant_at_position_1(self):
        data = _make_data(["doc1", "doc2"], ["doc1"])
        detail = RuleMRR.eval(data)
        assert detail.score == pytest.approx(1.0)

    def test_relevant_at_position_2(self):
        data = _make_data(["doc1", "doc2"], ["doc2"])
        detail = RuleMRR.eval(data)
        assert detail.score == pytest.approx(0.5)

    def test_relevant_at_position_5(self):
        data = _make_data(["a", "b", "c", "d", "rel"], ["rel"])
        detail = RuleMRR.eval(data)
        assert detail.score == pytest.approx(0.2)

    def test_no_relevant_in_top_k(self):
        data = _make_data(["a", "b", "c"], ["missing"])
        detail = RuleMRR.eval(data)
        assert detail.score == 0.0


class TestRuleRecall:
    def test_all_found(self):
        data = _make_data(["d1", "d2", "d3", "d4", "d5"], ["d1", "d3"])
        detail = RuleRecall.eval(data)
        assert detail.score == pytest.approx(1.0)

    def test_half_found(self):
        data = _make_data(["d1", "d2", "d3"], ["d1", "d4"])
        detail = RuleRecall.eval(data)
        assert detail.score == pytest.approx(0.5)

    def test_none_found(self):
        data = _make_data(["a", "b"], ["x", "y"])
        detail = RuleRecall.eval(data)
        assert detail.score == 0.0


class TestRulePrecision:
    def test_all_relevant(self):
        data = _make_data(["d1", "d2", "d3"], ["d1", "d2", "d3"])
        detail = RulePrecision.eval(data)
        # Precision@10 with 3 results, all relevant: 3/10 = 0.3
        assert detail.score == pytest.approx(0.3)

    def test_precision_at_k_smaller_than_results(self):
        data = _make_data(
            ["d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8", "d9", "d10"],
            ["d1", "d2", "d3", "d4", "d5"],
        )
        detail = RulePrecision.eval(data)
        assert detail.score == pytest.approx(0.5)

    def test_no_relevant(self):
        data = _make_data(["a", "b", "c"], ["x"])
        detail = RulePrecision.eval(data)
        assert detail.score == 0.0


class TestRuleMAP:
    def test_perfect_ranking(self):
        data = _make_data(["d1", "d2", "x", "y", "z"], ["d1", "d2"])
        detail = RuleMAP.eval(data)
        # AP = (1/1 + 2/2) / 2 = 1.0
        assert detail.score == pytest.approx(1.0)

    def test_partial_ranking(self):
        data = _make_data(["x", "d1", "y", "d2", "z"], ["d1", "d2"])
        detail = RuleMAP.eval(data)
        # AP = (1/2 + 2/4) / 2 = (0.5 + 0.5) / 2 = 0.5
        assert detail.score == pytest.approx(0.5)

    def test_no_relevant(self):
        data = _make_data(["a", "b", "c"], ["missing"])
        detail = RuleMAP.eval(data)
        assert detail.score == 0.0


class TestRuleHitRate:
    def test_hit(self):
        data = _make_data(["a", "b", "target"], ["target"])
        detail = RuleHitRate.eval(data)
        assert detail.score == 1.0

    def test_miss(self):
        data = _make_data(["a", "b", "c"], ["missing"])
        detail = RuleHitRate.eval(data)
        assert detail.score == 0.0

    def test_empty_reference(self):
        data = _make_data(["a"], [])
        detail = RuleHitRate.eval(data)
        assert detail.score == 0.0


class TestEvalDetailContract:
    """Verify all evaluators return proper EvalDetail objects."""

    @pytest.mark.parametrize("cls", [RuleNDCG, RuleMRR, RuleRecall, RulePrecision, RuleMAP, RuleHitRate])
    def test_returns_eval_detail(self, cls):
        from dingo.io.output.eval_detail import EvalDetail

        data = _make_data(["d1", "d2"], ["d1"])
        detail = cls.eval(data)
        assert isinstance(detail, EvalDetail)
        assert detail.metric == cls.__name__
        assert detail.score is not None
        assert detail.label is not None
        assert detail.reason is not None

    @pytest.mark.parametrize("cls", [RuleNDCG, RuleMRR, RuleRecall, RulePrecision, RuleMAP, RuleHitRate])
    def test_no_search_results(self, cls):
        data = Data(data_id="q", prompt="q")
        detail = cls.eval(data)
        assert detail.score == 0.0


class TestRegistration:
    def test_all_registered_in_retrieval_group(self):
        from dingo.model import Model
        Model.load_model()
        group = Model.rule_groups.get("retrieval", [])
        names = {c.__name__ for c in group}
        assert "RuleNDCG" in names
        assert "RuleMRR" in names
        assert "RuleRecall" in names
        assert "RulePrecision" in names
        assert "RuleMAP" in names
        assert "RuleHitRate" in names
