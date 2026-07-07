"""20 个小模型注册表。

按 6 大场景组织，是平台运行时的"模型清单事实源"。
启动时由 sync_registry() 同步至 model_metadata 表。
"""
from __future__ import annotations

from typing import TypedDict, Optional


class ModelEntry(TypedDict, total=False):
    name: str
    scene: str  # ZJ / XC / FH / TQ / YD / ZC
    io_type: str  # timeseries / image / tabular / multimodal
    backend_type: str  # local / mcp / http
    description: str
    input_spec: list
    output_spec: list
    sub_scenes: Optional[list]
    weight_path: Optional[str]
    loader: Optional[str]  # joblib / torch_cpu / sklearn
    status: str  # running / planned / offline / error


SCENE_CATALOG: list[dict] = [
    {"code": "ZJ", "name": "采集自愈", "description": "采集系统自愈与运维智能化", "icon": "wrench"},
    {"code": "XC", "name": "现场作业", "description": "现场作业行为识别与稽核", "icon": "camera"},
    {"code": "FH", "name": "负荷资源管理", "description": "负荷资源评估、申报与调控", "icon": "battery"},
    {"code": "TQ", "name": "台区四精管理", "description": "台区精准运维与用户分析", "icon": "grid"},
    {"code": "YD", "name": "用电异常监控", "description": "用电异常识别与欺诈研判", "icon": "alert"},
    {"code": "ZC", "name": "资产管理", "description": "电力资产数字化识别", "icon": "tag"},
]


MODEL_REGISTRY: dict[str, ModelEntry] = {
    # ========== 采集自愈场景（5） ==========
    "ZJ-01": {
        "name": "终端健康评价模型",
        "scene": "ZJ",
        "io_type": "timeseries",
        "backend_type": "local",
        "description": "基于终端时序运行指标评估终端健康度，输出健康评分与异常原因",
        "input_spec": [{"field": "data", "type": "csv|json", "required": True}],
        "output_spec": [
            {"field": "prediction", "description": "0=健康 1=异常"},
            {"field": "score", "description": "异常概率"},
        ],
        "weight_path": "models_pool/ZJ-01/v1/terminal_xgb_model.joblib",
        "loader": "joblib",
        "status": "planned",
    },
    "ZJ-02": {
        "name": "电表健康评价模型",
        "scene": "ZJ",
        "io_type": "timeseries",
        "backend_type": "local",
        "description": "CNN+LSTM 多标签模型评估电表健康度，输出多类型异常预测",
        "input_spec": [{"field": "data", "type": "csv|json", "required": True}],
        "output_spec": [{"field": "labels", "description": "多标签预测结果"}],
        "weight_path": "models_pool/ZJ-02/v1/meter_cnn_lstm_model.pt",
        "loader": "torch_cpu",
        "status": "planned",
    },
    "ZJ-03": {
        "name": "主站异常研判模型",
        "scene": "ZJ",
        "io_type": "tabular",
        "backend_type": "local",
        "description": "基于主站日志与指标识别异常事件并定位类型",
        "status": "planned",
    },
    "ZJ-04": {
        "name": "采集策略智能调度模型",
        "scene": "ZJ",
        "io_type": "tabular",
        "backend_type": "local",
        "description": "根据任务负载与历史成功率推荐采集策略与调度计划",
        "status": "planned",
    },
    "ZJ-05": {
        "name": "采集链路故障诊断模型",
        "scene": "ZJ",
        "io_type": "multimodal",
        "backend_type": "local",
        "description": "结合拓扑与时序数据定位采集链路故障节点（终端、电表节点）",
        "status": "planned",
    },
    # ========== 现场作业场景（2） ==========
    "XC-01": {
        "name": "拆除旧表作业识别",
        "scene": "XC",
        "io_type": "image",
        "backend_type": "local",
        "description": "基于YOLO目标检测+BoT-SORT跟踪，对电表拆除过程进行自动化识别与状态跟踪。检测电表、端子、螺丝刀、端子盖、手套五类目标，通过多阶段状态机判断端子槽拆除进度和电表最终拆除状态。",
        "weight_path": "models_pool/XC/meter_remove/best.pt",
        "loader": "yolo",
        "input_spec": [{"field": "video", "type": "mp4|avi", "required": True}],
        "output_spec": [
            {"field": "report", "description": "拆表作业识别报告（含拆线时间、验证时间）"},
            {"field": "annotated_video", "description": "标注后的检测视频"},
            {"field": "key_frames", "description": "状态转换关键帧截图"},
        ],
        "status": "running",
    },
    "XC-02": {
        "name": "安装新表作业识别",
        "scene": "XC",
        "io_type": "image",
        "backend_type": "local",
        "description": "基于双YOLO模型+PaddleOCR，对电表安装过程进行自动化识别。主模型检测电表/端子/螺丝刀/端子盖/手套/导线，铭牌模型检测铭牌并通过OCR识别铭牌编号。状态机流转：铭牌识别→电表安装→端子接线→安装完成。",
        "weight_path": "models_pool/XC/meter_install/best.pt",
        "loader": "yolo",
        "input_spec": [{"field": "video", "type": "mp4|avi", "required": True}],
        "output_spec": [
            {"field": "report", "description": "装表作业识别报告（含接线时间、验证时间、铭牌编号）"},
            {"field": "annotated_video", "description": "标注后的检测视频"},
            {"field": "key_frames", "description": "状态转换关键帧截图"},
        ],
        "status": "running",
    },
    # ========== 负荷资源管理（3） ==========
    "FH-01": {
        "name": "负荷资源可调能力评估",
        "scene": "FH",
        "io_type": "timeseries",
        "backend_type": "local",
        "description": "评估用户侧负荷资源可调能力，支持多类资源场景",
        "sub_scenes": ["空调", "储能", "光伏", "充换电", "工业"],
        "status": "planned",
    },
    "FH-02": {
        "name": "运营商申报策略推荐",
        "scene": "FH",
        "io_type": "tabular",
        "backend_type": "local",
        "description": "结合历史报价与市场情况推荐运营商申报策略",
        "status": "planned",
    },
    "FH-03": {
        "name": "运营商调控策略推荐",
        "scene": "FH",
        "io_type": "tabular",
        "backend_type": "local",
        "description": "实时电网状态下推荐运营商调控策略",
        "status": "planned",
    },
    # ========== 台区四精管理（5） ==========
    "TQ-01": {
        "name": "台区负载率预测",
        "scene": "TQ",
        "io_type": "timeseries",
        "backend_type": "local",
        "description": "预测台区未来 24 小时负载率走势",
        "status": "planned",
    },
    "TQ-02": {
        "name": "台区功率因数预测",
        "scene": "TQ",
        "io_type": "timeseries",
        "backend_type": "local",
        "description": "预测台区功率因数走势，辅助无功补偿",
        "status": "planned",
    },
    "TQ-03": {
        "name": "台区三相不平衡度预测",
        "scene": "TQ",
        "io_type": "timeseries",
        "backend_type": "local",
        "description": "预测三相不平衡度并提前预警",
        "status": "planned",
    },
    "TQ-04": {
        "name": "用户停电风险等级研判",
        "scene": "TQ",
        "io_type": "tabular",
        "backend_type": "local",
        "description": "综合用户档案与告警数据研判停电风险等级",
        "status": "planned",
    },
    "TQ-05": {
        "name": "用户电能质量评价",
        "scene": "TQ",
        "io_type": "timeseries",
        "backend_type": "local",
        "description": "基于电压电流时序数据评价用户电能质量",
        "status": "planned",
    },
    # ========== 用电异常监控（4） ==========
    "YD-01": {
        "name": "漏电分析",
        "scene": "YD",
        "io_type": "timeseries",
        "backend_type": "local",
        "description": "结合时序与电气特征识别漏电风险",
        "status": "planned",
    },
    "YD-02": {
        "name": "烧表防治",
        "scene": "YD",
        "io_type": "timeseries",
        "backend_type": "local",
        "description": "预测烧表风险等级并给出防治建议",
        "status": "planned",
    },
    "YD-03": {
        "name": "电采暖高价低接研判",
        "scene": "YD",
        "io_type": "timeseries",
        "backend_type": "local",
        "description": "基于LightGBM+SHAP+规则化评分，识别电采暖高价低接欺诈用户。支持Optuna超参搜索、先验对齐样本权重、F0.5-beta阈值优化、16维规则评分体系。",
        "weight_path": "models_pool/YD/heating_fraud/fraud_detection_model.pkl",
        "loader": "joblib",
        "input_spec": [{"field": "features", "type": "csv", "required": True}],
        "output_spec": [
            {"field": "predictions", "description": "预测结果（含欺诈概率、风险等级、规则评分）"},
            {"field": "charts", "description": "ROC/PR曲线、风险分布、SHAP图等"},
        ],
        "status": "running",
    },
    "YD-04": {
        "name": "计量失准",
        "scene": "YD",
        "io_type": "timeseries",
        "backend_type": "local",
        "description": "识别计量装置失准并定位失准类型",
        "status": "planned",
    },
    # ========== 资产管理（1） ==========
    "ZC-01": {
        "name": "逆变器光伏铭牌识别",
        "scene": "ZC",
        "io_type": "image",
        "backend_type": "local",
        "description": "OCR 识别逆变器/光伏铭牌信息并结构化输出",
        "status": "planned",
    },
}


def sync_registry() -> int:
    """将 MODEL_REGISTRY 同步至 model_metadata 表。

    - 不存在的 code：INSERT
    - 已存在的 code：UPDATE 非状态字段（status / current_version 不覆盖运行时变更）

    Returns:
        同步的记录数
    """
    import json
    from datetime import datetime
    from app.db.database import session_scope
    from app.db.models import ModelMetadata

    count = 0
    with session_scope() as db:
        for code, entry in MODEL_REGISTRY.items():
            existing = db.get(ModelMetadata, code)
            payload = dict(
                name=entry["name"],
                scene=entry["scene"],
                io_type=entry["io_type"],
                backend_type=entry.get("backend_type", "local"),
                description=entry.get("description"),
                input_spec=json.dumps(entry.get("input_spec", []), ensure_ascii=False),
                output_spec=json.dumps(entry.get("output_spec", []), ensure_ascii=False),
                sub_scenes=(
                    json.dumps(entry["sub_scenes"], ensure_ascii=False)
                    if entry.get("sub_scenes")
                    else None
                ),
                updated_at=datetime.now(),
            )
            if existing is None:
                db.add(
                    ModelMetadata(
                        code=code,
                        status=entry.get("status", "planned"),
                        **payload,
                    )
                )
                count += 1
            else:
                for k, v in payload.items():
                    setattr(existing, k, v)
                count += 1
    return count
