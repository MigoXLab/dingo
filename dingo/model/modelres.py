from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QualityLabel:
    """质量标签常量类"""
    QUALITY_GOOD = "QUALITY_GOOD"  # Indicates pass the quality check
    QUALITY_BAD_PREFIX = "QUALITY_BAD_"  # Indicates not pass the quality check


class EvalDetail(BaseModel):
    label: list[str] = []
    metric: list[str] = []
    reason: list = []

    def merge(self, other: 'EvalDetail') -> None:
        # 合并并去重 label 和 metric
        self.label = list(set(self.label + other.label))
        self.metric = list(set(self.metric + other.metric))
        self.reason.extend(other.reason)

    def copy(self) -> 'EvalDetail':
        """创建当前 EvalDetail 的深拷贝"""
        return EvalDetail(
            label=self.label.copy(),
            metric=self.metric.copy(),
            reason=self.reason.copy()
        )

    def to_dict(self) -> Dict[str, Any]:
        """将 EvalDetail 转换为字典"""
        return {
            'label': self.label,
            'metric': self.metric,
            'reason': self.reason
        }


class ModelRes(BaseModel):
    eval_status: bool = False
    eval_details: EvalDetail = EvalDetail()
    score: Optional[float] = None

    def __setattr__(self, name, value):
        # 在赋值时拦截 eval_details 字段
        if name == 'eval_details' and isinstance(value, dict):
            value = EvalDetail(**value)
        super().__setattr__(name, value)
