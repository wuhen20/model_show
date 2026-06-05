from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TimeType(str, Enum):
    DATE = "date"
    HOUR = "hour"
    DATETIME = "datetime"


class FileStatus(str, Enum):
    UPLOADED = "uploaded"
    CONFIGURED = "configured"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class FileUpload(BaseModel):
    file_id: str
    original_name: str
    upload_time: datetime = Field(default_factory=datetime.now)
    headers: List[str] = []
    status: FileStatus = FileStatus.UPLOADED
    file_size: Optional[int] = None


class ProcessConfig(BaseModel):
    file_id: str
    time_column: Optional[str] = None  # 时间列名(对于日期类型)
    time_type: TimeType
    hour_columns: Optional[List[str]] = []  # 小时列名列表(对于小时类型)
    value_columns: Optional[List[str]] = []  # 需要转换为value的列
    common_columns: Optional[List[str]] = []  # 公共字段列


class ProcessedFile(BaseModel):
    file_id: str
    original_name: str
    new_name: str
    processed_time: datetime = Field(default_factory=datetime.now)
    file_size: Optional[int] = None
    status: FileStatus = FileStatus.COMPLETED


class UploadResponse(BaseModel):
    file_id: str
    original_name: str
    message: str


class HeaderResponse(BaseModel):
    file_id: str
    headers: List[str]
    suggested_time_columns: List[str] = []
    suggested_hour_columns: List[str] = []


class PreviewResponse(BaseModel):
    file_id: str
    headers: List[str]
    data: List[Dict[str, str]]
    total_rows: int


class ProcessStatusResponse(BaseModel):
    file_id: str
    status: FileStatus
    message: Optional[str] = None


class ProcessedFileListResponse(BaseModel):
    files: List[ProcessedFile]
    total: int


class BatchProcessRequest(BaseModel):
    file_ids: List[str]


class BatchProcessResult(BaseModel):
    file_id: str
    status: str
    message: str


class BatchProcessResponse(BaseModel):
    total: int
    success_count: int
    failed_count: int
    results: List[BatchProcessResult]


# 样本整合相关数据模型
class MergeJoinType(str, Enum):
    INNER = "inner"
    LEFT = "left"


class MergeTableConfig(BaseModel):
    file_id: str
    file_name: str
    role: str = "secondary"  # "main" 或 "secondary"
    join_columns: List[str] = []
    main_join_columns: List[str] = []  # 主表关联字段
    secondary_join_columns: List[str] = []  # 次表关联字段


class MergeRequest(BaseModel):
    main_table: MergeTableConfig
    secondary_tables: List[MergeTableConfig] = []
    join_type: MergeJoinType = MergeJoinType.LEFT


class MergedFile(BaseModel):
    file_id: str
    main_table_name: str
    merged_name: str
    merge_time: datetime = Field(default_factory=datetime.now)
    file_size: Optional[int] = None
    join_type: str
    table_count: int


class MergedFileListResponse(BaseModel):
    files: List[MergedFile]
    total: int


# 数据预测相关数据模型
class PredictStrategy(str, Enum):
    LINE = "line"  # 整行预测
    COL = "col"    # 逐列预测


class PredictRequest(BaseModel):
    # 允许使用 model_path 字段名（关闭 Pydantic 对 model_ 命名空间的保护告警）
    model_config = {"protected_namespaces": ()}

    file_id: str
    file_name: str
    file_type: str  # "uploaded", "processed" 或 "merged"
    id_column: str = Field(default="series_id", description="时序ID列名")
    timestamp_columns: List[str] = Field(
        default=["data_date"], 
        description="时间列名列表（支持1-2列，多列时会自动拼接为ISO 8601格式）"
    )
    target_fields: List[str] = Field(..., description="需要预测的字段列表")
    related_target_fields: List[str] = Field(default_factory=list, description="关联目标字段列表（排除预测目标字段后的剩余字段）")
    prediction_length: int = Field(..., gt=0, description="预测时长（如24点、96点等）")
    prediction_start_time: Optional[str] = Field(default=None, description="预测起始时间（可选，格式：YYYY-MM-DD HH:mm:ss）")
    quantile_levels: List[float] = Field(default_factory=lambda: [0.1, 0.5, 0.9])
    predict_strategy: PredictStrategy = Field(default=PredictStrategy.LINE, description="预测策略")
    related_data_file: Optional[str] = Field(default=None, description="关联数据文件路径（可选）")
    model_path: Optional[str] = Field(default=None, description="用户在前端选择的模型目录路径（为空则使用默认/环境变量模型）")


class PredictResponse(BaseModel):
    file_id: str
    status: FileStatus
    message: Optional[str] = None
    output_file: Optional[str] = None


class PredictFile(BaseModel):
    file_id: str
    source_file: str
    predict_name: str
    predict_time: Optional[str] = None  # 预测起始时间（字符串格式）
    generate_time: datetime = Field(default_factory=datetime.now)  # 文件生成时间（处理时间）
    file_size: Optional[int] = None
    prediction_length: int
    target_fields: List[str]


class PredictFileListResponse(BaseModel):
    files: List[PredictFile]
    total: int


# 数据分析相关数据模型
class AnalysisFileItem(BaseModel):
    file_id: str
    file_name: str
    original_name: str
    file_type: str  # "uploaded", "processed", "merged", "predicted"
    file_size: Optional[int] = None
    upload_time: Optional[str] = None


class AnalysisFileListResponse(BaseModel):
    uploaded_files: List[AnalysisFileItem] = []
    processed_files: List[AnalysisFileItem] = []
    merged_files: List[AnalysisFileItem] = []
    predicted_files: List[AnalysisFileItem] = []
    total: int


class AnalysisDataRequest(BaseModel):
    file_id: str
    file_name: str
    file_type: str  # "uploaded", "processed", "merged", "predicted"
    time_column: str  # 时间列名
    time_column_2: Optional[str] = None  # 第二时间列名（用于合并日期和时间）
    value_columns: List[str]  # 数值列名列表


class AnalysisDataResponse(BaseModel):
    headers: List[str]
    data: List[Dict[str, Any]]
    total_rows: int


class AnalysisMetricsRequest(BaseModel):
    real_file_id: str
    real_file_name: str
    real_file_type: str
    real_time_column: str
    real_time_column_2: Optional[str] = None
    real_time_range: Optional[List[str]] = None
    real_value_columns: List[str]
    predict_file_id: str
    predict_file_name: str
    predict_file_type: str
    predict_time_column: str
    predict_time_range: Optional[List[str]] = None
    predict_value_columns: List[str]


class MetricItem(BaseModel):
    real_column: str
    predict_column: str
    r2: Optional[float] = None
    mape: Optional[float] = None
    sample_count: int = 0


class AnalysisMetricsResponse(BaseModel):
    metrics: List[MetricItem]
