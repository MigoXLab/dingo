import pytest

from dingo.model.llm.llm_search_result_effectiveness import (  # isort: skip
    LLMFieldQuality,
    LLMSearchResultEffectiveness,
    _filter_llm_field_issues,
    _issues_to_labels,
    _looks_like_utf8_latin1_mojibake,
    _rule_abnormal_char_issues,
    _supported_text_evidence,
    _without_image_markup,
    extract_authors,
)


@pytest.mark.parametrize('fields', [('title',), ('abstract',), ('title', 'abstract')])
def test_recovered_fields_are_labeled_without_penalty_or_llm(monkeypatch, fields):
    grader = LLMSearchResultEffectiveness(enable_llm_quality=True)

    def unexpected_llm(**kwargs):
        pytest.fail('Recovery provenance must not trigger LLM calls')

    monkeypatch.setattr(grader, '_judge_llm_field_quality', unexpected_llm)
    grade = grader.grade(result={
        '_eval_profile': 'agentic', 'title': 'Title', 'abstract': 'Abstract',
        'chunk': 'Chunk', '_source_quality': 1,
        '_metadata_recovered_fields': {field: 'meta-search' for field in fields},
    })
    assert grade.score == 1
    assert set(grade.issues) == {f'{field}_recovered' for field in fields}
    assert set(_issues_to_labels(grade.issues)) == {
        f'Effectiveness.Error_{field.title()}_Recovered' for field in fields}


@pytest.mark.parametrize('metadata', [None, [], 'meta-search', {}, {'title': 'other'}])
def test_invalid_recovery_provenance_does_not_create_labels(metadata):
    grade = LLMSearchResultEffectiveness().grade(result={
        '_eval_profile': 'agentic', 'title': 'Title', 'abstract': 'Abstract',
        'chunk': 'Chunk', '_source_quality': 1, '_metadata_recovered_fields': metadata,
    })
    assert not grade.issues


def test_empty_recovered_fields_remain_missing():
    grade = LLMSearchResultEffectiveness().grade(result={
        '_eval_profile': 'agentic', 'title': ' ', 'abstract': '',
        'chunk': 'Chunk', '_source_quality': 1,
        '_metadata_recovered_fields': {'title': 'meta-search', 'abstract': 'meta-search'},
    })
    assert set(grade.issues) == {'missing_title', 'missing_abstract'}
    assert grade.score == 0.5


def test_recovery_labels_do_not_change_meta_search_profile():
    grade = LLMSearchResultEffectiveness().grade(result={
        'title': 'Title', 'abstract': 'Abstract',
        '_metadata_recovered_fields': {'title': 'meta-search'},
    })
    assert 'title_recovered' not in grade.issues

@pytest.mark.parametrize('text', ['刘凤军，64−80', '降解解析' * 30, 'differentiated\u2003thyroid\u00a0carcinoma'])
def test_normal_names_math_and_spaces_do_not_trigger(text):
    assert _rule_abnormal_char_issues(text) == []


@pytest.mark.parametrize('entity', ['&amp;', '&nbsp;', '&quot;', '&lt;', '&alpha;', '&#38;', '&#x26;', '&#X26;'])
def test_html_entity_triggers_candidate_even_in_long_text(entity):
    assert _rule_abnormal_char_issues('readable text ' * 100 + entity) == ['RuleHtmlEntity']


@pytest.mark.parametrize('entity', ['h&amp;auml;nchen', '&amp;', '&auml;', '&#247;', '&#38;', '&#x26;'])
@pytest.mark.parametrize('model_label', ['html_entity', 'html_tag', 'special_char_noise'])
def test_entity_gets_own_label_with_exact_evidence(monkeypatch, entity, model_label):
    grader = LLMSearchResultEffectiveness(enable_llm_quality=True)
    monkeypatch.setattr(grader, '_judge_llm_field_quality', lambda **kw: LLMFieldQuality(
        title_score=0.7, issues=[f'title:{model_label}'], evidence={'title': [entity]}))
    grade = grader.grade(result={'_eval_profile': 'agentic', 'title': 'Title '+entity,
                                 'abstract': 'A', 'chunk': 'C', '_source_quality': 1})
    assert grade.score == pytest.approx(0.925)
    assert _issues_to_labels(grade.issues) == ['Effectiveness.Error_HTML_Entity']


def test_entity_label_requires_entity_in_cited_evidence(monkeypatch):
    grader = LLMSearchResultEffectiveness(enable_llm_quality=True)
    monkeypatch.setattr(grader, '_judge_llm_field_quality', lambda **kw: LLMFieldQuality(
        title_score=0.7, issues=['title:html_entity'], evidence={'title': ['Title']}))
    grade = grader.grade(result={'_eval_profile': 'agentic', 'title': 'Title &amp;',
                                 'abstract': 'A', 'chunk': 'C', '_source_quality': 1})
    assert grade.score == 1
    assert not grade.issues


def test_entity_and_other_noise_are_not_globally_renamed(monkeypatch):
    grader = LLMSearchResultEffectiveness(enable_llm_quality=True)
    monkeypatch.setattr(grader, '_judge_llm_field_quality', lambda **kw: LLMFieldQuality(
        title_score=0.7, issues=['title:html_entity', 'title:special_char_noise'],
        evidence={'title': ['&amp;', '<|noise|>']}))
    grade = grader.grade(result={'_eval_profile': 'agentic', 'title': '&amp; <|noise|>',
                                 'abstract': 'A', 'chunk': 'C', '_source_quality': 1})
    assert set(_issues_to_labels(grade.issues)) == {
        'Effectiveness.Error_HTML_Entity', 'Effectiveness.Error_Special_Char_Noise'}


def test_entity_postfilter_ignores_image_destinations_and_decoded_characters():
    for text in ['![](x.png?a=1&amp;b=2)', 'hänchen & CO2', '&notARealEntity;']:
        assert _filter_llm_field_issues('chunk', text, ['chunk:html_entity']) == []
    assert _filter_llm_field_issues('title', '&amp;', ['title:special_char_noise']) == []


@pytest.mark.parametrize('text', [
    'N & K fertilization', 'https://example.org/?a=1&b=2', '&notARealEntity;',
    '&amp', '&#;', '&#xZZ;', '![](image.jpg?a=1&amp;b=2)',
])
def test_entity_detection_does_not_flag_plain_ampersands_or_image_paths(text):
    assert _rule_abnormal_char_issues(text) == []


def test_entity_title_is_sent_to_llm_as_candidate_not_auto_penalized(monkeypatch):
    grader = LLMSearchResultEffectiveness(enable_llm_quality=True)
    calls = []

    def judge(**kwargs):
        calls.append(kwargs)
        return LLMFieldQuality()

    monkeypatch.setattr(grader, '_judge_llm_field_quality', judge)
    grade = grader.grade(result={'_eval_profile': 'agentic',
        'title': 'the effect of n &amp; k fertilization on sweet cherry in ningxia heliogreenhouse',
        'abstract': 'Readable abstract', 'chunk': 'Readable chunk', '_source_quality': 1})
    assert len(calls) == 1
    assert calls[0]['candidate_fields'] == {'title'}
    assert grade.title_score == 1
    assert not grade.issues


def test_readable_html_table_can_pass_llm_confirmation(monkeypatch):
    grader = LLMSearchResultEffectiveness(enable_llm_quality=True)
    monkeypatch.setattr(grader, '_judge_llm_field_quality', lambda **kw: LLMFieldQuality())
    grade = grader.grade(result={'_eval_profile': 'agentic', 'title': 'T', 'abstract': 'A',
                                 'chunk': '<table><tr><td>CO2</td><td>12</td></tr></table>', '_source_quality': 1})
    assert grade.chunk_score == 1
    assert not grade.issues


@pytest.mark.parametrize('evidence,expected', [([], 1), (['invented'], 1), (['�'], 0.4)])
def test_llm_penalty_requires_exact_evidence(monkeypatch, evidence, expected):
    grader = LLMSearchResultEffectiveness(enable_llm_quality=True)
    monkeypatch.setattr(grader, '_judge_llm_field_quality', lambda **kw: LLMFieldQuality(
        chunk_score=0.4, issues=['chunk:mojibake'], evidence={'chunk': evidence}))
    grade = grader.grade(result={'_eval_profile': 'agentic', 'title': 'T', 'abstract': 'A',
                                 'chunk': 'damaged � word', '_source_quality': 1})
    assert grade.chunk_score == expected


def _mojibake(value: str) -> str:
    return value.encode("utf-8").decode("latin-1")


@pytest.mark.parametrize('image', [
    '![](dt=2026-03-11/ht=00/abc.jpg)',
    '![Figure](https://example.org/a(b).png?x=1&y=2)',
    '![](<images/my figure.png> "caption")',
    '![](images/<noise>.jpg)',
])
def test_markdown_image_destinations_are_not_noise(image):
    assert _rule_abnormal_char_issues(image) == []
    assert not _supported_text_evidence(image, image)


@pytest.mark.parametrize('evidence', [
    '![](dt=2026-03-11/ht=00/abc.jpg)', 'dt=2026-03-11/ht=00/abc.jpg',
])
def test_image_evidence_rejected_even_with_other_rule_candidates(monkeypatch, evidence):
    image = '![](dt=2026-03-11/ht=00/abc.jpg)'
    grader = LLMSearchResultEffectiveness(enable_llm_quality=True)
    monkeypatch.setattr(grader, '_judge_llm_field_quality', lambda **kw: LLMFieldQuality(
        chunk_score=0.7, issues=['chunk:special_char_noise'], evidence={'chunk': [evidence]}))
    grade = grader.grade(result={'_eval_profile': 'agentic', 'title': 'T', 'abstract': 'A',
        'chunk': image + '\n<table><tr><td>Readable</td></tr></table>', '_source_quality': 1})
    assert grade.chunk_score == 1
    assert grade.score == 1
    assert not grade.issues


@pytest.mark.parametrize('text', ['![damaged �](image.jpg)', '![](image.jpg) damaged �'])
def test_image_does_not_hide_real_corruption(text):
    assert 'RuleMojibake' in _rule_abnormal_char_issues(text)
    assert _supported_text_evidence('�', text)


def test_incomplete_image_markup_is_not_removed():
    text = '![](images/broken.jpg'
    assert _without_image_markup(text) == text


def test_detects_utf8_cyrillic_decoded_as_latin1():
    broken = _mojibake("Развитие научных исследований")

    assert _looks_like_utf8_latin1_mojibake(broken)
    assert "RuleMojibake" in _rule_abnormal_char_issues(broken)
    assert _filter_llm_field_issues("title", broken, ["title:mojibake"]) == ["title:mojibake"]
    assert _issues_to_labels(["RuleMojibake", "title:mojibake"]) == ["Effectiveness.Error_Mojibake"]


def test_does_not_flag_valid_latin_or_cyrillic_text():
    assert not _looks_like_utf8_latin1_mojibake("Ð is a valid Icelandic letter")
    assert not _looks_like_utf8_latin1_mojibake("Развитие научных исследований")


def test_detects_mojibake_fragment_in_mixed_language_text():
    broken = "中文标题 | " + _mojibake("Научные исследования")

    assert _looks_like_utf8_latin1_mojibake(broken)


def test_rule_only_grade_penalizes_mojibake_fields():
    broken_title = _mojibake("Развитие научных исследований")
    broken_abstract = _mojibake(
        "В этой статье рассматриваются современные научные исследования и методы анализа данных. " * 4
    )
    grader = LLMSearchResultEffectiveness(enable_llm_quality=False)

    grade = grader.grade(
        title=broken_title,
        abstract=broken_abstract,
        keywords=["research", "analysis", "data"],
        venue="Science Journal",
    )

    assert "RuleMojibake" in grade.issues
    assert grade.title_score == 0.1
    assert grade.abstract_score == 0.1
    assert grade.score < 0.5


def test_extract_authors_supports_common_response_shapes():
    assert extract_authors({"author": [{"name": "Alice"}, {"display_name": "张三"}]}) == ["Alice", "张三"]
    assert extract_authors({"authors": "Alice | Bob"}) == ["Alice", "Bob"]
    assert extract_authors({"author": {"author_name": "Carol"}}) == ["Carol"]


def test_author_is_scored_without_rewarding_author_count():
    grader = LLMSearchResultEffectiveness(enable_llm_quality=False)
    common = {
        "title": "A comprehensive evaluation of academic search result metadata",
        "abstract": "academic search metadata provides useful information for readers " * 15,
        "keywords": ["search", "metadata", "quality", "evaluation", "academic"],
        "venue": "International Journal of Search Quality Research",
    }

    single_author = grader.grade(**common, authors=["Alice"])
    multiple_authors = grader.grade(**common, authors=["Alice", "Bob", "Carol"])
    missing_author = grader.grade(**common)

    assert single_author.author_score == 1.0
    assert multiple_authors.author_score == 1.0
    assert single_author.score == multiple_authors.score
    assert missing_author.author_score == 0.0
    assert missing_author.score == pytest.approx(single_author.score - 0.1)
    assert "missing_author" in missing_author.issues
    assert _issues_to_labels(missing_author.issues) == ["Effectiveness.Error_Author_Miss"]


def test_nonempty_fields_are_not_penalized_for_length_or_item_count():
    grader = LLMSearchResultEffectiveness(enable_llm_quality=False)

    grade = grader.grade(
        title="D",
        abstract="短",
        keywords=["AI"],
        venue="J",
        authors=["Q"],
    )

    assert grade.title_score == 1.0
    assert grade.abstract_score == 1.0
    assert grade.keywords_score == 1.0
    assert grade.venue_score == 1.0
    assert grade.author_score == 1.0
    assert grade.score == 1.0
    assert grade.issues == []


def test_longer_content_does_not_receive_more_effectiveness_credit():
    grader = LLMSearchResultEffectiveness(enable_llm_quality=False)
    short = grader.grade(title="D", abstract="A", keywords=["K"], authors=["Q"])
    long = grader.grade(
        title="A comprehensive academic title",
        abstract="A complete and readable abstract. " * 100,
        keywords=["one", "two", "three", "four", "five"],
        authors=["Alice", "Bob"],
    )

    assert short.score == long.score == 1.0


def test_agentic_effectiveness_uses_four_equal_components():
    grade = LLMSearchResultEffectiveness(enable_llm_quality=False).grade(
        result={
            "_eval_profile": "agentic",
            "title": "Readable title",
            "abstract": "Readable abstract",
            "chunk": "Readable evidence chunk",
            "_source_quality": 0.3,
            "_source_exists": True,
            "_chunk_consistency": 0.0,
            "_source_issue": "chunk_source_inconsistent",
        }
    )

    assert grade.score == pytest.approx((1.0 + 1.0 + 1.0 + 0.3) / 4)
    assert grade.chunk_score == 1.0
    assert grade.source_score == 0.3
    assert grade.chunk_consistency == 0.0
    assert _issues_to_labels(grade.issues) == [
        "Effectiveness.Error_Chunk_Source_Inconsistent"
    ]


def test_agentic_transient_source_error_is_not_scored_as_bad_content():
    grade = LLMSearchResultEffectiveness(enable_llm_quality=False).grade(
        result={
            "_eval_profile": "agentic",
            "title": "Readable title",
            "abstract": "Readable abstract",
            "chunk": "Readable evidence chunk",
            "_source_quality": None,
            "_source_issue": "source_check_failed",
            "_source_check_error": "HTTP 503",
        }
    )

    assert grade.score is None
    assert grade.source_score is None
    assert grade.source_check_error == "HTTP 503"
    assert _issues_to_labels(grade.issues) == [
        "Effectiveness.Error_Source_Check_Failed"
    ]


def test_preview_navigation_text_is_not_treated_as_html():
    abstract = (
        "Preview this article: Meaning and the Structure of Language, by Wallace Chafe, "
        "Page 1 of 1 < Previous page | Next page > "
        "/docserver/preview/fulltext/ce/33/8/collegeenglish18315-1.gif"
    )

    assert "RuleSpecialCharacter" not in _rule_abnormal_char_issues(abstract)

    # LLM quality is enabled deliberately: this text should bypass the LLM
    # because it is not an abnormal-character candidate.
    grade = LLMSearchResultEffectiveness(enable_llm_quality=True).grade(
        title="Meaning and the Structure of Language, by Wallace Chafe",
        abstract=abstract,
        keywords=["Linguistics"],
        venue="College English",
        authors=["Frank Heny"],
    )

    assert grade.score == 1.0
    assert grade.issues == []


@pytest.mark.parametrize(
    "markup",
    [
        "<span class='highlight'>language</span>",
        "<i>language</i>",
        "H<sub>2</sub>O",
        "<scp>AM</scp>",
    ],
)
def test_real_academic_html_tags_remain_detectable(markup: str):
    assert "RuleSpecialCharacter" in _rule_abnormal_char_issues(markup)
    assert _filter_llm_field_issues("title", markup, ["title:html_tag"]) == [
        "title:html_tag"
    ]


def test_missing_venue_is_diagnostic_only_and_does_not_reduce_score():
    grader = LLMSearchResultEffectiveness(enable_llm_quality=False)
    common = {
        "title": "A comprehensive evaluation of academic search result metadata",
        "abstract": "academic search metadata provides useful information for readers " * 15,
        "keywords": ["search", "metadata", "quality", "evaluation", "academic"],
        "authors": ["Alice"],
    }

    with_venue = grader.grade(**common, venue="International Journal of Search Quality Research")
    without_venue = grader.grade(**common, venue="")

    assert with_venue.score == without_venue.score
    assert without_venue.venue_score == 0.0
    assert "missing_venue" not in without_venue.issues
    assert "Effectiveness.Error_Venue_Miss" not in _issues_to_labels(without_venue.issues)


def _complete_result() -> dict:
    return {
        "title": "A comprehensive evaluation of academic search result metadata",
        "abstract": "academic search metadata provides useful information for readers " * 15,
        "keywords": ["search", "metadata", "quality", "evaluation", "academic"],
        "publication_venue_name_unified": "International Journal of Search Quality Research",
        "author": [{"name": "Alice"}],
    }


@pytest.mark.parametrize("field", ["title", "abstract", "keywords", "venue", "author"])
def test_all_effectiveness_fields_scan_html_residue(field: str):
    result = _complete_result()
    contaminated = "clean text <span class='highlight'>leaked markup</span>"
    if field == "keywords":
        result["keywords"] = [contaminated]
    elif field == "venue":
        result["publication_venue_name_unified"] = contaminated
    elif field == "author":
        result["author"] = [{"name": contaminated}]
    elif field == "abstract":
        result["abstract"] = "readable abstract text " * 100 + contaminated
    else:
        result[field] = contaminated

    grade = LLMSearchResultEffectiveness(enable_llm_quality=False).grade(result=result)

    assert "RuleSpecialCharacter" in grade.issues
    assert getattr(grade, f"{field}_score") <= 0.1


@pytest.mark.parametrize("field", ["title", "abstract", "keywords", "venue", "author"])
def test_all_effectiveness_fields_scan_replacement_character(field: str):
    result = _complete_result()
    contaminated = "metadata contains \ufffd broken text"
    if field == "keywords":
        result["keywords"] = [contaminated]
    elif field == "venue":
        result["publication_venue_name_unified"] = contaminated
    elif field == "author":
        result["author"] = [{"name": contaminated}]
    else:
        result[field] = contaminated

    grade = LLMSearchResultEffectiveness(enable_llm_quality=False).grade(result=result)

    assert "RuleMojibake" in grade.issues
    assert getattr(grade, f"{field}_score") <= 0.1
