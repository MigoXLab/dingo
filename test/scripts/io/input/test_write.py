import os
import shutil

import pytest

from dingo.config import InputArgs
from dingo.exec import Executor


class TestWrite:
    def test_write_local_jsonl(self):
        input_data = {
            "input_path": "test/data/test_local_jsonl.jsonl",
            "dataset": {
                "source": "local",
                "format": "jsonl"
            },
            "executor": {
                "result_save": {
                    "bad": True,
                    "good": True
                }
            },
            "evaluator": [
                {
                    "fields": {"id": "id", "content": "content"},
                    "evals": [
                        {"name": "RuleContentNull"},
                        {"name": "RuleAbnormalChar"}
                    ]
                }
            ]
        }
        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute()
        # print(result)
        output_path = result.output_path
        assert os.path.exists(output_path)
        shutil.rmtree('outputs')
