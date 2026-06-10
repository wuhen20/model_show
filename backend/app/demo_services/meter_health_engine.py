#!/usr/bin/env python
# coding: utf-8
"""
电表健康评价系统 — 训练/预测引擎
提供后台训练、预测、图表生成等功能
"""

import os
import io
import pickle
import base64
import threading
import traceback
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

from app.demo_services.meter_health_model import (
    preprocess_features,
    score_RUN_YEARS,
    score_comm_time,
    IsolationForestScorer,
    MFRAnalyzer,
    grid_search_isolation_forest,
)

plt.rcParams['font.sans-serif'] = ['Heiti TC', 'SimHei', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

# 任务存储（内存字典）
tasks: dict = {}


# ==================== 工具函数 ====================

def fig_to_base64(fig) -> str:
    """将 matplotlib figure 转为 base64 PNG 字符串"""
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)
    return img_base64


def _generate_grid(start, end, step):
    """生成参数网格列表"""
    values = []
    current = start
    while current <= end + 1e-9:
        values.append(current)
        current += step
    return values


def generate_charts(df: pd.DataFrame, task_id: str) -> dict:
    """生成所有图表，返回 base64 编码的图片字典"""
    charts = {}

    # --- 图表1: 综合评分分布 ---
    fig, ax = plt.subplots(figsize=(10, 6))
    if 'is_removed' in df.columns:
        removed = df[df['is_removed'] == 1]['total_score']
        running = df[df['is_removed'] == 0]['total_score']
        ax.hist(running, bins=30, alpha=0.7, label='运行中', color='#2ecc71', density=True)
        ax.hist(removed, bins=30, alpha=0.7, label='已拆除', color='#e74c3c', density=True)
        ax.legend()
    else:
        ax.hist(df['total_score'], bins=30, alpha=0.7, color='#3498db', density=True)
    ax.set_xlabel('综合健康评分')
    ax.set_ylabel('密度')
    ax.set_title('综合评分分布')
    ax.grid(True, alpha=0.3)
    charts['score_distribution'] = fig_to_base64(fig)

    # --- 图表2: 各模块评分箱线图 ---
    fig, ax = plt.subplots(figsize=(10, 6))
    score_cols = ['score_years', 'score_comm', 'score_module3', 'score_module4', 'score_MFR']
    score_cols = [c for c in score_cols if c in df.columns]
    data = [df[c].values for c in score_cols]
    bp = ax.boxplot(data, labels=['年限', '通讯', '电气', '采集', '厂商'], patch_artist=True)
    colors = ['#3498db', '#2ecc71', '#e74c3c', '#f39c12', '#9b59b6']
    for patch, color in zip(bp['boxes'], colors[:len(data)]):
        patch.set_facecolor(color)
        patch.set_alpha(0.6)
    ax.set_ylabel('评分')
    ax.set_title('各模块评分分布')
    ax.grid(True, alpha=0.3)
    charts['module_boxplot'] = fig_to_base64(fig)

    # --- 图表3: 厂商平均综合评分对比 ---
    if 'MFR' in df.columns:
        fig, ax = plt.subplots(figsize=(10, 6))
        mfr_avg = df.groupby('MFR')['total_score'].mean().sort_values()
        colors_bar = ['#e74c3c' if v < 60 else '#f39c12' if v < 80 else '#2ecc71' for v in mfr_avg.values]
        ax.barh(mfr_avg.index, mfr_avg.values, color=colors_bar)
        ax.set_xlabel('平均综合评分')
        ax.set_title('各厂商平均综合评分对比')
        ax.grid(True, alpha=0.3)
        for i, v in enumerate(mfr_avg.values):
            ax.text(v + 0.5, i, f'{v:.1f}', va='center', fontsize=9)
        charts['mfr_comparison'] = fig_to_base64(fig)

    # --- 图表4: 厂商拆除率对比 ---
    if 'MFR' in df.columns and 'is_removed' in df.columns:
        fig, ax = plt.subplots(figsize=(10, 6))
        mfr_removal = df.groupby('MFR')['is_removed'].mean().sort_values() * 100
        ax.barh(mfr_removal.index, mfr_removal.values, color='#e74c3c', alpha=0.7)
        ax.set_xlabel('拆除率 (%)')
        ax.set_title('各厂商拆除率对比')
        ax.grid(True, alpha=0.3)
        for i, v in enumerate(mfr_removal.values):
            ax.text(v + 0.3, i, f'{v:.1f}%', va='center', fontsize=9)
        charts['mfr_removal'] = fig_to_base64(fig)

    return charts


def generate_validation_charts(cv_results: dict) -> dict:
    """生成模型验证相关图表"""
    charts = {}

    # --- K-fold AUC 柱状图 ---
    if 'fold_aucs' in cv_results and cv_results['fold_aucs']:
        fig, ax = plt.subplots(figsize=(8, 5))
        folds = [f"折{i+1}" for i in range(len(cv_results['fold_aucs']))]
        aucs = cv_results['fold_aucs']
        mean_auc = np.mean(aucs) if aucs else 0
        bars = ax.bar(folds, aucs, color='#3498db', alpha=0.7)
        ax.axhline(y=mean_auc, color='#e74c3c', linestyle='--', linewidth=2, label=f'均值 AUC={mean_auc:.4f}')
        ax.set_ylim(0, 1)
        ax.set_ylabel('AUC')
        ax.set_title('K-fold 交叉验证 AUC')
        ax.legend()
        ax.grid(True, alpha=0.3)
        for bar, v in zip(bars, aucs):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01, f'{v:.4f}', ha='center', fontsize=9)
        charts['cv_auc'] = fig_to_base64(fig)

    # --- 拆除样本排名分位数分布 ---
    if 'removed_ranks' in cv_results and cv_results['removed_ranks']:
        fig, ax = plt.subplots(figsize=(8, 5))
        ranks = cv_results['removed_ranks']
        ax.hist(ranks, bins=20, color='#e74c3c', alpha=0.7, edgecolor='black')
        ax.axvline(x=0.2, color='#2ecc71', linestyle='--', linewidth=2, label='优秀线 (0.2)')
        ax.set_xlabel('排名分位数')
        ax.set_ylabel('拆除样本数量')
        ax.set_title('拆除样本排名分位数分布 (越小越好)')
        ax.legend()
        ax.grid(True, alpha=0.3)
        charts['removed_ranks'] = fig_to_base64(fig)

    return charts


# ==================== 训练任务 ====================

def run_training(task_id: str, filepath: str, optimize: bool, n_calls: int,
                 use_grid_search: bool = False,
                 n_est_start: int = 100, n_est_end: int = 500, n_est_step: int = 100,
                 max_samp_start: float = 0.5, max_samp_end: float = 1.0, max_samp_step: float = 0.1,
                 max_feat_start: float = 0.5, max_feat_end: float = 1.0, max_feat_step: float = 0.1):
    """后台执行训练任务"""
    task = tasks.get(task_id)
    if not task:
        return

    try:
        task['status'] = 'training'
        task['progress'] = 5
        task['message'] = '正在读取数据...'

        df = pd.read_csv(filepath)
        task['progress'] = 10
        task['message'] = f'数据读取完成，共 {len(df)} 条记录'

        task['message'] = '正在进行数据预处理...'
        df = preprocess_features(df)
        task['progress'] = 15

        # 模块1: 使用年限评分
        task['message'] = '模块1: 计算使用年限评分...'
        if 'RUN_YEARS' in df.columns:
            df['score_years'] = df['RUN_YEARS'].apply(score_RUN_YEARS)
        else:
            df['score_years'] = 100
        task['progress'] = 20

        # 模块2: 通讯模块评分
        task['message'] = '模块2: 计算通讯模块评分...'
        if 'COMM_TIME_LOC' in df.columns:
            df['score_comm'] = df['COMM_TIME_LOC'].apply(score_comm_time)
        else:
            df['score_comm'] = 100
        task['progress'] = 25

        # 模块3 & 模块4: 特征定义
        features_module3 = [
            'TEMP_AVG', 'TEMP_STD', 'TEMP_ERR_RATE', 'TEMP_AVG_7D', 'TEMP_STD_7D',
            'ME_CLOCK_DEVIATION_30D', 'OFFSET_TIME', 'UNCAP_30D', 'OUTAGE_30D',
            'IS_FLY', 'IS_REVERSE', 'IS_REVERSE_CREEP', 'RATE_IMBALANCE_30D_FLAG',
            'CLOCK_BATTERY_FLAG', 'IS_OVERCURRENT_A', 'OVERCURRENT_7D_NUM_A',
            'OVERCURRENT_14D_NUM_A', 'OVERCURRENT_30D_NUM_A', 'IS_OVERVOLTAGE_A',
            'OVERVOLTAGE_7D_NUM_A', 'OVERVOLTAGE_14D_NUM_A', 'OVERVOLTAGE_30D_NUM_A'
        ]
        features_module4 = [
            'COLL_FAIL_IA_7D', 'COLL_FAIL_UA_7D', 'COLL_FAIL_PFA_7D',
            'COLL_COMPLETE_IA', 'COLL_COMPLETE_IA_7D', 'COLL_COMPLETE_IA_14D',
            'COLL_COMPLETE_UA', 'COLL_COMPLETE_UA_7D', 'COLL_COMPLETE_UA_14D',
            'COLL_COMPLETE_PFA', 'COLL_COMPLETE_PFA_7D', 'COLL_COMPLETE_PFA_14D'
        ]
        missing3 = [f for f in features_module3 if f not in df.columns]
        missing4 = [f for f in features_module4 if f not in df.columns]

        module3_model = None
        module4_model = None

        has_label = 'is_removed' in df.columns and len(np.unique(df['is_removed'])) > 1

        if use_grid_search and has_label:
            n_estimators_grid = [int(x) for x in _generate_grid(n_est_start, n_est_end, n_est_step)]
            max_samples_grid = _generate_grid(max_samp_start, max_samp_end, max_samp_step)
            max_features_grid = _generate_grid(max_feat_start, max_feat_end, max_feat_step)

            if not missing3:
                task['message'] = '模块3: 网格搜索超参数优化...'
                X3_full = df[features_module3].copy().fillna(df[features_module3].median())
                y_removed = df['is_removed'].values
                m3_best_params, m3_grid_results = grid_search_isolation_forest(
                    X3_full, y_removed,
                    n_estimators_grid=n_estimators_grid,
                    max_samples_grid=max_samples_grid,
                    max_features_grid=max_features_grid,
                    random_state=42, verbose=False
                )
                module3_scorer = IsolationForestScorer(
                    features_module3, module_name="电气异常检测",
                    n_estimators=m3_best_params['n_estimators'],
                    max_samples=m3_best_params['max_samples'],
                    max_features=m3_best_params['max_features'],
                    use_optimization=False, verbose=False
                )
                df['score_module3'] = module3_scorer.train(X3_full)
                module3_model = module3_scorer
                module3_model.best_params = m3_best_params
                module3_model.grid_search_results = m3_grid_results
            else:
                df['score_module3'] = 100

            if not missing4:
                task['message'] = '模块4: 网格搜索超参数优化...'
                X4_full = df[features_module4].copy().fillna(df[features_module4].median())
                y_removed4 = df['is_removed'].values
                m4_best_params, m4_grid_results = grid_search_isolation_forest(
                    X4_full, y_removed4,
                    n_estimators_grid=n_estimators_grid,
                    max_samples_grid=max_samples_grid,
                    max_features_grid=max_features_grid,
                    random_state=42, verbose=False
                )
                module4_scorer = IsolationForestScorer(
                    features_module4, module_name="采集完整率检测",
                    n_estimators=m4_best_params['n_estimators'],
                    max_samples=m4_best_params['max_samples'],
                    max_features=m4_best_params['max_features'],
                    use_optimization=False, verbose=False
                )
                df['score_module4'] = module4_scorer.train(X4_full)
                module4_model = module4_scorer
                module4_model.best_params = m4_best_params
                module4_model.grid_search_results = m4_grid_results
            else:
                df['score_module4'] = 100

            task['progress'] = 55
        else:
            # 模块3: 电气异常检测
            task['message'] = '模块3: 电气异常检测 (Isolation Forest)...'
            if not missing3:
                X3 = df[features_module3].copy().fillna(df[features_module3].median())
                module3_scorer = IsolationForestScorer(
                    features_module3, module_name="电气异常检测",
                    n_estimators=250, max_samples=0.8, max_features=0.7,
                    use_optimization=(optimize and not use_grid_search),
                    optimize_n_calls=n_calls,
                    use_grid_search=False,
                    verbose=False
                )
                y_removed3 = df['is_removed'].values if has_label and optimize else None
                df['score_module3'] = module3_scorer.train(X3, y_removed3)
                module3_model = module3_scorer
            else:
                df['score_module3'] = 100
            task['progress'] = 45

            # 模块4: 采集完整率检测
            task['message'] = '模块4: 采集完整率检测 (Isolation Forest)...'
            if not missing4:
                X4 = df[features_module4].copy().fillna(df[features_module4].median())
                module4_scorer = IsolationForestScorer(
                    features_module4, module_name="采集完整率检测",
                    n_estimators=200, max_samples=0.8, max_features=1.0,
                    use_optimization=(optimize and not use_grid_search),
                    optimize_n_calls=n_calls,
                    use_grid_search=False,
                    verbose=False
                )
                y_removed4 = df['is_removed'].values if has_label and optimize else None
                df['score_module4'] = module4_scorer.train(X4, y_removed4)
                module4_model = module4_scorer
            else:
                df['score_module4'] = 100
            task['progress'] = 65

        # 模块5: 厂商质量评估
        task['message'] = '模块5: 生产厂商质量评估...'
        mfr_analyzer = MFRAnalyzer(MFR_col='MFR')
        if 'MFR' in df.columns:
            mfr_analyzer.analyze_MFRs(df, 'is_removed')
            df = mfr_analyzer.calculate_quality_score(df, 'is_removed',
                                                       use_health_score=True,
                                                       use_removal_rate=False)
        else:
            df['score_MFR'] = 100
        task['progress'] = 75

        # 综合评分
        task['message'] = '计算综合评分...'
        weights = {
            'score_years': 0.25, 'score_comm': 0.10,
            'score_module3': 0.30, 'score_module4': 0.15, 'score_MFR': 0.20
        }
        available_weights = {k: v for k, v in weights.items() if k in df.columns and v > 0}
        total_weight = sum(available_weights.values())
        if total_weight > 0:
            available_weights = {k: v / total_weight for k, v in available_weights.items()}

        total_score = np.zeros(len(df))
        for col, w in available_weights.items():
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
        task['progress'] = 85

        # ========== 模型验证 ==========
        task['message'] = '执行模型验证 (K-fold CV + AUC)...'
        validation_results = {}

        if 'is_removed' in df.columns and len(np.unique(df['is_removed'])) > 1:
            y_all = df['is_removed'].values
            train_auc = roc_auc_score(y_all, -df['total_score'])
            validation_results['train_auc'] = round(float(train_auc), 4)

            module_aucs = {}
            for mod_name, mod_col in [('module3', 'score_module3'), ('module4', 'score_module4')]:
                if mod_col in df.columns:
                    try:
                        auc = roc_auc_score(y_all, -df[mod_col])
                        module_aucs[mod_name] = round(float(auc), 4)
                    except Exception:
                        module_aucs[mod_name] = None
            validation_results['module_aucs'] = module_aucs

            skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
            full_pipeline_fold_aucs = []
            full_pipeline_removed_ranks = []

            for fold_idx, (train_idx, test_idx) in enumerate(skf.split(df, y_all)):
                df_train = df.iloc[train_idx].copy()
                df_test = df.iloc[test_idx].copy()
                y_test_fold = y_all[test_idx]

                if 'RUN_YEARS' in df_train.columns:
                    df_test['score_years'] = df_test['RUN_YEARS'].apply(score_RUN_YEARS)
                else:
                    df_test['score_years'] = 100

                if 'COMM_TIME_LOC' in df_train.columns:
                    df_test['score_comm'] = df_test['COMM_TIME_LOC'].apply(score_comm_time)
                else:
                    df_test['score_comm'] = 100

                if not missing3:
                    X3_train = df_train[features_module3].copy().fillna(df_train[features_module3].median())
                    X3_test = df_test[features_module3].copy().fillna(df_test[features_module3].median())
                    cv_m3 = IsolationForestScorer(
                        features_module3, module_name="CV-M3",
                        n_estimators=module3_model.n_estimators if module3_model else 250,
                        max_samples=module3_model.max_samples if module3_model else 0.8,
                        max_features=module3_model.max_features if module3_model else 0.7,
                        use_optimization=False, verbose=False
                    )
                    cv_m3.train(X3_train)
                    df_test['score_module3'] = cv_m3.predict(X3_test)
                else:
                    df_test['score_module3'] = 100

                if not missing4:
                    X4_train = df_train[features_module4].copy().fillna(df_train[features_module4].median())
                    X4_test = df_test[features_module4].copy().fillna(df_test[features_module4].median())
                    cv_m4 = IsolationForestScorer(
                        features_module4, module_name="CV-M4",
                        n_estimators=module4_model.n_estimators if module4_model else 200,
                        max_samples=module4_model.max_samples if module4_model else 0.8,
                        max_features=module4_model.max_features if module4_model else 1.0,
                        use_optimization=False, verbose=False
                    )
                    cv_m4.train(X4_train)
                    df_test['score_module4'] = cv_m4.predict(X4_test)
                else:
                    df_test['score_module4'] = 100

                if 'MFR' in df_train.columns:
                    cv_mfr = MFRAnalyzer(MFR_col='MFR')
                    cv_mfr.analyze_MFRs(df_train, 'is_removed')
                    df_test = cv_mfr.calculate_quality_score(df_test, 'is_removed',
                                                              use_health_score=True,
                                                              use_removal_rate=False)
                else:
                    df_test['score_MFR'] = 100

                total_score_fold = np.zeros(len(df_test))
                for col, w in available_weights.items():
                    if col in df_test.columns:
                        total_score_fold += df_test[col].values * w
                df_test['total_score'] = total_score_fold

                if len(np.unique(y_test_fold)) > 1:
                    fold_auc = roc_auc_score(y_test_fold, -df_test['total_score'])
                    full_pipeline_fold_aucs.append(round(float(fold_auc), 4))

                for i, status in enumerate(y_test_fold):
                    if status == 1:
                        rank = np.sum(total_score_fold <= total_score_fold[i]) / len(total_score_fold)
                        full_pipeline_removed_ranks.append(round(float(rank), 4))

            validation_results['fold_aucs'] = full_pipeline_fold_aucs
            validation_results['cv_mean_auc'] = round(float(np.mean(full_pipeline_fold_aucs)), 4) if full_pipeline_fold_aucs else 0
            validation_results['cv_std_auc'] = round(float(np.std(full_pipeline_fold_aucs)), 4) if full_pipeline_fold_aucs else 0
            validation_results['removed_ranks'] = full_pipeline_removed_ranks
            validation_results['removed_rank_mean'] = round(float(np.mean(full_pipeline_removed_ranks)), 4) if full_pipeline_removed_ranks else 1.0
            validation_results['overfit_gap'] = round(float(train_auc - validation_results['cv_mean_auc']), 4)
            validation_results['cv_note'] = '使用 StratifiedKFold 对完整评分流水线进行5折交叉验证'
        else:
            validation_results['warning'] = '数据中无 is_removed 列或只有单一类别，无法进行验证'

        task['progress'] = 95

        # 生成图表
        task['message'] = '生成可视化图表...'
        charts = generate_charts(df, task_id)
        validation_charts = generate_validation_charts(validation_results)

        # 保存模型
        UPLOAD_DIR = task.get('upload_dir', 'uploads')
        model_path = os.path.join(UPLOAD_DIR, f"{task_id}_model.pkl")
        save_data = {
            'module3_model': module3_model.model if module3_model else None,
            'module3_scaler': module3_model.scaler if module3_model else None,
            'module3_params': module3_model.best_params if module3_model else None,
            'module4_model': module4_model.model if module4_model else None,
            'module4_scaler': module4_model.scaler if module4_model else None,
            'module4_params': module4_model.best_params if module4_model else None,
            'mfr_scores': mfr_analyzer.MFR_quality_score if 'MFR' in df.columns else {},
            'weights': available_weights,
            'features_module3': features_module3,
            'features_module4': features_module4,
        }
        with open(model_path, 'wb') as f:
            pickle.dump(save_data, f)

        result_csv_path = os.path.join(UPLOAD_DIR, f"{task_id}_result.csv")
        df.to_csv(result_csv_path, index=False, encoding='utf-8-sig')

        # 统计信息
        score_cols = ['score_years', 'score_comm', 'score_module3', 'score_module4', 'score_MFR', 'total_score']
        score_cols = [c for c in score_cols if c in df.columns]
        stats = {}
        for col in score_cols:
            stats[col] = {
                'mean': round(float(df[col].mean()), 2),
                'std': round(float(df[col].std()), 2),
                'min': round(float(df[col].min()), 2),
                'max': round(float(df[col].max()), 2),
                'median': round(float(df[col].median()), 2),
            }

        grade_counts = {str(k): int(v) for k, v in df['grade'].value_counts().items()}

        mfr_stats = {}
        if 'MFR' in df.columns:
            mfr_group = df.groupby('MFR')['total_score'].agg(['mean', 'count', 'std'])
            for mfr, row in mfr_group.iterrows():
                mfr_stats[str(mfr)] = {
                    'mean': round(float(row['mean']), 2),
                    'count': int(row['count']),
                    'std': round(float(row['std']), 2) if not pd.isna(row['std']) else 0,
                }

        grid_search_data = {}
        if use_grid_search:
            if module3_model and module3_model.grid_search_results:
                grid_search_data['module3'] = {
                    'module_name': '电气异常检测',
                    'best_params': module3_model.best_params if module3_model else {},
                    'grid_results': module3_model.grid_search_results,
                }
            if module4_model and module4_model.grid_search_results:
                grid_search_data['module4'] = {
                    'module_name': '采集完整率检测',
                    'best_params': module4_model.best_params if module4_model else {},
                    'grid_results': module4_model.grid_search_results,
                }

        task['status'] = 'completed'
        task['progress'] = 100
        task['message'] = '训练完成！'
        task['result'] = {
            'stats': stats,
            'grade_counts': grade_counts,
            'mfr_stats': mfr_stats,
            'charts': charts,
            'validation': validation_results,
            'validation_charts': validation_charts,
            'weights': {k: round(float(v), 4) for k, v in available_weights.items()},
            'model_path': model_path,
            'result_csv_path': result_csv_path,
            'total_rows': len(df),
            'grid_search': grid_search_data,
            'use_grid_search': use_grid_search,
        }

    except Exception as e:
        task['status'] = 'error'
        task['message'] = f'训练失败: {str(e)}'
        task['error_detail'] = traceback.format_exc()


# ==================== 预测任务 ====================

def run_prediction(predict_task_id: str, filepath: str, model_path: str):
    """后台执行预测任务"""
    task = tasks.get(predict_task_id)
    if not task:
        return

    try:
        task['status'] = 'predicting'
        task['progress'] = 10
        task['message'] = '读取预测数据...'

        df = pd.read_csv(filepath)
        task['progress'] = 20
        task['message'] = f'数据读取完成，共 {len(df)} 条记录'

        with open(model_path, 'rb') as f:
            saved_model = pickle.load(f)

        df = preprocess_features(df)
        task['progress'] = 30

        if 'RUN_YEARS' in df.columns:
            df['score_years'] = df['RUN_YEARS'].apply(score_RUN_YEARS)
        else:
            df['score_years'] = 100
        task['progress'] = 40

        if 'COMM_TIME_LOC' in df.columns:
            df['score_comm'] = df['COMM_TIME_LOC'].apply(score_comm_time)
        else:
            df['score_comm'] = 100
        task['progress'] = 50

        # 模块3 预测
        if saved_model.get('module3_model') is not None:
            features3 = saved_model.get('features_module3', [
                'TEMP_AVG', 'TEMP_STD', 'TEMP_ERR_RATE', 'TEMP_AVG_7D', 'TEMP_STD_7D',
                'ME_CLOCK_DEVIATION_30D', 'OFFSET_TIME', 'UNCAP_30D', 'OUTAGE_30D',
                'IS_FLY', 'IS_REVERSE', 'IS_REVERSE_CREEP', 'RATE_IMBALANCE_30D_FLAG',
                'CLOCK_BATTERY_FLAG', 'IS_OVERCURRENT_A', 'OVERCURRENT_7D_NUM_A',
                'OVERCURRENT_14D_NUM_A', 'OVERCURRENT_30D_NUM_A', 'IS_OVERVOLTAGE_A',
                'OVERVOLTAGE_7D_NUM_A', 'OVERVOLTAGE_14D_NUM_A', 'OVERVOLTAGE_30D_NUM_A'
            ])
            available3 = [f for f in features3 if f in df.columns]
            if available3:
                X3 = df[available3].copy().fillna(df[available3].median())
                scaler3 = saved_model['module3_scaler']
                model3 = saved_model['module3_model']
                X3_aligned = X3.reindex(columns=features3, fill_value=0)
                X3_scaled = scaler3.transform(X3_aligned)
                anomaly3 = model3.decision_function(X3_scaled)
                min_s = np.percentile(anomaly3, 5)
                max_s = np.percentile(anomaly3, 95)
                if max_s - min_s < 0.01:
                    df['score_module3'] = 50
                else:
                    df['score_module3'] = np.clip((anomaly3 - min_s) / (max_s - min_s) * 100, 0, 100)
            else:
                df['score_module3'] = 100
        else:
            df['score_module3'] = 100
        task['progress'] = 65

        # 模块4 预测
        if saved_model.get('module4_model') is not None:
            features4 = saved_model.get('features_module4', [
                'COLL_FAIL_IA_7D', 'COLL_FAIL_UA_7D', 'COLL_FAIL_PFA_7D',
                'COLL_COMPLETE_IA', 'COLL_COMPLETE_IA_7D', 'COLL_COMPLETE_IA_14D',
                'COLL_COMPLETE_UA', 'COLL_COMPLETE_UA_7D', 'COLL_COMPLETE_UA_14D',
                'COLL_COMPLETE_PFA', 'COLL_COMPLETE_PFA_7D', 'COLL_COMPLETE_PFA_14D'
            ])
            available4 = [f for f in features4 if f in df.columns]
            if available4:
                X4 = df[available4].copy().fillna(df[available4].median())
                scaler4 = saved_model['module4_scaler']
                model4 = saved_model['module4_model']
                X4_aligned = X4.reindex(columns=features4, fill_value=0)
                X4_scaled = scaler4.transform(X4_aligned)
                anomaly4 = model4.decision_function(X4_scaled)
                min_s = np.percentile(anomaly4, 5)
                max_s = np.percentile(anomaly4, 95)
                if max_s - min_s < 0.01:
                    df['score_module4'] = 50
                else:
                    df['score_module4'] = np.clip((anomaly4 - min_s) / (max_s - min_s) * 100, 0, 100)
            else:
                df['score_module4'] = 100
        else:
            df['score_module4'] = 100
        task['progress'] = 80

        mfr_scores = saved_model.get('mfr_scores', {})
        if 'MFR' in df.columns and mfr_scores:
            df['score_MFR'] = df['MFR'].map(mfr_scores).fillna(100)
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
        task['progress'] = 95

        UPLOAD_DIR = task.get('upload_dir', 'uploads')
        result_csv_path = os.path.join(UPLOAD_DIR, f"{predict_task_id}_predict_result.csv")
        df.to_csv(result_csv_path, index=False, encoding='utf-8-sig')

        score_cols = ['score_years', 'score_comm', 'score_module3', 'score_module4', 'score_MFR', 'total_score']
        score_cols = [c for c in score_cols if c in df.columns]
        stats = {}
        for col in score_cols:
            stats[col] = {
                'mean': round(float(df[col].mean()), 2),
                'std': round(float(df[col].std()), 2),
                'min': round(float(df[col].min()), 2),
                'max': round(float(df[col].max()), 2),
                'median': round(float(df[col].median()), 2),
            }

        grade_counts = {str(k): int(v) for k, v in df['grade'].value_counts().items()}

        display_cols = ['meter_id', 'MFR', 'total_score', 'grade',
                        'score_years', 'score_comm', 'score_module3', 'score_module4', 'score_MFR']
        display_cols = [c for c in display_cols if c in df.columns]
        de_meters = df[df['grade'].str.contains('D|E', na=False)]
        top_risk = de_meters.nsmallest(20, 'total_score')[display_cols].to_dict('records') if len(de_meters) > 0 else []

        task['status'] = 'completed'
        task['progress'] = 100
        task['message'] = '预测完成！'
        task['result'] = {
            'stats': stats,
            'grade_counts': grade_counts,
            'top_risk_meters': top_risk,
            'result_csv_path': result_csv_path,
            'total_rows': len(df),
            'de_count': len(de_meters),
        }

    except Exception as e:
        task['status'] = 'error'
        task['message'] = f'预测失败: {str(e)}'
        task['error_detail'] = traceback.format_exc()