from dingo.exec import Executor
from dingo.io import InputArgs

input_data = {
    'input_path': 'lmsys/mt_bench_human_judgments',  # huggingface dataset
    'eval_group': 'qa_standard_v1',
    'save_data': True,
    'save_correct': True,
    'end_index': 5,
    'data_format': 'multi_turn_dialog',
    'huggingface_split': 'human',
    'column_id': 'question_id',
    'column_content': 'conversation_a',
    'custom_config': {'multi_turn_mode': 'all'},
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map['local'](input_args)
result = executor.execute()
print(result)
