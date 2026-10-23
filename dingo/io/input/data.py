from typing import Any, Dict, Set

from pydantic import BaseModel, PrivateAttr


class Data(BaseModel):
    """
    Data, output of converter.
    Flexible data structure that allows any fields to be configured.
    """

    # Per-record converter metadata; never included in evaluator field mappings.
    _derived_fields: Set[str] = PrivateAttr(default_factory=set)

    class Config:
        extra = "allow"

    def to_dict(self) -> Dict[str, Any]:
        """
        将 Data 对象转换为字典

        Returns:
            Dict[str, Any]: 包含所有字段的字典
        """
        return self.dict()
