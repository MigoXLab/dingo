from typing import Any, List, Optional, Dict

from pydantic import BaseModel
from dingo.io.output.result_info import ResTypeInfo


class ModelRes(BaseModel):
    error_status: bool = False
    error_type: Dict[str, ResTypeInfo] = {}

    # Optional fields for enhanced functionality (e.g., hallucination detection)
    score: Optional[float] = None
    verdict_details: Optional[List[str]] = None

    class Config:
        # Allow extra attributes to be set dynamically
        extra = "allow"
