from typing import Any, Dict, List, Optional

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
    connect_args: str = ''  # 连接参数，如 ?charset=utf8mb4


class DatasetExcelArgs(BaseModel):
    sheet_name: str | int = 0  # 默认读取第一个工作表
    has_header: bool = True  # 第一行是否为列名，False 则使用列序号作为列名


class DatasetCsvArgs(BaseModel):
    has_header: bool = True  # 第一行是否为列名，False 则使用 column_x 作为列名
    encoding: str = 'utf-8'  # 文件编码，默认 utf-8，支持 gbk, gb2312, latin1 等
    dialect: str = 'excel'  # CSV 格式方言：excel(默认), excel-tab, unix 等
    delimiter: str | None = None  # 分隔符，None 表示根据 dialect 自动选择
    quotechar: str = '"'  # 引号字符，默认双引号


class DatasetParquetArgs(BaseModel):
    batch_size: int = 10000  # 每次读取的行数，用于流式读取大文件
    columns: Optional[List[str]] = None  # 指定读取的列，None 表示读取所有列


class DatasetFieldArgs(BaseModel):
    id: str = ''
    prompt: str = ''
    content: str = ''
    context: str = ''
    image: str = ''


class DatasetMinerUArgs(BaseModel):
    include_types: Optional[List[str]] = None  # 只保留指定的 block 类型，None 表示全部保留


class DatasetArgs(BaseModel):
    source: str = 'hugging_face'
    format: str = 'json'
    # field: DatasetFieldArgs = DatasetFieldArgs()
    # fields: List[str] = []
    hf_config: DatasetHFConfigArgs = DatasetHFConfigArgs()
    s3_config: DatasetS3ConfigArgs = DatasetS3ConfigArgs()
    sql_config: DatasetSqlArgs = DatasetSqlArgs()
    excel_config: DatasetExcelArgs = DatasetExcelArgs()
    csv_config: DatasetCsvArgs = DatasetCsvArgs()
    parquet_config: DatasetParquetArgs = DatasetParquetArgs()
    mineru_config: DatasetMinerUArgs = DatasetMinerUArgs()


class ExecutorResultSaveArgs(BaseModel):
    bad: bool = True
    good: bool = False
    all_labels: bool = False
    raw: bool = False
    merge: bool = False  # 如果为True，所有数据写入同一个jsonl文件，不分文件夹
    limit: Optional[int] = None  # 每个输出文件最多写入条数，None表示不限制
    field_list: Optional[List[str]] = None  # 仅保存指定字段；若均不存在则报错
    full_field_sample_count: int = 0  # 保留完整字段样本条数，0表示关闭


class OpenEvalArgs(BaseModel):
    """LLM-as-Judge open eval config (Exa-style pointwise grading)."""
    enabled: bool = False
    model: Optional[str] = None
    key: Optional[str] = None
    api_url: Optional[str] = None
    top_k: int = 5
    aggregate: str = "mean"
    max_workers: int = 4
    prompt_mode: str = "standard"
    expected_criteria: Optional[str] = None


class RetrievalArgs(BaseModel):
    backend: str = "agentic"
    api_url: str = ""
    api_token: Optional[str] = None
    limit: int = 100
    retrieval_mode: str = "hybrid"
    sub_queries: Optional[int] = None
    search_type: str = "paper"
    sort_by: Optional[str] = None
    freshness_boost: Optional[str] = None
    filters: Optional[List[Dict[str, Any]] | Dict[str, Any]] = None
    max_queries: Optional[int] = None
    title_fuzzy_enabled: bool = False
    title_fuzzy_threshold: float = 0.95
    title_fuzzy_margin: float = 0.01
    title_fuzzy_min_len: int = 20
    title_fuzzy_max_candidates: int = 300
    timeout: float = 120.0
    rate_limit: Optional[float] = None
    max_retries: int = 3
    max_workers: int = 1
    open_eval: Optional[OpenEvalArgs] = None
    input_queries: Optional[str] = None


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
    retrieval: Optional[RetrievalArgs] = None


class EvaluatorRuleArgs(BaseModel):
    model_config = {"extra": "allow"}

    threshold: Optional[float] = None
    pattern: Optional[str] = None
    key_list: Optional[List[str]] = None
    refer_path: Optional[List[str]] = None


class EmbeddingConfigArgs(BaseModel):
    """Embedding 模型独立配置"""
    model: Optional[str] = None
    key: Optional[str] = None
    api_url: Optional[str] = None


class CustomLLMMetricArgs(BaseModel):
    metric: str
    description: Optional[str] = ""
    criteria: List[str]
    input_fields: List[str]


class EvaluatorLLMArgs(BaseModel):
    model_config = {"extra": "allow"}

    model: Optional[str] = None
    key: Optional[str] = None
    api_url: Optional[str] = None
    embedding_config: Optional[EmbeddingConfigArgs] = None
    custom_metric: Optional[CustomLLMMetricArgs] = None


class EvalPiplineConfig(BaseModel):
    """Single evaluator configuration item."""
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

    dataset: DatasetArgs = DatasetArgs()
    executor: ExecutorArgs = ExecutorArgs()
    evaluator: List[EvalPipline] = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
