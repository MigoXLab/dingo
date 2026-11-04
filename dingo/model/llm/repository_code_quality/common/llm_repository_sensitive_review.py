"""Contextual adjudication of deterministic repository security candidates."""

import json

from pydantic import BaseModel, ConfigDict, Field

from dingo.io.output.eval_detail import EvalDetail
from dingo.model.llm.code_quality.base_code_quality import BaseCodeEvaluation, parse_response


class SensitiveDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    pii_exposure: bool
    internal_endpoint_exposure: bool
    secret_credentials: bool
    reason: str = Field(min_length=1)


class LLMRepositorySensitiveReview(BaseCodeEvaluation):
    """Internal stage; the public entry point is the repository pipeline."""

    prompt = """
You are an independent security reviewer for repository source-code training data.
Review only the supplied candidate metadata and redacted context hints. The original
source and matched values are deliberately unavailable.

Confirm pii_exposure when a context hint indicates a real person's contact or account
data: personal email, phone, ID, bank/card detail, individual IP/MAC, or a person's name.
Real-looking personal emails and personal names count even inside tests, demos, sample
data, ordinary code, and copyright or license headers; treat name@university,
name@webmail, or name@company values as personal. Hardcoded routable public IP addresses
in source or configuration also count. Exclude placeholders and example domains,
role-based or shared project contacts (info@, support@, admin@, sales@, noreply@),
organization, company, team, or project names inside attributions, dummy identities such
as a@a.a, documentation metadata, version strings, timestamps, standard payment test
fixtures (published test card numbers and their CVVs), and IP addresses that are clearly
illustrative examples inside README or documentation prose. Blockchain and smart-contract
addresses are public ledger identifiers: never confirm them.

Confirm internal_endpoint_exposure only when context exposes a non-public service layout,
port, route, private infrastructure address, or internal domain. localhost, documentation
ranges, generic demos, IP-shaped version strings, markdown or docs illustrative
hostnames, and code package or module names are excluded.

Confirm secret_credentials for plausible literal credential values, quoted or unquoted,
including hardcoded credentials inside tests or localhost-only connections, credential
values carried in URL query parameters, and connection-string password segments. Exclude
environment-variable references, identifiers and method calls, public keys, placeholders,
and markdown tutorial examples that merely show a format. Strongly validated passwords,
keys, tokens, and connection strings are handled before this review. Never claim a
credential is active and never reproduce sensitive values.

The candidate list may be a capped sample of a longer file. Judge only what is shown and
confirm a category when at least one shown candidate is genuinely sensitive.

Return only JSON:
{"pii_exposure":true|false,"internal_endpoint_exposure":true|false,
"secret_credentials":true|false,"reason":"brief redacted explanation"}
"""

    _CATEGORY_PRIORITY = {"secret": 0, "internal_endpoint": 1, "pii": 2}
    _MAX_CANDIDATES_PER_KIND = 6
    _MAX_CANDIDATES = 40

    @classmethod
    def _select_candidates(cls, candidates):
        """Bound the prompt: keep the most security-relevant sample of each candidate kind."""
        ordered = sorted(
            candidates,
            key=lambda item: (cls._CATEGORY_PRIORITY.get(item.get("category"), 3), item.get("kind", "")),
        )
        selected = []
        per_kind = {}
        for candidate in ordered:
            if len(selected) >= cls._MAX_CANDIDATES:
                break
            kind = candidate.get("kind", "")
            if per_kind.get(kind, 0) >= cls._MAX_CANDIDATES_PER_KIND:
                continue
            per_kind[kind] = per_kind.get(kind, 0) + 1
            selected.append(candidate)
        return selected

    @classmethod
    def build_messages(cls, input_data):
        candidates = [
            {key: value for key, value in candidate.items() if key != "matched_value"}
            for candidate in getattr(input_data, "repository_security_candidates", [])
        ]
        payload = {
            "candidates": cls._select_candidates(candidates),
            "total_candidates": len(candidates),
        }
        return [
            {"role": "system", "content": cls.prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

    @classmethod
    def process_response(cls, response):
        parsed = parse_response(response, SensitiveDecision)
        labels = []
        if parsed.pii_exposure:
            labels.append("Security.PII_Exposure")
        if parsed.internal_endpoint_exposure:
            labels.append("Security.Internal_Endpoint_Exposure")
        if parsed.secret_credentials:
            labels.append("Security.Secret_Credentials")
        return EvalDetail(
            metric=cls.__name__,
            status=bool(labels),
            score=0 if labels else 1,
            label=labels or ["QUALITY_GOOD"],
            reason=[parsed.reason],
        )
