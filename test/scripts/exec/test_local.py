import pytest

from dingo.config import InputArgs
from dingo.exec import Executor, LocalExecutor
from dingo.io import ResultInfo


class TestLocal:
    def test_merge_result_info(self):
        existing_list = []
        new_item1 = ResultInfo(
            track_id = "1",
            raw_data = {
                "content": "�I am 8 years old. ^I love apple because:",
            },
            eval_status = True,
            eval_details = {
                "content": {
                    "label": ["QUALITY_BAD_EFFECTIVENESS-RuleColonEnd"],
                    "metric": ["RuleColonEnd"],
                    "reason": ["�I am 8 years old. ^I love apple because:"]
                }
            }
        )
        new_item2 = ResultInfo(
            track_id = "1",
            raw_data = {
                "content": "�I am 8 years old. ^I love apple because:",
            },
            eval_status = True,
            eval_details = {
                "content": {
                    "label": ["QUALITY_BAD_EFFECTIVENESS-PromptContentChaos"],
                    "metric": ["PromptContentChaos"],
                    "reason": ["文本中包含不可见字符或乱码（如�和^），可能影响阅读理解。"]
                }
            }
        )

        localexecutor = LocalExecutor({})

        new_existing_list = localexecutor.merge_result_info(existing_list, new_item1)
        assert new_existing_list[0] == new_item1

        existing_list = []
        new_existing_list = localexecutor.merge_result_info(existing_list, new_item1)
        new_existing_list = localexecutor.merge_result_info(new_existing_list, new_item2)
        assert len(new_existing_list) == 1
        assert len(new_existing_list[0].eval_details.get('content').label) == 2
        assert len(new_existing_list[0].eval_details.get('content').metric) == 2
        assert len(new_existing_list[0].eval_details.get('content').reason) == 2
        assert "QUALITY_BAD_EFFECTIVENESS-RuleColonEnd" in new_existing_list[0].eval_details.get('content').label
        assert "QUALITY_BAD_EFFECTIVENESS-PromptContentChaos" in new_existing_list[0].eval_details.get('content').label
        assert "�I am 8 years old. ^I love apple because:" in new_existing_list[0].eval_details.get('content').reason
        assert "文本中包含不可见字符或乱码（如�和^），可能影响阅读理解。" in new_existing_list[0].eval_details.get('content').reason

    def test_all_labels_config(self):
        input_data = {
            "input_path": "test/data/test_local_jsonl.jsonl",
            "dataset": {
                "source": "local",
                "format": "jsonl"
            },
            "executor": {
                "result_save": {
                    "all_labels": True,
                },
                "end_index": 1
            },
            "evaluator": [
                {
                    "fields": {"content": "content"},
                    "evals": [
                        {"name": "RuleColonEnd"},
                        {"name": "RuleSpecialCharacter"},
                        {"name": "RuleDocRepeat"}
                    ]
                }
            ]
        }
        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute()
        print(result)
        assert all([item in result.type_ratio.get('content') for item in ["QUALITY_BAD_EFFECTIVENESS.RuleColonEnd",
                                                      "QUALITY_BAD_EFFECTIVENESS.RuleSpecialCharacter",
                                                      "QUALITY_GOOD"]])

        input_data["executor"]["result_save"]["all_labels"] = False
        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute()
        assert all([item in result.type_ratio.get('content') for item in ["QUALITY_BAD_EFFECTIVENESS.RuleColonEnd",
                                                           "QUALITY_BAD_EFFECTIVENESS.RuleSpecialCharacter"]])
