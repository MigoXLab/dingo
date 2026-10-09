"""Sciverse source and metadata enrichment for subjective search evaluation."""

from __future__ import annotations
import html
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

AUTHORITY_FIELDS = (
    "doc_id",
    "unique_id",
    "title",
    "abstract",
    "doi",
    "citation_count",
    "influential_citation_count",
    "citation_normalized_percentile",
    "cited_by_percentile_year",
    "fwci",
    "publication_venue_name_unified",
    "publication_venue_type",
    "publication_venue_issn",
    "publication_publisher",
    "publication_published_year",
    "locations",
)


def normalize_source_text(value: Any) -> str:
    """Normalize display-only differences before comparing chunk prefixes."""
    text = html.unescape(html.unescape(str(value or "")))
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " image ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_source_compare_text(value: Any) -> str:
    """Normalize line endings only; preserve evidence at the original offset."""
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n")


def chunk_consistency_score(chunk: Any, source_text: Any, prefix_length: int = 50) -> float:
    """Binary prefix comparison, without searching or correcting the offset."""
    chunk_prefix = normalize_source_compare_text(chunk)[: max(1, int(prefix_length))]
    source_window = normalize_source_compare_text(source_text)
    if not chunk_prefix or not source_window:
        return 0.0
    return float(chunk_prefix == source_window[:len(chunk_prefix)])


@dataclass
class SourceVerification:
    source_quality: float | None
    source_exists: bool | None
    chunk_consistency: float | None
    issue: str = ""
    error: str = ""
    chars_returned: int = 0
    offset_adjusted: bool = False
    text: str = ""
    http_status: int | None = None

    def to_result_fields(self) -> dict[str, Any]:
        return {
            "_source_quality": self.source_quality,
            "_source_exists": self.source_exists,
            "_chunk_consistency": self.chunk_consistency,
            "_source_issue": self.issue,
            "_source_check_error": self.error,
            "_source_chars_returned": self.chars_returned,
            "_source_offset_adjusted": self.offset_adjusted,
            "_source_text": self.text,
            "_source_http_status": self.http_status,
        }


class SciverseQualityEnricher:
    """Read source windows and batch-load paper authority metadata."""

    def __init__(
        self,
        *,
        api_url: str,
        api_token: str,
        timeout: float = 60.0,
        max_retries: int = 3,
        request_interval: float = 0.0,
        content_limit: int = 200,
        prefix_length: int = 50,
        offset_tolerance: int = 0,
    ) -> None:
        base_url = str(api_url or "https://api.sciverse.space").rstrip("/")
        for endpoint in ("/agentic-search", "/meta-search", "/content"):
            if base_url.endswith(endpoint):
                base_url = base_url[: -len(endpoint)]
                break
        self.base_url = base_url
        self.api_token = api_token
        self.timeout = timeout
        self.request_interval = max(0.0, float(request_interval))
        self.content_limit = max(100, int(content_limit))
        self.prefix_length = max(1, int(prefix_length))
        self.offset_tolerance = max(0, int(offset_tolerance))
        if self.offset_tolerance:
            raise ValueError("Source verification requires the original offset; offset_tolerance must be 0")
        self.content_limit = max(self.content_limit, self.prefix_length)
        self._last_request_time = 0.0
        self._rate_lock = threading.Lock()
        self._source_cache: dict[tuple[str, int, str], SourceVerification] = {}
        self._metadata_cache: dict[str, dict[str, Any] | None] = {}
        self._session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
        }

    def _wait(self) -> None:
        if self.request_interval <= 0:
            return
        with self._rate_lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.request_interval:
                time.sleep(self.request_interval - elapsed)
            self._last_request_time = time.monotonic()

    def verify_source(self, result: dict[str, Any]) -> SourceVerification:
        doc_id = str(result.get("doc_id") or "").strip()
        chunk = str(result.get("chunk") or "")
        raw_offset = result.get("offset")
        if not doc_id:
            return SourceVerification(0.0, False, 0.0, "missing_doc_id")
        if raw_offset in (None, ""):
            return SourceVerification(0.0, None, 0.0, "missing_offset")
        try:
            offset = int(raw_offset)
            if offset < 0:
                raise ValueError
        except (TypeError, ValueError):
            return SourceVerification(0.0, None, 0.0, "missing_offset")

        cache_key = (doc_id, offset, normalize_source_compare_text(chunk)[: self.prefix_length])
        if cache_key in self._source_cache:
            return self._source_cache[cache_key]

        try:
            response = self._get_content(doc_id, offset, self.content_limit)
        except requests.RequestException as exc:
            verification = SourceVerification(None, None, None, "source_check_failed", str(exc))
            self._source_cache[cache_key] = verification
            return verification

        if response.status_code == 401:
            raise PermissionError("Sciverse /content authentication failed (HTTP 401)")
        if response.status_code == 404:
            verification = SourceVerification(0.0, False, 0.0, "source_not_found")
        elif response.status_code != 200:
            verification = SourceVerification(
                None,
                None,
                None,
                "source_check_failed",
                f"HTTP {response.status_code}: {response.text[:200]}",
            )
        else:
            try:
                data = response.json()
            except ValueError as exc:
                verification = SourceVerification(None, None, None, "source_check_failed", str(exc))
            else:
                if not isinstance(data, dict) or not isinstance(data.get("text"), str):
                    return SourceVerification(
                        None, None, None, "source_check_failed", "Invalid /content response: expected text string",
                        http_status=response.status_code,
                    )
                text = data["text"]
                chars_returned = len(text)
                consistency = chunk_consistency_score(chunk, text, self.prefix_length)
                if text:
                    verification = SourceVerification(
                        0.30 + 0.70 * consistency,
                        True,
                        consistency,
                        "" if consistency == 1.0 else "chunk_source_inconsistent",
                        chars_returned=chars_returned,
                        text=text,
                    )
                else:
                    verification = SourceVerification(0.0, True, 0.0, "source_empty")
        verification.http_status = response.status_code
        self._source_cache[cache_key] = verification
        return verification

    def _get_content(self, doc_id: str, offset: int, limit: int) -> requests.Response:
        self._wait()
        return self._session.get(
            f"{self.base_url}/content",
            headers=self.headers,
            params={"doc_id": doc_id, "offset": offset, "limit": limit},
            timeout=self.timeout,
        )

    def enrich_authority_metadata(
        self,
        results: Iterable[dict[str, Any]],
        *,
        batch_size: int = 100,
    ) -> dict[str, int]:
        rows = list(results)
        doc_ids = list(
            dict.fromkeys(
                str(row.get("doc_id") or "").strip()
                for row in rows
                if str(row.get("doc_id") or "").strip()
            )
        )
        missing_ids = [doc_id for doc_id in doc_ids if doc_id not in self._metadata_cache]
        errors = 0
        batch_size = max(1, min(200, int(batch_size)))
        for start in range(0, len(missing_ids), batch_size):
            batch = missing_ids[start:start + batch_size]
            self._wait()
            payload = {
                "filters": [
                    {
                        "field": "doc_id",
                        "operator": "FILTER_OP_IN",
                        "value": batch,
                    }
                ],
                "fields": list(AUTHORITY_FIELDS),
                "page": 1,
                "page_size": len(batch),
            }
            try:
                response = self._session.post(
                    f"{self.base_url}/meta-search",
                    headers=self.headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except requests.RequestException as exc:
                errors += len(batch)
                for doc_id in batch:
                    self._metadata_cache[doc_id] = {
                        "_authority_metadata_error": str(exc),
                    }
                continue
            if response.status_code == 401:
                raise PermissionError("Sciverse /meta-search authentication failed (HTTP 401)")
            if response.status_code != 200:
                errors += len(batch)
                error = f"HTTP {response.status_code}: {response.text[:200]}"
                for doc_id in batch:
                    self._metadata_cache[doc_id] = {"_authority_metadata_error": error}
                continue
            try:
                payload_results = response.json().get("results") or []
            except (AttributeError, ValueError) as exc:
                errors += len(batch)
                for doc_id in batch:
                    self._metadata_cache[doc_id] = {
                        "_authority_metadata_error": str(exc),
                    }
                continue
            by_doc_id = {
                str(item.get("doc_id") or "").strip(): item
                for item in payload_results
                if isinstance(item, dict) and str(item.get("doc_id") or "").strip() in batch
            }
            for doc_id in batch:
                self._metadata_cache[doc_id] = by_doc_id.get(doc_id)

        found = 0
        not_found = 0
        for row in rows:
            doc_id = str(row.get("doc_id") or "").strip()
            if not doc_id:
                row["_authority_metadata_status"] = "missing_doc_id"
                continue
            metadata = self._metadata_cache.get(doc_id)
            if metadata is None:
                row["_authority_metadata_status"] = "not_found"
                not_found += 1
            elif metadata.get("_authority_metadata_error"):
                row["_authority_metadata_status"] = "error"
                row["_authority_metadata_error"] = metadata["_authority_metadata_error"]
            else:
                for key, value in metadata.items():
                    if key in ("title", "abstract"):
                        if isinstance(value, str) and value.strip() and not str(row.get(key) or "").strip():
                            row.setdefault("_metadata_original_fields", {})[key] = row.get(key)
                            row[key] = value
                            row.setdefault("_metadata_recovered_fields", {})[key] = "meta-search"
                        continue
                    if value not in (None, "", [], {}):
                        row[key] = value
                row["_authority_metadata_status"] = "found"
                found += 1
        return {
            "unique_doc_ids": len(doc_ids),
            "found_results": found,
            "not_found_results": not_found,
            "error_doc_ids": errors,
        }
