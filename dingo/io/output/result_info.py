from typing import Dict, List

from pydantic import BaseModel

from dingo.io.output.eval_detail import EvalDetail


class ResultInfo(BaseModel):
    dingo_id: str = ''
    raw_data: Dict = {}
    eval_status: bool = False
    eval_details: Dict[str, List[EvalDetail]] = {}

    def to_dict(self):
        """将ResultInfo转换为字典格式

        Returns:
            包含所有字段的字典，其中eval_details被转换为嵌套字典结构
        """
        return {
            'dingo_id': self.dingo_id,
            'raw_data': self.raw_data,
            'eval_status': self.eval_status,
            'eval_details': {
                k: [model_res.model_dump() for model_res in v]
                for k, v in self.eval_details.items()
            },
        }

    def to_raw_dict(self):
        """将ResultInfo合并到raw_data中

        Returns:
            包含原始数据和dingo_result的字典
        """
        dingo_result = {
            'eval_status': self.eval_status,
            'eval_details': {
                k: [model_res.model_dump() for model_res in v]
                for k, v in self.eval_details.items()
            },
        }
        self.raw_data['dingo_result'] = dingo_result
        return self.raw_data
