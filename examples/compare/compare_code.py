from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

input_data = {
    'input_path': str(PROJECT_ROOT / 'test/data/compare/WebMainBench_test_1011_dataset_with_results_clean.jsonl'),
    'dataset': {
        'source': 'local',
        'format': 'jsonl',
    },
    'executor': {
        'batch_size': 10,
        'max_workers': 10,
        'result_save': {
            'bad': True,
            'good': True,
            'raw': True
        }
    },
    "evaluator": [
        {
            "fields": {'id': 'id', 'content': 'clean_html'},
            "evals": [
                {"name": "LLMCodeCompare", "config": {"key": "", "api_url": "", 'temperature': 0}}
            ]
        }
    ]
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map['local'](input_args)
result = executor.execute()
print(result)
