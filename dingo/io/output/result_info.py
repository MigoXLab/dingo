from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ResTypeInfo(BaseModel):
    label: list[str] = []
    metric: list[str] = []
    reason: list = []

    def merge(self, other: 'ResTypeInfo') -> None:
        self.label.extend(other.label)
        self.metric.extend(other.metric)
        self.reason.extend(other.reason)

    def copy(self) -> 'ResTypeInfo':
        """创建当前 ResTypeInfo 的深拷贝"""
        return ResTypeInfo(
            label=self.label.copy(),
            metric=self.metric.copy(),
            reason=self.reason.copy()
        )


class ResultInfo(BaseModel):
    track_id: str = ''
    raw_data: Dict = {}
    error_status: bool = False
    error_type: Dict[str, ResTypeInfo] = {}

    def to_dict(self):
        return {
            'track_id': self.track_id,
            'raw_data': self.raw_data,
            'error_status': self.error_status,
            'error_type': self.error_type,
        }

    def to_raw_dict(self):
        dingo_result = {
            'error_status': self.error_status,
            'error_type': self.error_type,
        }
        self.raw_data['dingo_result'] = dingo_result
        return self.raw_data
