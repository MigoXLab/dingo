"""Unit tests for open eval (LLM-as-Judge search result grading)."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from dingo.io.input import Data
from dingo.model.llm.llm_search_result_relevance import LLMSearchResultRelevance, OpenEvalSummary, RelevanceGrade, _build_user_message, _get_system_prompt, _parse_grade_response, aggregate_grades


class TestGetSystemPrompt:
    def test_standard(self):
        prompt = _get_system_prompt("standard")
        assert "relevance score" in prompt
        assert len(prompt) < 1000

    def test_detailed(self):
        prompt = _get_system_prompt("detailed")
        assert "Perfect match" in prompt
        assert "Key scoring principles" in prompt
        assert len(prompt) > 1000

    def test_unknown_falls_back_to_standard(self):
        prompt = _get_system_prompt("unknown")
        assert prompt == _get_system_prompt("standard")


class TestBuildUserMessage:
    def test_basic(self):
        msg = _build_user_message("test query", "Result Title", "Some abstract")
        assert "test query" in msg
        assert "Result Title" in msg
        assert "Some abstract" in msg

    def test_no_abstract(self):
        msg = _build_user_message("query", "Title", "")
        assert "[no content available]" in msg

    def test_long_abstract_truncated(self):
        long_abstract = "x" * 5000
        msg = _build_user_message("query", "Title", long_abstract)
        assert "[content truncated]" in msg

    def test_expected_criteria(self):
        msg = _build_user_message("query", "Title", "abs", expected_criteria="Must mention X")
        assert "Must mention X" in msg

    def test_json_format_instruction(self):
        msg = _build_user_message("q", "t", "a")
        assert '"score"' in msg
        assert "JSON" in msg


class TestParseGradeResponse:
    def test_valid_json(self):
        response = json.dumps({
            "reasoning": "Good match",
            "query_relevance": 0.9,
            "result_quality": 0.8,
            "content_issues": False,
            "confidence": 0.95,
            "score": 0.85,
        })
        grade = _parse_grade_response(response)
        assert grade.score == 0.85
        assert grade.query_relevance == 0.9
        assert grade.result_quality == 0.8
        assert grade.content_issues is False
        assert grade.confidence == 0.95
        assert grade.reasoning == "Good match"
        assert grade.error == ""

    def test_json_with_markdown_fence(self):
        response = '```json\n{"score": 0.7, "query_relevance": 0.7, "result_quality": 0.7, "content_issues": false, "confidence": 0.8, "reasoning": "ok"}\n```'
        grade = _parse_grade_response(response)
        assert grade.score == 0.7

    def test_invalid_json(self):
        grade = _parse_grade_response("not json at all")
        assert grade.error
        assert "JSON parse failed" in grade.error

    def test_missing_fields_default_to_zero(self):
        grade = _parse_grade_response('{"score": 0.5}')
        assert grade.score == 0.5
        assert grade.query_relevance == 0.0
        assert grade.content_issues is False

    def test_non_dict_json(self):
        grade = _parse_grade_response('[1, 2, 3]')
        assert grade.error
        assert "not a dictionary" in grade.error


class TestRelevanceGrade:
    def test_to_dict_no_error(self):
        grade = RelevanceGrade(score=0.8, reasoning="good")
        d = grade.to_dict()
        assert d["score"] == 0.8
        assert "error" not in d

    def test_to_dict_with_error(self):
        grade = RelevanceGrade(error="timeout")
        d = grade.to_dict()
        assert d["error"] == "timeout"


class TestAggregateGrades:
    def test_empty(self):
        summary = aggregate_grades([])
        assert summary.graded_pairs == 0
        assert summary.mean_score == 0.0

    def test_all_errors(self):
        grades = [RelevanceGrade(error="err1"), RelevanceGrade(error="err2")]
        summary = aggregate_grades(grades)
        assert summary.graded_pairs == 2
        assert summary.error_count == 2
        assert summary.mean_score == 0.0

    def test_normal_aggregation(self):
        grades = [
            RelevanceGrade(score=0.8, query_relevance=0.9, result_quality=0.7, confidence=0.95),
            RelevanceGrade(score=0.6, query_relevance=0.7, result_quality=0.5, confidence=0.85),
        ]
        summary = aggregate_grades(grades, method="mean")
        assert summary.mean_score == pytest.approx(0.7, abs=0.01)
        assert summary.median_score == pytest.approx(0.7, abs=0.01)
        assert summary.mean_query_relevance == pytest.approx(0.8, abs=0.01)
        assert summary.graded_pairs == 2
        assert summary.error_count == 0

    def test_mixed_valid_and_error(self):
        grades = [
            RelevanceGrade(score=0.9, query_relevance=0.9, result_quality=0.9, confidence=1.0),
            RelevanceGrade(error="api_error"),
        ]
        summary = aggregate_grades(grades)
        assert summary.mean_score == pytest.approx(0.9, abs=0.01)
        assert summary.graded_pairs == 2
        assert summary.error_count == 1

    def test_content_issues_rate(self):
        grades = [
            RelevanceGrade(score=0.5, content_issues=True, confidence=0.5),
            RelevanceGrade(score=0.5, content_issues=False, confidence=0.5),
            RelevanceGrade(score=0.5, content_issues=True, confidence=0.5),
        ]
        summary = aggregate_grades(grades)
        assert summary.content_issues_rate == pytest.approx(2 / 3, abs=0.01)


class TestOpenEvalSummary:
    def test_to_dict_keys(self):
        summary = OpenEvalSummary(mean_score=0.75, graded_pairs=10)
        d = summary.to_dict()
        assert "open_eval_mean_score" in d
        assert "open_eval_median_score" in d
        assert "open_eval_graded_pairs" in d
        assert d["open_eval_graded_pairs"] == 10


class TestLLMSearchResultRelevanceRegistered:
    """Test the registered LLM evaluator using the standard eval(Data) API."""

    def test_registered_in_model(self):
        from dingo.model import Model
        Model.load_model()
        assert "LLMSearchResultRelevance" in Model.llm_name_map

    def test_process_response(self):
        responses = [
            json.dumps({"reasoning": "good", "query_relevance": 0.9, "result_quality": 0.8,
                        "content_issues": False, "confidence": 0.9, "score": 0.85}),
            json.dumps({"reasoning": "ok", "query_relevance": 0.6, "result_quality": 0.7,
                        "content_issues": False, "confidence": 0.8, "score": 0.65}),
        ]
        detail = LLMSearchResultRelevance.process_response(responses)
        assert detail.metric == "LLMSearchResultRelevance"
        assert detail.score == pytest.approx(0.75, abs=0.01)
        assert detail.status is False
        assert len(detail.reason) == 3  # summary + 2 per-result

    def test_process_response_with_error(self):
        responses = [
            "invalid json",
            json.dumps({"score": 0.8, "reasoning": "x"}),
        ]
        detail = LLMSearchResultRelevance.process_response(responses)
        assert detail.score == pytest.approx(0.8, abs=0.01)
        assert "1 errors" in detail.reason[0]

    def test_process_response_below_threshold(self):
        responses = [
            json.dumps({"score": 0.3, "reasoning": "bad"}),
            json.dumps({"score": 0.2, "reasoning": "bad"}),
        ]
        detail = LLMSearchResultRelevance.process_response(responses)
        assert detail.status is True
        assert "QUALITY_BAD" in detail.label[0]

    def test_build_messages(self):
        data = Data(
            data_id="q1",
            prompt="machine learning",
            search_results=[
                {"title": "ML Paper", "abstract": "About ML..."},
                {"title": "DL Paper", "abstract": "About DL..."},
            ],
        )
        messages_list = LLMSearchResultRelevance.build_messages(data)
        assert len(messages_list) == 2
        assert messages_list[0]["result_index"] == 0
        assert len(messages_list[0]["messages"]) == 2
        assert "machine learning" in messages_list[0]["messages"][1]["content"]

    def test_eval_no_search_results(self):
        data = Data(data_id="q1", prompt="query")
        detail = LLMSearchResultRelevance.eval(data)
        assert detail.score == 0.0
        assert detail.status is True
        assert "NO_SEARCH_RESULTS" in detail.label[0]

    def test_eval_with_mocked_client(self):
        data = Data(
            data_id="q1",
            prompt="test query",
            search_results=[
                {"title": "Paper A", "abstract": "Content A"},
                {"title": "Paper B", "abstract": "Content B"},
            ],
        )

        mock_response = json.dumps({
            "reasoning": "relevant", "query_relevance": 0.9, "result_quality": 0.8,
            "content_issues": False, "confidence": 0.95, "score": 0.85,
        })

        with patch.object(LLMSearchResultRelevance, "send_messages", return_value=mock_response):
            with patch.object(LLMSearchResultRelevance, "create_client"):
                LLMSearchResultRelevance.client = MagicMock()
                detail = LLMSearchResultRelevance.eval(data)

        assert detail.score == pytest.approx(0.85, abs=0.01)
        assert detail.status is False
        LLMSearchResultRelevance.client = None

    def test_grade_single_method(self):
        mock_response = json.dumps({
            "reasoning": "good", "query_relevance": 0.9, "result_quality": 0.8,
            "content_issues": False, "confidence": 0.95, "score": 0.88,
        })

        with patch.object(LLMSearchResultRelevance, "send_messages", return_value=mock_response):
            with patch.object(LLMSearchResultRelevance, "create_client"):
                LLMSearchResultRelevance.client = MagicMock()
                grade = LLMSearchResultRelevance.grade_single(
                    query="test", title="Test Paper", abstract="Content"
                )

        assert grade.score == 0.88
        assert grade.error == ""
        LLMSearchResultRelevance.client = None


class TestRetrievalExecutorIntegration:
    """Integration tests for the unified RetrievalExecutor pipeline."""

    def test_traces_to_data_rows(self):
        from dingo.exec.retrieval import RetrievalExecutor

        traces = [
            {
                "task": "TestTask",
                "queries": [
                    {
                        "qid": "q1",
                        "query_text": "What is ML?",
                        "top_api_results": [
                            {"rank": 1, "title": "ML Paper", "abstract": "...",
                             "resolved_corpus_id": "doc1"},
                        ],
                        "gold_doc_ids": ["doc1", "doc2"],
                    },
                    {
                        "qid": "q2",
                        "query_text": "What is DL?",
                        "error": "timeout",
                        "top_api_results": [],
                    },
                ],
            }
        ]

        rows = RetrievalExecutor._traces_to_data_rows(traces)
        assert len(rows) == 1  # q2 skipped due to error
        assert rows[0].prompt == "What is ML?"
        assert rows[0].reference == ["doc1", "doc2"]
        assert len(rows[0].search_results) == 1

    def test_evaluate_data_rows_with_rule_evaluators(self):
        from dingo.config.input_args import EvalPiplineConfig
        from dingo.exec.retrieval import RetrievalExecutor
        from dingo.model import Model

        Model.load_model()

        data_rows = [
            Data(
                data_id="q1",
                prompt="test",
                search_results=[
                    {"rank": 1, "resolved_corpus_id": "d1"},
                    {"rank": 2, "resolved_corpus_id": "d2"},
                ],
                reference=["d1"],
            ),
        ]

        eval_configs = [
            EvalPiplineConfig(name="RuleNDCG"),
            EvalPiplineConfig(name="RuleRecall"),
        ]

        from dingo.config.input_args import InputArgs, RetrievalArgs
        input_args = InputArgs(
            input_path="test",
            output_path="/tmp/test",
            executor={"retrieval": RetrievalArgs(backend="agentic", api_url="http://test").model_dump()},
        )
        executor = RetrievalExecutor(input_args)
        results = executor._evaluate_data_rows(data_rows, eval_configs)

        assert len(results) == 1
        details = results[0].eval_details["retrieval"]
        assert len(details) == 2
        ndcg_detail = next(d for d in details if d.metric == "RuleNDCG")
        assert ndcg_detail.score == pytest.approx(1.0)
        recall_detail = next(d for d in details if d.metric == "RuleRecall")
        assert recall_detail.score == pytest.approx(1.0)

    def test_aggregate_results(self):
        from dingo.config.input_args import InputArgs, RetrievalArgs
        from dingo.exec.retrieval import RetrievalExecutor
        from dingo.io import ResultInfo, SummaryModel
        from dingo.io.output.eval_detail import EvalDetail

        input_args = InputArgs(
            input_path="test",
            output_path="/tmp/test",
            executor={"retrieval": RetrievalArgs(backend="agentic", api_url="http://test").model_dump()},
        )
        executor = RetrievalExecutor(input_args)

        results = [
            ResultInfo(
                dingo_id="q1",
                eval_status=False,
                eval_details={"retrieval": [
                    EvalDetail(metric="RuleNDCG", score=0.8, status=False, label=["QUALITY_GOOD"]),
                    EvalDetail(metric="RuleRecall", score=1.0, status=False, label=["QUALITY_GOOD"]),
                ]},
            ),
            ResultInfo(
                dingo_id="q2",
                eval_status=False,
                eval_details={"retrieval": [
                    EvalDetail(metric="RuleNDCG", score=0.6, status=False, label=["QUALITY_GOOD"]),
                    EvalDetail(metric="RuleRecall", score=0.5, status=False, label=["QUALITY_GOOD"]),
                ]},
            ),
        ]

        summary = SummaryModel()
        summary = executor._aggregate_results(results, summary)
        assert summary.total == 2
        assert "retrieval" in summary.metrics_score_stats
        ndcg_stats = summary.metrics_score_stats["retrieval"]["RuleNDCG"]
        assert ndcg_stats["score_average"] == 0.7
        recall_stats = summary.metrics_score_stats["retrieval"]["RuleRecall"]
        assert recall_stats["score_average"] == 0.75
