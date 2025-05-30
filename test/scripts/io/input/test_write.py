import os
import shutil

import pytest
from dingo.exec import Executor
from dingo.io import InputArgs


class TestWrite:
    def test_write_local_jsonl(self):
        input_args = InputArgs(**{
            "eval_group": "qa_standard_v1",
            "input_path": "test/data/test_local_jsonl.jsonl",
            "save_data": True,
            "save_correct": True,
            "dataset": "local",
            "data_format": "jsonl",
            "column_id": "id",
            "column_content": "content",
        })
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute().to_dict()
        # print(result)
        output_path = result['output_path']
        assert os.path.exists(output_path)
        shutil.rmtree('outputs')
