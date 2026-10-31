"""Rule-first and LLM-assisted repository code quality pipeline."""

from __future__ import annotations

from dingo.io.input import Data
from dingo.io.input.required_field import RequiredField
from dingo.io.output.eval_detail import EvalDetail
from dingo.model import Model
from dingo.model.llm.code_quality.base_code_quality import BaseCodeEvaluation, configured_evaluator, execution_error
from dingo.model.llm.llm_text_advertisement import LLMTextAdvertisement
from dingo.model.llm.repository_code_quality.input_content_rules import input_content_findings
from dingo.model.llm.repository_code_quality.llm_repository_security_review import LLMRepositorySecurityPolitics, LLMRepositorySecurityProhibition
from dingo.model.llm.repository_code_quality.llm_repository_sensitive_review import LLMRepositorySensitiveReview
from dingo.model.llm.repository_code_quality.schema_rules import REQUIRED_FIELDS, schema_findings
from dingo.model.llm.repository_code_quality.sensitive_rules import confirmed_security_findings, contextual_security_candidates, security_candidates, security_evidence
from dingo.model.llm.repository_code_quality.similarity_rules import RepositoryDuplicateIndex, intra_document_repetition, record_reference
from dingo.model.llm.repository_code_quality.truncation_rules import code_truncation_finding


@Model.llm_register("LLMRepositoryCodeQualityPipeline")
class LLMRepositoryCodeQualityPipeline(BaseCodeEvaluation):
    """Schema, completeness, security, effectiveness, and similarity review."""

    _prepared_fields = ("_repository_duplicate_findings",)
    # The schema hard gate in eval() validates exactly these fields, so they are
    # the metric contract. Field-mapping consumers (e.g. Dingo SaaS) project each
    # record down to the required fields; advertising only `content` made every
    # record fail Effectiveness.Missing_Required before any LLM stage ran.
    _required_fields = [RequiredField(name) for name in REQUIRED_FIELDS]
    prompt = "\n".join((
        "Repository code quality pipeline v3 with schema, content, and code-truncation hard gates.",
        LLMTextAdvertisement.prompt,
        LLMRepositorySensitiveReview.prompt,
        LLMRepositorySecurityProhibition.prompt,
        LLMRepositorySecurityPolitics.prompt,
    ))
    _metric_info = {
        "category": "Pretrain Text Quality Assessment Metrics",
        "metric_name": "LLMRepositoryCodeQualityPipeline",
        "description": (
            "Repository record-field schema, code truncation, content validity, advertisement, "
            "sensitive data, prohibited/political content, and repetition checks."
        ),
        "examples": "examples/repository_code_quality/evaluate_repository_executor.py",
    }

    @classmethod
    def prepare_state(cls, _config=None):
        return RepositoryDuplicateIndex()

    @classmethod
    def prepare_record(cls, data, state, ref):
        findings = state.annotate(data, record_reference(data, ref))
        object.__setattr__(data, "_repository_duplicate_findings", findings)

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
        stages = [
            ("advertisement", LLMTextAdvertisement, input_data),
            ("prohibition", LLMRepositorySecurityProhibition, input_data),
            ("politics", LLMRepositorySecurityPolitics, input_data),
        ]
        if contextual_candidates:
            stages.insert(1, ("sensitive", LLMRepositorySensitiveReview, review_input))

        stage_results = []
        for name, evaluator, data in stages:
            try:
                stage_results.append((name, cls._run_stage(evaluator, data, config)))
            except Exception as exc:
                stage_results.append((name, execution_error(evaluator.__name__, type(exc).__name__)))

        findings = list(getattr(input_data, "_repository_duplicate_findings", []) or [])
        findings.extend(confirmed_security_findings(candidates))
        repeated = intra_document_repetition(input_data.content)
        if repeated:
            findings.append(repeated)
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
                findings.append({"label": label, "reason": str(reason)})

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
