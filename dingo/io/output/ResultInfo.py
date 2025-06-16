from typing import Dict, List

from pydantic import BaseModel


class ResultInfo(BaseModel):
    data_id: str = ''
    prompt: str = ''
    content: str = ''
    error_status: bool = False
    type_list: List[str] = []
    name_list: List[str] = []
    reason_list: List[str] = []
    raw_data: Dict = {}

    def to_dict(self):
        return {
            'data_id': self.data_id,
            'prompt': self.prompt,
            'content': self.content,
            'error_status': self.error_status,
            'type_list': self.type_list,
            'name_list': self.name_list,
            'reason_list': self.reason_list,
            'raw_data': self.raw_data
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
