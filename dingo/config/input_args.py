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


class EmbeddingConfigArgs(BaseModel):
    """Embedding 模型独立配置"""
    model: Optional[str] = None
    key: Optional[str] = None
    api_url: Optional[str] = None


class EvaluatorLLMArgs(BaseModel):
    model: Optional[str] = None
    key: Optional[str] = None
    api_url: Optional[str] = None
    parameters: Optional[dict] = None
    embedding_config: Optional[EmbeddingConfigArgs] = None


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
