from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

SCRIPT_DIR = Path(__file__).parent

input_data = {
    'input_path': str(SCRIPT_DIR.joinpath('../../test/data/compare/WebMainBench_test_1011_dataset_with_results_clean_llm_webkit_html.jsonl').resolve()),
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
            "fields": {'id': 'id', 'content': 'clean_llm_webkit_html'},
            "evals": [
                {"name": "LLMTableCompare", "config": {"key": "", "api_url": "", 'temperature': 0}}
            ]
        }
    ]
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map['local'](input_args)
result = executor.execute()
print(result)
