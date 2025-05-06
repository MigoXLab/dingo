import json
import os
import time
import uuid
from typing import Optional

from pydantic import BaseModel, ValidationError


class InputArgs(BaseModel):
    """
    Input arguments, input of project.
    """
    task_name: str = "dingo"
    eval_group: str = ''

    input_path: str = "test/data/test_local_json.json"
    output_path: str = "outputs/"

    save_data: bool = False
    save_correct: bool = False
    save_raw: bool = False

    # Resume settings
    start_index: int = 0
    end_index: int = -1

    # Concurrent settings
    max_workers: int = 1
    batch_size: int = 1

    # Dataset setting
    dataset: str = "hugging_face"  # ['local', 'hugging_face']
    data_format: str = "json"

    # Huggingface specific setting
    huggingface_split: str = ""
    huggingface_config_name: Optional[str] = None

    column_id: str = ''
    column_prompt: str = ''
    column_content: str = ''
    column_image: str = ''

    custom_config: Optional[str | dict] = None

    log_level: str = 'WARNING'
    use_browser: bool = False

    class Config:
        extra = 'forbid'  # Forbid extra parameters

    def __init__(self, **kwargs):
        try:
            super().__init__(**kwargs)
            self.check_args()
        except ValidationError as e:
            raise ValueError(f"Invalid input parameters: {e}")

    def check_args(self):
        # check eval group
        if not self.eval_group:
            if not self.custom_config:
                raise ValueError("eval_group cannot be empty.")
            else:
                tmp_config = {}
                if isinstance(self.custom_config, str):
                    with open(self.custom_config, 'r', encoding='utf-8') as f:
                        tmp_config = json.load(f)
                else:
                    tmp_config = self.custom_config
                if 'rule_list' in tmp_config or 'prompt_list' in tmp_config:
                    self.eval_group = 'custom_group' + '_' + time.strftime('%H%M%S', time.localtime()) + '_' + str(uuid.uuid1())[:8]
                else:
                    raise ValueError("eval_group cannot be empty.")

        # check input path
        if self.dataset != 'hugging_face' and not os.path.exists(self.input_path):
            raise FileNotFoundError(f"Input path '{self.input_path}' does not exist.")

        # check save_data/save_correct
        if not self.save_data and self.save_correct:
            raise ValueError('save_correct is True but save_data is False. Please set save_data to True.')

        # check start index
        if self.start_index < 0:
            raise ValueError("start_index must be non negative.")

        if self.end_index >= 0 and self.end_index < self.start_index:
            raise ValueError("if end_index is non negative, end_index must be greater than start_index")

        # check max workers
        if self.max_workers <= 0:
            raise ValueError("max_workers must be a positive integer.")

        # check batch size
        if self.batch_size <= 0:
            raise ValueError("batch_size must be a positive integer.")

        # check dataset
        if self.dataset not in ['local', 'hugging_face']:
            raise ValueError("dataset must in ['local', 'hugging_face']")

        # check llm config
        if self.custom_config and isinstance(self.custom_config, dict) and self.custom_config.get("prompt_list"):
            if not self.custom_config.get("llm_config"):
                raise ValueError("llm_config in custom_config cannot be empty when using llm evaluation.")

        # check log_level
        if self.log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            raise ValueError("log_level must in ['DEBUG', 'INFO', 'WARNING', 'ERROR']")
