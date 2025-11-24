from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from dingo.io.output.result_info import ResTypeInfo


class ModelRes(BaseModel):
    eval_status: bool = False
    eval_details: ResTypeInfo = ResTypeInfo()

    def __setattr__(self, name, value):
        # 在赋值时拦截 eval_details 字段
        if name == 'eval_details' and isinstance(value, dict):
            value = ResTypeInfo(**value)
        super().__setattr__(name, value)
