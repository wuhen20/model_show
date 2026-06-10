from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    server_port: int = 3002
    # 多个允许的源用逗号分隔；保持 "*" 时会自动禁用 credentials（避免浏览器拒绝）。
    cors_origin: str = "http://localhost:5173,http://127.0.0.1:5173"

    max_file_size: int = 10 * 1024 * 1024
    allowed_image_types: str = "image/jpeg,image/png,image/gif,image/webp,image/bmp"
    upload_dir: str = "uploads"

    # 数据与模型权重根目录
    data_dir: str = "data"
    models_pool_dir: str = "models_pool"
    experience_data_dir: str = "experience_data"

    # 数据集预览
    dataset_preview_max: int = 500       # 预览最大行数/图片数
    dataset_preview_page_size: int = 20  # 每页默认条数
    mcp_port_start: int = 8100
    mcp_port_end: int = 8199

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