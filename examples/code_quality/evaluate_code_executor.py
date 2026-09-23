"""Evaluate existing JSONL or sample two code corpora with Dingo's LocalExecutor.

--input writes native Executor results only. In corpus sampling mode, each
attempt is checkpointed in native label directories. --resume retries only
missing/failed records. Final label files are written by the same Executor writer.
"""

import argparse
import csv
import hashlib
import json
import os
import random
import re
import subprocess
import uuid
import warnings
from collections import Counter
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec.local import LocalExecutor
from dingo.io.output.result_info import ResultInfo
from dingo.model.llm.code_quality.base_code_quality import DEFAULT_CLASSIFICATION_MODELS, DEFAULT_QUALITY_MODEL, LABELS, CodeQualityDetail
from dingo.model.llm.code_quality.llm_code_quality_pipeline import LLMCodeQualityPipeline


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        temporary.write_text(text, encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def save_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def save_rows(path, rows):
    atomic_write(path, ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in rows))


def read_rows(path, allow_incomplete_tail=False):
    rows = []
    lines = path.read_bytes().splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line.decode('utf-8-sig'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            if allow_incomplete_tail and index == len(lines) - 1 and not line.endswith(b'\n'):
                warnings.warn(f'Ignored interrupted final record in {path.name}', RuntimeWarning)
                break
            raise ValueError(f'Invalid JSONL in {path.name} at line {index + 1}') from None
        if not isinstance(row, dict):
            raise ValueError(f'Expected an object in {path.name} at line {index + 1}')
        rows.append(row)
    return rows


def sample_file(path, count, seed, category, language):
    rows = read_rows(path)
    if count < 0 or count > len(rows):
        raise ValueError(f'{path.name}: requested {count} rows from {len(rows)} available')
    selected = sorted(random.Random(seed).sample(range(len(rows)), count))
    output = []
    for index in selected:
        original = rows[index]
        if not isinstance(original.get('content'), str):
            raise ValueError(f'{path.name}: selected row {index + 1} has no string content')
        if '_code_qc' in original:
            raise ValueError('Reserved sampling metadata field already exists')
        row = dict(original)
        row.setdefault('sample_id', f'{category}-{language}:{index + 1:06d}')
        if not isinstance(row['sample_id'], str) or not row['sample_id'].strip():
            raise ValueError(f'{path.name}: selected row {index + 1} has an invalid sample_id')
        row['_code_qc'] = {'source_file': str(path.resolve()), 'source_record': index + 1,
                           'category': category, 'language': language,
                           'content_sha256': hashlib.sha256(row['content'].encode()).hexdigest()}
        output.append(row)
    return output, {'path': str(path.resolve()), 'population': len(rows), 'sampled': count,
                    'seed': seed, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def detail_of(record):
    details = record['eval_details']['content']
    if len(details) != 1 or details[0]['metric'] != 'LLMCodeQualityPipeline':
        raise ValueError('Checkpoint must contain exactly one code-quality result')
    detail = details[0]
    allowed = {'QUALITY_GOOD'} | {f'{kind}.{name}' for kind, names in LABELS.items() for name in names}
    if not detail.get('label') or any(
        label not in allowed and not re.fullmatch(r'REVIEW_EXECUTION_ERROR\.[A-Za-z0-9_]+', label)
        for label in detail['label']
    ):
        raise ValueError('Invalid checkpoint label')
    return detail


def successful(record):
    return bool(record and detail_of(record)['applicable'])


def latest_records(group, samples=None, rubric=None):
    expected = {row['sample_id']: row for row in samples} if samples is not None else None
    latest = {}
    for attempt in sorted((group / 'attempts').glob('*')):
        for path in sorted((attempt / 'content').rglob('*.jsonl')):
            for record in read_rows(path, allow_incomplete_tail=True):
                sample_id = record['raw_data']['sample_id']
                if expected is not None:
                    if sample_id not in expected or record['raw_data'] != expected[sample_id]:
                        raise ValueError('Checkpoint does not match the sampled input')
                detail = detail_of(record)
                if detail['metric'] != 'LLMCodeQualityPipeline' or type(detail['applicable']) is not bool:
                    raise ValueError('Invalid checkpoint evaluator/status')
                if rubric and detail['applicable'] and detail.get('rubric_version') != rubric:
                    raise ValueError('Checkpoint prompt version differs from the current run')
                # A failed later retry must not replace an already successful evaluation.
                if not successful(latest.get(sample_id)):
                    latest[sample_id] = record
    return latest


def make_config(input_path, output_path, model, session_id, workers, max_tokens, reasoning_effort=None, pipeline_config=None):
    extra = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
    return InputArgs(task_name='code_quality_executor', input_path=str(input_path.resolve()),
                     output_path=str(output_path.resolve()),
                     dataset={'source': 'local', 'format': 'jsonl'},
                     executor={'max_workers': workers, 'batch_size': workers * 2,
                               'result_save': {'bad': True, 'good': True, 'all_labels': True}},
                     evaluator=[{'fields': {'content': 'content'}, 'evals': [{
                         'name': 'LLMCodeQualityPipeline', 'config': {
                             'key': os.environ['OPENAI_API_KEY'], 'api_url': os.environ['OPENAI_BASE_URL'],
                             'model': model, 'request_timeout': 180, 'max_retries': 0,
                             'max_tokens': max_tokens, 'extra_headers': {'X-Session-ID': session_id}, **extra, **(pipeline_config or {}),
                         }}]}])


def export_final(group, rows, records, config):
    # Build a new version so previous results are never erased during resume.
    final = group / ('results_' + uuid.uuid4().hex[:8])
    final.mkdir()
    writer = LocalExecutor(config)
    counts = Counter()
    labels = Counter()
    review = []
    for row in rows:
        record = records.get(row['sample_id'])
        if not record:
            counts['missing'] += 1
            continue
        detail = detail_of(record)
        outcome = 'execution_error' if not detail['applicable'] else ('candidate' if detail['status'] else 'good')
        counts[outcome] += 1
        info = ResultInfo(dingo_id=record['dingo_id'], raw_data=record['raw_data'],
                          eval_status=record['eval_status'],
                          eval_details={'content': [CodeQualityDetail.model_validate(detail)]})
        writer.write_single_data(str(final), config, info)
        for label in set(detail.get('label') or []):
            labels[label] += 1
        for finding in detail.get('details', {}).get('findings', []):
            label = finding['type'] + '.' + finding['name']
            review.append({'review_id': hashlib.sha256((row['sample_id'] + '|' + label).encode()).hexdigest()[:24],
                           'sample_id': row['sample_id'], 'source_category': row['_code_qc']['category'],
                           'language': row['_code_qc']['language'], 'doc_url': row.get('doc_url', ''),
                           'label': label, 'reason': finding['reason'], 'line_start': finding['line_start'],
                           'line_end': finding['line_end'], 'human_decision': '', 'human_reason': ''})
    summary = {'total': len(rows), 'good': counts['good'], 'automatic_candidates': counts['candidate'],
               'execution_errors': counts['execution_error'], 'missing': counts['missing'],
               'label_counts': dict(sorted(labels.items())), 'human_confirmed': False,
               'output_path': str(final.resolve())}
    save_json(final / 'summary.json', summary)
    save_rows(final / 'review_queue.jsonl', review)
    with (final / 'human_review_queue.csv').open('w', encoding='utf-8-sig', newline='') as target:
        columns = ['review_id', 'sample_id', 'source_category', 'language', 'doc_url', 'label', 'reason',
                   'line_start', 'line_end', 'human_decision', 'human_reason']
        csv_writer = csv.DictWriter(target, fieldnames=columns)
        csv_writer.writeheader()
        csv_writer.writerows(review)
    save_json(group / 'latest.json', summary)
    return summary


def repository_state():
    try:
        repo = Path(__file__).resolve().parents[2]

        def git(*args):
            return subprocess.check_output(['git', *args], cwd=repo, text=True, stderr=subprocess.DEVNULL).strip()
        return {'branch': git('branch', '--show-current'), 'commit': git('rev-parse', 'HEAD'),
                'uncommitted_code': bool(git('status', '--porcelain'))}
    except (OSError, subprocess.CalledProcessError):
        return {'branch': None, 'commit': None, 'uncommitted_code': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='Evaluate an existing content JSONL directly; native Executor output only')
    parser.add_argument('--nemotron', type=Path)
    parser.add_argument('--zh', type=Path)
    parser.add_argument('--en', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=100, help='Count per corpus; web is split equally by language')
    parser.add_argument('--seed', type=int, default=20260911)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--max-tokens', type=int, default=8192)
    parser.add_argument('--reasoning-effort', choices=['low', 'medium', 'high', 'max'])
    parser.add_argument('--retry-rounds', type=int, default=2)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--classification-models', nargs=2, default=list(DEFAULT_CLASSIFICATION_MODELS))
    args = parser.parse_args()
    if args.workers <= 0 or args.retry_rounds < 0 or args.max_tokens <= 0:
        parser.error('workers and max-tokens must be positive; retry-rounds nonnegative')
    if args.input:
        if args.resume or any((args.nemotron, args.zh, args.en)):
            parser.error('--input cannot be combined with --resume or corpus sampling options')
        if not args.input.is_file():
            parser.error('--input must point to an existing JSONL file')
    elif not all((args.nemotron, args.zh, args.en)) or args.count <= 0 or args.count % 2:
        parser.error('Supply --input, or --nemotron/--zh/--en with a positive even --count')
    model = os.environ.get('OPENAI_MODEL', DEFAULT_QUALITY_MODEL)
    if not os.environ.get('OPENAI_API_KEY') or not os.environ.get('OPENAI_BASE_URL'):
        parser.error('Set OPENAI_API_KEY and OPENAI_BASE_URL')
    # Thread-only mode is supported by LocalExecutor and avoids unrelated Windows process imports.
    os.environ['LOCAL_DEPLOYMENT_MODE'] = 'true'
    if len(set(args.classification_models)) != 2:
        parser.error('Supply two distinct classification models')
    pipeline_config = {'classification_models': args.classification_models}
    if args.input:
        config = make_config(args.input, args.output, model, 'dingo-code-' + uuid.uuid4().hex,
                             args.workers, args.max_tokens, args.reasoning_effort, pipeline_config)
        summary = LocalExecutor(config).execute()
        print(json.dumps({'total': summary.total, 'output_path': summary.output_path}, ensure_ascii=False), flush=True)
        return
    pipeline_identity = dict(pipeline_config)
    rubric = LLMCodeQualityPipeline.rubric_version()
    if args.resume:
        manifest = json.loads((args.output / 'manifest.json').read_text(encoding='utf-8'))
        if (manifest.get('pipeline') != pipeline_identity or manifest['rubric_version'] != rubric or manifest['model'] != model
                or manifest['api_url'].rstrip('/') != os.environ['OPENAI_BASE_URL'].rstrip('/')):
            parser.error('Resume must use the same pipeline, prompts, models, API URL')
        for name in ('nemotron', 'web'):
            path = args.output / name / 'samples.jsonl'
            if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['sample_sha256'][name]:
                parser.error('Sample file changed since original run')
    else:
        if args.output.exists():
            parser.error('Use a new output directory or --resume')
        nemotron, n_meta = sample_file(args.nemotron, args.count, args.seed, 'nemotron', 'mixed')
        zh, z_meta = sample_file(args.zh, args.count // 2, args.seed + 1, 'web', 'zh')
        en, e_meta = sample_file(args.en, args.count // 2, args.seed + 2, 'web', 'en')
        for name, rows in [('nemotron', nemotron), ('web', zh + en)]:
            if len({r['sample_id'] for r in rows}) != len(rows) or len({r.get('doc_url') or (r['_code_qc']['source_file'], r['_code_qc']['source_record']) for r in rows}) != len(rows):
                raise ValueError('Selected sample IDs/source locations are not unique')
            save_rows(args.output / name / 'samples.jsonl', rows)
        manifest = {'run_id': 'dingo-code-' + uuid.uuid4().hex, 'model': model,
                    'api_url': os.environ['OPENAI_BASE_URL'], 'rubric_version': rubric,
                    **repository_state(), 'sources': [n_meta, z_meta, e_meta],
                    'sample_sha256': {name: hashlib.sha256((args.output / name / 'samples.jsonl').read_bytes()).hexdigest()
                                      for name in ('nemotron', 'web')},
                    'checks': 'Eleven rules, quality LLM, dual classification and LLM safety', 'pipeline': pipeline_identity,
                    'sampling': 'Seeded simple random samples; web stratified 50/50 by language',
                    'truncation': False}
        save_json(args.output / 'manifest.json', manifest)
        (args.output / 'prompt.txt').write_text(LLMCodeQualityPipeline.prompt, encoding='utf-8')
        print(json.dumps({'sampled': {'nemotron': len(nemotron), 'web_zh': len(zh), 'web_en': len(en)},
                          'max_content_chars': {name: max(len(r['content']) for r in rows)
                                                for name, rows in [('nemotron', nemotron), ('web', zh + en)]}}, ensure_ascii=False), flush=True)
    summaries = {}
    for name in ('nemotron', 'web'):
        group = args.output / name
        rows = read_rows(group / 'samples.jsonl')
        for attempt in range(args.retry_rounds + 1):
            records = latest_records(group, rows, rubric)
            pending = [row for row in rows if not successful(records.get(row['sample_id']))]
            session_id = manifest['run_id'] + '-' + name + '-' + uuid.uuid4().hex[:8]
            pending_path = group / ('pending_' + session_id[-8:] + '.jsonl')
            config = make_config(pending_path, group / 'attempts', model, session_id, args.workers, args.max_tokens, args.reasoning_effort, pipeline_config)
            if not pending:
                break
            save_rows(pending_path, pending)
            save_json(group / ('config_' + session_id[-8:] + '.json'), config.to_dict())
            print(json.dumps({'dataset': name, 'attempt': attempt + 1, 'pending': len(pending), 'session_id': session_id}), flush=True)
            summary = LocalExecutor(config).execute()
            print(json.dumps({'dataset': name, 'attempt_output': summary.output_path, 'total': summary.total}), flush=True)
        records = latest_records(group, rows, rubric)
        summaries[name] = export_final(group, rows, records, config)
        save_json(args.output / 'run_summary.json', summaries)
        print(json.dumps({'dataset': name, **summaries[name]}, ensure_ascii=False), flush=True)
    if any(s['execution_errors'] or s['missing'] for s in summaries.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
