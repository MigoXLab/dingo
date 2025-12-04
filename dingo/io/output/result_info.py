from typing import Any, Dict, List

from pydantic import BaseModel, Field

from dingo.model.modelres import EvalDetail


class ResultInfo(BaseModel):
    dingo_id: str = ''
    raw_data: Dict = {}
    eval_status: bool = False
    eval_details: Dict[str, EvalDetail] = {}

    def to_dict(self):
        return {
            'dingo_id': self.dingo_id,
            'raw_data': self.raw_data,
            'eval_status': self.eval_status,
            'eval_details': {k: v.to_dict() for k,v in self.eval_details.items()},
        }

    def to_raw_dict(self):
        dingo_result = {
            'eval_status': self.eval_status,
            'eval_details': {k: v.to_dict() for k,v in self.eval_details.items()},
        }
        self.raw_data['dingo_result'] = dingo_result
        return self.raw_data
