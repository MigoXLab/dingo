from dingo.config import InputArgs
from dingo.exec import Executor

input_data = {
    'input_path': '../../test/data/compare/WebMainBench_test_1011_dataset_with_results_clean_llm_webkit_html.jsonl',
    'dataset': {
        'source': 'local',
        'format': 'jsonl',
        'field': {
            'id': 'id',
            'content': 'clean_llm_webkit_html'
        }
    },
    'executor': {
        'prompt_list': ['PromptTableCompare'],
        'batch_size': 10,
        'max_workers': 10,
        'result_save': {
            'bad': True,
            'good': True,
            'raw': True
        }
    },
    'evaluator': {
        'llm_config': {
            'LLMTableCompare': {
                "key": "",
                "api_url": "",
                'temperature': 0
            }
        }
    }
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map['local'](input_args)
result = executor.execute()
print(result)
