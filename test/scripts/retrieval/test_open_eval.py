"""Unit tests for open eval (LLM-as-Judge search result grading)."""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

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


class TestLLMSearchResultRelevanceGrader:
    def test_grade_with_mocked_client(self):
        grader = LLMSearchResultRelevance(
            model="test-model",
            api_key="test-key",
            api_url="http://test",
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "reasoning": "Highly relevant",
            "query_relevance": 0.95,
            "result_quality": 0.9,
            "content_issues": False,
            "confidence": 0.98,
            "score": 0.92,
        })

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        grader._client = mock_client

        grade = grader.grade(
            query="machine learning papers",
            title="Deep Learning Review",
            abstract="A comprehensive review of deep learning...",
        )

        assert grade.score == 0.92
        assert grade.query_relevance == 0.95
        assert grade.error == ""
        mock_client.chat.completions.create.assert_called_once()

    def test_grade_handles_api_error(self):
        grader = LLMSearchResultRelevance(
            model="test-model", api_key="test-key",
        )
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API down")
        grader._client = mock_client

        grade = grader.grade(query="test", title="test")
        assert grade.error
        assert "API down" in grade.error


# class TestRetrievalExecutorOpenEval:
#     """Integration test for _run_open_eval on synthetic traces."""

#     def test_run_open_eval_on_traces(self):
#         from dingo.config.input_args import OpenEvalArgs
#         from dingo.exec.retrieval import RetrievalExecutor

#         traces = [
#             {
#                 "task": "TestTask",
#                 "queries": [
#                     {
#                         "qid": "q1",
#                         "query_text": "What is transformers?",
#                         "top_api_results": [
#                             {"rank": 1, "title": "Attention Is All You Need", "abstract": "We propose a new model...", "score": 0.9},
#                             {"rank": 2, "title": "BERT paper", "abstract": "BERT is a...", "score": 0.8},
#                         ],
#                     },
#                 ],
#             },
#         ]

#         oe_args = OpenEvalArgs(
#             enabled=True,
#             model="test-model",
#             key="test-key",
#             top_k=2,
#         )

#         mock_grade = RelevanceGrade(
#             score=0.85, query_relevance=0.9, result_quality=0.8,
#             confidence=0.95, reasoning="good",
#         )

#         with patch.object(LLMSearchResultRelevance, "grade", return_value=mock_grade):
#             metrics = RetrievalExecutor._run_open_eval(
#                 traces, oe_args, ["TestTask"],
#             )

#         assert "TestTask" in metrics
#         assert metrics["TestTask"]["open_eval_mean_score"] == pytest.approx(0.85, abs=0.01)
#         assert metrics["TestTask"]["open_eval_graded_pairs"] == 2

#         assert traces[0]["queries"][0]["top_api_results"][0]["llm_grade"]["score"] == 0.85


# class TestStandaloneOpenEval:
#     """Test standalone open eval with query file."""

#     def test_execute_standalone(self):
#         from dingo.config.input_args import InputArgs, OpenEvalArgs, RetrievalArgs
#         from dingo.exec.retrieval import RetrievalExecutor
#         from dingo.retrieval.search_client import PaperResult, SearchResponse

#         queries = [
#             {"query": "machine learning basics"},
#             {"query": "neural network architectures"},
#         ]

#         with tempfile.NamedTemporaryFile(
#             mode="w", suffix=".jsonl", delete=False
#         ) as f:
#             for q in queries:
#                 f.write(json.dumps(q) + "\n")
#             queries_path = f.name

#         with tempfile.TemporaryDirectory() as tmpdir:
#             try:
#                 ra = RetrievalArgs(
#                     backend="agentic",
#                     api_url="http://test",
#                     api_token="test-token",
#                     limit=5,
#                     open_eval=OpenEvalArgs(
#                         enabled=True,
#                         model="test-model",
#                         key="test-key",
#                         top_k=2,
#                     ),
#                     input_queries=queries_path,
#                 )
#                 input_args = InputArgs(
#                     task_name="test_open_eval",
#                     input_path="__open_eval__",
#                     output_path=tmpdir,
#                     executor={"retrieval": ra.model_dump()},
#                 )
#                 executor = RetrievalExecutor(input_args)

#                 mock_response = SearchResponse(
#                     query="test",
#                     results=[
#                         PaperResult(paper_id="p1", title="ML Intro", abstract="Intro to ML..."),
#                         PaperResult(paper_id="p2", title="DL Primer", abstract="Deep learning..."),
#                     ],
#                     response_time_ms=100.0,
#                     status_code=200,
#                 )
#                 mock_grade = RelevanceGrade(
#                     score=0.78, query_relevance=0.8, result_quality=0.75,
#                     confidence=0.9, reasoning="relevant",
#                 )

#                 with patch(
#                     "dingo.exec.retrieval.create_client"
#                 ) as mock_create:
#                     mock_client = MagicMock()
#                     mock_client.search.return_value = mock_response
#                     mock_create.return_value = mock_client

#                     with patch.object(
#                         LLMSearchResultRelevance, "grade", return_value=mock_grade
#                     ):
#                         summary = executor.execute()

#                 assert summary.score == pytest.approx(0.78, abs=0.01)
#                 assert summary.total == 2

#                 summary_path = os.path.join(summary.output_path, "summary.json")
#                 assert os.path.exists(summary_path)
#                 with open(summary_path) as sf:
#                     saved = json.load(sf)
#                 assert saved["config"]["mode"] == "standalone_open_eval"

#             finally:
#                 os.unlink(queries_path)
