from collections import defaultdict
from typing import Dict, List

from pydantic import BaseModel, Field


class SummaryModel(BaseModel):
    task_id: str = ''
    task_name: str = ''
    eval_group: str = ''
    input_path: str = ''
    output_path: str = ''
    create_time: str = ''
    finish_time: str = ''
    score: float = 0.0
    num_good: int = 0
    num_bad: int = 0
    total: int = 0
    type_ratio: Dict[str, int] = Field(default_factory=lambda: defaultdict(int))
    name_ratio: Dict[str, int] = Field(default_factory=lambda: defaultdict(int))

    def to_dict(self):
        return {
            'task_id': self.task_id,
            'task_name': self.task_name,
            'eval_group': self.eval_group,
            'input_path': self.input_path,
            'output_path': self.output_path,
            'create_time': self.create_time,
            'finish_time': self.finish_time,
            'score': self.score,
            'num_good': self.num_good,
            'num_bad': self.num_bad,
            'total': self.total,
            'type_ratio': self.type_ratio,
            'name_ratio': self.name_ratio,
        }
