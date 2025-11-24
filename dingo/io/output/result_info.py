from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ResTypeInfo(BaseModel):
    label: list[str] = []
    metric: list[str] = []
    reason: list = []

    def merge(self, other: 'ResTypeInfo') -> None:
        # 合并并去重 label 和 metric
        self.label = list(set(self.label + other.label))
        self.metric = list(set(self.metric + other.metric))
        self.reason.extend(other.reason)

    def copy(self) -> 'ResTypeInfo':
        """创建当前 ResTypeInfo 的深拷贝"""
        return ResTypeInfo(
            label=self.label.copy(),
            metric=self.metric.copy(),
            reason=self.reason.copy()
        )

    def to_dict(self) -> Dict[str, Any]:
        """将 ResTypeInfo 转换为字典"""
        return {
            'label': self.label,
            'metric': self.metric,
            'reason': self.reason
        }


class ResultInfo(BaseModel):
    track_id: str = ''
    raw_data: Dict = {}
    eval_status: bool = False
    eval_details: Dict[str, ResTypeInfo] = {}

    def to_dict(self):
        return {
            'track_id': self.track_id,
            'raw_data': self.raw_data,
            'eval_status': self.eval_status,
            'eval_details': {k: v.to_dict() for k,v in self.eval_details.items()},
        }

    def to_raw_dict(self):
        dingo_result = {
            'eval_status': self.eval_status,
            'eval_details': {k: v.to_dict() for k,v in self.eval_details.items()},
        }
        self.raw_data['dingo_result'] = dingo_result
        return self.raw_data
