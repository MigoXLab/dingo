"""Paper metadata validation with independently configurable field checks."""

from typing import Any

from dingo.config.input_args import EvaluatorRuleArgs
from dingo.model.model import Model
from dingo.model.rule.scibase.base_check_paper import (check_abstract, check_access_oa_url, check_access_xinghe_repository_model_name, check_access_xinghe_repository_model_version,
                                                       check_access_xinghe_repository_origin_path, check_access_xinghe_repository_sha256, check_author, check_best_oa_location, check_citations,
                                                       check_cited_by_api_url, check_contributors, check_doi, check_grade, check_grade_class, check_isbn13, check_isbns, check_language,
                                                       check_metadata_type, check_primary_location, check_publication_pages, check_publication_published_date, check_publication_published_year,
                                                       check_publication_venue_biblio_issue, check_publication_venue_biblio_pages, check_publication_venue_biblio_volume, check_publication_venue_issn,
                                                       check_publication_venue_name_unified, check_references, check_related_works, check_supplementary_material, check_title)
from dingo.model.rule.scibase.base_field_validation import BaseFieldValidation, ValidationResult

PAPER_LOCATION_REQUIRED_KEYS = (
    "license", "is_oa", "pdf_url", "landing_page_url", "source_url",
    "origin_url", "source", "version", "is_published", "is_accepted", "meta_db_name",
)


def check_locations(locations: Any) -> ValidationResult:
    """Validate paper location objects; missing fields are handled by eval()."""
    def _check_license(license_value: Any) -> ValidationResult:
        if not isinstance(license_value, str):
            return BaseFieldValidation._fail("license.wrong_type", "license must be a string")
        allowed = {
            "cc-by", "cc-by-nc", "cc-by-sa", "cc-by-nd", "cc-by-nc-sa", "cc-by-nc-nd",
            "other-oa", "cc0", "", "public-domain", "publisher-specific-oa",
            "publisher-specific", "wiley-specific", "elsevier-specific", "oup-specific",
            "acs-specific", "rsc-specific", "iop-specific", "unspecified-oa", "implied-oa",
            "nonexclusive-distrib", "gpl-v1", "gpl-v2", "gpl-v3", "mit", "apache-2-0",
            "isc", "ogl-c", "pd",
        }
        if license_value not in allowed:
            return BaseFieldValidation._fail(
                "license.unsupported_value", "license must be a supported license string",
            )
        return BaseFieldValidation._ok()

    def _check_is_oa(is_oa: Any) -> ValidationResult:
        """Validate the string enum used by locations[].is_oa."""
        if not isinstance(is_oa, str):
            return BaseFieldValidation._fail("is_oa.wrong_type", "is_oa must be a string")
        if is_oa not in {"true", "false", "unknown"}:
            return BaseFieldValidation._fail(
                "is_oa.unsupported_value", "is_oa must be one of 'true', 'false' or 'unknown'",
            )
        return BaseFieldValidation._ok()

    def _check_source(source: Any) -> ValidationResult:
        if not isinstance(source, dict):
            return BaseFieldValidation._fail("source.wrong_type", "source must be an object")
        if not source:
            return BaseFieldValidation._fail("source.empty", "source cannot be an empty object")
        required_keys = (
            "id", "display_name", "issn_l", "issn", "is_oa", "is_in_doaj", "is_core",
            "listed_in", "type", "host_organization", "host_organization_name",
            "host_organization_lineage", "host_organization_lineage_names",
        )
        missing = [key for key in required_keys if key not in source]
        return (
            bool(missing), ["source.missing_key"] * len(missing),
            [f"source missing key '{key}'" for key in missing],
        )

    def _check_version(version: Any) -> ValidationResult:
        if not isinstance(version, str):
            return BaseFieldValidation._fail("version.wrong_type", "version must be a string")
        if version not in {
            "publishedVersion", "acceptedVersion", "submittedVersion",
        }:
            return BaseFieldValidation._fail(
                "version.unsupported_value",
                "version must be one of 'publishedVersion', 'acceptedVersion' or 'submittedVersion'",
            )
        return BaseFieldValidation._ok()

    def _check_is_published(is_published: Any, version: Any) -> ValidationResult:
        if not isinstance(is_published, bool):
            return BaseFieldValidation._fail(
                "is_published.wrong_type", "is_published must be a boolean",
            )
        if version == "publishedVersion":
            if not is_published:
                return BaseFieldValidation._fail(
                    "is_published.version_mismatch",
                    "is_published must be true when version='publishedVersion'",
                )
        else:
            if is_published:
                return BaseFieldValidation._fail(
                    "is_published.version_mismatch",
                    "is_published must be false when version != 'publishedVersion'",
                )
        return BaseFieldValidation._ok()

    def _check_is_accepted(is_accepted: Any, version: Any) -> ValidationResult:
        if not isinstance(is_accepted, bool):
            return BaseFieldValidation._fail(
                "is_accepted.wrong_type", "is_accepted must be a boolean",
            )
        if version in ("publishedVersion", "acceptedVersion"):
            if not is_accepted:
                return BaseFieldValidation._fail(
                    "is_accepted.version_mismatch",
                    "is_accepted must be true when version is 'publishedVersion' or 'acceptedVersion'",
                )
        else:
            if is_accepted:
                return BaseFieldValidation._fail(
                    "is_accepted.version_mismatch",
                    "is_accepted must be false when version is neither 'publishedVersion' nor 'acceptedVersion'",
                )
        return BaseFieldValidation._ok()

    if locations is None:
        return BaseFieldValidation._fail("null", "value is null")
    if not isinstance(locations, list):
        return BaseFieldValidation._fail("wrong_type", "value must be a list of objects")
    error_labels: list[str] = []
    reasons: list[str] = []
    for idx, item in enumerate(locations):
        if not isinstance(item, dict):
            error_labels.append("wrong_type")
            reasons.append(f"item[{idx}] must be an object")
            continue
        if not item:
            error_labels.append("empty")
            reasons.append(f"item[{idx}] cannot be an empty object")
            continue
        for key in PAPER_LOCATION_REQUIRED_KEYS:
            if key not in item:
                error_labels.append("missing_key")
                reasons.append(f"item[{idx}] missing key '{key}'")
                continue
            if key == "license":
                invalid, labels, detail_reasons = _check_license(item[key])
            elif key == "is_oa":
                invalid, labels, detail_reasons = _check_is_oa(item[key])
            elif key == "source":
                invalid, labels, detail_reasons = _check_source(item[key])
            elif key == "version":
                invalid, labels, detail_reasons = _check_version(item[key])
            elif key == "is_published":
                invalid, labels, detail_reasons = _check_is_published(item[key], item.get("version"))
            elif key == "is_accepted":
                invalid, labels, detail_reasons = _check_is_accepted(item[key], item.get("version"))
            else:
                continue
            if invalid:
                error_labels.extend(labels)
                reasons.extend(f"item[{idx}].{reason}" for reason in detail_reasons)
    return bool(error_labels), error_labels, reasons


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
