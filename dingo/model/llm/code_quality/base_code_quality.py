"""Shared input handling, response parsing and validation for code evaluators.

Concrete evaluators supply prompts and metadata, following BaseTextQuality's
separation of judging policy from result processing. API calls remain in BaseOpenAI.
"""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from dingo.config.input_args import EvaluatorLLMArgs
from dingo.io.input import Data, RequiredField
from dingo.io.output.eval_detail import EvalDetail
from dingo.model.llm.base_openai import BaseOpenAI
from dingo.utils.exception import ConvertJsonError

# Public taxonomy and strict model-output contract.
CODE_COMPONENTS = (
    'code_fence_block_boundary_corruption',
    'truncated_or_missing_code',
    'invalid_code_syntax_or_semantics',
)
MIXED = 'mixed_multiple_corruptions'
SYNTAX_SUBTYPES = (
    'syntax_delimiter_parser_error',
    'cross_language_transpilation_artifact',
)
RULE_NAMES = (
    'RuleContentNull', 'RuleContentShort', 'RuleSpecialCharacter', 'RuleAbnormalChar',
    'RuleSpaceMore', 'RuleOnlyUrl', 'RuleLoremIpsum', 'RuleDocRepeat', 'RulePIIDetection',
    'RuleHtmlEntity', 'RuleHtmlTag',
)
LABELS = {
    'Effectiveness': {'Empty_Content', 'Insufficient_Content', 'Special_Characters',
                      'Abnormal_Characters', 'HTML_Markup', 'Only_URL',
                      'Placeholder_Content', 'Code_Whitespace', 'Redundant_Language_Label',
                      'Fence_Language_Mismatch', 'Syntax_Error', 'Cross_Language_Mixing', 'Low_Code_Content'},
    'Completeness': {'Code_Truncation'},
    'Similarity': {'Document_Repetition'},
    'Security': {'PII_Exposure', 'Secret_Credentials', 'Internal_Endpoint_Exposure',
                 'Porn', 'Violent', 'Gamble', 'Drug', 'Politics'},
}
FENCE_LABELS = {('Effectiveness', 'Redundant_Language_Label'), ('Effectiveness', 'Fence_Language_Mismatch')}
SYNTAX_LABELS = {
    'syntax_delimiter_parser_error': {('Effectiveness', 'Syntax_Error'), ('Effectiveness', 'Code_Whitespace')},
    'cross_language_transpilation_artifact': {('Effectiveness', 'Cross_Language_Mixing')},
}
RULE_LABELS = {
    'RuleHtmlEntity': {('Effectiveness', 'HTML_Markup')},
    'RuleHtmlTag': {('Effectiveness', 'HTML_Markup')},
    'RuleContentNull': {('Effectiveness', 'Empty_Content')},
    'RuleContentShort': {('Effectiveness', 'Insufficient_Content')},
    'RuleSpecialCharacter': {('Effectiveness', 'Special_Characters'), ('Effectiveness', 'Syntax_Error')},
    'RuleAbnormalChar': {('Effectiveness', 'Special_Characters'), ('Effectiveness', 'Abnormal_Characters'),
                         ('Effectiveness', 'Syntax_Error')},
    'RuleSpaceMore': {('Effectiveness', 'Code_Whitespace')},
    'RuleOnlyUrl': {('Effectiveness', 'Only_URL')},
    'RuleLoremIpsum': {('Effectiveness', 'Placeholder_Content')},
    'RuleDocRepeat': {('Similarity', 'Document_Repetition')},
    'RulePIIDetection': {('Security', 'PII_Exposure'), ('Security', 'Internal_Endpoint_Exposure'),
                         ('Security', 'Secret_Credentials')},
}


class StrictResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)


class Classification(StrictResponse):
    score: int = Field(ge=0, le=5)
    contains_code: bool
    reason: str = Field(min_length=1)


class Finding(StrictResponse):
    type: str
    name: str
    reason: str = Field(min_length=1)
    line_start: int | None = Field(ge=1)
    line_end: int | None = Field(ge=1)

    @model_validator(mode='after')
    def validate_finding(self):
        if self.name not in LABELS.get(self.type, set()):
            raise ValueError('Unknown finding type/name pair')
        if (self.line_start is None) != (self.line_end is None):
            raise ValueError('Evidence must give both line bounds or neither')
        if self.line_start is not None and self.line_end < self.line_start:
            raise ValueError('Evidence line range is reversed')
        return self


class CodeError(StrictResponse):
    primary: str | None
    tags: list[str]
    syntax_subtypes: list[str]

    @model_validator(mode='after')
    def validate_taxonomy(self):
        if len(self.tags) != len(set(self.tags)) or not set(self.tags) <= set(CODE_COMPONENTS):
            raise ValueError('Invalid or duplicate code component tags')
        if len(self.syntax_subtypes) != len(set(self.syntax_subtypes)) or not set(self.syntax_subtypes) <= set(SYNTAX_SUBTYPES):
            raise ValueError('Invalid or duplicate syntax subtypes')
        if not self.tags:
            if self.primary is not None or self.syntax_subtypes:
                raise ValueError('No code defects must have null primary and empty subtypes')
        elif self.primary == MIXED:
            if len(self.tags) < 2:
                raise ValueError('Mixed corruption requires at least two components')
        elif self.primary not in self.tags:
            raise ValueError('Code primary must be a supported component')
        has_syntax = 'invalid_code_syntax_or_semantics' in self.tags
        if has_syntax != bool(self.syntax_subtypes):
            raise ValueError('Syntax component and subtype presence must agree')
        return self


class Politics(StrictResponse):
    hurt_socialist_regime_system: Literal['neg', 'pos', 'none']
    hurt_china_interests_image: Literal['neg', 'pos', 'none']
    hurt_china_unity_stability: Literal['neg', 'pos', 'none']
    terrorism_and_extremism: Literal['neg', 'pos', 'none']
    ethnic_hate_and_discrimination: Literal['neg', 'pos', 'none']


class RuleReview(StrictResponse):
    metric: Literal[
        'RuleContentNull', 'RuleContentShort', 'RuleSpecialCharacter', 'RuleAbnormalChar',
        'RuleSpaceMore', 'RuleOnlyUrl', 'RuleLoremIpsum', 'RuleDocRepeat', 'RulePIIDetection',
        'RuleHtmlEntity', 'RuleHtmlTag',
    ]
    confirmed: bool
    reason: str = Field(min_length=1)


class CodeQualityResponse(StrictResponse):
    score: int = Field(ge=0, le=1)
    type: str
    name: str
    reason: str = Field(min_length=1)
    classification: Classification
    findings: list[Finding]
    code_error: CodeError
    politics: Politics
    rule_reviews: list[RuleReview]

    @model_validator(mode='after')
    def validate_consistency(self):
        labels = {(item.type, item.name) for item in self.findings}
        if len(labels) != len(self.findings):
            raise ValueError('Duplicate finding labels')
        if self.findings:
            if self.score != 0 or (self.type, self.name) not in labels:
                raise ValueError('Defect primary must match an actual finding with score zero')
        elif (self.score, self.type, self.name) != (1, 'Good', 'None'):
            raise ValueError('Passing result must be 1 / Good / None')
        if (self.classification.score <= 2) != (('Effectiveness', 'Low_Code_Content') in labels):
            raise ValueError('Code relevance finding disagrees with classification score')
        if bool(labels & FENCE_LABELS) != ('code_fence_block_boundary_corruption' in self.code_error.tags):
            raise ValueError('Fence component and language-label findings disagree')
        if (('Completeness', 'Code_Truncation') in labels) != ('truncated_or_missing_code' in self.code_error.tags):
            raise ValueError('Truncation component and finding disagree')
        for subtype, allowed_labels in SYNTAX_LABELS.items():
            matching = labels & allowed_labels
            if subtype == 'syntax_delimiter_parser_error' and matching == {('Effectiveness', 'Code_Whitespace')}:
                continue
            if bool(matching) != (subtype in self.code_error.syntax_subtypes):
                raise ValueError('Syntax subtype and finding disagree')
        if ('neg' in self.politics.model_dump().values()) != (('Security', 'Politics') in labels):
            raise ValueError('Politics finding disagrees with aspect judgments')
        metrics = [item.metric for item in self.rule_reviews]
        if len(metrics) != len(set(metrics)):
            raise ValueError('Duplicate rule review')
        if any(item.confirmed and not labels.intersection(RULE_LABELS[item.metric]) for item in self.rule_reviews):
            raise ValueError('Confirmed rule review must retain a corresponding finding')
        return self


def parse_response(response, schema):
    """Reject incomplete, contradictory or invented outputs without logging payloads."""
    try:
        text = response.strip()
        if text.startswith('```json') and text.endswith('```'):
            text = text[7:-3].strip()
        elif text.startswith('```') and text.endswith('```'):
            text = text[3:-3].strip()
        return schema.model_validate(json.loads(text))
    except (AttributeError, TypeError, ValueError, ValidationError):
        # Pydantic/JSON exceptions may contain the complete model response, including secrets.
        raise ConvertJsonError('Invalid code-quality response: JSON/schema consistency check failed.') from None


def execution_error(metric, code):
    return CodeQualityDetail(
        metric=metric, status=False, applicable=False, not_applicable_kind='execution_error',
        score=None, label=[f'REVIEW_EXECUTION_ERROR.{code}'], reason=[code],
    )


class CodeQualityDetail(EvalDetail):
    """Expose all findings to Executor; retain the primary decision in details."""

    details: dict = Field(default_factory=dict)


class BaseCodeEvaluation(BaseOpenAI):
    _required_fields = [RequiredField.CONTENT]
    _instance_config_defaults = BaseOpenAI.dynamic_config.model_copy(deep=True)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Capture declared defaults before the legacy Executor writes class config.
        cls._instance_config_defaults = cls.__dict__.get(
            'dynamic_config', cls._instance_config_defaults).model_copy(deep=True)

    def __init__(self):
        # Executor configures the instance before invoking eval. Never inherit
        # config left on the registered class by another task or evaluator group.
        self.dynamic_config = self._instance_config_defaults.model_copy(deep=True)
        self.eval = self._eval_instance

    def _eval_instance(self, input_data: Data):
        runtime = configured_evaluator(type(self), self.dynamic_config)
        try:
            return runtime.eval(input_data)
        finally:
            clients = [getattr(runtime, name, None) for name in ('client', 'embedding_client')]
            closed = set()
            for client in clients:
                if id(client) not in closed and callable(getattr(client, 'close', None)):
                    closed.add(id(client))
                    client.close()

    @classmethod
    def build_messages(cls, input_data: Data):
        if not isinstance(getattr(input_data, 'content', None), str):
            raise ValueError('Code evaluation requires string content; input is not coerced or rewritten.')
        return [
            {'role': 'system', 'content': cls.prompt},
            {'role': 'user', 'content': json.dumps({'content': input_data.content}, ensure_ascii=False)},
        ]

    @classmethod
    def eval(cls, input_data: Data):
        if not isinstance(getattr(input_data, 'content', None), str):
            return execution_error(cls.__name__, 'MissingOrNonStringContent')
        try:
            result = super().eval(input_data)
        except Exception as exc:
            # Client construction/message building happen outside BaseOpenAI's
            # retry block. Do not expose exception text that may contain inputs.
            result = execution_error(cls.__name__, type(exc).__name__)
        if not result.applicable:
            result.reason = ['Code evaluation failed; see the execution-error label.']
            result.rubric_version = cls.rubric_version()
        return result

    @classmethod
    def rubric_version(cls):
        return f'{cls.__name__}:sha256:{hashlib.sha256(cls.prompt.encode("utf-8")).hexdigest()}'


class BaseCodeClassification(BaseCodeEvaluation):
    """Convert independent 0-5 relevance scores to standard evaluation results."""

    @classmethod
    def process_response(cls, response):
        result = parse_response(response, Classification)
        return CodeQualityDetail(
            metric=cls.__name__, status=result.score <= 2, score=result.score,
            label=['Effectiveness.Low_Code_Content'] if result.score <= 2 else ['QUALITY_GOOD'],
            reason=[result.reason],
            details={**result.model_dump(), 'positive': result.score >= 4,
                     'review_priority': 'high' if result.score <= 2 else 'normal',
                     'review_required': result.score <= 2},
            rubric_version=cls.rubric_version(),
        )


class BaseCodeQuality(BaseCodeEvaluation):
    """Parse quality decisions and validate multi-label evidence and rule reviews."""

    @classmethod
    def build_messages(cls, input_data: Data):
        messages = super().build_messages(input_data)
        candidates = getattr(input_data, 'rule_candidates', [])
        if not isinstance(candidates, list):
            raise ValueError('rule_candidates must be a list')
        metrics = [item.get('metric') for item in candidates if isinstance(item, dict)]
        if len(metrics) != len(candidates) or len(set(metrics)) != len(metrics) or not set(metrics) <= set(RULE_NAMES):
            raise ValueError('rule_candidates contains unknown or duplicate rules')
        messages[1]['content'] = json.dumps(
            {'content': input_data.content, 'rule_candidates': candidates}, ensure_ascii=False,
        )
        return messages

    @classmethod
    def process_response(cls, response):
        parsed = parse_response(response, CodeQualityResponse)
        return CodeQualityDetail(
            metric=cls.__name__, status=bool(parsed.findings), score=parsed.score,
            label=[f'{item.type}.{item.name}' for item in parsed.findings] if parsed.findings else ['QUALITY_GOOD'],
            reason=[item.reason for item in parsed.findings] if parsed.findings else [parsed.reason],
            details={**parsed.model_dump(), 'review_required': bool(parsed.findings),
                     'all_labels': [f'{item.type}.{item.name}' for item in parsed.findings],
                     'classification_positive': parsed.classification.score >= 4,
                     'classification_review_priority': 'high' if parsed.classification.score <= 2 else 'normal'},
            rubric_version=cls.rubric_version(),
        )

    @classmethod
    def eval(cls, input_data: Data):
        # Executor supplies just content. Run preliminary rules here so a normal
        # registered evaluator includes contextual review without executor coupling.
        if not isinstance(getattr(input_data, 'content', None), str):
            return execution_error(cls.__name__, 'MissingOrNonStringContent')
        rule_results = None
        if not hasattr(input_data, 'rule_candidates'):
            rule_results = run_code_rules(input_data)
            if any(not item.applicable for item in rule_results):
                error = execution_error(cls.__name__, 'RuleFailed')
                error.details['rules'] = [
                    {'metric': item.metric, 'status': item.status, 'applicable': item.applicable,
                     'label': item.label} for item in rule_results
                ]
                return error
            input_data = input_data.model_copy(update={'rule_candidates': rule_candidates(rule_results)})
        # Validate before API calls; malformed supplied candidates are execution errors.
        try:
            cls.build_messages(input_data)
        except (ValueError, TypeError):
            return execution_error(cls.__name__, 'InvalidRuleCandidates')
        result = super().eval(input_data)
        if not result.applicable:
            return result
        payload = result.details
        if rule_results is not None:
            payload['rules'] = [
                {'metric': item.metric, 'status': item.status, 'applicable': item.applicable,
                 'label': item.label} for item in rule_results
            ]
        expected = {item['metric'] for item in getattr(input_data, 'rule_candidates', [])}
        if {item['metric'] for item in payload['rule_reviews']} != expected:
            error = execution_error(cls.__name__, 'IncompleteRuleReview')
            error.usage = result.usage
            return error
        line_count = len(input_data.content.split('\n'))
        if any(item['line_end'] is not None and item['line_end'] > line_count for item in payload['findings']):
            error = execution_error(cls.__name__, 'EvidenceLineOutOfRange')
            error.usage = result.usage
            return error
        return result


# Shared workflow helpers used by standalone evaluators and the pipeline.
DEFAULT_QUALITY_MODEL = 'bailian/deepseek-v4.1-flash'
DEFAULT_CLASSIFICATION_MODELS = ('glm-5.3-flash', DEFAULT_QUALITY_MODEL)


def configured_evaluator(evaluator, config):
    """Create an isolated runtime class for a classmethod-based evaluator."""
    if isinstance(config, dict):
        config = EvaluatorLLMArgs(**config)
    return type(evaluator.__name__, (evaluator,), {
        'dynamic_config': config.model_copy(deep=True), 'client': None,
    })


def run_code_rules(input_data):
    """Run deterministic candidates on a copy; keep failures separate from hits."""
    from dingo.model.rule import rule_common

    results = []
    for name in RULE_NAMES:
        rule = getattr(rule_common, name)
        try:
            results.append(rule.eval(input_data.model_copy(deep=True)))
        except Exception:
            results.append(EvalDetail(
                metric=name, status=False, applicable=False, not_applicable_kind='execution_error',
                label=['REVIEW_EXECUTION_ERROR.RuleFailed'], reason=['Rule execution failed'],
            ))
    return results


def rule_candidates(results):
    """Return candidate identity and labels without copying detector snippets."""
    return [{'metric': result.metric, 'label': result.label}
            for result in results if result.applicable and result.status]


def classification_consensus(results):
    """Both classifiers must succeed; their unrounded mean <=2 indicates low content."""
    scores = [item.score if item.applicable else None for item in results]
    if any(score is not None and (isinstance(score, bool) or score not in range(6)) for score in scores):
        raise ValueError('Classification scores must be integers from 0 to 5')
    complete = len(scores) == 2 and all(score is not None for score in scores)
    if not complete:
        return {'positive': None, 'low_code_content': None, 'scores': scores, 'average_score': None,
                'review_required': True, 'execution_error': True, 'threshold_disagreement': None}
    average = sum(scores) / 2
    low = average <= 2
    positive = all(score >= 4 for score in scores)
    return {
        'positive': positive, 'low_code_content': low, 'scores': scores, 'average_score': average,
        'threshold_disagreement': (scores[0] >= 4) != (scores[1] >= 4),
        'review_priority': 'high' if low else 'normal',
        'review_required': not positive, 'execution_error': False,
    }
