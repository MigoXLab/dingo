"""Repository code quality pipeline V2.

V2 keeps the V1 contract (same required fields, same hard gates and LLM stages) and
adds the checks ported from the handover validators:

- contextual character anomalies (zero-width, private-use, unassigned) as a hard gate,
  with a review-level label for ambiguous boundary contexts;
- deterministic rule groups: non-code artifacts, language/content consistency,
  TODO and NotImplemented placeholder implementations, optional ClamAV scan;
- candidate-then-confirm stages for license declarations and reverse-shell code, so a
  signature match alone never produces a hard label.

The class is self-contained on purpose: like ``LLMTextQualityV7``/``V8``, a version is a
frozen snapshot, so later V1 changes must not silently alter V2 results. Callers pick a
version by evaluator name.
"""

from __future__ import annotations

from dingo.io.input import Data
from dingo.io.input.required_field import RequiredField
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.code_quality.base_code_quality import BaseCodeEvaluation, configured_evaluator, execution_error
from dingo.model.llm.llm_text_advertisement import LLMTextAdvertisement
from dingo.model.llm.repository_code_quality.common.llm_repository_license_review import LLMRepositoryLicenseReview
from dingo.model.llm.repository_code_quality.common.llm_repository_malware_review import LLMRepositoryReverseShellReview
from dingo.model.llm.repository_code_quality.common.llm_repository_security_review import LLMRepositorySecurityPolitics, LLMRepositorySecurityProhibition
from dingo.model.llm.repository_code_quality.common.llm_repository_sensitive_review import LLMRepositorySensitiveReview
from dingo.model.llm.repository_code_quality.common.rules_artifact import artifact_findings
from dingo.model.llm.repository_code_quality.common.rules_input_content import contextual_character_findings, input_content_findings, input_content_review_findings
from dingo.model.llm.repository_code_quality.common.rules_language_consistency import language_consistency_findings, language_consistency_review_findings
from dingo.model.llm.repository_code_quality.common.rules_license import license_candidates, license_review_findings, license_rule_finding
from dingo.model.llm.repository_code_quality.common.rules_malware import clamav_findings, reverse_shell_candidates, reverse_shell_rule_findings
from dingo.model.llm.repository_code_quality.common.rules_placeholder_implementation import placeholder_implementation_findings, placeholder_implementation_review_findings
from dingo.model.llm.repository_code_quality.common.rules_schema import REQUIRED_FIELDS, schema_findings
from dingo.model.llm.repository_code_quality.common.rules_sensitive import confirmed_security_findings, contextual_security_candidates, security_candidates, security_evidence
from dingo.model.llm.repository_code_quality.common.rules_similarity import intra_document_repetition
from dingo.model.llm.repository_code_quality.common.rules_truncation import code_truncation_finding


@Model.llm_register("LLMRepositoryCodeQualityPipelineV2")
class LLMRepositoryCodeQualityPipelineV2(BaseCodeEvaluation):
    """V1 checks plus contextual characters, ported rule groups, and confirmed findings."""

    _required_fields = [RequiredField(name) for name in REQUIRED_FIELDS]
    prompt = "\n".join((
        "Repository code quality pipeline V2 with contextual-character hard gate and "
        "candidate-then-confirm license and reverse-shell stages.",
        LLMTextAdvertisement.prompt,
        LLMRepositorySensitiveReview.prompt,
        LLMRepositorySecurityProhibition.prompt,
        LLMRepositorySecurityPolitics.prompt,
        LLMRepositoryLicenseReview.prompt,
        LLMRepositoryReverseShellReview.prompt,
    ))
    _metric_info = {
        "category": "Pretrain Text Quality Assessment Metrics",
        "metric_name": "LLMRepositoryCodeQualityPipelineV2",
        "description": (
            "Extends LLMRepositoryCodeQualityPipeline with contextual character anomalies, "
            "artifact, language consistency, placeholder implementation, ClamAV, and "
            "model-confirmed license declaration and reverse-shell checks."
        ),
        "examples": "examples/repository_code_quality/evaluate_repository_executor.py",
    }

    @classmethod
    def _run_stage(cls, evaluator, input_data, config):
        runtime = configured_evaluator(evaluator, config)
        try:
            return runtime.eval(input_data.model_copy(deep=True))
        finally:
            client = getattr(runtime, "client", None)
            if callable(getattr(client, "close", None)):
                client.close()

    @classmethod
    def eval(cls, input_data: Data):
        hard_findings = schema_findings(input_data)
        if isinstance(getattr(input_data, "content", None), str):
            hard_findings.extend(input_content_findings(input_data))
            hard_findings.extend(contextual_character_findings(input_data))
            truncation = code_truncation_finding(input_data)
            if truncation:
                hard_findings.append(truncation)
        if hard_findings:
            return EvalDetail(
                metric=cls.__name__,
                status=True,
                score=0,
                label=[finding["label"] for finding in hard_findings],
                reason=[finding["reason"] for finding in hard_findings],
                rubric_version=cls.rubric_version(),
            )
        config = cls.dynamic_config.model_copy(deep=True)
        candidates = security_candidates(input_data.content)
        contextual_candidates = contextual_security_candidates(candidates)
        review_input = input_data.model_copy(update={"repository_security_candidates": contextual_candidates})
        license_hits = license_candidates(input_data)
        shell_hits = reverse_shell_candidates(input_data)
        stages = [
            ("advertisement", LLMTextAdvertisement, input_data),
            ("prohibition", LLMRepositorySecurityProhibition, input_data),
            ("politics", LLMRepositorySecurityPolitics, input_data),
        ]
        if contextual_candidates:
            stages.insert(1, ("sensitive", LLMRepositorySensitiveReview, review_input))
        # Candidate-then-confirm stages: the rule bounds the prompt, the model decides.
        if license_hits:
            stages.append((
                "license",
                LLMRepositoryLicenseReview,
                input_data.model_copy(update={"repository_license_candidates": license_hits}),
            ))
        if shell_hits:
            stages.append((
                "reverse_shell",
                LLMRepositoryReverseShellReview,
                input_data.model_copy(update={"repository_reverse_shell_candidates": shell_hits}),
            ))

        stage_results = []
        for name, evaluator, data in stages:
            try:
                stage_results.append((name, cls._run_stage(evaluator, data, config)))
            except Exception as exc:
                stage_results.append((name, execution_error(evaluator.__name__, type(exc).__name__)))

        findings = artifact_findings(input_data)
        findings.extend(placeholder_implementation_findings(input_data))
        findings.extend(language_consistency_findings(input_data))
        findings.extend(clamav_findings(input_data))
        findings.extend(input_content_review_findings(input_data))
        findings.extend(language_consistency_review_findings(input_data))
        findings.extend(placeholder_implementation_review_findings(input_data))
        findings.extend(license_review_findings(input_data))
        findings.extend(list(getattr(input_data, "repository_duplicate_findings", []) or []))
        findings.extend(confirmed_security_findings(candidates))
        repeated = intra_document_repetition(input_data.content)
        if repeated:
            findings.append(repeated)
        candidate_evidence = {
            "license": [candidate["summary"] for candidate in license_hits[:3]],
            "reverse_shell": [candidate["summary"] for candidate in shell_hits[:3]],
        }
        errors = []
        for name, result in stage_results:
            if not result.applicable:
                error_type = next(
                    (
                        label.removeprefix("REVIEW_EXECUTION_ERROR.")
                        for label in (result.label or [])
                        if label.startswith("REVIEW_EXECUTION_ERROR.")
                    ),
                    "UnknownError",
                )
                error_reason = (result.reason or ["Stage did not complete."])[0]
                errors.append((name, error_type, error_reason))
                continue
            for index, label in enumerate(result.label or []):
                if label == "QUALITY_GOOD":
                    continue
                reason = (result.reason or [label])[min(index, len(result.reason or [label]) - 1)]
                if name == "sensitive":
                    category = {
                        "Security.PII_Exposure": "pii",
                        "Security.Internal_Endpoint_Exposure": "internal_endpoint",
                        "Security.Secret_Credentials": "secret",
                    }.get(label)
                    evidence = security_evidence(candidates, category) if category else ""
                    if evidence:
                        reason = f"{reason} Matched evidence: {evidence}."
                signature_evidence = "; ".join(candidate_evidence.get(name, []))
                if signature_evidence:
                    reason = f"{reason} Rule evidence: {signature_evidence}."
                findings.append({"label": label, "reason": str(reason)})

        # Fail open to the deterministic verdict so an LLM outage never hides a hit.
        failed_stages = {name for name, _, _ in errors}
        if "license" in failed_stages and license_hits:
            findings.append(license_rule_finding(license_hits[0]))
        if "reverse_shell" in failed_stages and shell_hits:
            findings.extend(reverse_shell_rule_findings(shell_hits))

        deduplicated = []
        labels_seen = set()
        for finding in findings:
            if finding["label"] not in labels_seen:
                labels_seen.add(finding["label"])
                deduplicated.append(finding)
        labels = [item["label"] for item in deduplicated]
        reasons = [item["reason"] for item in deduplicated]
        for stage, error_type, error_reason in errors:
            labels.append(f"REVIEW_EXECUTION_ERROR.{stage}")
            reasons.append(f"{stage} stage failed with {error_type}: {error_reason}")

        result = EvalDetail(
            metric=cls.__name__,
            status=bool(deduplicated),
            applicable=not errors,
            not_applicable_kind="execution_error" if errors else None,
            score=None if errors else (0 if deduplicated else 1),
            label=labels or ["QUALITY_GOOD"],
            reason=reasons or ["All repository code checks passed."],
            rubric_version=cls.rubric_version(),
        )
        for _, stage_result in stage_results:
            result.usage = BaseCodeEvaluation._merge_token_usage(result.usage, stage_result.usage)
        return result
