"""Rule-based search result authority grader."""

from __future__ import annotations
import html
import math
import re
import statistics
from dataclasses import dataclass
from typing import Any

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model

PRESTIGIOUS_VENUE_PATTERNS = (
    r"^nature(?:$|\s)",
    r"^npj(?:$|\s)",
    r"^communications (?:biology|chemistry|earth & environment|materials|physics)$",
    r"^scientific (?:reports|data)$",
    r"^science$",
    r"^science (?:advances|immunology|robotics|signaling|translational medicine)$",
    r"^cell$",
    r"^cell (?:reports|metabolism|systems|stem cell|chemical biology|host & microbe|genomics)$",
    r"^(?:cancer|molecular|developmental) cell$",
    r"^(?:the )?lancet(?:$|\s)",
    r"^(?:the )?new england journal of medicine$",
    r"^nejm(?:$|\s)",
    r"^jama(?:$|\s)",
    r"^(?:the )?bmj$",
    r"^(?:proceedings of the national academy of sciences(?: of the united states of america)?|pnas)$",
    r"^journal of the american chemical society$",
    r"^physical review letters$",
    r"^angewandte chemie(?: international edition)?$",
    r"^(?:neurips|icml|iclr|cvpr|acl|emnlp|aaai|ijcai|sigir)$",
    r"^advances in neural information processing systems$",
)

RECOGNIZED_VENUE_PATTERNS = (
    r"\bieee\b",
    r"\bacm\b",
    r"^plos(?:$|\s)",
    r"^frontiers in ",
    r"^bmj(?:$|\s)",
)

RECOGNIZED_PUBLISHER_HINTS = (
    "nature portfolio",
    "springer nature",
    "springer",
    "elsevier",
    "wiley",
    "taylor & francis",
    "routledge",
    "sage publishing",
    "oxford university press",
    "cambridge university press",
    "institute of electrical and electronics engineers",
    "association for computing machinery",
    "american chemical society",
    "royal society of chemistry",
    "institute of physics",
    "iop publishing",
    "american physical society",
    "american institute of physics",
    "frontiers media",
    "public library of science",
    "bmj publishing",
    "wolters kluwer",
    "lippincott williams & wilkins",
    "american geophysical union",
    "royal society",
    "american association for the advancement of science",
    "de gruyter",
    "crc press",
    "chapman & hall",
    "world scientific",
    "academic press",
    "humana press",
    "emerald publishing",
)

REPOSITORY_VENUE_HINTS = (
    "arxiv",
    "biorxiv",
    "medrxiv",
    "chemrxiv",
    "ssrn",
    "zenodo",
    "figshare",
    "mendeley data",
    "open science framework",
    "osf preprints",
    "research square",
    "repository",
)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _normalize_text(text: Any) -> str:
    value = html.unescape(str(text or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    return " ".join(value.lower().split())


def _venue_aliases(venue: str) -> list[str]:
    aliases = [part.strip(" .,:;-") for part in venue.split("|") if part.strip(" .,:;-")]
    return aliases or [venue]


def _matches_venue_patterns(venue: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, alias) for alias in _venue_aliases(venue) for pattern in patterns)


def _extract_publishers(result: dict[str, Any]) -> str:
    value = result.get("publication_publisher") or result.get("publisher") or ""
    if isinstance(value, list):
        return _normalize_text(" | ".join(str(item) for item in value if item))
    return _normalize_text(value)


def _has_venue_issn(result: dict[str, Any]) -> bool:
    value = result.get("publication_venue_issn") or result.get("issn") or []
    values = value if isinstance(value, list) else [value]
    return any(re.fullmatch(r"\d{4}-?\d{3}[\dXx]", str(item or "").strip()) for item in values)


def extract_venue(result: dict[str, Any]) -> str:
    return str(
        result.get("publication_venue_name_unified")
        or result.get("publication_venue_name")
        or result.get("venue")
        or result.get("source")
        or ""
    )


def extract_citations(result: dict[str, Any], key: str = "citation_count") -> float:
    try:
        return float(result.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _has_doi_in_locations(locations: Any) -> bool:
    """Return whether a valid locations list contains a DOI URL or value."""
    if not isinstance(locations, list):
        return False

    for location in locations:
        if isinstance(location, dict):
            values = (
                location.get("doi"),
                location.get("url"),
                location.get("landing_page_url"),
            )
        elif isinstance(location, str):
            values = (location,)
        else:
            continue

        if any("doi.org/" in str(value or "").lower() for value in values):
            return True
    return False


@dataclass
class AuthorityGrade:
    """Structured authority score for one search result."""

    score: float = 0.0
    citation_score: float = 0.0
    influential_citation_score: float = 0.0
    venue_score: float = 0.0
    doi_score: float = 0.0
    reason: str = ""
    citation_basis: str = "citation_count"
    metadata_status: str = ""
    metadata_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 5),
            "citation_score": round(self.citation_score, 5),
            "influential_citation_score": round(self.influential_citation_score, 5),
            "venue_score": round(self.venue_score, 5),
            "doi_score": round(self.doi_score, 5),
            "reason": self.reason,
            "citation_basis": self.citation_basis,
            "metadata_status": self.metadata_status,
            "metadata_error": self.metadata_error,
        }


@dataclass
class AuthoritySummary:
    mean_score: float = 0.0
    median_score: float = 0.0
    mean_citation_score: float = 0.0
    mean_influential_citation_score: float = 0.0
    mean_venue_score: float = 0.0
    mean_doi_score: float = 0.0
    graded_pairs: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "authority_mean_score": round(self.mean_score, 5),
            "authority_median_score": round(self.median_score, 5),
            "authority_mean_citation_score": round(self.mean_citation_score, 5),
            "authority_mean_influential_citation_score": round(self.mean_influential_citation_score, 5),
            "authority_mean_venue_score": round(self.mean_venue_score, 5),
            "authority_mean_doi_score": round(self.mean_doi_score, 5),
            "authority_graded_pairs": self.graded_pairs,
        }


@Model.llm_register("LLMSearchResultAuthority")
class LLMSearchResultAuthority:
    """Authority scorer based on citation impact, venue, and DOI metadata."""

    dynamic_config = EvaluatorLLMArgs()
    default_threshold = 0.15

    def grade(self, *, result: dict[str, Any]) -> AuthorityGrade:
        venue = _normalize_text(extract_venue(result))
        venue_type = _normalize_text(result.get("publication_venue_type") or "")
        publishers = _extract_publishers(result)
        citations = max(0.0, extract_citations(result, "citation_count"))
        influential = max(0.0, extract_citations(result, "influential_citation_count"))

        normalized_percentile = result.get("citation_normalized_percentile") or {}
        try:
            percentile_value = float(
                normalized_percentile.get("value")
                if isinstance(normalized_percentile, dict)
                else normalized_percentile
            )
        except (TypeError, ValueError):
            percentile_value = -1.0
        fwci = max(0.0, extract_citations(result, "fwci"))
        if 0.0 <= percentile_value <= 1.0:
            citation_score = percentile_value
            citation_basis = "citation_normalized_percentile"
        elif fwci > 0.0:
            citation_score = _clamp(math.log1p(fwci) / math.log1p(10.0))
            citation_basis = "fwci"
        else:
            citation_score = _clamp(math.log1p(citations) / math.log1p(500.0))
            citation_basis = "citation_count"
        influential_score = _clamp(math.log1p(influential) / math.log1p(50.0))

        venue_score = 0.25
        reason = "unknown_or_low_signal_venue"
        is_repository = "repository" in venue_type or "preprint" in venue_type or any(
            hint in venue for hint in REPOSITORY_VENUE_HINTS
        )
        is_academic_book = "book series" in venue_type or "ebook platform" in venue_type or "ebooks" in venue
        if is_repository:
            venue_score = 0.45
            reason = "repository_or_preprint"
        elif is_academic_book:
            venue_score = 0.55
            reason = "academic_book_series"
        elif _matches_venue_patterns(venue, PRESTIGIOUS_VENUE_PATTERNS):
            venue_score = 0.85
            reason = "prestigious_venue_family"
        elif _matches_venue_patterns(venue, RECOGNIZED_VENUE_PATTERNS) or any(
            hint in publishers for hint in RECOGNIZED_PUBLISHER_HINTS
        ):
            venue_score = 0.75
            reason = "recognized_scholarly_publisher_or_venue"
        elif "journal" in venue_type or "conference" in venue_type or _has_venue_issn(result):
            venue_score = 0.65
            reason = "structured_journal_or_conference"
        elif venue:
            venue_score = 0.40
            reason = "named_venue"

        doi_score = 1.0 if result.get("doi") or _has_doi_in_locations(result.get("locations")) else 0.0
        score = (
            0.45 * citation_score
            + 0.20 * influential_score
            + 0.25 * venue_score
            + 0.10 * doi_score
        )
        return AuthorityGrade(
            score=_clamp(score),
            citation_score=citation_score,
            influential_citation_score=influential_score,
            venue_score=venue_score,
            doi_score=doi_score,
            reason=reason,
            citation_basis=citation_basis,
            metadata_status=str(result.get("_authority_metadata_status") or ""),
            metadata_error=str(result.get("_authority_metadata_error") or ""),
        )

    @classmethod
    def _config_value(cls, name: str, default: Any = None) -> Any:
        return getattr(cls.dynamic_config, name, default)

    @classmethod
    def eval(cls, input_data: Data) -> EvalDetail:
        """Executor entry point: evaluate one flattened search result row."""
        result = getattr(input_data, "search_result", None)
        if not isinstance(result, dict):
            result = input_data.to_dict()

        grade = cls().grade(result=result)
        threshold = float(cls._config_value("threshold", cls.default_threshold) or cls.default_threshold)

        labels: list[str] = []
        if grade.metadata_status == "not_found":
            labels.append("Authority.Error_Metadata_Not_Found")
        elif grade.metadata_status == "missing_doc_id":
            labels.append("Authority.Error_Metadata_DocID_Miss")
        elif grade.metadata_status == "error":
            if "HTTP 403" in grade.metadata_error:
                labels.append("Authority.Error_Metadata_Field_Denied")
            else:
                labels.append("Authority.Error_Metadata_Check_Failed")
        if grade.score < threshold:
            labels.append("Authority.Error_Authority_Low")
            if grade.citation_score <= 0.0:
                labels.append("Authority.Error_Citation_Miss")
            if grade.venue_score <= 0.25:
                labels.append("Authority.Error_Venue_Low_Signal")
            if grade.doi_score <= 0.0:
                labels.append("Authority.Error_DOI_Miss")

        status = bool(labels)
        if not labels:
            labels = ["QUALITY_GOOD"]

        return EvalDetail(
            metric=cls.__name__,
            status=status,
            score=round(grade.score, 5),
            label=labels,
            reason=[grade.to_dict()],
        )


def aggregate_grades(grades: list[AuthorityGrade]) -> AuthoritySummary:
    if not grades:
        return AuthoritySummary()
    return AuthoritySummary(
        mean_score=statistics.mean(g.score for g in grades),
        median_score=statistics.median(g.score for g in grades),
        mean_citation_score=statistics.mean(g.citation_score for g in grades),
        mean_influential_citation_score=statistics.mean(g.influential_citation_score for g in grades),
        mean_venue_score=statistics.mean(g.venue_score for g in grades),
        mean_doi_score=statistics.mean(g.doi_score for g in grades),
        graded_pairs=len(grades),
    )
