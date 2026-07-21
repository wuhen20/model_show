"""生成四川四模型（负荷预测/负载率/功率因数/三相不平衡）的体验数据集。

运行后生成:
  - experience_data/TQ/TQ01_load_forecast/train_data.npz + predict_sample.csv
  - experience_data/TQ/TQ01_load_rate/train_data.npz + predict_sample.csv
  - experience_data/TQ/TQ02_pf/train_data.npz + predict_sample.csv
  - experience_data/TQ/TQ03_unbalance/train_data.npz + predict_sample.csv
"""
import sys
import os
import json
import numpy as np
import pandas as pd
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
RAW_CSV_DIR = BACKEND_DIR / "data" / "datasets" / "TQ" / "raw_csv"
EXP_DATA_DIR = BACKEND_DIR / "experience_data" / "TQ"

MODEL_CONFIGS = {
    "load_forecast": {
        "project_dir": r"f:\qoderproject\四川\负荷预测",
        "output_dir": EXP_DATA_DIR / "TQ01_load_forecast",
        "input_vars": ["power", "pf", "voltage", "current"],
    },
    "load_rate": {
        "project_dir": r"f:\qoderproject\四川\负载率",
        "output_dir": EXP_DATA_DIR / "TQ01_load_rate",
        "input_vars": ["power", "pf"],
    },
    "power_factor": {
        "project_dir": r"f:\qoderproject\四川\功率因数",
        "output_dir": EXP_DATA_DIR / "TQ02_pf",
        "input_vars": ["power", "pf"],
    },
    "unbalance": {
        "project_dir": r"f:\qoderproject\四川\三相不平衡",
        "output_dir": EXP_DATA_DIR / "TQ03_unbalance",
        "input_vars": ["power", "pf", "Ia", "Ib", "Ic"],
    },
}


def _clear_cached_modules():
    to_remove = []
    for name in list(sys.modules.keys()):
        if name in ("config", "data", "data.data_loader", "features",
                     "features.feature_builder", "losses", "models",
                     "models.cnn_lstm", "evaluate"):
            to_remove.append(name)
        elif name.startswith("data.") or name.startswith("features."):
            to_remove.append(name)
    for name in to_remove:
        del sys.modules[name]


def _override_config_paths(cfg, csv_dir):
    csv_dir = str(csv_dir)
    cfg.CSV_DIR = csv_dir
    for attr in dir(cfg):
        if attr.startswith("FILE_"):
            val = getattr(cfg, attr)
            if isinstance(val, str) and os.path.basename(val):
                fname = os.path.basename(val)
                setattr(cfg, attr, os.path.join(csv_dir, fname))


def _serialize_normalizer_params(params):
    out = {}
    for eid, curves in params.items():
        key = str(int(eid))
        out[key] = {}
        for var, p in curves.items():
            out[key][var] = {"min": float(p["min"]), "max": float(p["max"])}
    return json.dumps(out, ensure_ascii=False)


def _generate_predict_csv(data_dict, input_vars, entity_ids, input_dates_list, output_path):
    point_cols = [f"p{h:02d}{m:02d}" for h in range(24) for m in (0, 15, 30, 45)]
    rows = []
    n_samples = min(3, len(entity_ids))
    for i in range(n_samples):
        eid = entity_ids[i]
        input_dates = input_dates_list[i]
        for dt in input_dates:
            date_str = dt.strftime("%Y-%m-%d")
            for var in input_vars:
                if eid in data_dict and var in data_dict[eid]:
                    vals = data_dict[eid][var].loc[dt].values
                    row = {"entity_id": int(eid), "date": date_str, "variable": var}
                    for j, col in enumerate(point_cols):
                        row[col] = round(float(vals[j]), 6) if j < len(vals) else 0.0
                    rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"  predict_sample.csv: {output_path} ({len(df)} rows)")


def generate_model_data(model_key):
    cfg_model = MODEL_CONFIGS[model_key]
    project_dir = cfg_model["project_dir"]
    output_dir = cfg_model["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'=' * 55}")
    print(f"  Model: {model_key}")
    print(f"  Project: {project_dir}")
    print(f"  Output: {output_dir}")
    print(f"{'=' * 55}")

    _clear_cached_modules()
    project_dir_str = str(project_dir)
    if project_dir_str in sys.path:
        sys.path.remove(project_dir_str)
    sys.path.insert(0, project_dir_str)

    try:
        import config as cfg
        _override_config_paths(cfg, RAW_CSV_DIR)

        from data.data_loader import load_all_curves
        from features.feature_builder import MinMaxNormalizer, build_samples, split_data

        print("  Loading curves...")
        data_dict = load_all_curves()
        print(f"  Districts: {len(data_dict)}")
        for eid, curves in data_dict.items():
            first_key = list(curves.keys())[0]
            print(f"    {cfg.DISTRICTS.get(eid, {}).get('name', eid)}: {len(curves[first_key])} days")

        print("  Building samples...")
        normalizer = MinMaxNormalizer()
        normalizer.fit(data_dict)
        X_time, X_static, Y, entity_ids, dates_all = build_samples(data_dict, normalizer)
        print(f"  Samples: {len(X_time)}  X_time: {X_time.shape}  Y: {Y.shape}")

        splits = split_data(X_time, X_static, Y, entity_ids, dates_all)
        for name, (xt, *_) in splits.items():
            print(f"    {name}: {len(xt)}")

        # Combine train+val
        tr = splits["train"]
        va = splits["val"]
        all_X_time = np.concatenate([tr[0], va[0]], axis=0)
        all_X_static = np.concatenate([tr[1], va[1]], axis=0)
        all_Y = np.concatenate([tr[2], va[2]], axis=0)
        all_eids = np.array(tr[3] + va[3])
        norm_json = _serialize_normalizer_params(normalizer.params)

        npz_path = output_dir / "train_data.npz"
        np.savez(npz_path, X_time=all_X_time, X_static=all_X_static,
                 Y=all_Y, entity_ids=all_eids, normalizer_params=norm_json)
        print(f"  train_data.npz: {npz_path}")

        # Predict sample CSV from test set
        test_data = splits["test"]
        test_eids = test_data[3]
        test_dates = test_data[4] if len(test_data) > 4 else None
        input_days = cfg.INPUT_DAYS
        input_dates_list = []
        for i, eid in enumerate(test_eids):
            if test_dates:
                output_dates = test_dates[i]
                first_var = list(data_dict[eid].keys())[0]
                all_dates = list(data_dict[eid][first_var].index)
                out_idx = all_dates.index(output_dates[0])
                in_start = max(0, out_idx - input_days)
                input_dates_list.append(all_dates[in_start:out_idx])
            else:
                input_dates_list.append([])

        csv_path = output_dir / "predict_sample.csv"
        _generate_predict_csv(data_dict, cfg_model["input_vars"],
                              test_eids, input_dates_list, csv_path)
        print(f"  Done: {model_key}")
    finally:
        if project_dir_str in sys.path:
            sys.path.remove(project_dir_str)
        _clear_cached_modules()


if __name__ == "__main__":
    for mk in MODEL_CONFIGS:
        generate_model_data(mk)
    print("\nAll experience data generated successfully!")
