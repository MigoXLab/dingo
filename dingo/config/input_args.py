from typing import Dict, List, Optional

from pydantic import BaseModel


class DatasetHFConfigArgs(BaseModel):
    huggingface_split: str = ""
    huggingface_config_name: Optional[str] = None


class DatasetS3ConfigArgs(BaseModel):
    s3_ak: str = ""
    s3_sk: str = ""
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_addressing_style: str = "path"


class DatasetSqlArgs(BaseModel):
    dialect: str = ''
    driver: str = ''
    username: str = ''
    password: str = ''
    host: str = ''
    port: str = ''
    database: str = ''


class DatasetFieldArgs(BaseModel):
    id: str = ''
    prompt: str = ''
    content: str = ''
    context: str = ''
    image: str = ''


class DatasetArgs(BaseModel):
    source: str = 'hugging_face'
    format: str = 'json'
    # field: DatasetFieldArgs = DatasetFieldArgs()
    # fields: List[str] = []
    hf_config: DatasetHFConfigArgs = DatasetHFConfigArgs()
    s3_config: DatasetS3ConfigArgs = DatasetS3ConfigArgs()
    sql_config: DatasetSqlArgs = DatasetSqlArgs()


class ExecutorResultSaveArgs(BaseModel):
    bad: bool = True
    good: bool = False
    all_labels: bool = False
    raw: bool = False


class ExecutorArgs(BaseModel):
    # eval_group: str = ""
    # rule_list: List[str] = []
    # prompt_list: List[str] = []
    start_index: int = 0
    end_index: int = -1
    max_workers: int = 1
    batch_size: int = 1
    multi_turn_mode: Optional[str] = None
    result_save: ExecutorResultSaveArgs = ExecutorResultSaveArgs()


class EvaluatorRuleArgs(BaseModel):
    threshold: Optional[float] = None
    pattern: Optional[str] = None
    key_list: Optional[List[str]] = None
    refer_path: Optional[List[str]] = None
    parameters: Optional[dict] = None


class EvaluatorLLMArgs(BaseModel):
    model: Optional[str] = None
    key: Optional[str] = None
    api_url: Optional[str] = None
    parameters: Optional[dict] = None


class EvalPiplineConfig(BaseModel):
    """Single evaluator configuration item"""
    name: str
    config: Optional[EvaluatorRuleArgs | EvaluatorLLMArgs] = None


class EvalPipline(BaseModel):
    """Evaluation group for specific fields"""
    fields: dict = {}
    evals: List[EvalPiplineConfig] = []


# class EvaluatorArgs(BaseModel):
#     rule_config: Dict[str, EvaluatorRuleArgs] = {}
#     llm_config: Dict[str, EvaluatorLLMArgs] = {}


class InputArgs(BaseModel):
    task_name: str = "dingo"
    input_path: str = "test/data/test_local_json.json"
    output_path: str = "outputs/"

    log_level: str = "WARNING"
    use_browser: bool = False

    dataset: DatasetArgs = DatasetArgs()
    executor: ExecutorArgs = ExecutorArgs()
    evaluator: List[EvalPipline]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
