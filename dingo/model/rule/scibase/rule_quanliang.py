"""Quanliang metadata validation with independently configurable field checks."""

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.model.model import Model
from dingo.model.rule.scibase.base_check_paper import (check_abstract, check_access_is_oa, check_access_license, check_access_oa_status, check_access_oa_url, check_access_xinghe_repository_model_name,
                                                       check_access_xinghe_repository_model_version, check_access_xinghe_repository_origin_path, check_access_xinghe_repository_sha256, check_author,
                                                       check_best_oa_location, check_citations, check_cited_by_api_url, check_contributors, check_doi, check_grade, check_grade_class, check_isbn13,
                                                       check_isbns, check_language, check_locations, check_metadata_type, check_primary_location, check_publication_pages,
                                                       check_publication_published_date, check_publication_published_year, check_publication_venue_biblio_issue, check_publication_venue_biblio_pages,
                                                       check_publication_venue_biblio_volume, check_publication_venue_issn, check_publication_venue_name_unified, check_references, check_related_works,
                                                       check_supplementary_material, check_title)
from dingo.model.rule.scibase.base_field_validation import BaseFieldValidation


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["xinghe", "quanliang"])
class RuleQuanliangFieldValidation(BaseFieldValidation):
    _metric_info = {
        "category": "Rule-Based Metadata Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RuleQuanliangFieldValidation",
        "description": "Validate Quanliang metadata fields and report invalid fields",
        "paper_title": "",
        "paper_url": "",
        "paper_authors": "",
        "evaluation_results": "",
    }

    field_validators = {
        "metadata_type": lambda record: check_metadata_type(record.get("metadata_type")),
        "doi": lambda record: check_doi(record.get("doi"), record.get("metadata_type")),
        "isbns": lambda record: check_isbns(record.get("isbns"), record.get("metadata_type")),
        "isbn13": lambda record: check_isbn13(record.get("isbn13"), record.get("metadata_type")),
        "title": lambda record: check_title(record.get("title")),
        "abstract": lambda record: check_abstract(record.get("abstract"), record.get("title")),
        "language": lambda record: check_language(record.get("language")),
        "author": lambda record: check_author(record.get("author")),
        "contributors": lambda record: check_contributors(record.get("contributors")),
        "locations": lambda record: check_locations(record.get("locations")),
        "access_is_oa": lambda record: check_access_is_oa(
            record.get("access_is_oa"),
            record.get("metadata_type"),
            record.get("access_oa_status"),
            record.get("access_oa_url"),
            record.get("access_license"),
        ),
        "access_oa_status": lambda record: check_access_oa_status(record.get("access_oa_status")),
        "access_oa_url": lambda record: check_access_oa_url(record.get("access_oa_url")),
        "access_license": lambda record: check_access_license(record.get("access_license")),
        "publication_published_date": lambda record: check_publication_published_date(
            record.get("publication_published_date")
        ),
        "publication_published_year": lambda record: check_publication_published_year(
            record.get("publication_published_year")
        ),
        "publication_venue_issn": lambda record: check_publication_venue_issn(record.get("publication_venue_issn")),
        "publication_venue_biblio_volume": lambda record: check_publication_venue_biblio_volume(
            record.get("publication_venue_biblio_volume")
        ),
        "publication_venue_biblio_issue": lambda record: check_publication_venue_biblio_issue(
            record.get("publication_venue_biblio_issue")
        ),
        "publication_venue_biblio_pages": lambda record: check_publication_venue_biblio_pages(
            record.get("publication_venue_biblio_pages")
        ),
        "publication_pages": lambda record: check_publication_pages(record.get("publication_pages")),
        "publication_venue_name_unified": lambda record: check_publication_venue_name_unified(
            record.get("publication_venue_name_unified"),
            record.get("publication_venue_name"),
        ),
        "grade_class": lambda record: check_grade_class(record.get("grade_class")),
        "grade": lambda record: check_grade(record.get("grade"), record.get("grade_class")),
        "references": lambda record: check_references(record.get("references")),
        "related_works": lambda record: check_related_works(record.get("related_works")),
        "citations": lambda record: check_citations(record.get("citations")),
        "supplementary_material": lambda record: check_supplementary_material(
            record.get("supplementary_material")
        ),
        "cited_by_api_url": lambda record: check_cited_by_api_url(record.get("cited_by_api_url")),
        "access_xinghe_repository_sha256": lambda record: check_access_xinghe_repository_sha256(
            record.get("access_xinghe_repository_sha256"),
            record.get("access_xinghe_repository_has_fulltext"),
        ),
        "access_xinghe_repository_origin_path": lambda record: check_access_xinghe_repository_origin_path(
            record.get("access_xinghe_repository_origin_path"),
            record.get("access_xinghe_repository_has_fulltext"),
        ),
        "access_xinghe_repository_model_name": lambda record: check_access_xinghe_repository_model_name(
            record.get("access_xinghe_repository_model_name"),
            record.get("access_xinghe_repository_process_status"),
        ),
        "access_xinghe_repository_model_version": lambda record: check_access_xinghe_repository_model_version(
            record.get("access_xinghe_repository_model_version"),
            record.get("access_xinghe_repository_model_name"),
            record.get("access_xinghe_repository_process_status"),
        ),
    }

    _required_fields = []
    dynamic_config = EvaluatorRuleArgs(key_list=list(field_validators))
