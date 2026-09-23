import copy
import importlib.util
import json
from pathlib import Path

from dingo.config import InputArgs

# Examples are standalone scripts, not an installed Python package.
_spec = importlib.util.spec_from_file_location(
    'code_executor_example', Path(__file__).resolve().parents[4] / 'examples/code_quality/evaluate_code_executor.py')
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)
export_final, latest_records, sample_file = runner.export_final, runner.latest_records, runner.sample_file


def test_direct_input_runs_pipeline_without_review_exports(tmp_path, monkeypatch, capsys):
    import sys
    from types import SimpleNamespace

    source = tmp_path / 'input.jsonl'
    source.write_text('{"content": "print(1)"}\n', encoding='utf-8')
    output = tmp_path / 'output'
    configs = []

    class FakeExecutor:
        def __init__(self, config):
            configs.append(config)

        def execute(self):
            return SimpleNamespace(total=1, output_path=str(output / 'results_test'))

    def unexpected_export(*args, **kwargs):
        raise AssertionError('Direct input must not create review exports')

    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://example.com/v1')
    monkeypatch.setattr(sys, 'argv', ['runner', '--input', str(source), '--output', str(output)])
    monkeypatch.setattr(runner, 'LocalExecutor', FakeExecutor)
    monkeypatch.setattr(runner, 'export_final', unexpected_export)
    runner.main()
    assert len(configs) == 1
    config = configs[0]
    assert config.input_path == str(source.resolve())
    evaluator = config.evaluator[0].evals[0]
    assert evaluator.name == 'LLMCodeQualityPipeline'
    assert evaluator.config.classification_models == ['glm-5.3-flash', 'bailian/deepseek-v4.1-flash']
    assert evaluator.config.extra_headers['X-Session-ID'].startswith('dingo-code-')
    assert json.loads(capsys.readouterr().out)['total'] == 1
    assert not output.exists()


def test_sampling_is_reproducible_and_keeps_source_fields(tmp_path):
    source = tmp_path / 'source.jsonl'
    rows = [{'sample_id': str(i), 'content': f'print({i})', 'doc_url': f's3://bucket/file?bytes={i},1',
             'original': {'keep': True}} for i in range(12)]
    text = ''.join(json.dumps(row) + '\n' for row in rows)
    source.write_text(text, encoding='utf-8')
    first, meta = sample_file(source, 6, 42, 'web', 'zh')
    second, _ = sample_file(source, 6, 42, 'web', 'zh')
    assert first == second
    assert len({row['sample_id'] for row in first}) == 6
    assert meta['population'] == 12
    assert source.read_text(encoding='utf-8') == text
    for row in first:
        assert {k: v for k, v in row.items() if k != '_code_qc'} == rows[int(row['sample_id'])]


def record(sample_id, applicable, label):
    return {'dingo_id': sample_id,
            'raw_data': {'sample_id': sample_id, 'content': 'print(1)',
                         '_code_qc': {'category': 'web', 'language': 'zh'}},
            'eval_status': applicable,
            'eval_details': {'content': [{'metric': 'LLMCodeQualityPipeline', 'applicable': applicable,
                                          'status': applicable, 'score': 0 if applicable else None,
                                          'label': [label], 'reason': ['Test reason'], 'details': {}}]}}


def test_resume_uses_successful_record_and_deduplicates_label_files(tmp_path):
    failed = record('one', False, 'REVIEW_EXECUTION_ERROR.ConvertJsonError')
    good = record('one', True, 'Effectiveness.Syntax_Error')
    for attempt, value in [('01', failed), ('02', good), ('03', failed)]:
        path = tmp_path / 'attempts' / attempt / 'content' / 'result.jsonl'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(value) + '\n', encoding='utf-8')
    latest = latest_records(tmp_path)
    assert latest == {'one': good}


def test_final_writer_separates_errors_from_good_records(tmp_path):
    issue = record('one', True, 'Effectiveness.Syntax_Error')
    error = record('two', False, 'REVIEW_EXECUTION_ERROR.ConvertJsonError')
    config = InputArgs(executor={'result_save': {'bad': True, 'good': True, 'all_labels': True}})
    rows = [issue['raw_data'], error['raw_data']]
    before = copy.deepcopy(rows)
    summary = export_final(tmp_path, rows, {'one': issue, 'two': error}, config)
    assert summary['total'] == 2
    assert summary['automatic_candidates'] == summary['execution_errors'] == 1
    assert summary['good'] == summary['missing'] == 0
    assert rows == before
    output = Path(summary['output_path']) / 'content'
    assert (output / 'Effectiveness' / 'Syntax_Error.jsonl').exists()
    assert (output / 'REVIEW_EXECUTION_ERROR' / 'ConvertJsonError.jsonl').exists()
    assert not (output / 'QUALITY_GOOD.jsonl').exists()


def test_resume_ignores_only_an_interrupted_final_line(tmp_path):
    import pytest

    read_rows = runner.read_rows

    path = tmp_path / 'checkpoint.jsonl'
    path.write_bytes(b'{"valid": 1}\n{"unfinished": "\xe4\xb8')
    with pytest.warns(RuntimeWarning, match='interrupted'):
        assert read_rows(path, allow_incomplete_tail=True) == [{'valid': 1}]
    with pytest.raises(ValueError):
        read_rows(path)
    path.write_text('{invalid}\n{"valid": 1}\n', encoding='utf-8')
    with pytest.raises(ValueError):
        read_rows(path, allow_incomplete_tail=True)


def test_resume_rejects_stale_input_with_same_sample_id(tmp_path):
    import pytest

    save_rows = runner.save_rows

    saved = record('one', True, 'Effectiveness.Syntax_Error')
    path = tmp_path / 'attempts' / '01' / 'content' / 'issue.jsonl'
    save_rows(path, [saved])
    changed = copy.deepcopy(saved['raw_data'])
    changed['content'] = 'different source content'
    with pytest.raises(ValueError, match='sampled input'):
        latest_records(tmp_path, [changed])


def test_resume_rejects_stale_prompt(tmp_path):
    import pytest

    save_rows = runner.save_rows

    saved = record('one', True, 'Effectiveness.Syntax_Error')
    saved['eval_details']['content'][0]['rubric_version'] = 'old-prompt'
    save_rows(tmp_path / 'attempts' / '01' / 'content' / 'issue.jsonl', [saved])
    with pytest.raises(ValueError, match='prompt version'):
        latest_records(tmp_path, [saved['raw_data']], 'new-prompt')


def test_sampling_rejects_invalid_source_record(tmp_path):
    import pytest
    source = tmp_path / 'source.jsonl'
    source.write_text('[]\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Expected an object'):
        sample_file(source, 1, 42, 'web', 'zh')


def test_export_rejects_unsafe_checkpoint_label(tmp_path):
    import pytest
    saved = record('one', True, '../escape')
    config = InputArgs(executor={'result_save': {'bad': True, 'good': True, 'all_labels': True}})
    with pytest.raises(ValueError, match='checkpoint label'):
        export_final(tmp_path, [saved['raw_data']], {'one': saved}, config)
    assert not (tmp_path / 'escape.jsonl').exists()


def test_complete_resume_makes_no_model_calls(tmp_path, monkeypatch):
    import hashlib
    import sys

    rubric = runner.LLMCodeQualityPipeline.rubric_version()
    hashes = {}
    for name in ('nemotron', 'web'):
        saved = record(name, True, 'Effectiveness.Syntax_Error')
        saved['eval_details']['content'][0]['rubric_version'] = rubric
        sample_path = tmp_path / name / 'samples.jsonl'
        runner.save_rows(sample_path, [saved['raw_data']])
        hashes[name] = hashlib.sha256(sample_path.read_bytes()).hexdigest()
        runner.save_rows(tmp_path / name / 'attempts' / '01' / 'content' / 'issue.jsonl', [saved])
    runner.save_json(tmp_path / 'manifest.json', {'rubric_version': rubric, 'model': 'offline',
                                                'api_url': 'https://example.invalid/v1',
                                                'sample_sha256': hashes, 'run_id': 'offline',
                                                'pipeline': {'classification_models': list(runner.DEFAULT_CLASSIFICATION_MODELS)}})
    monkeypatch.setenv('OPENAI_API_KEY', 'unused-offline-value')
    monkeypatch.setenv('OPENAI_BASE_URL', 'https://example.invalid/v1')
    monkeypatch.setenv('OPENAI_MODEL', 'offline')

    def forbidden(self):
        raise AssertionError('Completed resume must not call the Executor')

    monkeypatch.setattr(runner.LocalExecutor, 'execute', forbidden)
    monkeypatch.setattr(sys, 'argv', ['runner', '--nemotron', 'unused', '--zh', 'unused', '--en', 'unused',
                                    '--output', str(tmp_path), '--resume'])
    runner.main()
    for name in ('nemotron', 'web'):
        summary = json.loads((tmp_path / name / 'latest.json').read_text(encoding='utf-8'))
        assert summary['total'] == summary['automatic_candidates'] == 1
        assert summary['execution_errors'] == 0
