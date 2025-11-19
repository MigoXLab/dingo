from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from dingo.io.output.result_info import ResTypeInfo


class ModelRes(BaseModel):
    error_status: bool = False
    error_type: ResTypeInfo = ResTypeInfo()

    # Optional fields for enhanced functionality (e.g., hallucination detection)
    score: Optional[float] = None
    verdict_details: Optional[List[str]] = None

    class Config:
        # Allow extra attributes to be set dynamically
        extra = "allow"

    def __setattr__(self, name, value):
        # 在赋值时拦截 error_type 字段
        if name == 'error_type' and isinstance(value, dict):
            value = ResTypeInfo(**value)
        super().__setattr__(name, value)
