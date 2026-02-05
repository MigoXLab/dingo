from pathlib import Path

from dingo.config import InputArgs
from dingo.exec import Executor

# 获取项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

if __name__ == '__main__':
    input_data = {
        "input_path": str(PROJECT_ROOT / "test/data/sciencemetabench/ebook.jsonl"),
        "dataset": {
            "source": "local",
            "format": "jsonl",
        },
        "executor": {
            "result_save": {
                "merge": True,
            }
        },
        "evaluator": [
            {
                "fields": {"metadata": "isbn"},
                "evals": [
                    {"name": "RuleMetadataSimilarity", "config": {"threshold": 0.8}}
                ]
            },
            {
                "fields": {"metadata": "title"},
                "evals": [
                    {"name": "RuleMetadataSimilarity", "config": {"threshold": 0.8}}
                ]
            },
            {
                "fields": {"metadata": "author"},
                "evals": [
                    {"name": "RuleMetadataSimilarity", "config": {"threshold": 0.8}}
                ]
            },
            {
                "fields": {"metadata": "abstract"},
                "evals": [
                    {"name": "RuleMetadataSimilarity", "config": {"threshold": 0.8}}
                ]
            },
            {
                "fields": {"metadata": "category"},
                "evals": [
                    {"name": "RuleMetadataSimilarity", "config": {"threshold": 0.8}}
                ]
            },
            {
                "fields": {"metadata": "pub_time"},
                "evals": [
                    {"name": "RuleMetadataSimilarity", "config": {"threshold": 0.8}}
                ]
            },
            {
                "fields": {"metadata": "publisher"},
                "evals": [
                    {"name": "RuleMetadataSimilarity", "config": {"threshold": 0.8}}
                ]
            }
        ]
    }
    input_args = InputArgs(**input_data)
    executor = Executor.exec_map["local"](input_args)
    result = executor.execute()
    print(result)
