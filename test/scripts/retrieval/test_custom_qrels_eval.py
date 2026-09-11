"""Tests for bundled labeled retrieval evaluation without an MTEB dependency."""

import json

import pytest

from dingo.config import InputArgs
from dingo.exec import retrieval as retrieval_module
from dingo.exec.retrieval import RetrievalExecutor
from dingo.retrieval.search_client import PaperResult, SearchResponse
from dingo.retrieval.tasks import resolve_builtin_task


class TestCustomQrelsEval:
    @pytest.mark.parametrize("relevance", [-1, 2, "0", None])
    def test_rejects_non_binary_qrels(self, tmp_path, relevance):
        path = tmp_path / "invalid.json"
        path.write_text(json.dumps([{"qid": "q1", "query": "q", "qrels": {"d": relevance}}]),
                        encoding="utf-8")
        with pytest.raises(ValueError, match="binary relevance"):
            RetrievalExecutor._load_qrels_file(str(path))

    def test_builtin_task_rejects_path_traversal(self):
        assert resolve_builtin_task("../cjk_evalset_v1") is None

    def test_aggregates_overall_and_groups(self, tmp_path, monkeypatch):
        evalset = tmp_path / "cjk.json"
        evalset.write_text(json.dumps({
            "name": "cjk_test",
            "queries": [
                {"qid": "A01", "group": "known_item", "query": "标题", "qrels": ["gold-1"]},
                {"qid": "B01", "group": "term_query", "query": "术语", "qrels": ["gold-2"]},
            ],
        }), encoding="utf-8")

        class FakeClient:
            name = "fake-agentic"

            def search(self, query, limit=100):
                ids = ["noise", "gold-1"] if query == "标题" else ["noise"]
                return SearchResponse(
                    query=query,
                    results=[PaperResult(paper_id=doc_id, title=doc_id) for doc_id in ids],
                    response_time_ms=1.0,
                    status_code=200,
                )

        monkeypatch.setattr(retrieval_module, "create_client", lambda *a, **k: FakeClient())
        monkeypatch.setattr(
            retrieval_module,
            "resolve_builtin_task",
            lambda name: evalset if name == "cjk_test" else None,
        )
        input_args = InputArgs(**{
            "input_path": "cjk_test",
            "output_path": str(tmp_path / "out"),
            "executor": {"retrieval": {
                "backend": "agentic",
                "limit": 100,
                "max_workers": 2,
            }},
        })

        summary = RetrievalExecutor(input_args).execute()

        metrics = summary.metrics_score_stats["cjk_test"]
        assert summary.total == 2
        assert metrics["recall_at_100"] == 0.5
        assert metrics["mrr_at_10"] == 0.25
        assert metrics["groups"]["known_item"]["recall_at_100"] == 1.0
        assert metrics["groups"]["term_query"]["recall_at_100"] == 0.0
        assert (tmp_path / "out").exists()

    def test_rejects_duplicate_qids(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"queries": [
            {"qid": "same", "query": "q1", "qrels": ["d1"]},
            {"qid": "same", "query": "q2", "qrels": ["d2"]},
        ]}), encoding="utf-8")

        with pytest.raises(ValueError, match="duplicate qid"):
            RetrievalExecutor._load_qrels_file(str(path))

    def test_checked_in_cjk_evalset(self):
        path = resolve_builtin_task("cjk_evalset_v1")

        assert path is not None
        items, metadata = RetrievalExecutor._load_qrels_file(str(path))

        assert metadata["name"] == "cjk_evalset_v1"
        assert len(items) == 100
        assert len({item["qid"] for item in items}) == 100
        assert {item["group"] for item in items} == {
            "known_item", "term_query", "nl_question",
        }
