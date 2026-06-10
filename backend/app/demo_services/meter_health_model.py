#!/usr/bin/env python
# coding: utf-8

"""
电能表健康评分系统 — 核心算法模块
包含模块：
1. 使用年限评分
2. 通讯模块评分
3. 电气异常检测 (Isolation Forest + 超参数优化)
4. 采集完整率检测 (Isolation Forest + 超参数优化)
5. 生产厂商质量评估
6. 综合评分与阈值校准
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold, StratifiedKFold
from sklearn.metrics import roc_auc_score
from skopt import gp_minimize
from skopt.space import Real, Integer
from skopt.utils import use_named_args
import warnings
warnings.filterwarnings('ignore')


# ==================== 辅助函数 ====================

def plot_score_distribution(scores, is_removed, title="分数分布"):
    """绘制分数分布图，返回 figure"""
    fig, ax = plt.subplots(figsize=(10, 6))
    removed_scores = scores[is_removed == 1]
    normal_scores = scores[is_removed == 0]
    ax.hist(normal_scores, bins=30, alpha=0.7, label='运行中', color='green', density=True)
    ax.hist(removed_scores, bins=30, alpha=0.7, label='已拆除', color='red', density=True)
    ax.set_xlabel('健康分数')
    ax.set_ylabel('密度')
    ax.set_title(f'{title} - 拆除样本 vs 运行样本')
    ax.legend()
    ax.grid(True, alpha=0.3)
    return fig


def optimize_isolation_forest(X, y_removed=None, n_calls=30, random_state=42, verbose=True):
    """使用贝叶斯优化调优 Isolation Forest 的超参数"""
    space = [
        Integer(100, 500, name='n_estimators'),
        Real(0.5, 1.0, name='max_samples'),
        Real(0.5, 1.0, name='max_features')
    ]

    @use_named_args(space)
    def objective(**params):
        try:
            model = IsolationForest(
                n_estimators=int(params['n_estimators']),
                max_samples=params['max_samples'],
                max_features=params['max_features'],
                random_state=random_state,
                contamination='auto',
                bootstrap=False
            )
            if y_removed is not None and len(np.unique(y_removed)) > 1:
                skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state)
                auc_scores = []
                for train_idx, val_idx in skf.split(X, y_removed):
                    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                    y_val = y_removed[val_idx]
                    scaler = StandardScaler()
                    X_train_scaled = scaler.fit_transform(X_train)
                    X_val_scaled = scaler.transform(X_val)
                    temp_model = IsolationForest(
                        n_estimators=int(params['n_estimators']),
                        max_samples=params['max_samples'],
                        max_features=params['max_features'],
                        random_state=random_state,
                        contamination='auto',
                        bootstrap=False
                    )
                    temp_model.fit(X_train_scaled)
                    scores = temp_model.decision_function(X_val_scaled)
                    if len(np.unique(y_val)) > 1:
                        auc = roc_auc_score(y_val, -scores)
                        auc_scores.append(auc)
                if len(auc_scores) == 0:
                    return 999
                return -np.mean(auc_scores)
            else:
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)
                model.fit(X_scaled)
                anomaly_scores = model.decision_function(X_scaled)
                return -np.std(anomaly_scores)
        except Exception:
            return 999

    if verbose:
        print("开始超参数优化（贝叶斯优化）...")

    result = gp_minimize(
        objective, space, n_calls=n_calls,
        n_initial_points=10, acq_func='EI',
        random_state=random_state, verbose=False
    )

    best_params = {
        'n_estimators': int(result.x[0]),
        'max_samples': float(result.x[1]),
        'max_features': float(result.x[2])
    }

    if verbose:
        print(f"优化完成！最佳 n_estimators={best_params['n_estimators']}, "
              f"max_samples={best_params['max_samples']:.4f}, max_features={best_params['max_features']:.4f}")

    return best_params, result


def grid_search_isolation_forest(X, y_removed=None,
                                  n_estimators_grid=None,
                                  max_samples_grid=None,
                                  max_features_grid=None,
                                  random_state=42, verbose=True):
    """
    使用网格搜索调优 Isolation Forest 的超参数
    遍历所有参数组合，使用 K-fold 交叉验证评估 AUC
    """
    if n_estimators_grid is None:
        n_estimators_grid = [100, 200, 300, 400, 500]
    if max_samples_grid is None:
        max_samples_grid = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    if max_features_grid is None:
        max_features_grid = [0.5, 0.7, 1.0]

    total_combinations = len(n_estimators_grid) * len(max_samples_grid) * len(max_features_grid)

    if verbose:
        print(f"开始网格搜索: {total_combinations} 种组合")

    grid_results = []
    best_auc = -1
    best_params = {}
    combo_idx = 0

    for n_est in n_estimators_grid:
        for max_samp in max_samples_grid:
            for max_feat in max_features_grid:
                combo_idx += 1
                try:
                    if y_removed is not None and len(np.unique(y_removed)) > 1:
                        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state)
                        auc_scores = []
                        for train_idx, val_idx in skf.split(X, y_removed):
                            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                            y_val = y_removed[val_idx]
                            scaler = StandardScaler()
                            X_train_scaled = scaler.fit_transform(X_train)
                            X_val_scaled = scaler.transform(X_val)
                            temp_model = IsolationForest(
                                n_estimators=n_est, max_samples=max_samp,
                                max_features=max_feat, random_state=random_state,
                                contamination='auto', bootstrap=False
                            )
                            temp_model.fit(X_train_scaled)
                            scores = temp_model.decision_function(X_val_scaled)
                            if len(np.unique(y_val)) > 1:
                                auc = roc_auc_score(y_val, -scores)
                                auc_scores.append(auc)
                        if len(auc_scores) > 0:
                            mean_auc = np.mean(auc_scores)
                            std_auc = np.std(auc_scores)
                        else:
                            mean_auc = 0
                            std_auc = 0
                    else:
                        scaler = StandardScaler()
                        X_scaled = scaler.fit_transform(X)
                        model = IsolationForest(
                            n_estimators=n_est, max_samples=max_samp,
                            max_features=max_feat, random_state=random_state,
                            contamination='auto', bootstrap=False
                        )
                        model.fit(X_scaled)
                        anomaly_scores = model.decision_function(X_scaled)
                        mean_auc = np.std(anomaly_scores)
                        std_auc = 0

                    result_entry = {
                        'n_estimators': n_est,
                        'max_samples': round(max_samp, 2),
                        'max_features': round(max_feat, 2),
                        'mean_auc': round(float(mean_auc), 4),
                        'std_auc': round(float(std_auc), 4),
                    }
                    grid_results.append(result_entry)

                    if mean_auc > best_auc:
                        best_auc = mean_auc
                        best_params = {
                            'n_estimators': n_est,
                            'max_samples': max_samp,
                            'max_features': max_feat,
                            'best_auc': round(float(mean_auc), 4)
                        }
                except Exception as e:
                    grid_results.append({
                        'n_estimators': n_est,
                        'max_samples': round(max_samp, 2),
                        'max_features': round(max_feat, 2),
                        'mean_auc': 0,
                        'std_auc': 0,
                        'error': str(e)
                    })

    grid_results.sort(key=lambda x: x['mean_auc'], reverse=True)
    return best_params, grid_results


# ==================== 模块1：使用年限评分 ====================

def score_RUN_YEARS(years):
    """
    模块1：使用年限评分
    5年及以下: 100分，5-8年: 线性递减到0分，8年以上: 0分
    """
    if years <= 5:
        return 100
    elif years >= 8:
        return 0
    else:
        return 100 * (1 - (years - 5) / 3)


# ==================== 模块2：通讯模块评分 ====================

def score_comm_time(COMM_TIME_LOC):
    """
    模块2：本地通讯时长评分
    10s以下: 100分，10-180s: 指数衰减，180s及以上: 0分
    """
    t = COMM_TIME_LOC
    if t <= 10:
        return 100
    elif t >= 180:
        return 0
    else:
        k = 0.05145
        score = 100 * np.exp(-k * (t - 10))
        return max(0, min(100, score))


# ==================== 模块3&4：Isolation Forest 模块 ====================

class IsolationForestScorer:
    """封装Isolation Forest，支持训练、评分、交叉验证、阈值校准、超参数优化"""

    def __init__(self, feature_names, module_name="", n_estimators=250, max_samples=0.8,
                 max_features=0.7, use_optimization=False, optimize_n_calls=30,
                 use_grid_search=False, verbose=True):
        self.feature_names = feature_names
        self.module_name = module_name
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.max_features = max_features
        self.use_optimization = use_optimization
        self.optimize_n_calls = optimize_n_calls
        self.use_grid_search = use_grid_search
        self.verbose = verbose
        self.model = None
        self.scaler = None
        self.scores_history = []
        self.best_params = {}
        self.grid_search_results = []
        self.repair_threshold = 60
        self.warning_threshold = 80

    def train(self, X, y_removed=None):
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)

        if self.use_grid_search and y_removed is not None and len(np.unique(y_removed)) > 1:
            best_params, grid_results = grid_search_isolation_forest(
                X, y_removed, random_state=42, verbose=self.verbose
            )
            self.n_estimators = best_params['n_estimators']
            self.max_samples = best_params['max_samples']
            self.max_features = best_params['max_features']
            self.best_params = best_params
            self.grid_search_results = grid_results
        elif self.use_optimization and y_removed is not None and len(np.unique(y_removed)) > 1:
            best_params, _ = optimize_isolation_forest(
                X, y_removed, n_calls=self.optimize_n_calls,
                random_state=42, verbose=self.verbose
            )
            self.n_estimators = best_params['n_estimators']
            self.max_samples = best_params['max_samples']
            self.max_features = best_params['max_features']
            self.best_params = best_params

        self.model = IsolationForest(
            n_estimators=self.n_estimators, max_samples=self.max_samples,
            max_features=self.max_features, random_state=42,
            contamination='auto', bootstrap=False
        )
        self.model.fit(X_scaled)
        anomaly_scores = self.model.decision_function(X_scaled)
        return self._anomaly_to_health(anomaly_scores)

    def _anomaly_to_health(self, anomaly_scores):
        min_score = np.percentile(anomaly_scores, 5)
        max_score = np.percentile(anomaly_scores, 95)
        if max_score - min_score < 0.01:
            normalized = np.ones_like(anomaly_scores) * 0.5
        else:
            normalized = (anomaly_scores - min_score) / (max_score - min_score)
        return np.clip(normalized * 100, 0, 100)

    def predict(self, X):
        X_scaled = self.scaler.transform(X)
        anomaly_scores = self.model.decision_function(X_scaled)
        return self._anomaly_to_health(anomaly_scores)

    def predict_anomaly(self, X):
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def cross_validate(self, X, y_removed, n_folds=5):
        y_removed = np.array(y_removed)
        removed_indices = np.where(y_removed == 1)[0]
        if len(removed_indices) == 0:
            return None
        kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
        removed_ranks = []
        fold_aucs = []
        for fold, (train_idx, test_idx) in enumerate(kf.split(X), 1):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_test_removed = y_removed[test_idx]
            temp_model = IsolationForestScorer(
                self.feature_names, self.module_name,
                self.n_estimators, self.max_samples, self.max_features,
                use_optimization=False, verbose=False
            )
            temp_model.train(X_train)
            test_scores = temp_model.predict(X_test)
            if len(np.unique(y_test_removed)) > 1:
                auc = roc_auc_score(y_test_removed, -test_scores)
                fold_aucs.append(auc)
            for i, is_removed in enumerate(y_test_removed):
                if is_removed == 1:
                    rank = np.sum(test_scores <= test_scores[i]) / len(test_scores)
                    removed_ranks.append(rank)
        avg_rank = np.mean(removed_ranks) if removed_ranks else 1.0
        mean_auc = np.mean(fold_aucs) if fold_aucs else 0
        return removed_ranks

    def calibrate_thresholds(self, X, y_removed):
        health_scores = self.predict(X)
        removed_scores = health_scores[y_removed == 1]
        if len(removed_scores) == 0:
            return 60, 80
        q25 = np.percentile(removed_scores, 25)
        q75 = np.percentile(removed_scores, 75)
        self.repair_threshold = q25
        self.warning_threshold = q75
        return q25, q75


# ==================== 模块5：生产厂商质量评估 ====================

class MFRAnalyzer:
    """生产厂商分析和质量评估模块"""

    def __init__(self, MFR_col='MFR'):
        self.MFR_col = MFR_col
        self.MFR_stats = {}
        self.MFR_quality_score = {}
        self.cluster_model = None

    def analyze_MFRs(self, df, is_removed_col='is_removed'):
        if self.MFR_col not in df.columns:
            return None
        MFRs = df[self.MFR_col].unique()
        stats = []
        for mfr in MFRs:
            mfr_data = df[df[self.MFR_col] == mfr]
            total_count = len(mfr_data)
            if is_removed_col in df.columns:
                removed_count = mfr_data[mfr_data[is_removed_col] == 1].shape[0]
                removal_rate = removed_count / total_count if total_count > 0 else 0
            else:
                removed_count = 0
                removal_rate = 0
            if 'total_score' in df.columns:
                avg_health = mfr_data['total_score'].mean()
                median_health = mfr_data['total_score'].median()
            else:
                avg_health = median_health = 0
            stats.append({
                'MFR': mfr, 'total_count': total_count,
                'removed_count': removed_count, 'removal_rate': removal_rate,
                'avg_health_score': avg_health, 'median_health_score': median_health
            })
        self.MFR_stats = stats
        return stats

    def calculate_quality_score(self, df, is_removed_col='is_removed',
                                 use_health_score=True, use_removal_rate=True):
        if self.MFR_col not in df.columns:
            df['score_MFR'] = 100
            return df
        MFRs = df[self.MFR_col].unique()
        quality_scores = {}
        health_cols = [c for c in ['score_module3', 'score_module4'] if c in df.columns]
        for mfr in MFRs:
            mfr_data = df[df[self.MFR_col] == mfr]
            score = 100
            if use_removal_rate and is_removed_col in df.columns:
                removal_rate = mfr_data[mfr_data[is_removed_col] == 1].shape[0] / len(mfr_data)
                removal_penalty = min(30, removal_rate * 100 * 0.6)
                score -= removal_penalty
            if use_health_score and health_cols:
                avg_health = mfr_data[health_cols].mean(axis=1).mean()
                anchor = 75
                if avg_health < anchor:
                    health_penalty = min(30, (anchor - avg_health) * 0.8)
                    score -= health_penalty
                else:
                    bonus = min(10, (avg_health - anchor) * 0.5)
                    score += bonus
            quality_scores[mfr] = max(0, min(100, score))
        self.MFR_quality_score = quality_scores
        df['score_MFR'] = df[self.MFR_col].map(quality_scores)
        df['score_MFR'] = df['score_MFR'].fillna(100)
        return df

    def cluster_MFRs(self, df, n_clusters=3, feature_cols=None):
        if self.MFR_col not in df.columns:
            return None
        if feature_cols is None:
            feature_cols = [
                'TEMP_AVG', 'TEMP_STD', 'TEMP_ERR_RATE', 'TEMP_AVG_7D', 'TEMP_STD_7D',
                'ME_CLOCK_DEVIATION_30D', 'OFFSET_TIME',
                'COLL_FAIL_IA_7D', 'COLL_FAIL_UA_7D', 'COLL_FAIL_PFA_7D',
                'COLL_COMPLETE_IA', 'COLL_COMPLETE_IA_7D', 'COLL_COMPLETE_IA_14D',
                'COLL_COMPLETE_UA', 'COLL_COMPLETE_UA_7D', 'COLL_COMPLETE_UA_14D',
                'COLL_COMPLETE_PFA', 'COLL_COMPLETE_PFA_7D', 'COLL_COMPLETE_PFA_14D'
            ]
        available_features = [f for f in feature_cols if f in df.columns]
        if len(available_features) < 2:
            return None
        from sklearn.preprocessing import StandardScaler as SS
        from sklearn.cluster import KMeans
        MFR_features = df.groupby(self.MFR_col)[available_features].mean()
        if len(MFR_features) < n_clusters:
            n_clusters = len(MFR_features)
        if n_clusters < 2:
            return None
        scaler = SS()
        features_scaled = scaler.fit_transform(MFR_features)
        self.cluster_model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = self.cluster_model.fit_predict(features_scaled)
        MFR_features['cluster'] = cluster_labels
        cluster_map = MFR_features['cluster'].to_dict()
        df['MFR_cluster'] = df[self.MFR_col].map(cluster_map)
        return MFR_features


# ==================== 最佳模型存储 ====================

class BestModelStorage:
    """存储最佳模型和参数"""

    def __init__(self):
        self.models = {}
        self.params = {}
        self.scalers = {}
        self.thresholds = {}

    def save_model(self, module_name, model, scaler, params, thresholds):
        self.models[module_name] = model
        self.scalers[module_name] = scaler
        self.params[module_name] = params
        self.thresholds[module_name] = thresholds

    def save_all(self, module3_model, module4_model, MFR_analyzer, weights):
        if module3_model:
            self.models['module3'] = module3_model.model
            self.scalers['module3'] = module3_model.scaler
            self.params['module3'] = module3_model.best_params if module3_model.best_params else {
                'n_estimators': module3_model.n_estimators,
                'max_samples': module3_model.max_samples,
                'max_features': module3_model.max_features
            }
        if module4_model:
            self.models['module4'] = module4_model.model
            self.scalers['module4'] = module4_model.scaler
            self.params['module4'] = module4_model.best_params if module4_model.best_params else {
                'n_estimators': module4_model.n_estimators,
                'max_samples': module4_model.max_samples,
                'max_features': module4_model.max_features
            }
        self.params['MFR'] = MFR_analyzer.MFR_quality_score
        self.params['weights'] = weights


# ==================== 数据预处理 ====================

def preprocess_features(df):
    """预处理特征数据"""
    binary_features = ['IS_FLY', 'IS_REVERSE', 'IS_REVERSE_CREEP', 'RATE_IMBALANCE_30D_FLAG',
                       'CLOCK_BATTERY_FLAG', 'IS_OVERCURRENT_A', 'IS_OVERVOLTAGE_A']
    for col in binary_features:
        if col in df.columns:
            df[col] = df[col].map({'是': 1, '否': 0, True: 1, False: 0, 'Y': 1, 'N': 0})
            df[col] = df[col].fillna(0)

    if 'is_removed' in df.columns:
        df['is_removed'] = df['is_removed'].astype(str).str.strip()
        df['is_removed'] = df['is_removed'].apply(
            lambda x: 1 if x in ['1', '1.0', '02', '03', '04'] else 0
        )

    feature_groups = {
        'COLL_FAIL_IA_7D': ['COLL_FAIL_IA_7D', 'COLL_FAIL_IB_7D', 'COLL_FAIL_IC_7D'],
        'COLL_FAIL_UA_7D': ['COLL_FAIL_UA_7D', 'COLL_FAIL_UB_7D', 'COLL_FAIL_UC_7D'],
        'COLL_FAIL_PFA_7D': ['COLL_FAIL_PFA_7D', 'COLL_FAIL_PFB_7D', 'COLL_FAIL_PFC_7D'],
        'COLL_COMPLETE_IA': ['COLL_COMPLETE_IA', 'COLL_COMPLETE_IB', 'COLL_COMPLETE_IC'],
        'COLL_COMPLETE_UA': ['COLL_COMPLETE_UA', 'COLL_COMPLETE_UB', 'COLL_COMPLETE_UC'],
        'COLL_COMPLETE_PFA': ['COLL_COMPLETE_PFA', 'COLL_COMPLETE_PFA', 'COLL_COMPLETE_PFA'],
        'COLL_COMPLETE_IA_7D': ['COLL_COMPLETE_IA_7D', 'COLL_COMPLETE_IB_7D', 'COLL_COMPLETE_IC_7D'],
        'COLL_COMPLETE_UA_7D': ['COLL_COMPLETE_UA_7D', 'COLL_COMPLETE_UB_7D', 'COLL_COMPLETE_UC_7D'],
        'COLL_COMPLETE_PFA_7D': ['COLL_COMPLETE_PFA_7D', 'COLL_COMPLETE_PFA_7D', 'COLL_COMPLETE_PFA_7D'],
        'COLL_COMPLETE_IA_14D': ['COLL_COMPLETE_IA_14D', 'COLL_COMPLETE_IB_14D', 'COLL_COMPLETE_IC_14D'],
        'COLL_COMPLETE_UA_14D': ['COLL_COMPLETE_UA_14D', 'COLL_COMPLETE_UB_14D', 'COLL_COMPLETE_UC_14D'],
        'COLL_COMPLETE_PFA_14D': ['COLL_COMPLETE_PFA_14D', 'COLL_COMPLETE_PFA_14D', 'COLL_COMPLETE_PFA_14D']
    }

    if 'WIRE_MODE' in df.columns:
        df['WIRE_MODE'] = df['WIRE_MODE'].astype(str)
        mask_01 = df['WIRE_MODE'].isin(['01', '1'])
        mask_02 = df['WIRE_MODE'].isin(['02', '2'])
        mask_03 = df['WIRE_MODE'].isin(['03', '3'])
        for target_col, source_cols in feature_groups.items():
            if target_col in df.columns or source_cols[0] in df.columns:
                if target_col not in df.columns and source_cols[0] in df.columns:
                    df[target_col] = df[source_cols[0]].copy()
                for col in source_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                if mask_02.any() and source_cols[1] in df.columns:
                    df.loc[mask_02, target_col] = (
                        df.loc[mask_02, source_cols[0]] + df.loc[mask_02, source_cols[1]]
                    ) / 2
                if mask_03.any() and source_cols[1] in df.columns and source_cols[2] in df.columns:
                    df.loc[mask_03, target_col] = (
                        df.loc[mask_03, source_cols[0]] +
                        df.loc[mask_03, source_cols[1]] +
                        df.loc[mask_03, source_cols[2]]
                    ) / 3

    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        df[col] = df[col].fillna(df[col].median())

    return df


# ==================== 预测函数 ====================

def predict_with_best_model(df, model_path='best_model.pkl'):
    """使用保存的最佳模型进行预测"""
    import pickle
    with open(model_path, 'rb') as f:
        saved_model = pickle.load(f)

    df = preprocess_features(df)

    if 'RUN_YEARS' in df.columns:
        df['score_years'] = df['RUN_YEARS'].apply(score_RUN_YEARS)
    else:
        df['score_years'] = 100

    if 'COMM_TIME_LOC' in df.columns:
        df['score_comm'] = df['COMM_TIME_LOC'].apply(score_comm_time)
    else:
        df['score_comm'] = 100

    if saved_model.get('module3_model') is not None:
        module3_scaler = saved_model['module3_scaler']
        module3_model = saved_model['module3_model']
        features_module3 = [
            'TEMP_AVG', 'TEMP_STD', 'TEMP_ERR_RATE', 'TEMP_AVG_7D', 'TEMP_STD_7D',
            'ME_CLOCK_DEVIATION_30D', 'OFFSET_TIME', 'UNCAP_30D', 'OUTAGE_30D',
            'IS_FLY', 'IS_REVERSE', 'IS_REVERSE_CREEP', 'RATE_IMBALANCE_30D_FLAG',
            'CLOCK_BATTERY_FLAG', 'IS_OVERCURRENT_A', 'OVERCURRENT_7D_NUM_A',
            'OVERCURRENT_14D_NUM_A', 'OVERCURRENT_30D_NUM_A', 'IS_OVERVOLTAGE_A',
            'OVERVOLTAGE_7D_NUM_A', 'OVERVOLTAGE_14D_NUM_A', 'OVERVOLTAGE_30D_NUM_A'
        ]
        X3 = df[features_module3].copy()
        X3 = X3.fillna(X3.median())
        X3_scaled = module3_scaler.transform(X3)
        anomaly_scores3 = module3_model.decision_function(X3_scaled)
        min_score = np.percentile(anomaly_scores3, 5)
        max_score = np.percentile(anomaly_scores3, 95)
        if max_score - min_score < 0.01:
            health_scores3 = np.ones_like(anomaly_scores3) * 50
        else:
            health_scores3 = (anomaly_scores3 - min_score) / (max_score - min_score) * 100
        df['score_module3'] = np.clip(health_scores3, 0, 100)
    else:
        df['score_module3'] = 100

    if saved_model.get('module4_model') is not None:
        module4_scaler = saved_model['module4_scaler']
        module4_model = saved_model['module4_model']
        features_module4 = [
            'COLL_FAIL_IA_7D', 'COLL_FAIL_UA_7D', 'COLL_FAIL_PFA_7D',
            'COLL_COMPLETE_IA', 'COLL_COMPLETE_IA_7D', 'COLL_COMPLETE_IA_14D',
            'COLL_COMPLETE_UA', 'COLL_COMPLETE_UA_7D', 'COLL_COMPLETE_UA_14D',
            'COLL_COMPLETE_PFA', 'COLL_COMPLETE_PFA_7D', 'COLL_COMPLETE_PFA_14D'
        ]
        X4 = df[features_module4].copy()
        X4 = X4.fillna(X4.median())
        X4_scaled = module4_scaler.transform(X4)
        anomaly_scores4 = module4_model.decision_function(X4_scaled)
        min_score = np.percentile(anomaly_scores4, 5)
        max_score = np.percentile(anomaly_scores4, 95)
        if max_score - min_score < 0.01:
            health_scores4 = np.ones_like(anomaly_scores4) * 50
        else:
            health_scores4 = (anomaly_scores4 - min_score) / (max_score - min_score) * 100
        df['score_module4'] = np.clip(health_scores4, 0, 100)
    else:
        df['score_module4'] = 100

    MFR_scores = saved_model.get('MFR_scores', {})
    if 'MFR' in df.columns and MFR_scores:
        df['score_MFR'] = df['MFR'].map(MFR_scores).fillna(100)
    else:
        df['score_MFR'] = 100

    weights = saved_model.get('weights', {
        'score_years': 0.25, 'score_comm': 0.10,
        'score_module3': 0.30, 'score_module4': 0.15, 'score_MFR': 0.20
    })
    total_score = np.zeros(len(df))
    for col, w in weights.items():
        if col in df.columns:
            total_score += df[col].values * w
    df['total_score'] = total_score

    def get_grade(score):
        if score < 60:
            return 'D - 建议维修/拆换'
        elif score < 80:
            return 'C - 重点关注'
        else:
            return 'B - 运行良好'
    df['grade'] = df['total_score'].apply(get_grade)
    if 'score_years' in df.columns:
        df.loc[df['score_years'] == 0, 'grade'] = 'E - 超龄建议直接拆除'

    return df