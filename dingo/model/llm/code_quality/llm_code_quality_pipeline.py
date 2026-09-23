"""Executor entry point combining quality and safety review with dual scoring."""

import copy
import uuid

from dingo.io.input import Data
from dingo.model import Model
from dingo.model.llm.code_quality.base_code_quality import (DEFAULT_CLASSIFICATION_MODELS, DEFAULT_QUALITY_MODEL, BaseCodeEvaluation, CodeQualityDetail, classification_consensus, configured_evaluator,
                                                            execution_error)
from dingo.model.llm.code_quality.llm_code_classification_v1 import LLMCodeClassificationV1
from dingo.model.llm.code_quality.llm_code_quality_v1 import LLMCodeQualityV1


def merge_results(quality, classified, models, metric, rubric):
    """Keep raw decisions while deduplicating the final public issue labels."""
    consensus = classification_consensus(classified)
    # In this pipeline the two independent classifiers own the low-content label.
    findings = [copy.deepcopy(item) for item in getattr(quality, 'details', {}).get('findings', [])
                if (item['type'], item['name']) != ('Effectiveness', 'Low_Code_Content')]
    if consensus['low_code_content']:
        scores = ', '.join(f'{model}={score}' for model, score in zip(models, consensus['scores']))
        findings.append({'type': 'Effectiveness', 'name': 'Low_Code_Content',
                         'reason': f'Dual classification: {scores}; average={consensus["average_score"]} <=2.',
                         'line_start': None, 'line_end': None})
    stages = [('quality', quality), *[(f'classification_{index}', item) for index, item in enumerate(classified)]]
    errors = [name for name, item in stages if not item.applicable]
    labels = [f"{item['type']}.{item['name']}" for item in findings]
    reasons = [item['reason'] for item in findings]
    for name in errors:
        labels.append(f'REVIEW_EXECUTION_ERROR.{name}')
        reasons.append(f'{name} did not complete; inspect stage results.')
    result = CodeQualityDetail(
        metric=metric, applicable=not errors, status=bool(findings),
        not_applicable_kind='execution_error' if errors else None,
        score=None if errors else (0 if findings else 1),
        label=labels or ['QUALITY_GOOD'], reason=reasons or ['All pipeline stages passed.'],
        rubric_version=rubric,
        details={'findings': findings, 'all_labels': [label for label in labels if not label.startswith('REVIEW_EXECUTION_ERROR.')],
                 'quality': quality.model_dump(), 'classification_models': list(models),
                 'classification': [item.model_dump() for item in classified],
                 'classification_consensus': consensus,
                 'execution_errors': errors, 'review_required': bool(errors or findings or consensus['review_required'])},
    )
    for _, item in stages:
        result.usage = BaseCodeEvaluation._merge_token_usage(result.usage, item.usage)
    if result.usage and len({item.usage.model for _, item in stages if item.usage}) > 1:
        result.usage.model = 'multiple'
    return result


@Model.llm_register('LLMCodeQualityPipeline')
class LLMCodeQualityPipeline(BaseCodeEvaluation):
    """Three LLM requests per record; one native Executor result."""

    prompt = 'Code pipeline v3: both classifiers succeed and mean <=2; LLM-only safety.\n' + LLMCodeQualityV1.prompt + LLMCodeClassificationV1.prompt
    _metric_info = {
        'category': 'Pretrain Text Quality Assessment Metrics', 'metric_name': 'LLMCodeQualityPipeline',
        'description': 'Code quality, DeepSeek/GLM dual classification and LLM safety review.',
        'examples': 'examples/code_quality/evaluate_code_executor.py',
    }

    @classmethod
    def eval(cls, input_data: Data):
        if not isinstance(getattr(input_data, 'content', None), str):
            return execution_error(cls.__name__, 'MissingOrNonStringContent')
        config = dict(cls.dynamic_config)
        if not config.get('model'):
            config['model'] = DEFAULT_QUALITY_MODEL
        models = config.pop('classification_models', list(DEFAULT_CLASSIFICATION_MODELS))
        request_overrides = config.pop('classification_request_overrides', {})
        if (not isinstance(models, (list, tuple)) or len(models) != 2
                or any(not isinstance(model, str) or not model.strip() for model in models) or models[0] == models[1]):
            return execution_error(cls.__name__, 'InvalidClassificationModels')
        if (not isinstance(request_overrides, dict)
                or any(model not in models or not isinstance(params, dict)
                       or set(params) - {'extra_body'}
                       or ('extra_body' in params and not isinstance(params['extra_body'], dict))
                       for model, params in request_overrides.items())):
            return execution_error(cls.__name__, 'InvalidClassificationRequestOverrides')
        headers = dict(config.get('extra_headers') or {})
        session = headers.get('X-Session-ID') or 'dingo-code-' + uuid.uuid4().hex

        def run(evaluator, model, stage):
            # Replace extra_body as a whole so incompatible inherited options can be removed.
            overrides = request_overrides.get(model, {}) if stage.startswith('classification-') else {}
            stage_config = dict(config)
            if model == DEFAULT_QUALITY_MODEL:
                stage_config.setdefault('extra_body', {'enable_thinking': False})
            if model == 'glm-5.3-flash' and stage.startswith('classification-'):
                stage_config['extra_body'] = {'reasoning_effort': 'low'}
            judge = configured_evaluator(evaluator, {**stage_config, **overrides, 'model': model,
                                         'extra_headers': {**headers, 'X-Session-ID': session + '-' + stage}})
            try:
                return judge.eval(input_data.model_copy(deep=True))
            finally:
                if callable(getattr(judge.client, 'close', None)):
                    judge.client.close()

        quality = run(LLMCodeQualityV1, config.get('model'), 'quality')
        classified = [run(LLMCodeClassificationV1, model, f'classification-{index}') for index, model in enumerate(models)]
        return merge_results(quality, classified, models, cls.__name__, cls.rubric_version())
