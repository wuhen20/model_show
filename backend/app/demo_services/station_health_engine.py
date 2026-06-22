"""
主站异常研判 — 推理与训练引擎
基于 XGBoost + RandomForest + 1D-CNN Stacking 集成
"""
import warnings
warnings.filterwarnings('ignore')

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import accuracy_score, f1_score, classification_report
from imblearn.over_sampling import SMOTE
import optuna

# TensorFlow 延迟导入（避免模块级导入时的 DLL 问题）
def _tf_imports():
    import keras
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import Conv1D, Flatten, Dense, Dropout, TFSMLayer
    from tensorflow.keras.utils import to_categorical
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    return Sequential, load_model, Conv1D, Flatten, Dense, Dropout, to_categorical, EarlyStopping, ReduceLROnPlateau, TFSMLayer, keras

# ===================== 全局配置 =====================
TARGET_NAMES = [
    "正常", "通信前置异常", "采集前置异常", "消息队列异常",
    "数据路由异常", "数据校核异常", "调控管理异常", "数据库异常"
]
N_CLASSES = len(TARGET_NAMES)
RANDOM_STATE = 42
DROP_NUM = 20
N_FOLDS = 5
CNN_MAX_EPOCHS = 50
CNN_BATCH_SIZE = 32
TEST_SIZE = 0.2

# 路径计算
_BACKEND_DIR = Path(__file__).parent.parent.parent  # backend/
_DEFAULT_MODEL_DIR = str(_BACKEND_DIR / "models_pool" / "ZJ" / "station_health" / "default")
_TRAINED_MODEL_DIR = str(_BACKEND_DIR / "models_pool" / "ZJ" / "station_health")

# 训练状态
_train_status = {"running": False, "progress": 0, "message": "", "metrics": None}


def get_model_dir(use_trained: bool = False) -> str:
    return _TRAINED_MODEL_DIR if use_trained and os.path.exists(os.path.join(_TRAINED_MODEL_DIR, "traction_detect_xgb_model.json")) else _DEFAULT_MODEL_DIR


def get_train_status() -> dict:
    return dict(_train_status)


# ===================== 模型加载 =====================
def load_models(model_dir: str = None):
    if model_dir is None:
        model_dir = _DEFAULT_MODEL_DIR
    _, load_model, _, _, _, _, _, _, _, TFSMLayer, keras = _tf_imports()

    model_xgb = xgb.XGBClassifier()
    model_xgb.load_model(os.path.join(model_dir, "traction_detect_xgb_model.json"))

    model_rf = joblib.load(os.path.join(model_dir, "traction_detect_rf_model.json"))

    # 兼容 SavedModel 目录和 Keras .keras 文件两种格式
    cnn_dir = os.path.join(model_dir, "traction_detect_1D_CNN_model")
    cnn_keras = os.path.join(model_dir, "traction_detect_1D_CNN_model.keras")
    if os.path.isdir(cnn_dir):
        # Keras 3 不支持 load_model 加载 SavedModel 目录，使用 TFSMLayer
        model_cnn = keras.Sequential([TFSMLayer(cnn_dir, call_endpoint='serving_default')])
    elif os.path.exists(cnn_keras):
        model_cnn = load_model(cnn_keras)
    else:
        raise FileNotFoundError(f"CNN 模型不存在: {cnn_dir} 或 {cnn_keras}")

    cnn_scaler = joblib.load(os.path.join(model_dir, "cnn_scaler.pkl"))

    meta_learner = joblib.load(os.path.join(model_dir, "stacking_meta_learner.pkl"))

    label_encoder = joblib.load(os.path.join(model_dir, "label_encoder.pkl"))

    return model_xgb, model_rf, model_cnn, cnn_scaler, meta_learner, label_encoder


def get_feature_importance(model_dir: str = None) -> list:
    if model_dir is None:
        model_dir = _DEFAULT_MODEL_DIR
    fi_path = os.path.join(model_dir, "特征重要性.csv")
    if os.path.exists(fi_path):
        fi = pd.read_csv(fi_path)
        return fi.to_dict(orient="records")
    return []


def get_dropped_features(model_dir: str = None) -> list:
    if model_dir is None:
        model_dir = _DEFAULT_MODEL_DIR
    fi_path = os.path.join(model_dir, "特征重要性.csv")
    if os.path.exists(fi_path):
        fi = pd.read_csv(fi_path)
        fi = fi.sort_values("importance", ascending=True)
        return fi.head(DROP_NUM)["feature"].tolist()
    return []


# ===================== 推理 =====================
def stacking_predict(xgb_proba, rf_proba, cnn_proba, meta_learner):
    meta_features = np.hstack([xgb_proba, rf_proba, cnn_proba])
    y_pred = meta_learner.predict(meta_features)
    y_proba = meta_learner.predict_proba(meta_features)
    return y_pred, y_proba


def predict(df: pd.DataFrame, model_dir: str = None) -> dict:
    if model_dir is None:
        model_dir = _DEFAULT_MODEL_DIR

    model_xgb, model_rf, model_cnn, cnn_scaler, meta_learner, label_encoder = load_models(model_dir)
    drop_features = get_dropped_features(model_dir)

    X = df.copy()
    existing_drop = [f for f in drop_features if f in X.columns]
    X_selected = X.drop(columns=existing_drop, errors="ignore")

    xgb_proba = model_xgb.predict_proba(X_selected)
    rf_proba = model_rf.predict_proba(X_selected)

    X_scaled = cnn_scaler.transform(X_selected)
    X_cnn = np.expand_dims(X_scaled, axis=-1)
    cnn_proba = model_cnn.predict(X_cnn, verbose=0)

    y_pred, y_proba = stacking_predict(xgb_proba, rf_proba, cnn_proba, meta_learner)

    predictions = []
    for i in range(len(X)):
        row = {
            "index": i,
            "stacking_prediction": TARGET_NAMES[label_encoder.inverse_transform([y_pred[i]])[0]],
            "confidence": round(float(np.max(y_proba[i])), 4),
            "probabilities": {TARGET_NAMES[j]: round(float(y_proba[i, j]), 4) for j in range(N_CLASSES)},
        }
        predictions.append(row)

    return {
        "n_samples": len(X),
        "n_features": X_selected.shape[1],
        "n_classes": N_CLASSES,
        "target_names": TARGET_NAMES,
        "predictions": predictions,
    }


# ===================== 训练辅助函数 =====================
def build_light_cnn(input_dim, n_classes):
    Sequential, _, Conv1D, Flatten, Dense, Dropout, *_ = _tf_imports()
    model = Sequential([
        Conv1D(32, 3, activation='relu', input_shape=(input_dim, 1)),
        Dropout(0.2),
        Flatten(),
        Dense(64, activation='relu'),
        Dropout(0.2),
        Dense(n_classes, activation='softmax')
    ])
    model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])
    return model


def feature_select_by_xgb(X_train, y_train, X_test, drop_num=DROP_NUM, output_dir=None):
    xgb_select = xgb.XGBClassifier(
        max_depth=6, learning_rate=0.1, n_estimators=200,
        random_state=RANDOM_STATE, eval_metric='mlogloss',
        objective='multi:softprob', num_class=N_CLASSES
    )
    xgb_select.fit(X_train, y_train)

    feature_importance = pd.DataFrame({
        'feature': X_train.columns,
        'importance': xgb_select.feature_importances_
    }).sort_values('importance', ascending=True)

    if output_dir:
        feature_importance.to_csv(os.path.join(output_dir, "特征重要性.csv"), index=False, encoding="utf-8-sig")

    drop_features = feature_importance.head(drop_num)['feature'].tolist()
    X_train_selected = X_train.drop(columns=drop_features)
    X_test_selected = X_test.drop(columns=drop_features)
    return X_train_selected, X_test_selected, feature_importance


def sample_balance(X_train, y_train):
    class_counts = pd.Series(y_train).value_counts()
    max_count = class_counts.max()
    sampling_strategy = {cls: max(int(max_count * 0.5), count) for cls, count in class_counts.items() if count < max_count}
    if not sampling_strategy:
        return X_train, y_train
    smote = SMOTE(sampling_strategy=sampling_strategy, random_state=RANDOM_STATE)
    X_train_bal, y_train_bal = smote.fit_resample(X_train, y_train)
    if isinstance(X_train, pd.DataFrame) and not isinstance(X_train_bal, pd.DataFrame):
        X_train_bal = pd.DataFrame(X_train_bal, columns=X_train.columns)
    if not isinstance(y_train_bal, pd.Series):
        y_train_bal = pd.Series(y_train_bal)
    return X_train_bal, y_train_bal


def _filter_model_params(params, model_type):
    filtered = dict(params)
    if model_type == "xgb":
        filtered.update({'use_label_encoder': False, 'verbosity': 0, 'objective': 'multi:softprob', 'num_class': N_CLASSES, 'eval_metric': ['mlogloss', 'merror'], 'early_stopping_rounds': 50})
    elif model_type == "rf":
        filtered.update({'random_state': RANDOM_STATE, 'n_jobs': -1, 'verbose': 0})
    return filtered


def train_tree_model(X_train_bal, y_train_bal, X_test, y_test, model_type, n_trials=10):
    def objective(trial: optuna.Trial):
        if model_type == "xgb":
            params = {
                'max_depth': trial.suggest_int('max_depth', 3, 9),
                'learning_rate': trial.suggest_float('learning_rate', 1e-3, 1e-1, log=True),
                'n_estimators': trial.suggest_int('n_estimators', 50, 500),
                'gamma': trial.suggest_float('gamma', 1e-8, 1.0, log=True),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'subsample': trial.suggest_float('subsample', 0.5, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
            }
        else:
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 100, 800, step=100),
                'max_depth': trial.suggest_int('max_depth', 3, 15),
                'min_samples_split': trial.suggest_int('min_samples_split', 2, 20),
                'min_samples_leaf': trial.suggest_int('min_samples_leaf', 1, 10),
                'max_features': trial.suggest_categorical('max_features', ['sqrt', 'log2', None]),
                'criterion': trial.suggest_categorical('criterion', ['gini', 'entropy']),
                'bootstrap': trial.suggest_categorical('bootstrap', [True, False]),
            }

        skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)
        fold_accs = []
        for fold_idx, (train_idx, val_idx) in enumerate(skf.split(X_train_bal, y_train_bal)):
            X_fold_train = X_train_bal.iloc[train_idx]
            y_fold_train = y_train_bal.iloc[train_idx]
            X_fold_val = X_train_bal.iloc[val_idx]
            y_fold_val = y_train_bal.iloc[val_idx]

            if model_type == "xgb":
                p = _filter_model_params(params, "xgb")
                fold_model = xgb.XGBClassifier(**p)
                fold_model.fit(X_fold_train, y_fold_train, eval_set=[(X_fold_train, y_fold_train), (X_fold_val, y_fold_val)], verbose=False)
                fold_acc = accuracy_score(y_fold_val, fold_model.predict(X_fold_val))
            else:
                p = _filter_model_params(params, "rf")
                fold_model = RandomForestClassifier(**p)
                fold_model.fit(X_fold_train, y_fold_train)
                fold_acc = accuracy_score(y_fold_val, fold_model.predict(X_fold_val))

            fold_accs.append(fold_acc)
            trial.report(fold_acc, fold_idx)
            if trial.should_prune():
                raise optuna.TrialPruned()

        return np.mean(fold_accs)

    study = optuna.create_study(direction='maximize', pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=2, interval_steps=1))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    best_params = _filter_model_params(study.best_params, model_type)
    if model_type == "xgb":
        best_model = xgb.XGBClassifier(**best_params)
        best_model.fit(X_train_bal, y_train_bal, eval_set=[(X_train_bal, y_train_bal), (X_test, y_test)])
        evals = best_model.evals_result()
        training_metrics = {
            'train_loss': [float(x) for x in evals['validation_0']['mlogloss']],
            'val_loss': [float(x) for x in evals['validation_1']['mlogloss']],
            'train_acc': [1.0 - float(x) for x in evals['validation_0']['merror']],
            'val_acc': [1.0 - float(x) for x in evals['validation_1']['merror']],
        }
    else:
        best_model = RandomForestClassifier(**best_params)
        best_model.fit(X_train_bal, y_train_bal)
        training_metrics = {}
    return best_model, best_params, training_metrics


def train_cnn_model(X_train_bal, y_train_bal, X_test, y_test, output_dir):
    _, _, _, _, _, _, to_categorical, EarlyStopping, ReduceLROnPlateau, *_ = _tf_imports()
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_bal)
    X_test_scaled = scaler.transform(X_test)
    joblib.dump(scaler, os.path.join(output_dir, "cnn_scaler.pkl"))

    model_cnn = build_light_cnn(X_train_scaled.shape[1], N_CLASSES)
    X_train_cnn = np.expand_dims(X_train_scaled, axis=-1)
    X_test_cnn = np.expand_dims(X_test_scaled, axis=-1)
    y_train_cnn = to_categorical(y_train_bal, N_CLASSES)
    y_test_cnn = to_categorical(y_test, N_CLASSES)

    callbacks = [
        EarlyStopping(monitor='val_accuracy', patience=5, restore_best_weights=True, verbose=0),
        ReduceLROnPlateau(monitor='val_accuracy', factor=0.5, patience=3, min_lr=1e-6, verbose=0)
    ]
    history = model_cnn.fit(X_train_cnn, y_train_cnn, epochs=CNN_MAX_EPOCHS, batch_size=CNN_BATCH_SIZE, verbose=0, validation_data=(X_test_cnn, y_test_cnn), callbacks=callbacks)
    model_cnn.save(os.path.join(output_dir, "traction_detect_1D_CNN_model.keras"))

    training_metrics = {
        'train_loss': [float(x) for x in history.history['loss']],
        'val_loss': [float(x) for x in history.history['val_loss']],
        'train_acc': [float(x) for x in history.history['accuracy']],
        'val_acc': [float(x) for x in history.history['val_accuracy']],
    }
    return model_cnn, scaler, training_metrics


def generate_oof_predictions(X, y, model_type, best_params=None):
    _, _, _, _, _, _, to_categorical, EarlyStopping, *_ = _tf_imports()
    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)
    oof_proba = np.zeros((len(y), N_CLASSES))
    for fold_idx, (train_idx, val_idx) in enumerate(skf.split(X, y)):
        X_fold_train = X.iloc[train_idx]; y_fold_train = y.iloc[train_idx]; X_fold_val = X.iloc[val_idx]
        if model_type == "xgb":
            fold_model = xgb.XGBClassifier(**best_params)
            fold_model.fit(X_fold_train, y_fold_train, eval_set=[(X_fold_val, y.iloc[val_idx])], verbose=False)
            oof_proba[val_idx] = fold_model.predict_proba(X_fold_val)
        elif model_type == "rf":
            fold_model = RandomForestClassifier(**best_params)
            fold_model.fit(X_fold_train, y_fold_train)
            oof_proba[val_idx] = fold_model.predict_proba(X_fold_val)
        elif model_type == "cnn":
            fold_scaler = StandardScaler()
            X_train_scaled = fold_scaler.fit_transform(X_fold_train); X_val_scaled = fold_scaler.transform(X_fold_val)
            X_train_cnn = np.expand_dims(X_train_scaled, axis=-1); X_val_cnn = np.expand_dims(X_val_scaled, axis=-1)
            y_train_cnn = to_categorical(y_fold_train, N_CLASSES)
            fold_model = build_light_cnn(X_train_scaled.shape[1], N_CLASSES)
            fold_model.fit(X_train_cnn, y_train_cnn, epochs=CNN_MAX_EPOCHS, batch_size=CNN_BATCH_SIZE, verbose=0, callbacks=[EarlyStopping(monitor='accuracy', patience=5, restore_best_weights=True)])
            oof_proba[val_idx] = fold_model.predict(X_val_cnn, verbose=0)
    return oof_proba


def train_stacking_model(X_train_bal, y_train_bal, xgb_best_params, rf_best_params, output_dir):
    oof_xgb = generate_oof_predictions(X_train_bal, y_train_bal, "xgb", xgb_best_params)
    oof_rf = generate_oof_predictions(X_train_bal, y_train_bal, "rf", rf_best_params)
    oof_cnn = generate_oof_predictions(X_train_bal, y_train_bal, "cnn")
    meta_features = np.hstack([oof_xgb, oof_rf, oof_cnn])
    meta_learner = LogisticRegression(max_iter=1000, random_state=RANDOM_STATE, solver='lbfgs')
    meta_learner.fit(meta_features, y_train_bal)
    joblib.dump(meta_learner, os.path.join(output_dir, "stacking_meta_learner.pkl"))
    return meta_learner


def model_evaluate(y_true, y_pred):
    acc = float(accuracy_score(y_true, y_pred))
    f1 = float(f1_score(y_true, y_pred, average='weighted'))
    return {"accuracy": round(acc, 4), "f1_score": round(f1, 4)}


# ===================== 训练主函数 =====================
def train_model(data_path: str, output_dir: str = None, n_trials: int = 10) -> dict:
    global _train_status
    _train_status = {"running": True, "progress": 0, "message": "开始训练...", "metrics": None}

    if output_dir is None:
        output_dir = _TRAINED_MODEL_DIR
    os.makedirs(output_dir, exist_ok=True)

    try:
        # 1. 加载数据
        _train_status["message"] = "加载数据..."
        df = pd.read_csv(data_path)
        X = df.iloc[:, :-2]
        y = df.iloc[:, -2].squeeze()
        le = LabelEncoder()
        y = pd.Series(le.fit_transform(y), index=y.index)
        joblib.dump(le, os.path.join(output_dir, "label_encoder.pkl"))

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y)

        # 2. 特征筛选
        _train_status["progress"] = 5; _train_status["message"] = "特征筛选..."
        X_train_sel, X_test_sel, fi = feature_select_by_xgb(X_train, y_train, X_test, DROP_NUM, output_dir)

        # 3. 样本均衡
        _train_status["progress"] = 10; _train_status["message"] = "样本均衡..."
        X_train_bal, y_train_bal = sample_balance(X_train_sel, y_train)

        # 4. XGBoost
        _train_status["progress"] = 15; _train_status["message"] = f"训练 XGBoost (Optuna {n_trials}轮)..."
        model_xgb, xgb_best_params, xgb_metrics = train_tree_model(X_train_bal, y_train_bal, X_test_sel, y_test, "xgb", n_trials)
        model_xgb.save_model(os.path.join(output_dir, "traction_detect_xgb_model.json"))

        # 5. RF
        _train_status["progress"] = 40; _train_status["message"] = f"训练 RandomForest (Optuna {n_trials}轮)..."
        model_rf, rf_best_params, rf_metrics = train_tree_model(X_train_bal, y_train_bal, X_test_sel, y_test, "rf", n_trials)
        joblib.dump(model_rf, os.path.join(output_dir, "traction_detect_rf_model.json"))

        # 6. CNN
        _train_status["progress"] = 65; _train_status["message"] = "训练 1D-CNN..."
        model_cnn, cnn_scaler, cnn_metrics = train_cnn_model(X_train_bal, y_train_bal, X_test_sel, y_test, output_dir)

        # 7. Stacking
        _train_status["progress"] = 85; _train_status["message"] = "训练 Stacking 元模型..."
        meta_learner = train_stacking_model(X_train_bal, y_train_bal, xgb_best_params, rf_best_params, output_dir)

        # 8. 评估
        _train_status["progress"] = 95; _train_status["message"] = "测试集评估..."
        xgb_proba = model_xgb.predict_proba(X_test_sel)
        rf_proba = model_rf.predict_proba(X_test_sel)
        X_test_scaled = cnn_scaler.transform(X_test_sel)
        X_test_cnn = np.expand_dims(X_test_scaled, axis=-1)
        cnn_proba = model_cnn.predict(X_test_cnn, verbose=0)
        y_pred_stack, _ = stacking_predict(xgb_proba, rf_proba, cnn_proba, meta_learner)

        # 计算各模型指标
        def label_decode(pred):
            return le.inverse_transform(pred)

        results = {
            "xgb": model_evaluate(y_test, np.argmax(xgb_proba, axis=1)),
            "rf": model_evaluate(y_test, np.argmax(rf_proba, axis=1)),
            "cnn": model_evaluate(y_test, np.argmax(cnn_proba, axis=1)),
            "stacking": model_evaluate(y_test, y_pred_stack),
        }

        metrics = {
            "n_samples": len(df),
            "n_features": X.shape[1],
            "n_features_selected": X_train_sel.shape[1],
            "results": results,
            "training_metrics": {
                "xgb": xgb_metrics,
                "rf": rf_metrics,
                "cnn": cnn_metrics,
            },
            "target_names": TARGET_NAMES,
            "output_dir": output_dir,
        }

        _train_status = {"running": False, "progress": 100, "message": "训练完成", "metrics": metrics}
        return {"status": "ok", **metrics}

    except Exception as e:
        _train_status = {"running": False, "progress": 0, "message": f"训练失败: {str(e)}", "metrics": None}
        raise


def reset_model():
    """重置为默认模型"""
    for fname in ["traction_detect_xgb_model.json", "traction_detect_rf_model.json",
              "traction_detect_1D_CNN_model.keras", "stacking_meta_learner.pkl", "cnn_scaler.pkl", "label_encoder.pkl", "特征重要性.csv"]:
        fp = os.path.join(_TRAINED_MODEL_DIR, fname)
        if os.path.exists(fp):
            os.remove(fp)
    return {"status": "ok", "message": "已重置为默认模型"}