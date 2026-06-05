"""统一推理入口路由。

M1 阶段所有模型走 mock_adapter，仅记录 invocation_log；
M2 起按 backend_type 路由到 local_adapter。
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import ModelMetadata, InvocationLog
from app.schemas.model import PredictRequest, PredictResponse

router = APIRouter()


def _mock_output(model: ModelMetadata, payload: Any) -> dict:
    """根据 io_type 返回示例输出（M1 骨架）。"""
    io_type = model.io_type
    base = {"model_code": model.code, "model_name": model.name, "io_type": io_type}
    if io_type == "timeseries":
        return {
            **base,
            "prediction": 1,
            "score": 0.83,
            "anomaly_level": "中风险",
            "suggestion": "建议关注后续运行趋势并安排现场核查",
            "details": {"timestamps": [], "values": []},
        }
    if io_type == "image":
        return {
            **base,
            "detections": [
                {"label": "示例目标", "confidence": 0.92, "bbox": [10, 20, 100, 200]},
            ],
        }
    if io_type == "tabular":
        return {
            **base,
            "prediction": "中等风险",
            "feature_importance": [
                {"feature": "feature_a", "weight": 0.41},
                {"feature": "feature_b", "weight": 0.27},
            ],
        }
    return {**base, "result": "mock", "received": str(payload)[:100]}


@router.post("/{code}", response_model=PredictResponse)
def predict(code: str, req: PredictRequest, db: Session = Depends(get_db)):
    model = db.get(ModelMetadata, code)
    if model is None:
        raise HTTPException(status_code=404, detail=f"model {code} not found")

    trace_id = uuid.uuid4().hex[:16]
    t0 = time.perf_counter()
    success = 1
    error_msg = None
    try:
        # M1：mock 推理
        output = _mock_output(model, req.input)
    except Exception as exc:  # noqa: BLE001
        success = 0
        error_msg = str(exc)
        output = {}
    latency_ms = int((time.perf_counter() - t0) * 1000)

    log = InvocationLog(
        model_code=code,
        request_id=trace_id,
        latency_ms=latency_ms,
        success=success,
        error_msg=error_msg,
        invoked_at=datetime.now(),
    )
    db.add(log)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="日志写入失败")

    if not success:
        raise HTTPException(status_code=500, detail=error_msg or "predict failed")
    return PredictResponse(
        code=code,
        output=output,
        latency_ms=latency_ms,
        trace_id=trace_id,
        mock=True,
    )
