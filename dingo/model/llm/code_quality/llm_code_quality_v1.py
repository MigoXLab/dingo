"""Version-one code evaluation policies; processing is inherited from shared bases."""

from dingo.model import Model
from dingo.model.llm.code_quality.base_code_quality import BaseCodeQuality
from dingo.model.llm.code_quality.prompts import CODE_QUALITY_PROMPT


@Model.llm_register('LLMCodeQualityV1')
class LLMCodeQualityV1(BaseCodeQuality):
    """Multi-label Executor output plus a primary decision and validated evidence."""

    prompt = CODE_QUALITY_PROMPT
    _metric_info = {
        'category': 'Pretrain Text Quality Assessment Metrics', 'metric_name': 'LLMCodeQualityV1',
        'description': 'Effectiveness (including low code content), completeness, repetition and security with contextual rule review and restricted code checks.',
        'paper_title': 'Internal Implementation (adapted from LLMTextQualityV6)',
        'examples': 'examples/code_quality/evaluate_code_executor.py',
        'evaluation_results': 'docs/code_quality/code_quality_v1.md',
    }
