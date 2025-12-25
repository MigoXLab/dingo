import json
import os.path
from pathlib import Path

import pytest

from dingo.config import InputArgs
from dingo.exec import Executor

# 获取项目根目录
ROOT_DIR = Path(__file__).parent.parent.parent.parent.parent


class TestContinue:
    def test_continue_local_jsonl(self):
        input_data = {
            "input_path": str(ROOT_DIR / "test/data/test_local_jsonl.jsonl"),
            "dataset": {
                "source": "local",
                "format": "jsonl",
            },
            "executor": {
                "result_save": {
                    "bad": True,
                    "good": True
                },
                "start_index": 1
            },
            "evaluator": [
                {
                    "fields": {"id": "id", "content": "content"},
                    "evals": [
                        {"name": "RuleColonEnd"}
                    ]
                }
            ]
        }

        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute().to_dict()

        output_path = result['output_path']
        p = os.path.join(output_path, 'id,content', 'QUALITY_GOOD.jsonl')
        assert os.path.exists(p)

        id = -1
        with open(p, 'r', encoding='utf-8') as f:
            for line in f:
                j = json.loads(line)
                print(j)
                id = j['raw_data']['id']
                break
        assert id == 1
