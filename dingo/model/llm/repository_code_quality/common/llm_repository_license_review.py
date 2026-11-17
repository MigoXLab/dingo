"""Model adjudication of deterministic license-declaration candidates.

``Security.License_Header`` drives data cleaning: the reported line span is meant
to be stripped from the record. A signature match alone cannot tell licensing
boilerplate from license wording carried by data content, so each candidate is
adjudicated here before the hard label is emitted.
"""

import json

from pydantic import BaseModel, ConfigDict, Field

from dingo.io.output.eval_detail import EvalDetail
from dingo.model.llm.code_quality.base_code_quality import BaseCodeEvaluation, parse_response


class LicenseDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    license_declaration: bool
    reason: str = Field(min_length=1)


class LLMRepositoryLicenseReview(BaseCodeEvaluation):
    """Internal stage; the public entry point is the repository pipeline."""

    prompt = """
You are a precision-first license reviewer for repository source-code training data.
Each candidate quotes one region that a deterministic rule matched as a license
declaration block. Decide whether that region is licensing boilerplate attached to this
file, which downstream cleaning strips, or license wording that is part of the payload.

Confirm license_declaration=true when the region is licensing text for this file:
Apache-2.0 boilerplate, GPL/LGPL/AGPL clause notices, the MIT "Permission is hereby
granted..." text, BSD redistribution clauses or Go-style "governed by a BSD-style
license" headers, SPDX-License-Identifier lines, MPL/EPL/CDDL/WTFPL/ISC/zlib notices,
Rust dual-license statements, Creative Commons or public-domain dedications for this
file, and the body of a LICENSE or COPYING file.

Return false when the license wording is payload rather than a strippable file header:
- license metadata inside data records: JSON/XML/YAML fields, HTML head attributes,
  page titles, catalogue, CVRF/CVE legal notes, or corpus documents;
- prose in documentation or dataset text describing the license of some other work;
- a bare pointer, tag or URL with no granting clause (see the LICENSE file,
  "license: MIT", "@license", a License section heading);
- copyright-only notices, or confidential and restrictive clauses that grant nothing;
- tests, fixtures, string constants, or identifiers that merely mention a license;
- any unrelated literal use of the word "license".

Judge only the quoted region and the surrounding lines shown. Return only JSON:
{"license_declaration":true|false,"reason":"brief explanation naming the deciding evidence"}
"""

    _MAX_CANDIDATES = 3

    @classmethod
    def build_messages(cls, input_data):
        candidates = getattr(input_data, "repository_license_candidates", []) or []
        meta = getattr(input_data, "file_meta", None)
        payload = {
            "file_path": meta.get("file_path") if isinstance(meta, dict) else None,
            "file_name": meta.get("file_name") if isinstance(meta, dict) else None,
            "language": getattr(input_data, "language", None),
            "candidates": [
                {
                    "families": candidate.get("families"),
                    "line_start": candidate.get("line_start"),
                    "line_end": candidate.get("line_end"),
                    "whole_file_is_license_document": candidate.get("license_document"),
                    "excerpt": candidate.get("excerpt"),
                }
                for candidate in candidates[: cls._MAX_CANDIDATES]
            ],
            "total_candidates": len(candidates),
        }
        return [
            {"role": "system", "content": cls.prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    @classmethod
    def process_response(cls, response):
        parsed = parse_response(response, LicenseDecision)
        if parsed.license_declaration:
            return EvalDetail(
                metric=cls.__name__,
                status=True,
                score=0,
                label=["Security.License_Header"],
                reason=[parsed.reason],
            )
        return EvalDetail(
            metric=cls.__name__,
            status=True,
            score=0,
            label=["Security.License_Reference_Review"],
            reason=[f"License wording is not a strippable header block: {parsed.reason}"],
        )
