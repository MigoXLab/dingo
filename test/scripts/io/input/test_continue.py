import json
import os.path

import pytest
from dingo.exec import Executor
from dingo.io import InputArgs


class TestContinue:
    def test_continue_local_jsonl(self):
        input_data = {
            "eval_group": "sft",
            "input_path": "test/data/test_local_jsonl.jsonl",
            "save_data": True,
            "save_correct": True,
            "dataset": "local",
            "data_format": "jsonl",
            "column_id": "id",
            "column_content": "content",
            "start_index": 1
        }

        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute().to_dict()

        output_path = result['output_path']
        p = os.path.join(output_path, 'QUALITY_GOOD', 'Data.jsonl')
        assert os.path.exists(p)

        id = -1
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                j = json.loads(line)
                print(j)
                id = j['data_id']
                break
        assert id == '1'
