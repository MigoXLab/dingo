"""Version-one code-content classification evaluator."""

from dingo.model import Model
from dingo.model.llm.code_quality.base_code_quality import BaseCodeClassification
from dingo.model.llm.code_quality.prompts import CODE_CLASSIFICATION_PROMPT


@Model.llm_register('LLMCodeClassificationV1')
class LLMCodeClassificationV1(BaseCodeClassification):
    """Standalone 0-5 scoring for separately configured dual-model classification."""

    prompt = CODE_CLASSIFICATION_PROMPT
    _metric_info = {
        'category': 'Classification Metrics', 'metric_name': 'LLMCodeClassificationV1',
        'description': 'Precision-first code-training relevance (0-5) and independent code presence, adapted from calibrated Prompt v5.',
        'paper_title': 'Internal Implementation',
        'examples': 'examples/code_quality/evaluate_code_executor.py',
    }
