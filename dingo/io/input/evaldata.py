from pydantic import BaseModel
from dingo.config.input_args import EvalConfigItem


class EvalData(BaseModel):
    track_id: str
    raw_data: dict
    eval_fields: list
    group_type: str
    group_list: list[EvalConfigItem]
