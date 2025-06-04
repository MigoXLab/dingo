from dingo.exec import Executor
from dingo.io import InputArgs

input_data = {
    'input_path': '../../test/data/test_mtbench101_jsonl.jsonl',  # local filesystem dataset
    'eval_group': 'qa_standard_v1',
    'save_data': True,
    'save_correct': True,
    'dataset': 'local',
    'data_format': 'multi_turn_dialog',
    'column_id': 'id',
    'column_content': 'history',  # the column name of multi-turn dialogues, e.g.: history, dialogues
    'custom_config': {'multi_turn_mode': 'all'},
}
input_args = InputArgs(**input_data)
executor = Executor.exec_map['local'](input_args)
result = executor.execute()
print(result)
