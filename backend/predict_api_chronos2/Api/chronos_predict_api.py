from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from typing import Any, Dict, List, Optional

import pandas as pd
import torch
from chronos import  Chronos2Pipeline
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator


class ChronosPredictRequest(BaseModel):
    """通用时序预测请求体。"""

    # 允许使用 model_path 字段名（关闭 Pydantic 对 model_ 命名空间的保护告警）
    model_config = {"protected_namespaces": ()}

    history_data: List[Dict[str, Any]] = Field(
        ...,
        description="历史N天数据（不能为空，不包含关联数据）",
    )
    related_data: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="关联数据（如温度/天气等），可为空；使用 series_id + data_date 关联",
    )
    target_fields: List[str] = Field(
        ...,
        description="需要预测的字段列表，例如 t0000,t0015,...",
    )
    prediction_length: int = Field(
        ...,
        gt=0,
        description="预测时长（如24点、96点等）",
    )

    id_column: str = Field(default="series_id", description="时序ID列名")
    timestamp_column: str = Field(default="data_date", description="时间列名")
    quantile_levels: List[float] = Field(default_factory=lambda: [0.1, 0.5, 0.9])
    predict_strategy: str = Field(
        default="line",
        description="预测策略：line=整行预测（所有target_fields一起预测），col=逐列预测（每个target_fields单独预测后合并）",
    )
    model_path: Optional[str] = Field(
        default=None,
        description="模型目录路径（可为空；为空则使用环境变量 CHRONOS2_MODEL_PATH 或默认 Model/chronos-2）",
    )

    @field_validator("predict_strategy")
    @classmethod
    def validate_predict_strategy(cls, value: str) -> str:
        if value not in ["line", "col"]:
            raise ValueError("predict_strategy 必须为 'line' 或 'col'")
        return value

    @field_validator("history_data")
    @classmethod
    def validate_history_data(cls, value: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not value:
            raise ValueError("history_data 不能为空")
        return value

    @field_validator("target_fields")
    @classmethod
    def validate_target_fields(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("target_fields 不能为空")
        return value


def _select_device_and_dtype() -> tuple[str, "torch.dtype", str]:
    """
    选择推理设备与精度，并打印诊断信息。

    返回 (device, dtype, reason)：
      - ("cuda", torch.bfloat16, ...) 表示 GPU 可用且已通过算子自检
      - ("cpu",  torch.float32,  ...) 表示回退 CPU（附带原因）

    设计要点：
      1. 显式识别 CPU-only 版 PyTorch（如 2.4.1+cpu），给出可操作的提示；
      2. 校验当前 GPU 架构（如 RTX 50 系 sm_120）是否在 PyTorch 编译架构内；
      3. 进行一次真实张量运算自检，确保 CUDA 内核（含 PTX JIT）真正可用，
         避免出现 “cuda_available=True 但实际无可用内核” 时静默算错/报错。
    """
    # 允许通过环境变量强制 CPU：CHRONOS2_FORCE_CPU=1/true/yes
    force_cpu = os.getenv("CHRONOS2_FORCE_CPU", "").strip().lower() in {"1", "true", "yes"}
    if force_cpu:
        print("[Chronos2] 已设置 CHRONOS2_FORCE_CPU，使用 CPU 推理。")
        return "cpu", torch.float32, "force_cpu"

    torch_version = torch.__version__

    # CPU-only 构建（如 2.4.1+cpu / torch.version.cuda 为 None）不含 CUDA 运行时
    if "+cpu" in torch_version or torch.version.cuda is None:
        print(
            f"[Chronos2] 当前安装的是 CPU 版 PyTorch（{torch_version}），无法使用 GPU。\n"
            f"           如需 GPU 加速，请安装对应 CUDA 的 PyTorch；\n"
            f"           RTX 50 系（Blackwell / sm_120）需 cu128 及以上，例如：\n"
            f"           pip install torch>=2.7.0 torchvision>=0.22.0 --index-url https://download.pytorch.org/whl/cu128"
        )
        return "cpu", torch.float32, "cpu_only_build"

    if not torch.cuda.is_available():
        print(
            f"[Chronos2] torch.cuda.is_available()=False"
            f"（torch {torch_version}, cuda {torch.version.cuda}），回退 CPU。"
        )
        return "cpu", torch.float32, "cuda_unavailable"

    # 至此为 CUDA 版 PyTorch 且 CUDA 可见，进一步做架构校验 + 真实算子自检
    try:
        name = torch.cuda.get_device_name(0)
        cap = torch.cuda.get_device_capability(0)          # 如 (12, 0) -> sm_120
        sm = f"sm_{cap[0]}{cap[1]}"
        supported = torch.cuda.get_arch_list()
        arch_ok = sm in supported

        # 真实张量运算自检（架构不匹配 / 无内核 / PTX JIT 失败都会在此暴露）
        probe = torch.randn(16, 16, device="cuda", dtype=torch.float32)
        _ = (probe @ probe).sum().item()
        torch.cuda.synchronize()

        if arch_ok:
            print(
                f"[Chronos2] GPU 已启用：{name} ({sm})，"
                f"PyTorch {torch_version} / CUDA {torch.version.cuda}，精度 bfloat16。"
            )
        else:
            print(
                f"[Chronos2] GPU 已启用（PTX JIT）：{name} ({sm}) 不在 PyTorch 预编译架构 {supported} 中，\n"
                f"           已通过 PTX 即时编译运行；如遇异常或性能不佳，建议升级到原生支持该架构的 PyTorch。"
            )
        return "cuda", torch.bfloat16, "cuda_ok"
    except Exception as exc:
        print(
            f"[Chronos2] GPU 自检失败，回退 CPU：{exc}\n"
            f"           可能原因：当前 PyTorch 不含本 GPU 架构内核（如 sm_120）。"
            f"RTX 50 系请安装 cu128+ 版本 PyTorch。"
        )
        return "cpu", torch.float32, "cuda_selftest_failed"


def default_model_dir() -> Path:
    """默认模型目录：项目内置 Model/chronos-2。"""
    return Path(__file__).resolve().parent.parent / "Model" / "chronos-2"


def has_model_weights(d: Path) -> bool:
    """目录内是否存在可用的权重文件（safetensors / bin / 分片索引）。"""
    try:
        if (d / "model.safetensors").exists():
            return True
        if (d / "pytorch_model.bin").exists():
            return True
        if (d / "model.safetensors.index.json").exists():
            return True
        if any(d.glob("*.safetensors")):
            return True
        return False
    except Exception:
        return False


def is_valid_model_dir(d: Path) -> bool:
    """是否为可加载的模型目录：含 config.json 且含权重文件。"""
    try:
        return d.is_dir() and (d / "config.json").exists() and has_model_weights(d)
    except Exception:
        return False


def resolve_model_path(model_path: Optional[str] = None) -> str:
    """
    解析并校验最终要加载的模型目录，返回正斜杠路径字符串。

    优先级：显式传入 model_path > 环境变量 CHRONOS2_MODEL_PATH > 默认 Model/chronos-2。
    若传入的是文件（如 model.safetensors / config.json），则自动取其所在目录。
    """
    if model_path and str(model_path).strip():
        candidate = Path(str(model_path).strip()).expanduser().resolve()
    else:
        env = os.getenv("CHRONOS2_MODEL_PATH", str(default_model_dir()))
        candidate = Path(env).expanduser().resolve()

    if not candidate.exists():
        raise RuntimeError(
            f"模型路径不存在: {candidate}\n"
            f"请在前端选择有效的模型目录，或配置环境变量 CHRONOS2_MODEL_PATH。"
        )

    # 用户若选中了模型目录内的某个文件，则使用其所在目录
    if candidate.is_file():
        candidate = candidate.parent

    if not (candidate / "config.json").exists():
        raise RuntimeError(f"所选目录缺少 config.json，不是有效的模型目录: {candidate}")
    if not has_model_weights(candidate):
        raise RuntimeError(
            f"所选目录缺少权重文件(model.safetensors / *.safetensors / pytorch_model.bin): {candidate}"
        )

    return str(candidate).replace("\\", "/")


# 当前已加载的模型（按路径缓存；切换模型时释放上一个，避免显存累积）
_PIPELINE_STATE: Dict[str, Any] = {"path": None, "pipeline": None}


def get_pipeline(model_path: Optional[str] = None) -> Chronos2Pipeline:
    """
    按所选路径懒加载 Chronos2Pipeline，优先 GPU、失败回退 CPU。

    - model_path 为空时使用默认/环境变量模型（向后兼容原有调用）。
    - 同一路径复用已加载实例；切换到不同模型时先释放旧实例与显存。
    """
    resolved = resolve_model_path(model_path)

    # 命中缓存：同一模型直接复用
    if _PIPELINE_STATE["pipeline"] is not None and _PIPELINE_STATE["path"] == resolved:
        return _PIPELINE_STATE["pipeline"]

    # 切换模型：释放上一个，回收显存
    if _PIPELINE_STATE["pipeline"] is not None:
        print(f"[Chronos2] 切换模型，释放旧实例: {_PIPELINE_STATE['path']}")
        _PIPELINE_STATE["pipeline"] = None
        _PIPELINE_STATE["path"] = None
        try:
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    # 选择推理设备与精度（含 CPU-only 识别、架构校验与真实算子自检）
    device, dtype, _reason = _select_device_and_dtype()
    print(f"[Chronos2] 加载模型: {resolved}（device={device}）")

    try:
        pipe = Chronos2Pipeline.from_pretrained(
            resolved,
            device_map=device,
            dtype=dtype,
            local_files_only=True,  # 强制使用本地文件
        )
    except Exception as exc:
        # GPU 加载阶段才暴露的问题（显存不足 / 驱动 / 运行时）再兜底回退 CPU
        if device != "cpu":
            print(f"[Chronos2] 在 {device} 上加载模型失败，回退 CPU：{exc}")
            pipe = Chronos2Pipeline.from_pretrained(
                resolved,
                device_map="cpu",
                dtype=torch.float32,
                local_files_only=True,
            )
        else:
            raise

    _PIPELINE_STATE["path"] = resolved
    _PIPELINE_STATE["pipeline"] = pipe
    return pipe


def _ensure_columns(df: pd.DataFrame, cols: List[str], df_name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"{df_name} 缺少必要字段: {missing}",
        )


def _parse_and_sort_df(df: pd.DataFrame, id_column: str, timestamp_column: str, df_name: str) -> pd.DataFrame:
    df = df.copy()
    df[timestamp_column] = pd.to_datetime(df[timestamp_column], errors="coerce")
    if df[timestamp_column].isna().any():
        raise HTTPException(status_code=400, detail=f"{df_name}.{timestamp_column} 存在无法解析的时间值")
    return df.sort_values([id_column, timestamp_column]).reset_index(drop=True)


def _normalize_history_dataframe(
    data: List[Dict[str, Any]],
    id_column: str,
    timestamp_column: str,
    target_fields: List[str],
) -> pd.DataFrame:
    df = pd.DataFrame(data)
    if df.empty:
        raise HTTPException(status_code=400, detail="history_data 不能为空")

    required_cols = [id_column, timestamp_column] + target_fields
    _ensure_columns(df, required_cols, "history_data")
    
    # 验证 history_data 不包含额外字段
    extra_cols = [c for c in df.columns if c not in required_cols]
    if extra_cols:
        raise HTTPException(
            status_code=400,
            detail=f"history_data 仅允许字段 {required_cols}，检测到附加字段 {extra_cols}。协变量请放在 related_data 中"
        )
    
    return _parse_and_sort_df(df, id_column, timestamp_column, "history_data")


def _build_predict_inputs(
    history_df: pd.DataFrame,
    related_data: Optional[List[Dict[str, Any]]],
    id_column: str,
    timestamp_column: str,
    target_fields: List[str],
) -> tuple[pd.DataFrame, Optional[pd.DataFrame], bool]:
    """
    返回: (df_for_predict, future_df_for_predict, used_related_data)

    规则：
    1) related_data 为空: df=history_data 本身，future_df 不传。
    2) related_data 非空: 通过 series_id + data_date 关联构建 df。
       - df: history_df 与 related_data 在历史日期上的关联结果（左连接）
       - future_df: related_data 中未来日期特征（若存在）
    """
    if not related_data:
        return history_df, None, False

    related_df = pd.DataFrame(related_data)
    if related_df.empty:
        return history_df, None, False

    _ensure_columns(related_df, [id_column, timestamp_column], "related_data")
    related_df = _parse_and_sort_df(related_df, id_column, timestamp_column, "related_data")

    history_max_date = history_df[timestamp_column].max()
    key_cols = [id_column, timestamp_column]

    related_feature_cols = [c for c in related_df.columns if c not in key_cols]

    # 1) 构建 predict_df 的 df：history 与 related 通过 id+time 关联
    related_hist = related_df[related_df[timestamp_column] <= history_max_date]
    predict_df = history_df.merge(
        related_hist[key_cols + related_feature_cols],
        on=key_cols,
        how="left",
        suffixes=("", "_related"),
    )

    # 避免相关数据中的同名 target 干扰模型 target 输入
    drop_target_cols = [c for c in predict_df.columns if c.endswith("_related") and c[:-8] in target_fields]
    if drop_target_cols:
        predict_df = predict_df.drop(columns=drop_target_cols)

    # 2) 构建 future_df：仅取未来日期的关联特征，不包含 target 字段
    related_future = related_df[related_df[timestamp_column] > history_max_date].copy()
    if related_future.empty:
        future_df: Optional[pd.DataFrame] = None
    else:
        future_drop_cols = [c for c in target_fields if c in related_future.columns]
        if future_drop_cols:
            related_future = related_future.drop(columns=future_drop_cols)
        future_df = related_future.sort_values(key_cols).reset_index(drop=True)

    return predict_df, future_df, True


def _predict_with_optional_future(
    pipeline: Chronos2Pipeline,
    df: pd.DataFrame,
    future_df: Optional[pd.DataFrame],
    request: ChronosPredictRequest,
) -> pd.DataFrame:
    """整行预测（原有逻辑）"""
    kwargs = dict(
        prediction_length=request.prediction_length,
        quantile_levels=request.quantile_levels,
        id_column=request.id_column,
        timestamp_column=request.timestamp_column,
        target=request.target_fields,
    )

    if future_df is None:
        return pipeline.predict_df(df=df, **kwargs)
    return pipeline.predict_df(df=df, future_df=future_df, **kwargs)


def _predict_column_by_column(
    pipeline: Chronos2Pipeline,
    df: pd.DataFrame,
    future_df: Optional[pd.DataFrame],
    request: ChronosPredictRequest,
) -> pd.DataFrame:
    """
    逐列预测：对每个 target_field 单独预测，最后合并结果
    
    返回格式与整行预测一致：包含 id_column, timestamp_column, target_name, 以及各分位数列
    """
    all_predictions = []
    
    for target_field in request.target_fields:
        # 准备单列预测的输入数据
        single_target_df = df[[request.id_column, request.timestamp_column, target_field]].copy()
        
        # 准备单列的 future_df（如果有）
        # 注意：逐列预测时，future_df 只能包含 id_column 和 timestamp_column
        # 因为协变量字段在单列 df 中不存在
        single_future_df = None
        if future_df is not None:
            # 只保留 id 和 time 列，不包含任何协变量
            single_future_df = future_df[[request.id_column, request.timestamp_column]].copy()
        
        # 执行单列预测
        kwargs = dict(
            prediction_length=request.prediction_length,
            quantile_levels=request.quantile_levels,
            id_column=request.id_column,
            timestamp_column=request.timestamp_column,
            target=[target_field],
        )
        
        if single_future_df is None:
            single_pred_df = pipeline.predict_df(df=single_target_df, **kwargs)
        else:
            single_pred_df = pipeline.predict_df(df=single_target_df, future_df=single_future_df, **kwargs)
        
        all_predictions.append(single_pred_df)
    
    # 合并所有列的预测结果
    if not all_predictions:
        raise HTTPException(status_code=500, detail="逐列预测未生成任何结果")
    
    # 将所有预测结果拼接在一起
    combined_pred_df = pd.concat(all_predictions, ignore_index=True)
    
    return combined_pred_df


def _build_quantile_wide(pred_df: pd.DataFrame, request: ChronosPredictRequest, quantile: float) -> List[Dict[str, Any]]:
    quantile_col = str(quantile)
    if quantile_col not in pred_df.columns:
        return []

    quantile_wide = (
        pred_df.pivot_table(
            index=[request.id_column, request.timestamp_column],
            columns="target_name",
            values=quantile_col,
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(columns=None)
    )

    sorted_targets = [c for c in request.target_fields if c in quantile_wide.columns]
    quantile_wide = quantile_wide[[request.id_column, request.timestamp_column] + sorted_targets]
    return quantile_wide.to_dict(orient="records")


def run_chronos_prediction(request: ChronosPredictRequest) -> Dict[str, Any]:
    history_df = _normalize_history_dataframe(
        request.history_data,
        request.id_column,
        request.timestamp_column,
        request.target_fields,
    )

    model_df, future_df, used_related_data = _build_predict_inputs(
        history_df,
        request.related_data,
        request.id_column,
        request.timestamp_column,
        request.target_fields,
    )

    pipeline = get_pipeline(request.model_path)

    # 根据预测策略选择预测方法
    if request.predict_strategy == "col":
        # 逐列预测
        pred_df = _predict_column_by_column(
            pipeline=pipeline,
            df=model_df,
            future_df=future_df,
            request=request,
        )
    else:
        # 整行预测（默认）
        pred_df = _predict_with_optional_future(
            pipeline=pipeline,
            df=model_df,
            future_df=future_df,
            request=request,
        )

    quantile_alias = {
        "0.1": "short_wide",
        "0.5": "median_wide",
        "0.9": "long_wide",
    }

    prediction_by_quantile: Dict[str, Any] = {}
    for q in request.quantile_levels:
        q_key = str(q)
        alias = quantile_alias.get(q_key, f"q{q_key}_wide")
        prediction_by_quantile[alias] = _build_quantile_wide(pred_df, request, q)

    return {
        "message": "预测成功",
        "used_related_data": used_related_data,
        "predict_strategy": request.predict_strategy,
        "prediction_length": request.prediction_length,
        "target_fields": request.target_fields,
        "quantile_levels": request.quantile_levels,
        "history_df_size": len(history_df),
        "model_df_size": len(model_df),
        "future_df_size": 0 if future_df is None else len(future_df),
        "prediction_result": prediction_by_quantile,
    }


app = FastAPI(title="Chronos2 通用时序预测接口", version="1.2.0")


@app.post("/api/chronos2/predict")
def predict(request: ChronosPredictRequest) -> Dict[str, Any]:
    try:
        return run_chronos_prediction(request)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"预测失败: {exc}") from exc
