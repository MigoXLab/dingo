import pytest

from dingo.config import InputArgs
from dingo.exec import Executor, LocalExecutor
from dingo.io import ResultInfo


class TestLocal:
    def test_merge_result_info(self):
        existing_list = []
        new_item1 = ResultInfo(
            data_id = "1",
            prompt = "",
            content = "�I am 8 years old. ^I love apple because:",
            error_status = True,
            type_list = ["QUALITY_BAD_EFFECTIVENESS"],
            name_list = ["QUALITY_BAD_EFFECTIVENESS-RuleColonEnd"],
            reason_list = ["�I am 8 years old. ^I love apple because:"],
            raw_data = {}
        )
        new_item2 = ResultInfo(
            data_id = "1",
            prompt = "",
            content = "�I am 8 years old. ^I love apple because:",
            error_status = True,
            type_list = ["QUALITY_BAD_EFFECTIVENESS"],
            name_list = ["QUALITY_BAD_EFFECTIVENESS-PromptContentChaos"],
            reason_list = ["文本中包含不可见字符或乱码（如�和^），可能影响阅读理解。"],
            raw_data = {}
        )

        localexecutor = LocalExecutor({})

        new_existing_list = localexecutor.merge_result_info(existing_list, new_item1)
        assert new_existing_list[0] == new_item1

        new_existing_list = localexecutor.merge_result_info(existing_list, new_item1)
        new_existing_list = localexecutor.merge_result_info(new_existing_list, new_item2)
        assert len(new_existing_list) == 1
        assert len(new_existing_list[0].type_list) == 1
        assert len(new_existing_list[0].name_list) == 2
        assert len(new_existing_list[0].reason_list) == 2
        assert "QUALITY_BAD_EFFECTIVENESS" in new_existing_list[0].type_list
        assert "QUALITY_BAD_EFFECTIVENESS-RuleColonEnd" in new_existing_list[0].name_list
        assert "QUALITY_BAD_EFFECTIVENESS-PromptContentChaos" in new_existing_list[0].name_list
        assert "�I am 8 years old. ^I love apple because:" in new_existing_list[0].reason_list
        assert "文本中包含不可见字符或乱码（如�和^），可能影响阅读理解。" in new_existing_list[0].reason_list

    def test_all_labels_config(self):
        input_data = {
            "input_path": "test/data//test_local_jsonl.jsonl",
            "dataset": {
                "source": "local",
                "format": "jsonl",
                "field": {
                    "content": "content"
                }
            },
            "executor": {
                "rule_list": ["RuleColonEnd", "RuleSpecialCharacter", "RuleDocRepeat"],
                "result_save": {
                    "all_labels": True,
                },
                "end_index": 1
            }
        }
        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute()
        assert all([item in result.name_ratio for item in ["QUALITY_BAD_EFFECTIVENESS-RuleColonEnd",
                                                      "QUALITY_BAD_EFFECTIVENESS-RuleSpecialCharacter",
                                                      "QUALITY_GOOD-Data"]])

        input_data["executor"]["result_save"]["all_labels"] = False
        input_args = InputArgs(**input_data)
        executor = Executor.exec_map["local"](input_args)
        result = executor.execute()
        assert all([item in result.name_ratio for item in ["QUALITY_BAD_EFFECTIVENESS-RuleColonEnd",
                                                           "QUALITY_BAD_EFFECTIVENESS-RuleSpecialCharacter"]])
