from typing import Any, List, Optional

from pydantic import BaseModel


class ModelRes(BaseModel):
    error_status: bool = False
    type: str | List[str] = "QUALITY_GOOD"
    name: str | List[str] = "Data"
    reason: List[str] = []

    # Optional fields for enhanced functionality (e.g., hallucination detection)
    score: Optional[float] = None
    verdict_details: Optional[List[str]] = None

    class Config:
        # Allow extra attributes to be set dynamically
        extra = "allow"
