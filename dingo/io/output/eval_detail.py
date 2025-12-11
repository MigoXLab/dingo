from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QualityLabel:
    """质量标签常量类"""
    QUALITY_GOOD = "QUALITY_GOOD"  # Indicates pass the quality check
    QUALITY_BAD_PREFIX = "QUALITY_BAD_"  # Indicates not pass the quality check


class EvalDetail(BaseModel):
    metric: str
    status: bool = False

    score: Optional[float] = None
    label: Optional[list[str]] = None
    reason: Optional[list] = None
