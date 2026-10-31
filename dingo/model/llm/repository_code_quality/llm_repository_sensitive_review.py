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

Confirm pii_exposure only when a context hint indicates private contact/account data,
an individual IP/MAC, a private person's name, or a personal blockchain address. Public
author contacts, documentation metadata, dummy identities, versions, timestamps,
institutional routing details, and ordinary account names are excluded.

Confirm internal_endpoint_exposure only when context exposes a non-public service layout,
port, route, private infrastructure address, or internal domain. localhost, documentation
ranges, generic demos, and IP-shaped version strings are excluded.

Confirm secret_credentials only for a plausible sensitive cookie or other contextual
credential candidate. Strongly validated passwords, keys, tokens, and connection strings
are handled before this review. Environment-variable references, public keys, placeholders,
known demo values, and test fixtures are excluded. Never claim a credential is active and
never reproduce sensitive values.

Return only JSON:
{"pii_exposure":true|false,"internal_endpoint_exposure":true|false,
"secret_credentials":true|false,"reason":"brief redacted explanation"}
"""

    @classmethod
    def build_messages(cls, input_data):
        candidates = [
            {key: value for key, value in candidate.items() if key != "matched_value"}
            for candidate in getattr(input_data, "repository_security_candidates", [])
        ]
        payload = {
            "candidates": candidates,
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
