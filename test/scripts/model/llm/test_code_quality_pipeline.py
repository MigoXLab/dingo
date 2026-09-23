import json
from types import SimpleNamespace

import pytest

from dingo.config import InputArgs
from dingo.exec.local import LocalExecutor
from dingo.io.input import Data
from dingo.io.output.eval_detail import EvalDetail
from dingo.model.llm.code_quality.base_code_quality import DEFAULT_CLASSIFICATION_MODELS, CodeQualityDetail, classification_consensus, configured_evaluator
from dingo.model.llm.code_quality.llm_code_classification_v1 import LLMCodeClassificationV1
from dingo.model.llm.code_quality.llm_code_quality_pipeline import LLMCodeQualityPipeline, merge_results
from dingo.model.llm.code_quality.llm_code_quality_v1 import LLMCodeQualityV1


def classified(score):
    if score is None:
        return EvalDetail(metric='classifier', applicable=False, label=['REVIEW_EXECUTION_ERROR.Timeout'])
    return LLMCodeClassificationV1.process_response(json.dumps({'score': score, 'contains_code': True, 'reason': 'fixture'}))


@pytest.mark.parametrize('evaluator', [LLMCodeQualityPipeline, LLMCodeQualityV1, LLMCodeClassificationV1])
def test_code_executor_isolates_eight_concurrent_configs(evaluator, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(8)
    clients = []
    monkeypatch.setattr(evaluator, 'dynamic_config', evaluator.dynamic_config.model_copy(deep=True))

    def evaluate(cls, data):
        client = SimpleNamespace(closed=False)
        client.close = lambda: setattr(client, 'closed', True)
        cls.client = client
        clients.append(client)
        if data.content == 'concurrent':
            barrier.wait(timeout=15)
        return CodeQualityDetail(metric=cls.__name__, label=['QUALITY_GOOD'], reason=[{
            'model': cls.dynamic_config.model,
            'temperature': getattr(cls.dynamic_config, 'temperature', None),
            'extra_headers': getattr(cls.dynamic_config, 'extra_headers', None)}])

    monkeypatch.setattr(evaluator, 'eval', classmethod(evaluate))
    executor = LocalExecutor(InputArgs(executor={'result_save': {'all_labels': True}}))

    def run(index):
        config = {'model': f'model-{index}'}
        if index < 8:
            config.update(temperature=index / 10, extra_headers={'X-Session-ID': f'session-{index}'})
        entries = InputArgs(evaluator=[{'evals': [{'name': evaluator.__name__, 'config': config}]}]).evaluator[0].evals
        result = executor.evaluate_single_data(str(index), {}, 'llm',
                                              {'content': 'concurrent' if index < 8 else 'sequential'}, entries)
        return result.eval_details['default'][0].reason[0]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, range(8)))
    assert results == [{'model': f'model-{i}', 'temperature': i / 10,
                        'extra_headers': {'X-Session-ID': f'session-{i}'}} for i in range(8)]
    last = run(8)
    assert last == {'model': 'model-8', 'temperature': None,
                    'extra_headers': None}
    assert len(clients) == 9 and all(client.closed for client in clients)


def test_configured_code_instance_preserves_explicit_config_and_closes_on_error(monkeypatch):
    client = SimpleNamespace(closed=False)
    client.close = lambda: setattr(client, 'closed', True)

    def fail(cls, data):
        assert cls.dynamic_config.model == 'configured-model'
        cls.client = client
        cls.embedding_client = client
        raise RuntimeError('fixture')

    monkeypatch.setattr(LLMCodeQualityV1, 'eval', classmethod(fail))
    judge = configured_evaluator(LLMCodeQualityV1, {'model': 'configured-model'})()
    with pytest.raises(RuntimeError, match='fixture'):
        judge.eval(Data(content='print(1)'))
    assert client.closed


def test_classification_request_overrides_do_not_leak_to_other_stages(monkeypatch):
    from dingo.model.llm.code_quality import llm_code_quality_pipeline as pipeline

    captured = []

    def configure(evaluator, config):
        captured.append(config)
        result = classified(4) if evaluator is LLMCodeClassificationV1 else CodeQualityDetail(metric='quality')
        return SimpleNamespace(client=None, eval=lambda data: result)

    monkeypatch.setattr(pipeline, 'configured_evaluator', configure)
    config = {'model': 'deepseek', 'classification_models': ['glm', 'deepseek'],
              'extra_body': {'enable_thinking': False},
              'classification_request_overrides': {'glm': {'extra_body': {'reasoning_effort': 'low'}}}}
    judge = configured_evaluator(LLMCodeQualityPipeline, config)
    assert judge.eval(Data(content='print(1)')).applicable
    assert [c['extra_body'] for c in captured] == [
        {'enable_thinking': False}, {'reasoning_effort': 'low'}, {'enable_thinking': False}]
    assert all('classification_request_overrides' not in c for c in captured)
    assert config['extra_body'] == {'enable_thinking': False}


@pytest.mark.parametrize('explicit_override', [False, True])
def test_default_flash_models_and_request_bodies(monkeypatch, explicit_override):
    from dingo.model.llm.code_quality import llm_code_quality_pipeline as pipeline

    captured = []

    def configure(evaluator, config):
        captured.append(config)
        result = classified(4) if evaluator is LLMCodeClassificationV1 else CodeQualityDetail(metric='quality')
        return SimpleNamespace(client=None, eval=lambda data: result)

    monkeypatch.setattr(pipeline, 'configured_evaluator', configure)
    config = {'extra_body': {'enable_thinking': False}}
    if explicit_override:
        config['classification_request_overrides'] = {
            'glm-5.3-flash': {'extra_body': {'reasoning_effort': 'high'}}}
    assert configured_evaluator(LLMCodeQualityPipeline, config).eval(Data(content='print(1)')).applicable
    assert [c['model'] for c in captured] == [
        'bailian/deepseek-v4.1-flash', 'glm-5.3-flash', 'bailian/deepseek-v4.1-flash']
    assert [c['extra_body'] for c in captured] == [
        {'enable_thinking': False}, {'reasoning_effort': 'high' if explicit_override else 'low'},
        {'enable_thinking': False}]


@pytest.mark.parametrize('overrides', [None, [], {'unknown': {}}, {'glm': {'model': 'other'}},
                                     {'glm': {'extra_body': False}}])
def test_invalid_classification_request_overrides_fail_before_requests(overrides, monkeypatch):
    from dingo.model.llm.code_quality import llm_code_quality_pipeline as pipeline

    def unexpected(*args, **kwargs):
        pytest.fail('Invalid config must not start requests')

    monkeypatch.setattr(pipeline, 'configured_evaluator', unexpected)
    judge = configured_evaluator(LLMCodeQualityPipeline, {
        'model': 'deepseek', 'classification_models': ['glm', 'deepseek'],
        'classification_request_overrides': overrides})
    assert not judge.eval(Data(content='print(1)')).applicable


@pytest.mark.parametrize('scores,low,complete',
                         [([a, b], a + b <= 4, True) for a in range(6) for b in range(6)]
                         + [([a, None], None, False) for a in range(6)]
                         + [([None, b], None, False) for b in range(6)]
                         + [([None, None], None, False)])
def test_dual_low_threshold_and_partial_failures(scores, low, complete):
    results = [classified(score) for score in scores]
    consensus = classification_consensus(results)
    assert consensus['low_code_content'] is low
    assert consensus['execution_error'] is not complete
    assert consensus['average_score'] == (sum(scores) / 2 if complete else None)
    quality = CodeQualityDetail(metric='quality', details={'findings': []})
    merged = merge_results(quality, results, DEFAULT_CLASSIFICATION_MODELS, 'pipeline', 'v1')
    assert ('Effectiveness.Low_Code_Content' in merged.label) == (low is True)
    assert merged.applicable is complete
    assert not (not complete and 'QUALITY_GOOD' in merged.label)
    if low:
        assert f'average={sum(scores) / 2} <=2' in merged.reason[0]


def test_dual_scores_own_label_and_preserve_quality_decision():
    quality = CodeQualityDetail(metric='quality', status=True, details={'findings': [
        {'type': 'Effectiveness', 'name': 'Low_Code_Content', 'reason': 'single model low', 'line_start': None, 'line_end': None}]})
    result = merge_results(quality, [classified(4), classified(5)], DEFAULT_CLASSIFICATION_MODELS,
                           'pipeline', 'v1')
    assert result.label == ['QUALITY_GOOD']
    assert result.details['quality']['status'] is True
    assert quality.details['findings']


def test_pipeline_preserves_consensus_review_requirement():
    result = merge_results(CodeQualityDetail(metric='quality'), [classified(3), classified(5)],
                           DEFAULT_CLASSIFICATION_MODELS, 'pipeline', 'v1')
    assert result.details['classification_consensus']['threshold_disagreement']
    assert result.details['review_required']
    assert not result.status
    assert result.label == ['QUALITY_GOOD']


def test_base_llm_failure_without_details_preserves_other_stage_findings():
    quality = EvalDetail(metric='LLMCodeQualityV1', applicable=False,
                         not_applicable_kind='execution_error', label=['REVIEW_EXECUTION_ERROR.ConvertJsonError'])
    result = merge_results(quality, [classified(1), classified(3)], DEFAULT_CLASSIFICATION_MODELS, 'pipeline', 'v3')
    assert not result.applicable
    assert result.score is None
    assert result.label == ['Effectiveness.Low_Code_Content', 'REVIEW_EXECUTION_ERROR.quality']
    assert result.details['quality']['label'] == ['REVIEW_EXECUTION_ERROR.ConvertJsonError']


def test_good_pipeline_result_is_exported_without_losing_source_fields(tmp_path):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        'code_executor_example', Path(__file__).resolve().parents[4] / 'examples/code_quality/evaluate_code_executor.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    export_final = runner.export_final

    result = merge_results(CodeQualityDetail(metric='quality'), [classified(4), classified(5)],
                           DEFAULT_CLASSIFICATION_MODELS, 'LLMCodeQualityPipeline', 'v1')
    row = {'sample_id': 'good', 'content': 'print(1)', 'doc_url': 's3://bucket/key?bytes=0,1',
           'extra': {'keep': True}, '_code_qc': {'category': 'web', 'language': 'en'}}
    record = {'dingo_id': 'good', 'raw_data': row, 'eval_status': result.status,
              'eval_details': {'content': [result.model_dump()]}}
    config = InputArgs(executor={'result_save': {'bad': True, 'good': True, 'all_labels': True}})
    summary = export_final(tmp_path, [row], {'good': record}, config)
    assert summary['good'] == 1 and summary['automatic_candidates'] == 0
    saved = json.loads((Path(summary['output_path']) / 'content/QUALITY_GOOD.jsonl').read_text(encoding='utf-8'))
    assert saved['raw_data'] == row
    assert saved['eval_details']['content'][0]['label'] == ['QUALITY_GOOD']
    assert saved['eval_details']['content'][0]['details']['all_labels'] == []


@pytest.mark.parametrize('quality_failure', [False, True])
def test_executor_full_pipeline_calls_stages_and_writes_results(tmp_path, monkeypatch, quality_failure):
    monkeypatch.setenv('LOCAL_DEPLOYMENT_MODE', 'true')
    calls = []

    def quality(cls, data):
        calls.append(('quality', cls.dynamic_config.model))
        assert 'classification_models' not in (cls.dynamic_config.model_extra or {})
        assert cls.dynamic_config.model_extra['extra_headers']['X-Session-ID'].endswith('-quality')
        if quality_failure:
            return CodeQualityDetail(metric='quality', applicable=False, label=['REVIEW_EXECUTION_ERROR.Timeout'])
        return CodeQualityDetail(metric='quality', details={'findings': [
            {'type': 'Security', 'name': 'Secret_Credentials', 'reason': 'LLM candidate [REDACTED]',
             'line_start': 1, 'line_end': 1}]})

    def classification(cls, data):
        calls.append(('classification', cls.dynamic_config.model))
        return classified(1 if cls.dynamic_config.model == DEFAULT_CLASSIFICATION_MODELS[0] else 3)

    monkeypatch.setattr(LLMCodeQualityV1, 'eval', classmethod(quality))
    monkeypatch.setattr(LLMCodeClassificationV1, 'eval', classmethod(classification))
    source = tmp_path / 'input.jsonl'
    source.write_text(json.dumps({'sample_id': 'one', 'content': 'print(1)'}) + '\n', encoding='utf-8')
    config = InputArgs(input_path=str(source), output_path=str(tmp_path / 'results'),
                       dataset={'source': 'local', 'format': 'jsonl'},
                       executor={'max_workers': 1, 'batch_size': 1, 'result_save': {'bad': True, 'good': True, 'all_labels': True}},
                       evaluator=[{'fields': {'content': 'content'}, 'evals': [{'name': 'LLMCodeQualityPipeline', 'config': {'model': 'quality-model'}}]}])
    summary = LocalExecutor(config).execute()
    from pathlib import Path
    folder = Path(summary.output_path) / 'content'
    low = folder / 'Effectiveness/Low_Code_Content.jsonl'
    assert low.exists()
    result = json.loads(low.read_text(encoding='utf-8'))['eval_details']['content'][0]
    assert result['applicable'] is not quality_failure
    assert (folder / 'Security/Secret_Credentials.jsonl').exists() is not quality_failure
    assert (folder / 'REVIEW_EXECUTION_ERROR/quality.jsonl').exists() is quality_failure
    assert len(calls) == 3
    assert [model for stage, model in calls if stage == 'classification'] == list(DEFAULT_CLASSIFICATION_MODELS)


def test_pipeline_closes_all_llm_clients(monkeypatch):
    clients = []
    from dingo.model.llm.code_quality import llm_code_quality_pipeline as pipeline

    def configure(evaluator, config):
        client = SimpleNamespace(closed=False)
        client.close = lambda: setattr(client, 'closed', True)
        clients.append(client)
        result = classified(4) if evaluator is LLMCodeClassificationV1 else CodeQualityDetail(metric='quality')
        return SimpleNamespace(client=client, eval=lambda data: result)

    monkeypatch.setattr(pipeline, 'configured_evaluator', configure)
    judge = configured_evaluator(LLMCodeQualityPipeline, {'model': 'offline'})
    assert judge.eval(Data(content='print(1)')).applicable
    assert len(clients) == 3 and all(client.closed for client in clients)
