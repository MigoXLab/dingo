from typing import Dict, List

from pydantic import BaseModel


class ResultInfo(BaseModel):
    track_id: str = ''
    raw_data: Dict = {}
    error_status: bool = False
    type_list: List[str] = []
    name_list: List[str] = []
    reason_list: List[str] = []

    def to_dict(self):
        return {
            'track_id': self.track_id,
            'raw_data': self.raw_data,
            'error_status': self.error_status,
            'type_list': self.type_list,
            'name_list': self.name_list,
            'reason_list': self.reason_list,
        }

    def to_raw_dict(self):
        dingo_result = {
            'error_status': self.error_status,
            'type_list': self.type_list,
            'name_list': self.name_list,
            'reason_list': self.reason_list,
        }
        self.raw_data['dingo_result'] = dingo_result
        return self.raw_data
