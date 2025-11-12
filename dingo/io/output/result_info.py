from typing import Dict, List, Any

from pydantic import BaseModel


class ResultInfo(BaseModel):
    track_id: str = ''
    raw_data: Dict = {}
    error_status: bool = False
    error_type: Dict[str, Any] = {}

    def to_dict(self):
        return {
            'track_id': self.track_id,
            'raw_data': self.raw_data,
            'error_status': self.error_status,
            'error_type': self.error_type,
        }

    def to_raw_dict(self):
        dingo_result = {
            'error_status': self.error_status,
            'error_type': self.error_type,
        }
        self.raw_data['dingo_result'] = dingo_result
        return self.raw_data
