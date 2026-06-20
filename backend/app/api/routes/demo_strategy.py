"""
采集策略智能调度模型 — FastAPI 路由
K-means 聚类 + LightGBM 预测 + 17 场景规则研判 + 补召排程
"""
from pathlib import Path
from io import BytesIO
import json
import os
import shutil
import tempfile
import traceback
import zipfile
from datetime import datetime

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.demo_services.strategy.scheduler import ModelBundle
from app.demo_services.strategy.rules import run_all_rules, SCENARIO_META
from app.demo_services.strategy.data_loader import load_dataset, EXPECTED_TABLES
from app.core.config import settings

router = APIRouter()

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).parent.parent.parent.parent  # backend/
_MODELS_DIR = _BACKEND_DIR / "models_pool" / "ZJ" / "strategy"
_EXPERIENCE_DIR = _BACKEND_DIR / "experience_data" / "ZJ" / "strategy"
_DEFAULT_DATASET = str(_EXPERIENCE_DIR)

# 全局状态
global_state = {
    "dataset_dir": _DEFAULT_DATASET,
    "tables": None,
    "rule_results": None,
    "pipeline_results": None,
    "upload_dir": None,
    "today": datetime.now().strftime("%Y-%m-%d"),
}

# 模型包（懒加载）
_bundle: ModelBundle | None = None


def get_bundle() -> ModelBundle:
    global _bundle
    if _bundle is None:
        _bundle = ModelBundle(str(_MODELS_DIR))
    return _bundle


# ---------------------------------------------------------------------------
# API 端点
# ---------------------------------------------------------------------------

@router.get("/ping")
def ping():
    return {"status": "ok", "message": "strategy scheduler demo is alive"}


@router.get("/model_info")
def model_info():
    try:
        bundle = get_bundle()
        return bundle.info()
    except Exception as e:
        return {"error": str(e)}


@router.get("/scenario_meta")
def scenario_meta():
    """返回 17 场景元数据"""
    result = {}
    for sid, (name, cat, typ) in SCENARIO_META.items():
        result[sid] = {"name": name, "category": cat, "action_type": typ}
    return result


@router.get("/dataset_info")
def dataset_info():
    """返回数据集目录信息"""
    data_dir = global_state.get("upload_dir") or _DEFAULT_DATASET
    p = Path(data_dir)
    if not p.exists():
        return {"status": "error", "message": "数据集目录不存在", "path": data_dir}

    tables = []
    for name in EXPECTED_TABLES:
        f = p / f"{name}.csv"
        if f.exists():
            try:
                df = pd.read_csv(f)
                tables.append({
                    "name": name,
                    "rows": len(df),
                    "columns": len(df.columns),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                })
            except Exception:
                tables.append({"name": name, "rows": 0, "columns": 0, "size_kb": 0, "error": "读取失败"})
        else:
            tables.append({"name": name, "rows": 0, "columns": 0, "size_kb": 0, "missing": True})

    total_rows = sum(t["rows"] for t in tables)
    return {
        "status": "ok",
        "path": str(p),
        "total_tables": len(tables),
        "total_rows": total_rows,
        "tables": tables,
        "is_default": data_dir == _DEFAULT_DATASET,
    }


@router.post("/upload_dataset")
async def upload_dataset(file: UploadFile = File(...)):
    """上传 ZIP 数据集，解压到临时目录"""
    try:
        content = await file.read()
        temp_dir = tempfile.mkdtemp(prefix="strategy_dataset_")
        zf = zipfile.ZipFile(BytesIO(content))
        zf.extractall(temp_dir)
        zf.close()

        # 验证目录
        try:
            load_dataset(temp_dir)
        except FileNotFoundError as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return {"status": "error", "message": f"数据集不完整: {str(e)}"}

        # 清理旧上传
        old_dir = global_state.get("upload_dir")
        if old_dir and old_dir != _DEFAULT_DATASET:
            shutil.rmtree(old_dir, ignore_errors=True)

        global_state["upload_dir"] = temp_dir
        global_state["tables"] = None
        global_state["rule_results"] = None
        global_state["pipeline_results"] = None

        return {"status": "ok", "message": f"数据集上传成功，解压到 {temp_dir}", "path": temp_dir}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"上传失败: {str(e)}"}


@router.post("/run_rules")
async def run_rules():
    """执行规则研判，返回 17 场景统计"""
    data_dir = global_state.get("upload_dir") or _DEFAULT_DATASET
    try:
        tables = load_dataset(data_dir)
        global_state["tables"] = tables
        today = global_state["today"]
        recs = run_all_rules(tables, today)

        by_scenario = {}
        by_category = {}
        for r in recs:
            d = r.to_dict()
            by_scenario[d["matched_scenario_id"]] = by_scenario.get(d["matched_scenario_id"], 0) + 1
            by_category[d["action_category"]] = by_category.get(d["action_category"], 0) + 1

        global_state["rule_results"] = {
            "total": len(recs),
            "by_scenario": dict(sorted(by_scenario.items())),
            "by_category": dict(sorted(by_category.items())),
            "recommendations": [r.to_dict() for r in recs[:50]],  # 前 50 条
        }

        # 场景元数据
        scenario_meta = {}
        for sid, (name, cat, typ) in SCENARIO_META.items():
            scenario_meta[sid] = {"name": name, "category": cat, "action_type": typ}

        return {"status": "ok", **global_state["rule_results"], "scenario_meta": scenario_meta}
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"规则研判失败: {str(e)}"}


@router.post("/run_clustering")
async def run_clustering():
    """执行 K-means 聚类，返回各簇分布"""
    data_dir = global_state.get("upload_dir") or _DEFAULT_DATASET
    try:
        if global_state["tables"] is None:
            tables = load_dataset(data_dir)
            global_state["tables"] = tables
        else:
            tables = global_state["tables"]

        bundle = get_bundle()
        hist = tables["history_success_curve"]
        hist["stat_date"] = hist["stat_date"].astype(str)
        recent_dates = sorted(hist["stat_date"].unique())[-7:]
        recent = hist[hist["stat_date"].isin(recent_dates)]
        pivot = (recent.groupby(["terminal_id", "slot"])["success_rate"]
                      .mean().unstack("slot"))
        pivot = pivot.fillna(pivot.mean())

        import numpy as np
        terminal_clusters = {}
        cluster_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        cluster_curves = {0: [], 1: [], 2: [], 3: []}

        for tid in pivot.index:
            curve = pivot.loc[tid].values
            cid = bundle.predict_cluster(curve.tolist())
            terminal_clusters[tid] = cid
            cluster_counts[cid] = cluster_counts.get(cid, 0) + 1
            cluster_curves[cid].append(curve.tolist())

        # 每簇平均曲线
        cluster_avg_curves = {}
        for cid in range(4):
            if cluster_curves[cid]:
                avg = np.mean(cluster_curves[cid], axis=0).tolist()
                cluster_avg_curves[cid] = [round(v, 4) for v in avg]
            else:
                cluster_avg_curves[cid] = []

        return {
            "status": "ok",
            "total_terminals": len(terminal_clusters),
            "cluster_counts": cluster_counts,
            "cluster_avg_curves": cluster_avg_curves,
            "cluster_meta": {
                str(cid): {"name": bundle.cluster_meta.get(cid, {}).get("name", ""),
                            "n_terminals": bundle.cluster_meta.get(cid, {}).get("n_terminals_in_cluster", 0)}
                for cid in range(4)
            },
        }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"聚类失败: {str(e)}"}


@router.post("/run_prediction")
async def run_prediction():
    """执行 LightGBM 预测，返回 4 簇 96 点曲线"""
    data_dir = global_state.get("upload_dir") or _DEFAULT_DATASET
    try:
        if global_state["tables"] is None:
            tables = load_dataset(data_dir)
            global_state["tables"] = tables
        else:
            tables = global_state["tables"]

        bundle = get_bundle()
        today = global_state["today"]
        dow = (datetime.strptime(today, "%Y-%m-%d").weekday() + 1) % 7

        hist = tables["history_success_curve"]
        hist["stat_date"] = hist["stat_date"].astype(str)
        recent_dates = sorted(hist["stat_date"].unique())[-7:]
        recent = hist[hist["stat_date"].isin(recent_dates)]

        # 先聚类
        pivot = (recent.groupby(["terminal_id", "slot"])["success_rate"]
                      .mean().unstack("slot"))
        pivot = pivot.fillna(pivot.mean())

        import numpy as np
        terminal_clusters = {}
        for tid in pivot.index:
            curve = pivot.loc[tid].values
            terminal_clusters[tid] = bundle.predict_cluster(curve.tolist())

        # 每簇计算 slot_lags 并预测
        curves = {}
        for cid in range(4):
            cid_tids = [t for t, c in terminal_clusters.items() if c == cid]
            if not cid_tids:
                curves[cid] = []
                continue

            sub = recent[recent["terminal_id"].isin(cid_tids)]
            slot_pivot = (sub.groupby(["slot", "stat_date"])["success_rate"]
                              .mean().unstack("stat_date").sort_index())
            slot_pivot = slot_pivot[sorted(slot_pivot.columns)]

            slot_lags = []
            for slot in range(96):
                if slot in slot_pivot.index:
                    lags = list(reversed(list(slot_pivot.loc[slot].values[-7:])))
                else:
                    lags = [0.9] * 7
                slot_lags.append(lags)

            curve = bundle.predict_24h_curve(cid, slot_lags, dow)
            curves[cid] = curve

        return {
            "status": "ok",
            "dow": dow,
            "curves": curves,
        }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"预测失败: {str(e)}"}


@router.post("/run_schedule")
async def run_schedule():
    """生成补召排程"""
    data_dir = global_state.get("upload_dir") or _DEFAULT_DATASET
    try:
        if global_state["tables"] is None:
            tables = load_dataset(data_dir)
            global_state["tables"] = tables
        else:
            tables = global_state["tables"]

        bundle = get_bundle()
        today = global_state["today"]
        dow = (datetime.strptime(today, "%Y-%m-%d").weekday() + 1) % 7

        hist = tables["history_success_curve"]
        hist["stat_date"] = hist["stat_date"].astype(str)
        recent_dates = sorted(hist["stat_date"].unique())[-7:]
        recent = hist[hist["stat_date"].isin(recent_dates)]

        pivot = (recent.groupby(["terminal_id", "slot"])["success_rate"]
                      .mean().unstack("slot"))
        pivot = pivot.fillna(pivot.mean())

        import numpy as np
        terminal_clusters = {}
        for tid in pivot.index:
            curve = pivot.loc[tid].values
            terminal_clusters[tid] = bundle.predict_cluster(curve.tolist())

        schedules = []
        schedule_date = (datetime.strptime(today, "%Y-%m-%d") + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        for cid in range(4):
            cid_tids = [t for t, c in terminal_clusters.items() if c == cid]
            if not cid_tids:
                continue

            sub = recent[recent["terminal_id"].isin(cid_tids)]
            slot_pivot = (sub.groupby(["slot", "stat_date"])["success_rate"]
                              .mean().unstack("stat_date").sort_index())
            slot_pivot = slot_pivot[sorted(slot_pivot.columns)]

            slot_lags = []
            for slot in range(96):
                if slot in slot_pivot.index:
                    lags = list(reversed(list(slot_pivot.loc[slot].values[-7:])))
                else:
                    lags = [0.9] * 7
                slot_lags.append(lags)

            curve = bundle.predict_24h_curve(cid, slot_lags, dow)
            s = bundle.topk_recall_slots(curve)
            s["cluster_id"] = cid
            s["schedule_id"] = f"RS_{schedule_date.replace('-','')}_C{cid}"
            s["schedule_date"] = schedule_date
            s["cluster_name"] = bundle.cluster_meta.get(cid, {}).get("name", "")
            schedules.append(s)

        return {
            "status": "ok",
            "schedule_date": schedule_date,
            "schedules": schedules,
        }
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"排程失败: {str(e)}"}


@router.post("/run_full_pipeline")
async def run_full_pipeline():
    """一键执行全流程"""
    data_dir = global_state.get("upload_dir") or _DEFAULT_DATASET
    try:
        tables = load_dataset(data_dir)
        global_state["tables"] = tables
        today = global_state["today"]
        bundle = get_bundle()

        # 1. 规则研判
        recs = run_all_rules(tables, today)
        by_scenario = {}
        by_category = {}
        for r in recs:
            d = r.to_dict()
            by_scenario[d["matched_scenario_id"]] = by_scenario.get(d["matched_scenario_id"], 0) + 1
            by_category[d["action_category"]] = by_category.get(d["action_category"], 0) + 1

        # 2. 聚类
        hist = tables["history_success_curve"]
        hist["stat_date"] = hist["stat_date"].astype(str)
        recent_dates = sorted(hist["stat_date"].unique())[-7:]
        recent = hist[hist["stat_date"].isin(recent_dates)]
        pivot = (recent.groupby(["terminal_id", "slot"])["success_rate"]
                      .mean().unstack("slot"))
        pivot = pivot.fillna(pivot.mean())

        import numpy as np
        terminal_clusters = {}
        cluster_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        for tid in pivot.index:
            curve = pivot.loc[tid].values
            cid = bundle.predict_cluster(curve.tolist())
            terminal_clusters[tid] = cid
            cluster_counts[cid] = cluster_counts.get(cid, 0) + 1

        # 3. 预测 + 排程
        dow = (datetime.strptime(today, "%Y-%m-%d").weekday() + 1) % 7
        schedule_date = (datetime.strptime(today, "%Y-%m-%d") + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        schedules = []
        curves = {}

        for cid in range(4):
            cid_tids = [t for t, c in terminal_clusters.items() if c == cid]
            if not cid_tids:
                continue
            sub = recent[recent["terminal_id"].isin(cid_tids)]
            slot_pivot = (sub.groupby(["slot", "stat_date"])["success_rate"]
                              .mean().unstack("stat_date").sort_index())
            slot_pivot = slot_pivot[sorted(slot_pivot.columns)]

            slot_lags = []
            for slot in range(96):
                if slot in slot_pivot.index:
                    lags = list(reversed(list(slot_pivot.loc[slot].values[-7:])))
                else:
                    lags = [0.9] * 7
                slot_lags.append(lags)

            curve = bundle.predict_24h_curve(cid, slot_lags, dow)
            curves[cid] = curve
            s = bundle.topk_recall_slots(curve)
            s["cluster_id"] = cid
            s["schedule_id"] = f"RS_{schedule_date.replace('-','')}_C{cid}"
            s["schedule_date"] = schedule_date
            s["cluster_name"] = bundle.cluster_meta.get(cid, {}).get("name", "")
            schedules.append(s)

        result = {
            "status": "ok",
            "today": today,
            "schedule_date": schedule_date,
            "rules": {
                "total": len(recs),
                "by_scenario": dict(sorted(by_scenario.items())),
                "by_category": dict(sorted(by_category.items())),
                "recommendations": [r.to_dict() for r in recs[:50]],
            },
            "clustering": {
                "total_terminals": len(terminal_clusters),
                "cluster_counts": cluster_counts,
            },
            "prediction": {
                "dow": dow,
                "curves": curves,
            },
            "schedules": schedules,
        }

        # 策略调整对比
        c1_recs = [r for r in recs if r.action_category == "C1"]
        strategy_changes = []
        for r in c1_recs[:30]:
            strategy_changes.append({
                "terminal_id": r.terminal_id or r.area_id or "-",
                "scenario": r.matched_scenario_id,
                "scenario_name": r.matched_scenario_name,
                "original": r.original_strategy_name,
                "suggested": r.suggested_strategy_name,
                "freq_change": r.freq_change,
                "data_item_change": r.data_item_change,
                "expected_benefit": r.expected_benefit,
                "match_confidence": r.match_confidence,
            })
        result["strategy_comparison"] = {
            "total_c1": len(c1_recs),
            "changes": strategy_changes,
        }

        # 场景元数据
        scenario_meta = {}
        for sid, (name, cat, typ) in SCENARIO_META.items():
            scenario_meta[sid] = {"name": name, "category": cat, "action_type": typ}
        result["scenario_meta"] = scenario_meta

        global_state["pipeline_results"] = result
        return result
    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": f"全流程执行失败: {str(e)}"}


@router.get("/export_csv")
def export_csv():
    """导出中间表 CSV"""
    data = global_state.get("pipeline_results")
    if not data or not data.get("rules"):
        raise HTTPException(status_code=400, detail="请先执行全流程")

    recs = data["rules"]["recommendations"]
    if not recs:
        raise HTTPException(status_code=400, detail="无推荐结果")

    df = pd.DataFrame(recs)
    csv_path = _BACKEND_DIR / "data" / "strategy_recommendations.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")

    return FileResponse(str(csv_path), media_type="text/csv", filename="strategy_recommendations.csv")