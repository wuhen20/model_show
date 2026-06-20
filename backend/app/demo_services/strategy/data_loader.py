"""
数据加载：从目录读取 24 张源表 CSV
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd


EXPECTED_TABLES = [
    "areas", "terminals", "users", "meters",
    "user_tags", "user_risk_tags", "special_periods",
    "daily_consumption", "load_curve_summary",
    "collection_stats", "area_collection_stats",
    "terminal_heartbeat", "restart_log",
    "business_changes", "anomaly_alerts",
    "event_report_task_existing", "fee_control_status",
    "area_loss_rates", "complaints",
    "collection_strategy_master", "terminal_strategy_bind",
    "param_consistency", "cross_conn_suspects",
    "history_success_curve",
]


def load_dataset(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    """从 data_dir 读 24 张 CSV，返回 dict[name -> DataFrame]"""
    p = Path(data_dir)
    if not p.exists():
        raise FileNotFoundError(f"数据集目录不存在: {p}")
    tables: dict[str, pd.DataFrame] = {}
    missing = []
    # 自动深一层找 areas.csv 作为锚点
    if not (p / "areas.csv").exists():
        anchor = next(p.rglob("areas.csv"), None)
        if anchor is None:
            raise FileNotFoundError(f"在 {p} 下找不到 areas.csv，疑似不是 24 表的数据集目录")
        p = anchor.parent
    for name in EXPECTED_TABLES:
        f = p / f"{name}.csv"
        if f.exists():
            tables[name] = pd.read_csv(f)
        else:
            missing.append(name)
    if missing:
        raise FileNotFoundError(f"数据集缺少这些 CSV: {', '.join(missing)}")
    return tables
