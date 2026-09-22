from datetime import date, datetime
from decimal import Decimal

import pytest

from dingo.io.output.result_info import ResultInfo


class TestResultInfo:
    def test_to_raw_dict_field_list_none_no_filter(self):
        result_info = ResultInfo(
            dingo_id="dingo-1",
            raw_data={"a": 1, "b": 2},
            eval_status=True,
        )

        output = result_info.to_raw_dict(field_list=None)
        assert "a" in output
        assert "b" in output
        assert "dingo_id" in output
        assert "dingo_result" in output

    def test_to_raw_dict_field_list_empty_filters_all(self):
        result_info = ResultInfo(
            dingo_id="dingo-1",
            raw_data={"a": 1},
            eval_status=False,
        )

        assert result_info.to_raw_dict(field_list=[]) == {}

    def test_to_raw_dict_field_list_only_keep_specified_fields(self):
        result_info = ResultInfo(
            dingo_id="dingo-1",
            raw_data={"a": 1, "b": 2},
            eval_status=True,
        )

        output = result_info.to_raw_dict(field_list=["a", "dingo_result"])
        assert set(output.keys()) == {"a", "dingo_result"}
        assert output["a"] == 1
        assert output["dingo_result"]["eval_status"] is True

    def test_to_raw_dict_field_list_missing_any_field_raises(self):
        result_info = ResultInfo(
            dingo_id="dingo-1",
            raw_data={"a": 1},
            eval_status=False,
        )

        with pytest.raises(ValueError, match="字段不存在"):
            result_info.to_raw_dict(field_list=["a", "missing_field"])

    def test_to_raw_dict_normalizes_container_and_scalar_types(self):
        result_info = ResultInfo(
            dingo_id="dingo-1",
            raw_data={
                "arr": '["x","y"]',
                "obj": '{"k": 1}',
                "nested": {"inner_arr": "[1,2,3]"},
                "amount": Decimal("1.23"),
                "day": date(2026, 6, 1),
                "ts": datetime(2026, 6, 1, 14, 0, 0),
            },
            eval_status=False,
        )

        output = result_info.to_raw_dict()
        assert output["arr"] == ["x", "y"]
        assert output["obj"] == {"k": 1}
        assert output["nested"]["inner_arr"] == [1, 2, 3]
        assert output["amount"] == 1.23
        assert output["day"] == "2026-06-01"
        assert output["ts"] == "2026-06-01T14:00:00"

    def test_to_raw_dict_parses_container_string_with_unescaped_newline(self):
        result_info = ResultInfo(
            dingo_id="dingo-1",
            raw_data={
                "claims": '[{"claim_text":"first line\nsecond line"}]',
            },
            eval_status=False,
        )

        output = result_info.to_raw_dict()
        assert output["claims"] == [
            {"claim_text": "first line\nsecond line"},
        ]

    def test_to_raw_dict_keeps_original_raw_data_unchanged(self):
        original_raw_data = {
            "dingo_id": "user-id",
            "dingo_result": {"foo": "bar"},
            "arr": "[1,2]",
        }
        result_info = ResultInfo(
            dingo_id="new-id",
            raw_data=original_raw_data,
            eval_status=True,
        )

        output = result_info.to_raw_dict()
        assert output["dingo_id"] == "new-id"
        assert output["dingo_id_old_v1"] == "user-id"
        assert output["dingo_result_old_v1"] == {"foo": "bar"}
        assert output["arr"] == [1, 2]

        # to_raw_dict 不应就地修改原始输入字典
        assert original_raw_data["dingo_id"] == "user-id"
        assert original_raw_data["dingo_result"] == {"foo": "bar"}
        assert original_raw_data["arr"] == "[1,2]"
