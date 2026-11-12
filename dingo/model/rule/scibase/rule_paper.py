"""Paper metadata validation with independently configurable field checks."""

from typing import Any

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.model.model import Model
from dingo.model.rule.scibase.base_field_validation import BaseFieldValidation, ValidationResult
from dingo.model.rule.scibase.base_check_paper import (
    check_abstract,
    check_access_oa_url,
    check_access_xinghe_repository_model_name,
    check_access_xinghe_repository_model_version,
    check_access_xinghe_repository_origin_path,
    check_access_xinghe_repository_sha256,
    check_author,
    check_best_oa_location,
    check_citations,
    check_cited_by_api_url,
    check_contributors,
    check_doi,
    check_grade,
    check_grade_class,
    check_isbn13,
    check_isbns,
    check_language,
    check_locations,
    check_metadata_type,
    check_primary_location,
    check_publication_pages,
    check_publication_published_date,
    check_publication_published_year,
    check_publication_venue_biblio_issue,
    check_publication_venue_biblio_pages,
    check_publication_venue_biblio_volume,
    check_publication_venue_issn,
    check_publication_venue_name_unified,
    check_references,
    check_related_works,
    check_supplementary_material,
    check_title,
)


def check_access_is_oa(access_is_oa: Any) -> ValidationResult:
    """Validate the paper OA flag; missing fields are handled by eval()."""
    if access_is_oa is None:
        return BaseFieldValidation._fail("null", "value is null")
    if not isinstance(access_is_oa, str):
        return BaseFieldValidation._fail("wrong_type", "value must be a string")
    if access_is_oa == "":
        return BaseFieldValidation._fail("empty", "value cannot be empty string")
    if access_is_oa not in {"true", "false", "unknown"}:
        return BaseFieldValidation._fail(
            "unsupported_value", f"unsupported value '{access_is_oa}'"
        )
    return BaseFieldValidation._ok()


def check_access_oa_status(
    access_oa_status: Any, access_is_oa: Any = None
) -> ValidationResult:
    """Validate the paper OA status and its relationship to the OA flag."""
    if access_oa_status is None:
        return BaseFieldValidation._fail("null", "value is null")
    if not isinstance(access_oa_status, str):
        return BaseFieldValidation._fail("wrong_type", "value must be a string")
    # Empty status is allowed, but still subject to the OA flag constraint.
    if access_oa_status not in {"diamond", "gold", "green", "hybrid", "bronze", "closed", ""}:
        return BaseFieldValidation._fail(
            "unsupported_value", f"unsupported value '{access_oa_status}'"
        )
    if access_is_oa == "false" and access_oa_status != "closed":
        return BaseFieldValidation._fail(
            "oa_status_mismatch",
            "value must be 'closed' when access_is_oa='false'",
        )
    if access_is_oa == "true" and access_oa_status == "closed":
        return BaseFieldValidation._fail(
            "oa_status_mismatch",
            "value must not be 'closed' when access_is_oa='true'",
        )
    return BaseFieldValidation._ok()


@Model.rule_register("QUALITY_BAD_EFFECTIVENESS", ["xinghe", "quanliang"])
class RulePaperFieldValidation(BaseFieldValidation):
    _metric_info = {
        "category": "Rule-Based Metadata Quality Metrics",
        "quality_dimension": "EFFECTIVENESS",
        "metric_name": "RulePaperFieldValidation",
        "description": "Validate paper metadata fields using shared paper checks",
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
        ),
        "access_oa_status": lambda record: check_access_oa_status(
            record.get("access_oa_status"), record.get("access_is_oa"),
        ),
        "access_oa_url": lambda record: check_access_oa_url(record.get("access_oa_url")),
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
        "primary_location": lambda record: check_primary_location(record.get("primary_location")),
        "best_oa_location": lambda record: check_best_oa_location(record.get("best_oa_location")),
    }

    _required_fields = []
    dynamic_config = EvaluatorRuleArgs(key_list=list(field_validators))
