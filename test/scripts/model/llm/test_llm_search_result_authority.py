from dingo.model.llm.llm_search_result_authority import LLMSearchResultAuthority, _has_doi_in_locations


class NonSerializableLocation:
    pass


def test_has_doi_in_location_dict_or_string():
    assert _has_doi_in_locations([{"url": "https://doi.org/10.1000/test"}])
    assert _has_doi_in_locations(["https://DOI.ORG/10.1000/test"])


def test_has_doi_in_locations_ignores_invalid_shapes():
    assert not _has_doi_in_locations(True)
    assert not _has_doi_in_locations({"url": "https://doi.org/10.1000/test"})
    assert not _has_doi_in_locations([NonSerializableLocation()])


def test_authority_grade_handles_non_serializable_location():
    grade = LLMSearchResultAuthority().grade(
        result={"doi": "", "locations": [NonSerializableLocation()]},
    )

    assert grade.doi_score == 0.0


def test_nature_portfolio_families_are_recognized():
    grader = LLMSearchResultAuthority()

    for venue in (
        "Nature Physics",
        "Nature Communications",
        "npj Digital Medicine",
        "Communications Biology",
        "Scientific Reports",
        "Scientific Data",
    ):
        grade = grader.grade(result={"publication_venue_name_unified": venue})
        assert grade.venue_score == 0.85
        assert grade.reason == "prestigious_venue_family"


def test_generic_science_names_do_not_match_science_family():
    grader = LLMSearchResultAuthority()

    named_only = grader.grade(result={"publication_venue_name_unified": "Grand Garden of Science"})
    structured = grader.grade(
        result={
            "publication_venue_name_unified": "Chemical Engineering Science",
            "publication_venue_type": "journal",
        }
    )

    assert named_only.venue_score == 0.4
    assert named_only.reason == "named_venue"
    assert structured.venue_score == 0.65
    assert structured.reason == "structured_journal_or_conference"


def test_repository_takes_priority_over_name_patterns():
    grade = LLMSearchResultAuthority().grade(
        result={"publication_venue_name_unified": "Open Science Framework"},
    )

    assert grade.venue_score == 0.45
    assert grade.reason == "repository_or_preprint"


def test_issn_and_recognized_publisher_provide_venue_fallbacks():
    grader = LLMSearchResultAuthority()
    issn_grade = grader.grade(
        result={
            "publication_venue_name_unified": "Specialist Research Journal",
            "publication_venue_issn": ["1234-567X"],
        }
    )
    publisher_grade = grader.grade(
        result={
            "publication_venue_name_unified": "Specialist Research Journal",
            "publication_publisher": ["Oxford University Press"],
        }
    )

    assert issn_grade.venue_score == 0.65
    assert issn_grade.reason == "structured_journal_or_conference"
    assert publisher_grade.venue_score == 0.75
    assert publisher_grade.reason == "recognized_scholarly_publisher_or_venue"


def test_html_highlight_is_removed_before_venue_matching():
    grade = LLMSearchResultAuthority().grade(
        result={"publication_venue_name_unified": "<span>Nature</span> Medicine"},
    )

    assert grade.venue_score == 0.85


def test_ieee_is_recognized_inside_full_conference_name():
    grade = LLMSearchResultAuthority().grade(
        result={
            "publication_venue_name_unified": (
                "13th IEEE International Workshops on Enabling Technologies"
            )
        },
    )

    assert grade.venue_score == 0.75
    assert grade.reason == "recognized_scholarly_publisher_or_venue"


def test_ebook_platform_and_academic_publisher_are_recognized():
    grader = LLMSearchResultAuthority()
    ebook_grade = grader.grade(
        result={
            "publication_venue_name_unified": "Springer eBooks",
            "publication_venue_type": "ebook platform",
        }
    )
    publisher_grade = grader.grade(
        result={"publication_publisher": ["Walter De Gruyter & Co"]},
    )

    assert ebook_grade.venue_score == 0.55
    assert ebook_grade.reason == "academic_book_series"
    assert publisher_grade.venue_score == 0.75
    assert publisher_grade.reason == "recognized_scholarly_publisher_or_venue"


def test_normalized_citation_percentile_takes_priority():
    grade = LLMSearchResultAuthority().grade(
        result={
            "citation_count": 1,
            "fwci": 8.0,
            "citation_normalized_percentile": {"value": 0.93},
        }
    )

    assert grade.citation_score == 0.93
    assert grade.citation_basis == "citation_normalized_percentile"


def test_negative_citation_counts_are_treated_as_zero():
    grade = LLMSearchResultAuthority().grade(
        result={
            "citation_count": -1,
            "influential_citation_count": -1,
            "fwci": -1,
        }
    )

    assert grade.citation_score == 0.0
    assert grade.influential_citation_score == 0.0
