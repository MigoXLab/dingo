import ast
import json
from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from dingo.io.output.eval_detail import EvalDetail


class ResultInfo(BaseModel):
    dingo_id: str = ''
    raw_data: Dict = {}
    eval_status: bool = False
    eval_details: Dict[str, List[EvalDetail]] = {}
    token_usage_details: Dict[str, List[EvalDetail]] = Field(
        default_factory=dict,
        exclude=True,
    )
    statistics_details: Dict[str, List[EvalDetail]] = Field(
        default_factory=dict,
        exclude=True,
    )

    @staticmethod
    def _eval_detail_to_dict(model_res: EvalDetail) -> Dict[str, Any]:
        detail = model_res.model_dump()
        if detail.get('usage') is None:
            detail.pop('usage', None)
        if detail.get('statistics') is None:
            detail.pop('statistics', None)
        return detail

    @staticmethod
    def _apply_field_filter(output_data: Dict[str, Any], field_list: Optional[List[str]]) -> Dict[str, Any]:
        if field_list is None:
            return output_data

        if len(field_list) == 0:
            return {}

        missing_fields = [field for field in field_list if field not in output_data]
        if missing_fields:
            sample_keys = list(output_data.keys())[:20]
            raise ValueError(
                f"result_save.field_list 中字段不存在: {missing_fields}。"
                f"可用字段示例: {sample_keys}"
            )

        return {field: output_data[field] for field in field_list}

    @classmethod
    def _parse_container_string(cls, value: str) -> Any:
        text = value.strip()
        if len(text) < 2:
            return value
        if not (
            (text.startswith("[") and text.endswith("]"))
            or (text.startswith("{") and text.endswith("}"))
        ):
            return value
        try:
            parsed = json.loads(text, strict=False)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                return value
        if isinstance(parsed, (dict, list, tuple, set)):
            return cls._normalize_value(parsed)
        return value

    @classmethod
    def _normalize_value(cls, value: Any) -> Any:
        if isinstance(value, (str, int, float, bool)) or value is None:
            if isinstance(value, str):
                return cls._parse_container_string(value)
            return value
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, Mapping):
            return {str(k): cls._normalize_value(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._normalize_value(item) for item in value]
        return value

    def to_dict(self, field_list: Optional[List[str]] = None):
        """将ResultInfo转换为字典格式

        Returns:
            包含所有字段的字典，其中eval_details被转换为嵌套字典结构
        """
        output_data = {
            'dingo_id': self.dingo_id,
            'raw_data': self._normalize_value(self.raw_data),
            'eval_status': self.eval_status,
            'eval_details': {
                k: [self._eval_detail_to_dict(model_res) for model_res in v]
                for k, v in self.eval_details.items()
            },
        }
        return self._apply_field_filter(output_data, field_list)

    def to_raw_dict(self, field_list: Optional[List[str]] = None):
        """将ResultInfo合并到raw_data中

        Returns:
            包含原始数据和dingo_result的字典
        """
        merged_raw_data = self._normalize_value(self.raw_data)

        def move_conflict_field(field_name: str):
            if field_name not in merged_raw_data:
                return

            index = 1
            while True:
                backup_field = f'{field_name}_old_v{index}'
                if backup_field not in merged_raw_data:
                    merged_raw_data[backup_field] = merged_raw_data[field_name]
                    del merged_raw_data[field_name]
                    return
                index += 1

        dingo_result = {
            'eval_status': self.eval_status,
            'eval_details': {
                k: [self._eval_detail_to_dict(model_res) for model_res in v]
                for k, v in self.eval_details.items()
            },
        }
        move_conflict_field('dingo_id')
        move_conflict_field('dingo_result')
        merged_raw_data['dingo_id'] = self.dingo_id
        merged_raw_data['dingo_result'] = dingo_result
        return self._apply_field_filter(merged_raw_data, field_list)
