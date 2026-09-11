"""Tests for the end-to-end search result evaluation example."""

import json
import os
import sys
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import pytest

EXAMPLE_DIR = Path(__file__).resolve().parents[3] / "examples" / "retrieval"
if str(EXAMPLE_DIR) not in sys.path:
    sys.path.insert(0, str(EXAMPLE_DIR))

import sdk_eval_search_result  # noqa: E402
from sdk_eval_search_result import build_reports, clear_executor_classification_dirs, load_env_file, metric_thresholds, normalize_search_result, retrieve_queries  # noqa: E402,E501
from search_result_eval_utils import load_queries, write_classified_jsonl  # noqa: E402

from dingo.retrieval.search_client import PaperResult, SearchResponse  # noqa: E402


def test_cached_agentic_response_enters_standard_executor_input(tmp_path):
    from sdk_eval_search_result import flatten_query_results
    raw = tmp_path / "raw.jsonl"
    raw.write_text(json.dumps({"query": "中文", "response": {"hits": [
        {"doc_id": "d1", "offset": 12, "chunk": "中文片段", "title": "标题"}
    ]}}), encoding="utf-8")
    flattened = tmp_path / "flattened.jsonl"
    count, empty = flatten_query_results(raw, flattened, top_k=100, max_queries=None,
                                        eval_profile="agentic")
    row = json.loads(flattened.read_text(encoding="utf-8"))
    assert count == 1 and not empty
    assert row["search_result"]["_eval_profile"] == "agentic"
    assert row["search_result"]["chunk"] == "中文片段"
    assert row["search_result"]["offset"] == 12


def test_null_effectiveness_is_excluded_without_promoting_later_ranks():
    from search_result_eval_utils import rank_discounted_mean
    assert rank_discounted_mean([None, 0.5]) == 0.5
    assert rank_discounted_mean([None]) is None
    assert rank_discounted_mean([1.0, None, 0.0]) == pytest.approx(2 / 3)
    records = [_record("query", 1, 1.0, None, 0.5), _record("query", 2, 1.0, 0.5, 0.5)]
    summary, rows, *_ = build_reports(records, _args(), SimpleNamespace(output_path="unused"))
    assert rows[0]["effectiveness"] == 0.5
    assert "REVIEW_EXECUTION_ERROR" in rows[0]["label"]
    assert summary["effectiveness_unscored_count"] == 1


def test_issue_export_keeps_evidence_and_deduplicates_labels(tmp_path):
    record = _record("query", 1, 1, 1, 1)
    detail = record["eval_details"]["search_result"][0]
    detail["label"] = ["Relevance.Low", "Relevance.Low"]
    sdk_eval_search_result.write_issue_lists(tmp_path, [record])
    rows = (tmp_path / "issues" / "Relevance.Low.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    assert json.loads(rows[0])["raw_data"]["rank"] == 1


def test_recovered_labels_export_as_separate_issue_files(tmp_path):
    from dingo.model.llm.llm_search_result_effectiveness import (
        LLMSearchResultEffectiveness, _issues_to_labels,
    )
    grade = LLMSearchResultEffectiveness().grade(result={
        '_eval_profile': 'agentic', 'title': 'Title', 'abstract': 'Abstract',
        'chunk': 'Chunk', '_source_quality': 1,
        '_metadata_recovered_fields': {'title': 'meta-search', 'abstract': 'meta-search'},
    })
    record = _record('query', 1, 1, grade.score, 1)
    labels = _issues_to_labels(grade.issues)
    record['eval_details']['search_result'][0]['label'] = labels
    sdk_eval_search_result.write_issue_lists(tmp_path, [record])
    assert json.loads((tmp_path / 'issue_counts.json').read_text(encoding='utf-8')) == {
        label: 1 for label in labels}
    for label in labels:
        assert (tmp_path / 'issues' / f'{label}.jsonl').exists()
        assert sdk_eval_search_result.EFFECTIVENESS_LABEL_TO_ISSUE[label].endswith('_recovered')


def test_agentic_local_executor_integration_without_network(tmp_path, monkeypatch):
    from dingo.config import InputArgs
    from dingo.exec import Executor
    from dingo.io.output.eval_detail import EvalDetail
    from dingo.model.llm.llm_search_result_authority import LLMSearchResultAuthority
    from dingo.model.llm.llm_search_result_effectiveness import LLMSearchResultEffectiveness
    from dingo.model.llm.llm_search_result_relevance import LLMSearchResultRelevance

    monkeypatch.setenv("LOCAL_DEPLOYMENT_MODE", "true")
    invoked = []

    def evaluate(cls, data):
        assert data.search_result["_eval_profile"] == "agentic"
        assert data.search_result["chunk"] == "evidence"
        invoked.append(cls.__name__)
        return EvalDetail(metric=cls.__name__, score=1.0, label=["QUALITY_GOOD"], reason=[{}])
    graders = (LLMSearchResultRelevance, LLMSearchResultEffectiveness, LLMSearchResultAuthority)
    for grader in graders:
        monkeypatch.setattr(grader, "eval", classmethod(evaluate))
    path = tmp_path / "input.jsonl"
    path.write_text(json.dumps({"query": "q", "rank": 1, "query_index": 1,
                              "search_result": {"_eval_profile": "agentic", "chunk": "evidence"}}),
                    encoding="utf-8")
    args = _args()
    args.openai_api_key = "test-not-used"
    args.openai_base_url = "https://example.invalid/v1"
    args.openai_session_id = None
    args.batch_size = 1
    args.output_dir = tmp_path / "output"
    config = sdk_eval_search_result.build_executor_input(args, path)
    summary = Executor.exec_map["local"](InputArgs(**config)).execute()
    records = sdk_eval_search_result.load_executor_records(summary.output_path)
    assert set(invoked) == {grader.__name__ for grader in graders}
    assert len(records) == 1


def _record(
    query: str,
    rank: int,
    relevance: float,
    effectiveness: float,
    authority: float,
) -> dict:
    return {
        "raw_data": {
            "query": query,
            "query_index": 1,
            "rank": rank,
            "title": f"Result {rank}",
            "search_result": {
                "title": f"Result {rank}",
                "abstract": f"Abstract {rank}",
                "_eval_query": query,
            },
        },
        "eval_details": {
            "search_result": [
                {"metric": "LLMSearchResultRelevance", "score": relevance},
                {"metric": "LLMSearchResultEffectiveness", "score": effectiveness},
                {"metric": "LLMSearchResultAuthority", "score": authority},
            ]
        }
    }


def _args() -> Namespace:
    return Namespace(
        top_k=10,
        threshold=0.15,
        openai_model="test-model",
        prompt_mode="detailed",
        llm_max_tokens=1024,
        openai_temperature=0.0,
        llm_timeout=60.0,
        llm_workers=1,
        disable_effectiveness_llm_quality=False,
        effectiveness_llm_max_tokens=512,
    )


def test_load_queries_supports_query_only_jsonl(tmp_path):
    path = tmp_path / "queries.jsonl"
    path.write_text(
        '\n'.join((json.dumps({"query": "first"}), json.dumps({"query_text": "second"}))),
        encoding="utf-8",
    )

    assert load_queries(path) == ["first", "second"]


def test_load_queries_deduplicates_queries(tmp_path):
    path = tmp_path / "queries.jsonl"
    path.write_text(
        "\n".join((json.dumps({"query": "same"}), json.dumps({"query": "same"}))),
        encoding="utf-8",
    )

    assert load_queries(path) == ["same"]


def test_load_env_file_does_not_override_process_environment(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    path.write_text("EXISTING=value-from-file\nNEW_VALUE=loaded\n", encoding="utf-8")
    monkeypatch.setenv("EXISTING", "value-from-process")
    monkeypatch.delenv("NEW_VALUE", raising=False)

    load_env_file(path)

    assert os.environ["EXISTING"] == "value-from-process"
    assert os.environ["NEW_VALUE"] == "loaded"


def test_dimension_threshold_defaults_and_unified_override():
    defaults = metric_thresholds(Namespace(threshold=None))
    unified = metric_thresholds(Namespace(threshold=0.2))

    assert defaults == {"relevance": 0.6, "effectiveness": 0.8, "authority": 0.3}
    assert unified == {"relevance": 0.2, "effectiveness": 0.2, "authority": 0.2}


def test_build_search_client_passes_meta_search_filters(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        sdk_eval_search_result,
        "create_client",
        lambda backend, **kwargs: captured.update(backend=backend, **kwargs),
    )
    args = Namespace(
        retrieval_backend="meta_search",
        search_api_url="https://api.sciverse.space",
        search_api_token="test-token",
        search_type="paper",
        filters_json='{"year_from": 2010}',
        search_timeout=60.0,
        search_rate_limit=1.0,
        search_max_retries=3,
    )

    sdk_eval_search_result._build_search_client(args)

    assert captured["backend"] == "meta_search"
    assert captured["filters"] == {"year_from": 2010}


@pytest.mark.parametrize("filters_json", ["2010", '["invalid"]'])
def test_build_search_client_rejects_invalid_filters(filters_json):
    args = Namespace(
        retrieval_backend="meta_search",
        search_api_url="https://api.sciverse.space",
        search_api_token="test-token",
        search_type="paper",
        filters_json=filters_json,
        search_timeout=60.0,
        search_rate_limit=1.0,
        search_max_retries=3,
    )

    with pytest.raises(ValueError, match="filters-json"):
        sdk_eval_search_result._build_search_client(args)


def test_retrieve_queries_writes_reusable_results_and_request_log(tmp_path, monkeypatch):
    input_path = tmp_path / "queries.jsonl"
    result_path = tmp_path / "retrieval_results.jsonl"
    log_path = tmp_path / "request_log.jsonl"
    input_path.write_text(json.dumps({"query": "test query"}), encoding="utf-8")

    class FakeClient:
        def search(self, query, limit=10):
            return SearchResponse(
                query=query,
                results=[PaperResult(paper_id="p1", title="Test result", raw={"title": "Test result"})],
                response_time_ms=12.5,
                status_code=200,
            )

    monkeypatch.setattr(sdk_eval_search_result, "_build_search_client", lambda args: FakeClient())
    args = Namespace(
        input_jsonl=input_path,
        max_queries=None,
        top_k=10,
        search_workers=1,
        retrieval_backend="meta_search",
    )

    summary = retrieve_queries(args, result_path, log_path)
    saved = json.loads(result_path.read_text(encoding="utf-8"))
    log = json.loads(log_path.read_text(encoding="utf-8"))

    assert saved["query"] == "test query"
    assert saved["results"][0]["title"] == "Test result"
    assert log["result_count"] == 1
    assert summary["success_count"] == 1


def test_normalize_openalex_result_maps_metric_fields():
    raw = {
        "id": "https://openalex.org/W1",
        "doi": "https://doi.org/10.1/example",
        "cited_by_count": 12,
        "publication_year": 2025,
        "type": "article",
        "language": "en",
        "keywords": [{"display_name": "Search"}],
        "authorships": [
            {"author": {"display_name": "A. Author", "orcid": "https://orcid.org/1"}}
        ],
        "primary_location": {
            "source": {
                "display_name": "Journal of Testing",
                "type": "journal",
                "issn": ["1234-5678"],
                "host_organization_name": "Test Publisher",
            }
        },
    }
    paper = PaperResult(
        paper_id=raw["id"],
        title="A result",
        abstract="An abstract",
        score=9.5,
        year=2025,
        raw=raw,
    )

    result = normalize_search_result(paper, "openalex")

    assert result["citation_count"] == 12
    assert result["keywords"] == ["Search"]
    assert result["author"][0]["name"] == "A. Author"
    assert result["publication_venue_name_unified"] == "Journal of Testing"
    assert result["publication_venue_type"] == "journal"
    assert result["publication_publisher"] == ["Test Publisher"]


def test_normalize_agentic_result_keeps_chunk_and_abstract_separate():
    paper = PaperResult(
        paper_id="doc-1",
        title="Agentic title",
        abstract="chunk fallback",
        score=0.9,
        raw={
            "doc_id": "doc-1",
            "title": "Agentic title",
            "chunk": "Evidence chunk",
            "abstract": "Paper abstract",
            "offset": 20,
        },
    )

    result = normalize_search_result(paper, "agentic")

    assert result["chunk"] == "Evidence chunk"
    assert result["abstract"] == "Paper abstract"
    assert result["_eval_profile"] == "agentic"


def test_meta_search_accepts_full_endpoint():
    from dingo.retrieval.backends.agentic import MetaSearchClient

    client = MetaSearchClient(api_url="https://api.sciverse.space/meta-search")

    assert client.base_url == "https://api.sciverse.space"


def test_query_report_uses_rank_weighted_means_and_embeds_full_results():
    records = [
        _record("query", 1, relevance=0.0, effectiveness=0.1, authority=0.3),
        _record("query", 2, relevance=0.2, effectiveness=0.2, authority=0.5),
    ]

    summary, query_rows, _, _, classified = build_reports(
        records,
        _args(),
        SimpleNamespace(output_path="output/test"),
    )

    assert summary["query_aggregation"] == "rank_discounted_mean"
    assert query_rows[0]["relevance"] == 0.07737
    assert query_rows[0]["effectiveness"] == 0.13869
    assert query_rows[0]["authority"] == 0.37737
    assert query_rows[0]["relevance_aggregation"] == "rank_discounted_mean"
    assert classified[0]["labels"] == [
        "QUALITY_BAD.SEARCH_RESULT_RELEVANCE_LOW",
        "QUALITY_BAD.SEARCH_RESULT_EFFECTIVENESS_LOW",
    ]
    assert classified[0]["results"][0]["abstract"] == "Abstract 1"
    assert classified[0]["results"][0]["_evaluation"] == {
        "rank": 1,
        "relevance": 0.0,
        "effectiveness": 0.1,
        "authority": 0.3,
    }
    assert "_eval_query" not in classified[0]["results"][0]


def test_query_report_has_no_overall_and_empty_query_uses_three_low_labels():
    summary, query_rows, result_rows, _, classified = build_reports(
        [],
        _args(),
        SimpleNamespace(output_path="output/test"),
        empty_queries=["empty query"],
    )

    assert "weights" not in summary
    assert "overall" not in summary["metrics"]
    assert "overall" not in query_rows[0]
    assert result_rows == []
    assert classified[0]["labels"] == [
        "QUALITY_BAD.SEARCH_RESULT_RELEVANCE_LOW",
        "QUALITY_BAD.SEARCH_RESULT_EFFECTIVENESS_LOW",
        "QUALITY_BAD.SEARCH_RESULT_AUTHORITY_LOW",
    ]


def test_result_level_executor_summary_is_not_exposed():
    summary, *_ = build_reports(
        [],
        _args(),
        SimpleNamespace(output_path="output/test"),
    )

    assert "result_level" not in summary


def test_clear_executor_classification_dirs(tmp_path):
    (tmp_path / "bad" / "result_level").mkdir(parents=True)
    (tmp_path / "good").mkdir()

    clear_executor_classification_dirs(tmp_path)

    assert not (tmp_path / "bad").exists()
    assert not (tmp_path / "good").exists()


def test_classified_output_contains_query_records_only(tmp_path):
    records = [
        {
            "query": "first",
            "eval_status": True,
            "labels": ["QUALITY_BAD.SEARCH_RESULT_RELEVANCE_LOW"],
            "results": [{"title": "First result"}],
        },
        {
            "query": "second",
            "eval_status": True,
            "labels": ["QUALITY_BAD.SEARCH_RESULT_RELEVANCE_LOW"],
            "results": [{"title": "Second result"}],
        },
    ]

    write_classified_jsonl(tmp_path, records)

    output = tmp_path / "bad" / "QUALITY_BAD" / "SEARCH_RESULT_RELEVANCE_LOW.jsonl"
    lines = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert [line["query"] for line in lines] == ["first", "second"]
    assert all(line["results"] for line in lines)
    assert not (tmp_path / "bad" / "query_level").exists()
    assert not (tmp_path / "bad" / "result_level").exists()
