from types import SimpleNamespace

from dingo.io.input import Data
from dingo.model.llm.llm_search_result_relevance import LLMSearchResultRelevance, RelevanceGrade, _extract_result_dois, _grade_doi_result, _normalize_doi, is_doi_query


def test_normalize_doi_variants():
    assert _normalize_doi("10.1016/j.ijbiomac.2025.143529") == "10.1016/j.ijbiomac.2025.143529"
    assert _normalize_doi("https://doi.org/10.1038/NCOMMS7112") == "10.1038/ncomms7112"
    assert _normalize_doi(":10.1111/jipb.70096") == "10.1111/jipb.70096"
    assert _normalize_doi("PBPK review") == ""
    assert is_doi_query("10.1016/j.ijbiomac.2025.143529")
    assert not is_doi_query("PBPK review")


def test_extract_result_dois_from_supported_fields():
    result = {
        "doi": "https://doi.org/10.1000/ABC",
        "unique_id": "paper:10.2000/xyz",
        "locations": [{"url": "https://doi.org/10.3000/location"}],
    }
    assert _extract_result_dois(result) == [
        "10.1000/abc",
        "10.2000/xyz",
        "10.3000/location",
    ]


def test_extract_result_dois_ignores_non_list_locations():
    assert _extract_result_dois({"locations": True}) == []
    assert _extract_result_dois({"locations": 1}) == []
    assert _extract_result_dois({"locations": {"url": "https://doi.org/10.1000/test"}}) == []


def test_doi_query_uses_exact_match():
    matched = _grade_doi_result(
        "10.1016/j.ijbiomac.2025.143529",
        {"doi": "https://doi.org/10.1016/j.ijbiomac.2025.143529"},
    )
    mismatched = _grade_doi_result(
        "10.1016/j.ijbiomac.2025.143529",
        {"doi": "https://doi.org/10.3390/plants14152362"},
    )

    assert matched is not None and matched.score == 1.0
    assert mismatched is not None and mismatched.score == 0.0
    assert "DOI mismatch" in mismatched.reasoning


def test_non_doi_query_falls_back_to_llm():
    assert _grade_doi_result("PBPK相关综述", {"doi": "10.1000/test"}) is None


def test_agentic_relevance_uses_query_relevance_only(monkeypatch):
    grader = SimpleNamespace(
        grade=lambda **_: RelevanceGrade(
            score=0.4,
            query_relevance=0.9,
            result_quality=0.2,
            confidence=0.8,
        )
    )
    monkeypatch.setattr(
        LLMSearchResultRelevance,
        "_build_from_config",
        classmethod(lambda cls: grader),
    )

    detail = LLMSearchResultRelevance.eval(
        Data(
            query="中文查询",
            search_result={
                "_eval_profile": "agentic",
                "title": "相关标题",
                "chunk": "相关证据",
            },
        )
    )

    assert detail.score == 0.9
    assert detail.reason[0]["judge_overall_score"] == 0.4
    assert detail.reason[0]["score_basis"] == "query_relevance"


def test_meta_and_agentic_select_different_relevance_evidence():
    from dingo.model.llm.llm_search_result_relevance import LLMSearchResultRelevance
    result = {"abstract": "paper abstract", "chunk": "retrieved evidence"}
    assert LLMSearchResultRelevance._extract_abstract(result) == "paper abstract"
    result["_eval_profile"] = "agentic"
    assert LLMSearchResultRelevance._extract_abstract(result) == "retrieved evidence"
