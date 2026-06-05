from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    server_port: int = 3002
    cors_origin: str = "*"

    max_file_size: int = 10 * 1024 * 1024
    allowed_image_types: str = "image/jpeg,image/png,image/gif,image/webp,image/bmp"
    upload_dir: str = "uploads"

    # ---- LightRAG ----
    lightrag_enabled: bool = True
    lightrag_base_url: str = "http://127.0.0.1:9621"

    # ---- Memgraph ----
    memgraph_enabled: bool = True
    memgraph_uri: str = "bolt://localhost:7687"
    memgraph_username: str = ""
    memgraph_password: str = ""
    memgraph_database: str = "memgraph"

    # Knowledge bases: id → workspace mapping (seed data for init_db)
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

    # ---- Metadata DB ----
    metadata_db_path: str = "data/knowledge_metadata.db"

    # ---- File Storage ----
    storage_backend: str = "local"  # "local" or "minio"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_prefix: str = "kb-"
    minio_secure: bool = False

    # ---- Milvus ----
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    milvus_collection_prefix: str = "kb_"

    # ---- Embedding ----
    embedding_model: str = "text-embedding-v3"
    embedding_dimension: int = 1024

    # ---- Folder-based Knowledge Base ----
    knowledge_base_dir: str = "知识库文件夹"

    # ---- Demo mode ----
    # When True, the graph API returns full stats (real DB counts) but
    # limits the actual nodes/links to `graph_demo_max_nodes` so the
    # frontend stays responsive.  When False, all nodes are returned.
    demo_mode: bool = True
    graph_demo_max_nodes: int = 2000

    # ---- Fake mode for demo ----
    # When True, non-graph API endpoints return data from the config file
    # instead of real backend data. Purpose: customizable demo data.
    fake_mode: bool = False
    fake_data_config_path: str = "data/fake_data_config.json"

    # ---- Default chunking settings ----
    default_chunk_size: int = 500
    default_chunk_overlap: int = 50
    default_parent_chunk_size: int = 1500

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


settings = Settings()
