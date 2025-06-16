import pytest
from dingo.exec import LocalExecutor
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
