import os
from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

if __name__ == '__main__':
    input_data = {
        "input_path": str(Path("test/data/test_audio_snr.jsonl")),
        "dataset": {
            "source": "local",
            "format": "jsonl",
            "field": {
                "content": "content"
            }
        },
        "executor": {
            "rule_list": ["RuleAudioSnrQuality"],
            "result_save": {
                "bad": True,
                "good": True
            }
        }
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
