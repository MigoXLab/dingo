"""
Tests for LLMSearchQualityPointwise and LLMSearchQualityListwise evaluators.

Covers:
- Pointwise: fan-out grading, JSON parsing, aggregation, empty results
- Listwise: metadata table construction, JSON parsing, empty results
- CSV input reading in RetrievalExecutor

Run:
    pytest test/scripts/model/llm/test_search_quality.py -v
"""

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.model.llm.llm_search_quality import LLMSearchQualityListwise, LLMSearchQualityPointwise, _format_authors_short, _parse_json_response, _strip_code_fence

SAMPLE_SEARCH_RESULTS = [
    {
        "rank": 1,
        "title": "DeepSeek-R1: Incentivizing Reasoning Capability",
        "abstract": "We introduce our first-generation reasoning model...",
        "venue": "arXiv.org",
        "year": 2025,
        "citation_count": 3403,
        "authors": "DeepSeek-AI, Daya Guo",
        "paper_type": "JournalArticle",
        "score": 0.97,
    },
    {
        "rank": 2,
        "title": "A Survey on Deep Learning",
        "abstract": "This survey covers recent advances in deep learning.",
        "venue": "Nature Reviews",
        "year": 2023,
        "citation_count": 150,
        "authors": "Jane Smith, John Doe",
        "paper_type": "Review",
        "score": 0.85,
    },
    {
        "rank": 3,
        "title": "Attention Is All You Need",
        "abstract": "The dominant sequence transduction models...",
        "venue": "NeurIPS",
        "year": 2017,
        "citation_count": 100000,
        "authors": "Vaswani et al.",
        "paper_type": "ConferencePaper",
        "score": 0.80,
    },
]


def _make_data(query: str = "DeepSeek", results=None):
    return Data(
        data_id="test_q1",
        prompt=query,
        search_results=results if results is not None else SAMPLE_SEARCH_RESULTS,
        reference=[],
    )


class TestHelpers:
    def test_strip_code_fence_json(self):
        assert _strip_code_fence('```json\n{"a":1}\n```') == '{"a":1}'

    def test_strip_code_fence_plain(self):
        assert _strip_code_fence('{"a":1}') == '{"a":1}'

    def test_parse_json_response(self):
        result = _parse_json_response('```json\n{"score": 0.8}\n```')
        assert result["score"] == 0.8

    def test_format_authors_string(self):
        assert _format_authors_short("Alice, Bob") == "Alice, Bob"

    def test_format_authors_list_of_dicts(self):
        authors = [{"name": "Alice"}, {"name": "Bob"}, {"name": "Charlie"}]
        result = _format_authors_short(authors)
        assert "Alice" in result
        assert "Bob" in result

    def test_format_authors_long_list(self):
        authors = [{"name": f"Author{i}"} for i in range(10)]
        result = _format_authors_short(authors)
        assert "+5 more" in result


class TestLLMSearchQualityPointwise:
    def test_eval_empty_results(self):
        data = _make_data(results=[])
        result = LLMSearchQualityPointwise.eval(data)
        assert result.metric == "LLMSearchQualityPointwise"
        assert result.score == 0.0
        assert any("NoSearchResults" in label for label in result.label)

    def test_eval_no_search_results_attr(self):
        data = Data(data_id="x", prompt="test")
        result = LLMSearchQualityPointwise.eval(data)
        assert result.score == 0.0

    @patch.object(LLMSearchQualityPointwise, "send_messages")
    @patch.object(LLMSearchQualityPointwise, "create_client")
    def test_eval_success(self, mock_create, mock_send):
        mock_create.return_value = None
        LLMSearchQualityPointwise.client = MagicMock()

        mock_send.return_value = json.dumps({
            "relevance": 0.9,
            "content_effectiveness": 0.8,
            "reasoning": "Highly relevant paper",
        })

        llm_config = EvaluatorLLMArgs(
            model="test-model",
            key="test-key",
            api_url="http://test/v1",
        )
        from dingo.model import Model
        Model.set_config_llm(LLMSearchQualityPointwise, llm_config)

        data = _make_data(results=SAMPLE_SEARCH_RESULTS[:1])
        result = LLMSearchQualityPointwise.eval(data)

        assert result.metric == "LLMSearchQualityPointwise"
        assert result.score == pytest.approx(0.9, abs=0.01)
        assert mock_send.call_count == 1

    @patch.object(LLMSearchQualityPointwise, "send_messages")
    @patch.object(LLMSearchQualityPointwise, "create_client")
    def test_eval_multiple_results(self, mock_create, mock_send):
        mock_create.return_value = None
        LLMSearchQualityPointwise.client = MagicMock()

        responses = [
            json.dumps({"relevance": 0.9, "content_effectiveness": 0.8, "reasoning": "good"}),
            json.dumps({"relevance": 0.7, "content_effectiveness": 0.6, "reasoning": "ok"}),
            json.dumps({"relevance": 0.5, "content_effectiveness": 0.4, "reasoning": "fair"}),
        ]
        mock_send.side_effect = responses

        llm_config = EvaluatorLLMArgs(
            model="test-model",
            key="test-key",
            api_url="http://test/v1",
        )
        from dingo.model import Model
        Model.set_config_llm(LLMSearchQualityPointwise, llm_config)

        data = _make_data()
        result = LLMSearchQualityPointwise.eval(data)

        assert result.metric == "LLMSearchQualityPointwise"
        expected_mean = (0.9 + 0.7 + 0.5) / 3
        assert result.score == pytest.approx(expected_mean, abs=0.01)
        assert mock_send.call_count == 3

    @patch.object(LLMSearchQualityPointwise, "send_messages")
    @patch.object(LLMSearchQualityPointwise, "create_client")
    def test_eval_llm_failure(self, mock_create, mock_send):
        mock_create.return_value = None
        LLMSearchQualityPointwise.client = MagicMock()
        mock_send.side_effect = Exception("API error")

        llm_config = EvaluatorLLMArgs(
            model="test-model",
            key="test-key",
            api_url="http://test/v1",
        )
        from dingo.model import Model
        Model.set_config_llm(LLMSearchQualityPointwise, llm_config)

        data = _make_data(results=SAMPLE_SEARCH_RESULTS[:1])
        result = LLMSearchQualityPointwise.eval(data)

        assert result.score == 0.0
        assert any("error" in str(r) for r in result.reason)


class TestLLMSearchQualityListwise:
    def test_eval_empty_results(self):
        data = _make_data(results=[])
        result = LLMSearchQualityListwise.eval(data)
        assert result.metric == "LLMSearchQualityListwise"
        assert result.score == 0.0

    @patch.object(LLMSearchQualityListwise, "send_messages")
    @patch.object(LLMSearchQualityListwise, "create_client")
    def test_eval_success(self, mock_create, mock_send):
        mock_create.return_value = None
        LLMSearchQualityListwise.client = MagicMock()

        mock_send.return_value = json.dumps({
            "authority": 0.8,
            "timeliness": 0.7,
            "diversity": 0.6,
            "reasoning": "Good mix of venues and years",
        })

        llm_config = EvaluatorLLMArgs(
            model="test-model",
            key="test-key",
            api_url="http://test/v1",
        )
        from dingo.model import Model
        Model.set_config_llm(LLMSearchQualityListwise, llm_config)

        data = _make_data()
        result = LLMSearchQualityListwise.eval(data)

        assert result.metric == "LLMSearchQualityListwise"
        expected = 0.8 * 0.4 + 0.7 * 0.3 + 0.6 * 0.3
        assert result.score == pytest.approx(expected, abs=0.01)
        assert mock_send.call_count == 1

        reason_json = json.loads(result.reason[2])
        assert reason_json["authority"] == 0.8
        assert reason_json["timeliness"] == 0.7
        assert reason_json["diversity"] == 0.6

    @patch.object(LLMSearchQualityListwise, "send_messages")
    @patch.object(LLMSearchQualityListwise, "create_client")
    def test_eval_llm_failure(self, mock_create, mock_send):
        mock_create.return_value = None
        LLMSearchQualityListwise.client = MagicMock()
        mock_send.side_effect = Exception("API error")

        llm_config = EvaluatorLLMArgs(
            model="test-model",
            key="test-key",
            api_url="http://test/v1",
        )
        from dingo.model import Model
        Model.set_config_llm(LLMSearchQualityListwise, llm_config)

        data = _make_data()
        result = LLMSearchQualityListwise.eval(data)

        assert result.score == 0.0
        assert result.status is True


try:
    from dingo.exec.retrieval import RetrievalExecutor
    _HAS_RETRIEVAL = True
except ImportError:
    _HAS_RETRIEVAL = False


@pytest.mark.skipif(not _HAS_RETRIEVAL, reason="mteb/retrieval deps not available")
class TestCSVInput:
    def test_read_csv_queries(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("query\n")
            f.write("DeepSeek\n")
            f.write("LLM reasoning\n")
            f.write("attention mechanism\n")
            csv_path = f.name

        try:
            items = RetrievalExecutor._read_query_items(csv_path)
            assert len(items) == 3
            assert items[0]["query"] == "DeepSeek"
            assert items[1]["query"] == "LLM reasoning"
            assert items[2]["query"] == "attention mechanism"
        finally:
            os.unlink(csv_path)

    def test_read_jsonl_queries(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
        ) as f:
            f.write(json.dumps({"query": "test query 1"}) + "\n")
            f.write(json.dumps({"query": "test query 2"}) + "\n")
            jsonl_path = f.name

        try:
            items = RetrievalExecutor._read_query_items(jsonl_path)
            assert len(items) == 2
            assert items[0]["query"] == "test query 1"
        finally:
            os.unlink(jsonl_path)

    def test_read_csv_empty_rows_skipped(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
            f.write("query\n")
            f.write("valid query\n")
            f.write("\n")
            f.write("   \n")
            f.write("another valid\n")
            csv_path = f.name

        try:
            items = RetrievalExecutor._read_query_items(csv_path)
            assert len(items) == 2
        finally:
            os.unlink(csv_path)


@pytest.mark.skipif(not _HAS_RETRIEVAL, reason="mteb/retrieval deps not available")
class TestPaperToResultDict:
    def test_basic_conversion(self):
        paper = MagicMock()
        paper.paper_id = "p123"
        paper.title = "Test Paper"
        paper.abstract = "Test abstract"
        paper.score = 0.95
        paper.raw = {
            "publication_venue_name_unified": "Nature",
            "publication_published_year": 2024,
            "citation_count": 500,
            "author": [{"name": "Alice"}, {"name": "Bob"}],
            "type": ["JournalArticle"],
        }

        result = RetrievalExecutor._paper_to_result_dict(1, paper)

        assert result["rank"] == 1
        assert result["title"] == "Test Paper"
        assert result["venue"] == "Nature"
        assert result["year"] == 2024
        assert result["citation_count"] == 500
        assert "Alice" in result["authors"]
        assert result["paper_type"] == "JournalArticle"

    def test_missing_raw_fields(self):
        paper = MagicMock()
        paper.paper_id = "p456"
        paper.title = "Minimal Paper"
        paper.abstract = ""
        paper.score = 0.5
        paper.raw = {}

        result = RetrievalExecutor._paper_to_result_dict(3, paper)

        assert result["venue"] == ""
        assert result["year"] is None
        assert result["citation_count"] is None
        assert result["paper_type"] == ""


class TestOpenEvalArgs:
    def test_eval_mode_default(self):
        from dingo.config.input_args import OpenEvalArgs

        args = OpenEvalArgs(enabled=True)
        assert args.eval_mode == "relevance"

    def test_eval_mode_quality(self):
        from dingo.config.input_args import OpenEvalArgs

        args = OpenEvalArgs(enabled=True, eval_mode="quality")
        assert args.eval_mode == "quality"
