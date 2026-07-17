from pathlib import Path

from pydantic_settings import BaseSettings, DotEnvSettingsSource
from pydantic import field_validator


class _MultiEncodingDotEnvSource(DotEnvSettingsSource):
    """先尝试 UTF-8，失败后回退 GBK/ANSI，兼容 Windows 记事本保存的 .env 文件。"""

    def _read_env_file(self, file_path: Path | None) -> dict[str, str | None]:
        if file_path is None or not file_path.is_file():
            return {}
        # 先 UTF-8
        try:
            return super()._read_env_file(file_path)
        except UnicodeDecodeError:
            pass
        # 回退 GBK
        saved = self.env_file_encoding
        self.env_file_encoding = "gbk"
        try:
            return super()._read_env_file(file_path)
        finally:
            self.env_file_encoding = saved


class Settings(BaseSettings):
    # ---- 通用 / LLM ----
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    server_port: int = 3002
    # 多个允许的源用逗号分隔；保持 "*" 时会自动禁用 credentials（避免浏览器拒绝）。
    cors_origin: str = "*"

    max_file_size: int = 10 * 1024 * 1024
    allowed_image_types: str = "image/jpeg,image/png,image/gif,image/webp,image/bmp"
    upload_dir: str = "uploads"

    # ---- 小模型平台（dev-algomodel）----
    data_dir: str = "data"
    models_pool_dir: str = "models_pool"
    mcp_port_start: int = 8100
    mcp_port_end: int = 8199

    # ---- 样本中心（sxy-sample-center，MySQL/Oracle）----
    db_type: str = "mysql"  # "mysql" 或 "oracle"
    db_host: str = "localhost"
    db_port: int = 13306
    db_user: str = "root"
    db_password: str = "Faker@T169"
    db_name: str = "sample_platform"  # Oracle 模式下为 SID/服务名
    db_schema: str = ""               # Oracle 模式下设置默认 schema（如 PDBADMIN），为空则不切换
    db_mode: str = ""  # Oracle 连接模式：sysdba / sysoper / 空（普通用户不需要填）
    sample_upload_dir: str = "E:\人工智能\现场作业专家系统"
    # 上传临时文件目录，用于批量导入大 ZIP 文件的临时存储；为空则使用系统临时目录（C:\Users\...\AppData\Local\Temp）
    upload_tmp_dir: str = ""

    # ---- 样本集版本管理 ----
    # 大版本变更阈值：样本总量每达到该阈值的下一个整数倍，大版本号 +1，小版本号归 0
    sample_major_version_threshold: int = 100

    # ---- Ceph 对象存储配置（图像采集使用） ----
    ceph_endpoint: str = ""          # 如 http://192.168.1.100:8080
    ceph_access_key: str = ""
    ceph_secret_key: str = ""
    ceph_secure: bool = False        # 是否使用 HTTPS

    # ---- 知识管理 · LightRAG ----
    lightrag_enabled: bool = True
    lightrag_base_url: str = "http://127.0.0.1:9621"

    # ---- 知识管理 · Memgraph ----
    memgraph_enabled: bool = True
    memgraph_uri: str = "bolt://localhost:7687"
    memgraph_username: str = ""
    memgraph_password: str = ""
    memgraph_database: str = "memgraph"

    # 知识库 id → workspace 映射（init_db 种子数据）
    knowledge_bases: list[dict] = [
        {
            "id": "cai_ji_zi_yu",
            "name": "采集自愈知识库",
            "workspace": "cai_ji_zi_yu",
            "description": "电力采集消缺与自愈恢复经验知识",
            "icon": "plug",
            "color": "#00d4ff",
        },
    ]

    # ---- 知识管理 · 元数据库 ----
    metadata_db_path: str = "data/knowledge_metadata.db"

    # ---- 知识管理 · 文件存储 ----
    storage_backend: str = "local"  # "local" 或 "minio"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_prefix: str = "kb-"
    minio_secure: bool = False

    # ---- 知识管理 · Milvus ----
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection_prefix: str = "kb_"

    # ---- 知识管理 · Embedding ----
    embedding_model: str = "text-embedding-v3"
    embedding_dimension: int = 1024

    # ---- 知识管理 · 文件夹知识库 ----
    knowledge_base_dir: str = "知识库文件夹"

    # ---- 知识管理 · 演示模式 ----
    demo_mode: bool = True

    # ===== SM4 加密配置自动解密 =====
    @field_validator("db_user", "db_password", mode="before")
    @classmethod
    def _decrypt_sm4_fields(cls, v: str) -> str:
        """自动解密带 SM4: 前缀的数据库用户名和密码"""
        if not isinstance(v, str):
            return v
        if not v.startswith("SM4:"):
            return v  # 未加密，直接返回
        # 加密格式，解密后返回
        from app.core.crypto import sm4_decrypt
        try:
            return sm4_decrypt(v)
        except Exception as e:
            raise ValueError(f"SM4 解密失败: {e}")
    graph_demo_max_nodes: int = 2000
    fake_mode: bool = False
    fake_data_config_path: str = "data/fake_data_config.json"

    # ---- 知识管理 · 默认切片 ----
    default_chunk_size: int = 500
    default_chunk_overlap: int = 50
    default_parent_chunk_size: int = 1500

    # ---- 对话用 LLM 列表 ----
    models: list[dict] = [
        {
            "id": "qwen-plus",
            "name": "Qwen2-72B",
            "type": "语言模型",
            "description": "通义千问2 72B，高性能语言模型，支持复杂对话与分析",
            "model_id": "qwen-plus",
            "max_tokens": 8192,
            "temperature": 0.7,
            "system_prompt": "你是电力业务智能助手，专注于电力系统分析、台区线损诊断、设备缺陷识别、负荷预测等电力业务场景。请用专业、简洁、结构化的方式回答用户问题。",
        },
        {
            "id": "qwen-vl-plus",
            "name": "Qwen-VL-Plus",
            "type": "视觉模型",
            "description": "通义千问VL Plus，多模态视觉理解与图像分析",
            "model_id": "qwen-vl-plus",
            "max_tokens": 4096,
            "temperature": 0.7,
            "system_prompt": "你是电力业务多模态智能助手，擅长分析电力设备图像、巡检照片、图表等视觉内容。请结合图像信息给出专业的电力业务分析。",
        },
    ]

    @property
    def allowed_image_types_list(self) -> list[str]:
        return [t.strip() for t in self.allowed_image_types.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # .env 中有未声明的变量时忽略而非报错

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings):
        # 用多编码回退的 DotEnv source 替换默认的
        return (
            init_settings,
            env_settings,
            _MultiEncodingDotEnvSource(
                settings_cls,
                env_file=cls.Config.env_file,
                env_file_encoding=cls.Config.env_file_encoding,
            ),
            file_secret_settings,
        )


settings = Settings()
