from typing import Any, Dict

from pydantic import BaseModel


class Data(BaseModel):
    """
    Data, output of converter.
    Flexible data structure that allows any fields to be configured.
    """

    class Config:
        extra = "allow"

    def to_dict(self) -> Dict[str, Any]:
        """
        将 Data 对象转换为字典

        Returns:
            Dict[str, Any]: 包含所有字段的字典
        """
        return self.dict()
