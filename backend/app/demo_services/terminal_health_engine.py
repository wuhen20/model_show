#!/usr/bin/env python
# coding: utf-8

# In[1]:


"""
终端健康评分系统
包含模块：
1. 使用年限评分
2. 通讯评分 (COMM_TIME_LOC + COMM_TIME_DIST)
3. 终端自身特征检测 (Isolation Forest + 超参数优化)
4. 下挂设备特征检测 (Isolation Forest + 超参数优化)
5. 生产厂商质量评估
6. 综合评分与阈值校准
"""

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # 非交互式后端，避免 Web 环境下弹窗
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


# In[2]:


plt.rcParams['font.sans-serif'] = ['Heiti TC'] 
plt.rcParams['axes.unicode_minus'] = False


# ==================== 辅助函数 ====================

def plot_score_distribution(scores, is_removed, title="分数分布"):
    """绘制分数分布图"""
    plt.figure(figsize=(10, 6))
    
    # 分离拆除和运行样本
    removed_scores = scores[is_removed == 1]
    normal_scores = scores[is_removed == 0]
    
    # 绘制直方图
    plt.hist(normal_scores, bins=30, alpha=0.7, label='运行中', color='green', density=True)
    plt.hist(removed_scores, bins=30, alpha=0.7, label='已拆除', color='red', density=True)
    
    plt.xlabel('健康分数')
    plt.ylabel('密度')
    plt.title(f'{title} - 拆除样本 vs 运行样本')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()


def optimize_isolation_forest(X, y_removed=None, n_calls=30, random_state=42, verbose=True):
    """
    使用贝叶斯优化调优 Isolation Forest 的超参数
    """
    
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
                
        except Exception as e:
            return 999
    
    if verbose:
        print("开始超参数优化（贝叶斯优化）...")
        print(f"搜索空间: {len(space)} 个参数")
        print(f"迭代次数: {n_calls}")
    
    result = gp_minimize(
        objective, 
        space, 
        n_calls=n_calls,
        n_initial_points=10,
        acq_func='EI',
        random_state=random_state,
        verbose=False
    )
    
    best_params = {
        'n_estimators': int(result.x[0]),
        'max_samples': float(result.x[1]),
        'max_features': float(result.x[2])
    }
    
    if verbose:
        print("\n" + "="*60)
        print("优化完成！最佳参数：")
        print("="*60)
        print(f"  n_estimators: {best_params['n_estimators']}")
        print(f"  max_samples: {best_params['max_samples']:.4f}")
        print(f"  max_features: {best_params['max_features']:.4f}")
        print(f"\n最佳目标值 (AUC): {max(0, -result.fun):.4f}")
    
    return best_params, result


def grid_search_isolation_forest(X, y_removed,
                                  n_estimators_start=100, n_estimators_end=500, n_estimators_step=100,
                                  max_samples_start=0.5, max_samples_end=1.0, max_samples_step=0.1,
                                  max_features_start=0.5, max_features_end=1.0, max_features_step=0.1,
                                  random_state=42, verbose=True):
    """
    使用网格搜索调优 Isolation Forest 的 n_estimators, max_samples, max_features 超参数
    
    参数:
    - X: 特征数据 DataFrame
    - y_removed: 拆除标签数组 (1=拆除, 0=运行)
    - n_estimators_start/end/step: n_estimators 的搜索范围
    - max_samples_start/end/step: max_samples 的搜索范围
    - max_features_start/end/step: max_features 的搜索范围
    
    返回:
    - best_params: 最佳参数 dict
    - grid_results: 完整结果列表 (用于热力图展示)
    """
    import itertools
    
    # 生成参数网格
    n_estimators_range = list(range(int(n_estimators_start), int(n_estimators_end) + 1, int(n_estimators_step)))
    max_samples_range = np.arange(max_samples_start, max_samples_end + max_samples_step / 2, max_samples_step).tolist()
    max_samples_range = [round(min(x, 1.0), 4) for x in max_samples_range]
    max_samples_range = sorted(list(set(max_samples_range)))
    max_features_range = np.arange(max_features_start, max_features_end + max_features_step / 2, max_features_step).tolist()
    max_features_range = [round(min(x, 1.0), 4) for x in max_features_range]
    max_features_range = sorted(list(set(max_features_range)))
    
    if verbose:
        print(f"Grid Search 参数网格:")
        print(f"  n_estimators: {n_estimators_range}")
        print(f"  max_samples: {max_samples_range}")
        print(f"  max_features: {max_features_range}")
        print(f"  总组合数: {len(n_estimators_range) * len(max_samples_range) * len(max_features_range)}")
    
    grid_results = []
    best_auc = -1
    best_params = {'n_estimators': n_estimators_range[0], 'max_samples': max_samples_range[0], 'max_features': max_features_range[0]}
    
    # 检查 y_removed 是否有效
    y_arr = np.array(y_removed)
    has_valid_y = len(np.unique(y_arr)) > 1
    
    for n_est, max_samp, max_feat in itertools.product(n_estimators_range, max_samples_range, max_features_range):
        try:
            if has_valid_y:
                skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state)
                auc_scores = []
                
                for train_idx, val_idx in skf.split(X, y_arr):
                    X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
                    y_val = y_arr[val_idx]
                    
                    scaler = StandardScaler()
                    X_train_scaled = scaler.fit_transform(X_train)
                    X_val_scaled = scaler.transform(X_val)
                    
                    model = IsolationForest(
                        n_estimators=int(n_est),
                        max_samples=float(max_samp),
                        max_features=float(max_feat),
                        random_state=random_state,
                        contamination='auto',
                        bootstrap=False
                    )
                    model.fit(X_train_scaled)
                    scores = model.decision_function(X_val_scaled)
                    
                    if len(np.unique(y_val)) > 1:
                        auc = roc_auc_score(y_val, -scores)
                        auc_scores.append(auc)
                
                mean_auc = np.mean(auc_scores) if auc_scores else 0.0
            else:
                scaler = StandardScaler()
                X_scaled = scaler.fit_transform(X)
                model = IsolationForest(
                    n_estimators=int(n_est),
                    max_samples=float(max_samp),
                    max_features=float(max_feat),
                    random_state=random_state,
                    contamination='auto',
                    bootstrap=False
                )
                model.fit(X_scaled)
                anomaly_scores = model.decision_function(X_scaled)
                mean_auc = np.std(anomaly_scores)
            
            result_entry = {
                'n_estimators': int(n_est),
                'max_samples': round(float(max_samp), 4),
                'max_features': round(float(max_feat), 4),
                'auc': round(float(mean_auc), 4)
            }
            grid_results.append(result_entry)
            
            if mean_auc > best_auc:
                best_auc = mean_auc
                best_params = {'n_estimators': int(n_est), 'max_samples': round(float(max_samp), 4), 'max_features': round(float(max_feat), 4)}
            
            if verbose:
                print(f"  n_estimators={n_est}, max_samples={max_samp:.2f}, max_features={max_feat:.2f} -> AUC={mean_auc:.4f}")
                
        except Exception as e:
            grid_results.append({
                'n_estimators': int(n_est),
                'max_samples': round(float(max_samp), 4),
                'max_features': round(float(max_feat), 4),
                'auc': 0.0,
                'error': str(e)
            })
    
    if verbose:
        print(f"\nGrid Search 完成！最佳参数:")
        print(f"  n_estimators: {best_params['n_estimators']}")
        print(f"  max_samples: {best_params['max_samples']}")
        print(f"  max_features: {best_params['max_features']}")
        print(f"  最佳 AUC: {best_auc:.4f}")
    
    return best_params, grid_results


# ==================== 模块1：使用年限评分 ====================

def score_RUN_YEARS(years):
    """
    模块1：使用年限评分
    5年及以下: 100分
    5-8年: 线性递减到0分
    8年以上: 0分
    """
    if years <= 5:
        return 100
    elif years >= 8:
        return 0
    else:
        return 100 * (1 - (years - 5) / 3)

def score_comm_time(comm_time):
    """
    模块2：通讯时长评分（通用公式，适用于COMM_TIME_LOC和COMM_TIME_DIST）
    10s以下: 100分
    10-180s: 指数衰减（前期慢后期快，符合通讯恶化规律）
    180s及以上: 0分
    """
    t = comm_time
    if t <= 10:
        return 100
    elif t >= 180:
        return 0
    else:
        # 使用指数衰减，公式: 100 * e^(-k*(t-10))，k控制衰减速度
        k = 0.00465
        score = 100 * np.exp(-k * (t - 10))
        return max(0, min(100, score))


def score_comm_combined(COMM_TIME_LOC, COMM_TIME_DIST):
    """
    模块2：通讯综合评分
    分别对本地通讯时长和远程通讯时长打分，取平均
    """
    score_loc = score_comm_time(COMM_TIME_LOC)
    score_dist = score_comm_time(COMM_TIME_DIST)
    return (score_loc + score_dist) / 2.0


# ==================== 模块2：Isolation Forest 模块（支持超参数优化）====================

class IsolationForestScorer:
    """
    封装Isolation Forest，支持训练、评分、交叉验证、阈值校准、超参数优化
    """
    
    def __init__(self, feature_names, module_name="", n_estimators=250, max_samples=0.8, max_features=0.7,
                 use_optimization=False, optimize_n_calls=30, verbose=True):
        """
        参数:
        - verbose: 是否打印详细信息（交叉验证时设为False）
        """
        self.feature_names = feature_names
        self.module_name = module_name
        self.n_estimators = n_estimators
        self.max_samples = max_samples
        self.max_features = max_features
        self.use_optimization = use_optimization
        self.optimize_n_calls = optimize_n_calls
        self.verbose = verbose
        self.model = None
        self.scaler = None
        self.scores_history = []
        self.best_params = {}
        self.repair_threshold = 60
        self.warning_threshold = 80
        
    def train(self, X, y_removed=None):
        """
        训练模型
        """
        # 标准化
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # 如果启用超参数优化且有拆除标签
        if self.use_optimization and y_removed is not None and len(np.unique(y_removed)) > 1:
            if self.verbose:
                print(f"\n  [{self.module_name}] 开始超参数优化...")
            best_params, opt_result = optimize_isolation_forest(
                X, 
                y_removed, 
                n_calls=self.optimize_n_calls,
                random_state=42,
                verbose=self.verbose
            )
            
            # 更新参数
            self.n_estimators = best_params['n_estimators']
            self.max_samples = best_params['max_samples']
            self.max_features = best_params['max_features']
            self.best_params = best_params
            
            if self.verbose:
                print(f"\n  [{self.module_name}] 使用优化后的参数训练模型")
                print(f"    n_estimators: {self.n_estimators}")
                print(f"    max_samples: {self.max_samples:.3f}")
                print(f"    max_features: {self.max_features:.3f}")
        else:
            if self.verbose:
                print(f"\n  [{self.module_name}] 使用默认参数训练模型")
        
        # 训练IForest
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            max_features=self.max_features,
            random_state=42,
            contamination='auto',
            bootstrap=False
        )
        self.model.fit(X_scaled)
        
        # 计算原始异常分数
        anomaly_scores = self.model.decision_function(X_scaled)
        
        # 转换为健康分数 (0-100)
        health_scores = self._anomaly_to_health(anomaly_scores)
        
        return health_scores
    
    def _anomaly_to_health(self, anomaly_scores):
        """将异常分数转换为0-100健康分（越高越健康）"""
        min_score = np.percentile(anomaly_scores, 5)
        max_score = np.percentile(anomaly_scores, 95)
        
        if max_score - min_score < 0.01:
            normalized = np.ones_like(anomaly_scores) * 0.5
        else:
            normalized = (anomaly_scores - min_score) / (max_score - min_score)
        
        health_scores = np.clip(normalized * 100, 0, 100)
        return health_scores
    
    def predict(self, X):
        """对新数据预测健康分数"""
        X_scaled = self.scaler.transform(X)
        anomaly_scores = self.model.decision_function(X_scaled)
        return self._anomaly_to_health(anomaly_scores)
    
    def predict_anomaly(self, X):
        """预测异常标签（-1表示异常，1表示正常）"""
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)
    
    def cross_validate(self, X, y_removed, n_folds=5):
        """
        交叉验证：验证模型对拆除样本的区分能力
        """
        y_removed = np.array(y_removed)
        removed_indices = np.where(y_removed == 1)[0]
        
        if len(removed_indices) == 0:
            if self.verbose:
                print(f"  [{self.module_name}] 警告：没有拆除样本，无法进行交叉验证")
            return None
        
        kf = KFold(n_splits=n_folds, shuffle=True, random_state=42)
        removed_ranks = []
        fold_aucs = []
        
        if self.verbose:
            print(f"\n  [{self.module_name}] 开始 {n_folds} 折交叉验证...")
        
        for fold, (train_idx, test_idx) in enumerate(kf.split(X), 1):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_test_removed = y_removed[test_idx]
            
            # 训练模型 - 关键：设置 verbose=False 和 use_optimization=False
            temp_model = IsolationForestScorer(
                self.feature_names, 
                self.module_name,
                self.n_estimators, 
                self.max_samples, 
                self.max_features,
                use_optimization=False,
                verbose=False
            )
            temp_model.train(X_train)
            
            # 预测测试集
            test_scores = temp_model.predict(X_test)
            
            # 计算AUC
            if len(np.unique(y_test_removed)) > 1:
                auc = roc_auc_score(y_test_removed, -test_scores)
                fold_aucs.append(auc)
            
            # 计算每个拆除样本的排名分位数
            for i, is_removed in enumerate(y_test_removed):
                if is_removed == 1:
                    rank = np.sum(test_scores <= test_scores[i]) / len(test_scores)
                    removed_ranks.append(rank)
            
            if self.verbose and fold % 2 == 0:
                print(f"    完成折 {fold}/{n_folds}")
        
        avg_rank = np.mean(removed_ranks) if removed_ranks else 1.0
        mean_auc = np.mean(fold_aucs) if fold_aucs else 0
        
        if self.verbose:
            print(f"\n  [{self.module_name}] 交叉验证结果:")
            print(f"    拆除样本平均排名分位数: {avg_rank:.3f} (越小越好，<0.2优秀)")
            print(f"    平均 AUC: {mean_auc:.3f} (越大越好，>0.7优秀)")
        
        return removed_ranks
    
    def grid_search_train(self, X, y_removed,
                           n_estimators_start=100, n_estimators_end=500, n_estimators_step=100,
                           max_samples_start=0.5, max_samples_end=1.0, max_samples_step=0.1,
                           max_features_start=0.5, max_features_end=1.0, max_features_step=0.1):
        """
        使用 Grid Search 训练模型
        返回: (health_scores, best_params, grid_results)
        """
        if self.verbose:
            print(f"\n  [{self.module_name}] 开始 Grid Search...")
        
        best_params, grid_results = grid_search_isolation_forest(
            X, y_removed,
            n_estimators_start=n_estimators_start,
            n_estimators_end=n_estimators_end,
            n_estimators_step=n_estimators_step,
            max_samples_start=max_samples_start,
            max_samples_end=max_samples_end,
            max_samples_step=max_samples_step,
            max_features_start=max_features_start,
            max_features_end=max_features_end,
            max_features_step=max_features_step,
            random_state=42,
            verbose=self.verbose
        )
        
        self.n_estimators = best_params['n_estimators']
        self.max_samples = best_params['max_samples']
        self.max_features = best_params['max_features']
        self.best_params = best_params
        
        if self.verbose:
            print(f"\n  [{self.module_name}] 使用 Grid Search 最佳参数训练模型")
        
        # 用最佳参数训练
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        self.model = IsolationForest(
            n_estimators=self.n_estimators,
            max_samples=self.max_samples,
            max_features=self.max_features,
            random_state=42,
            contamination='auto',
            bootstrap=False
        )
        self.model.fit(X_scaled)
        
        anomaly_scores = self.model.decision_function(X_scaled)
        health_scores = self._anomaly_to_health(anomaly_scores)
        
        return health_scores, best_params, grid_results
    
    def calibrate_thresholds(self, X, y_removed):
        """
        基于拆除样本的分数分布校准阈值
        """
        health_scores = self.predict(X)
        removed_scores = health_scores[y_removed == 1]
        
        if len(removed_scores) == 0:
            if self.verbose:
                print(f"  [{self.module_name}] 警告：没有拆除样本，无法校准阈值，使用默认值")
            return 60, 80
        
        q25 = np.percentile(removed_scores, 25)
        q75 = np.percentile(removed_scores, 75)
        
        repair_threshold = q25
        warning_threshold = q75
        
        self.repair_threshold = repair_threshold
        self.warning_threshold = warning_threshold
        
        if self.verbose:
            print(f"\n  [{self.module_name}] 阈值校准结果:")
            print(f"    拆除样本分数分布: min={removed_scores.min():.1f}, "
                  f"25%={q25:.1f}, 50%={np.median(removed_scores):.1f}, "
                  f"75%={q75:.1f}, max={removed_scores.max():.1f}")
            print(f"    建议: {repair_threshold:.1f}分以下 -> 建议维修/拆换")
            print(f"    建议: {warning_threshold:.1f}分 - {repair_threshold:.1f}分 -> 重点关注")
        
        return repair_threshold, warning_threshold


# ==================== 模块5：生产厂商质量评估 ====================

class MFRAnalyzer:
    """
    生产厂商分析和质量评估模块
    """
    
    def __init__(self, MFR_col='MFR'):
        self.MFR_col = MFR_col
        self.MFR_stats = {}
        self.MFR_quality_score = {}
        self.cluster_model = None
        
    def analyze_MFRs(self, df, is_removed_col='is_removed'):
        """分析各厂商的基本统计信息"""
        if self.MFR_col not in df.columns:
            print("  ⚠️ 数据中没有生产厂商信息，跳过厂商分析")
            return None
        
        MFRs = df[self.MFR_col].unique()
        print("\n  " + "="*56)
        print("  厂商基本信息统计")
        print("  " + "="*56)
        
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
                'MFR': mfr,
                'total_count': total_count,
                'removed_count': removed_count,
                'removal_rate': removal_rate,
                'avg_health_score': avg_health,
                'median_health_score': median_health
            })
            
            print(f"\n  厂商: {mfr}")
            print(f"    样本数量: {total_count}")
            print(f"    拆除数量: {removed_count}")
            print(f"    拆除率: {removal_rate:.2%}")
            #print(f"    平均健康分: {avg_health:.1f}")
        
        self.MFR_stats = stats
        return stats
    
    def calculate_quality_score(self, df, is_removed_col='is_removed', 
                                 use_health_score=True, use_removal_rate=True):
        """
        计算厂商质量评分（0-100分）
        """
        if self.MFR_col not in df.columns:
            print("  ⚠️ 没有厂商信息，所有厂商质量分设为100")
            df['score_MFR'] = 100
            return df
        
        MFRs = df[self.MFR_col].unique()
        quality_scores = {}
        health_cols = [c for c in ['score_module3', 'score_module4'] if c in df.columns]
        
        for mfr in MFRs:
            mfr_data = df[df[self.MFR_col] == mfr]
            score = 100
            
            # 基于拆除率扣分
            if use_removal_rate and is_removed_col in df.columns:
                removal_rate = mfr_data[mfr_data[is_removed_col] == 1].shape[0] / len(mfr_data)
                removal_penalty = min(30, removal_rate * 100 * 0.6)
                score -= removal_penalty
            
            '''# 基于平均健康分调整
            if use_health_score and 'total_score' in df.columns:
                avg_health = mfr_data['total_score'].mean()
                if avg_health < 70:
                    health_penalty = (70 - avg_health) * 0.5
                    score -= min(20, health_penalty)
                elif avg_health > 85:
                    bonus = min(10, (avg_health - 85) * 0.5)
                    score += bonus
                    '''
            # 基于该厂商在终端特征/下挂设备模块上的平均健康分调整
            if use_health_score and health_cols:
                # 先对每行取模块3/4的平均，再对该厂商所有样本取均值
                avg_health = mfr_data[health_cols].mean(axis=1).mean()
                anchor = 75  # 锚点分：高于加分，低于扣分
                if avg_health < anchor:
                    health_penalty = min(30, (anchor - avg_health) * 0.8)
                    score -= health_penalty
                else:
                    bonus = min(10, (avg_health - anchor) * 0.5)
                    score += bonus

            quality_scores[mfr] = max(0, min(100, score))
        
        self.MFR_quality_score = quality_scores
        
        # 添加到DataFrame
        df['score_MFR'] = df[self.MFR_col].map(quality_scores)
        df['score_MFR'] = df['score_MFR'].fillna(100)
        
        print("\n  " + "="*56)
        print("  厂商质量评分结果")
        print("  " + "="*56)
        for mfr, score in sorted(quality_scores.items(), key=lambda x: x[1], reverse=True):
            status = "优秀" if score >= 80 else "一般" if score >= 60 else "较差"
            print(f"    {mfr:15} : {score:.1f} 分 ({status})")
        
        return df
    
    def cluster_MFRs(self, df, n_clusters=3, feature_cols=None):
        """基于电气特征对厂商进行聚类分析"""
        if self.MFR_col not in df.columns:
            print("  ⚠️ 没有厂商信息，无法聚类")
            return None
        
        if feature_cols is None:
            feature_cols = ['CPU_RATE', 'CPU_RATE_AVG', 'DISK_RATE', 'DISK_RATE_AVG', 
                           'TEMP_ERR_RATE', 'ONLINE_DUR', 'ONLINE_TIME', 'SIG_STR', 
                           'ONOFF_NUM', 'ONOFF_30D_NUM', 'OFFSET_TIME',
                           'FLOW_STAT', 'METER_NET_RATE', 'CUST_NUM_FLAG', 
                           'COLL_FAIL_RATE_7D', 'METER_FAIL_RATE', 
                           'POWEROFF_NUM_30D', 'TASK_SUCC_RATE']
        
        available_features = [f for f in feature_cols if f in df.columns]
        if len(available_features) < 2:
            print("  ⚠️ 可用特征太少，无法进行有效聚类")
            return None
        
        # 按厂商聚合特征均值
        MFR_features = df.groupby(self.MFR_col)[available_features].mean()
        
        if len(MFR_features) < n_clusters:
            n_clusters = len(MFR_features)
        
        if n_clusters < 2:
            print("  ⚠️ 厂商数量不足，跳过聚类")
            return None
        
        # 标准化并聚类
        from sklearn.preprocessing import StandardScaler
        from sklearn.cluster import KMeans
        
        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(MFR_features)
        
        self.cluster_model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = self.cluster_model.fit_predict(features_scaled)
        
        MFR_features['cluster'] = cluster_labels
        
        print("\n  " + "="*56)
        print("  厂商聚类分析结果")
        print("  " + "="*56)
        
        for cluster_id in range(self.cluster_model.n_clusters):
            cluster_MFRs = MFR_features[MFR_features['cluster'] == cluster_id].index.tolist()
            print(f"\n  聚类 {cluster_id}:")
            print(f"    厂商: {', '.join(cluster_MFRs)}")
        
        # 将聚类结果映射回原始数据
        cluster_map = MFR_features['cluster'].to_dict()
        df['MFR_cluster'] = df[self.MFR_col].map(cluster_map)
        
        return MFR_features
    
    def plot_MFR_analysis(self, df, is_removed_col='is_removed'):
        """可视化厂商分析结果"""
        if self.MFR_col not in df.columns:
            print("  ⚠️ 没有厂商信息，无法绘图")
            return
        
        fig, axes = plt.subplots(1, 3, figsize=(14, 10))
        
        # 1. 各厂商拆除率对比
        ax1 = axes[0]
        mfr_removal = df.groupby(self.MFR_col)[is_removed_col].mean() * 100
        mfr_removal.sort_values().plot(kind='barh', ax=ax1, color='coral')
        ax1.set_xlabel('拆除率 (%)')
        ax1.set_title('各厂商拆除率对比')
        ax1.grid(True, alpha=0.3)
        
        '''# 2. 各厂商健康分分布
        ax2 = axes[0, 1]
        if 'total_score' in df.columns:
            data_to_plot = [df[df[self.MFR_col] == mfr]['total_score'].values 
                          for mfr in df[self.MFR_col].unique()]
            bp = ax2.boxplot(data_to_plot, labels=df[self.MFR_col].unique(), 
                           patch_artist=True)
            ax2.set_ylabel('健康分')
            ax2.set_title('各厂商健康分分布')
            ax2.grid(True, alpha=0.3)
        else:
            ax2.text(0.5, 0.5, '无健康分数据', ha='center', va='center')
            ax2.set_title('各厂商健康分分布')'''
        
        # 3. 厂商质量评分
        ax2 = axes[1]
        if 'score_MFR' in df.columns:
            mfr_quality = df.groupby(self.MFR_col)['score_MFR'].mean()
            colors = ['green' if x >= 80 else 'orange' if x >= 60 else 'red' for x in mfr_quality]
            mfr_quality.sort_values().plot(kind='barh', ax=ax2, color=colors)
            ax2.set_xlabel('质量评分')
            ax2.set_title('厂商质量评分')
            ax2.grid(True, alpha=0.3)
        
        # 4. 厂商样本分布
        ax3 = axes[2]
        mfr_counts = df[self.MFR_col].value_counts()
        mfr_counts.plot(kind='pie', autopct='%1.1f%%', ax=ax3)
        ax3.set_title('厂商样本分布')
        ax3.set_ylabel('')
        
        plt.tight_layout()
        plt.show()
        
        return fig


# ==================== 最佳模型存储 ====================

class BestModelStorage:
    """存储最佳模型和参数"""
    
    def __init__(self):
        self.models = {}  # 存储训练好的模型
        self.params = {}  # 存储最佳参数
        self.scalers = {}  # 存储标准化器
        self.thresholds = {}  # 存储阈值
        
    def save_model(self, module_name, model, scaler, params, thresholds):
        """保存模型"""
        self.models[module_name] = model
        self.scalers[module_name] = scaler
        self.params[module_name] = params
        self.thresholds[module_name] = thresholds
        
    def save_all(self, module3_model, module4_model, MFR_analyzer, weights):
        """保存所有模型"""
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
        
        print("\n" + "="*60)
        print("最佳模型已保存")
        print("="*60)
        if 'module3' in self.params:
            print("模块3最佳参数:", self.params['module3'])
        if 'module4' in self.params:
            print("模块4最佳参数:", self.params['module4'])
        
    def print_summary(self):
        """打印模型总结"""
        print("\n" + "="*60)
        print("模型总结")
        print("="*60)
        for module_name, params in self.params.items():
            if module_name in ['module3', 'module4']:
                print(f"\n{module_name.upper()}:")
                for param, value in params.items():
                    if isinstance(value, float):
                        print(f"  {param}: {value:.4f}")
                    else:
                        print(f"  {param}: {value}")


# ==================== 数据预处理函数 ====================

def preprocess_features(df):
    """预处理特征数据（终端版本）"""
    # 处理二值特征（终端相关）
    binary_features = ['CUST_NUM_FLAG']
    for col in binary_features:
        if col in df.columns:
            # 确保是数值类型
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    if 'is_removed' in df.columns:
        # 将状态转换为字符串
        df['is_removed'] = df['is_removed'].astype(str).str.strip()
        
        # '03'拆除、'02'检修、'04'停用 → 1
        # '01'运行、'05'待装 → 0
        # 兼容两种格式：
        # 格式1（业务数据）: '03'拆除、'02'检修、'04'停用 → 1; '01'运行、'05'待装 → 0
        # 格式2（模拟数据）: '1'或'1.0' → 1; '0'或'0.0' → 0
        df['is_removed'] = df['is_removed'].apply(
            lambda x: 1 if x in ['1', '1.0', '02', '03', '04'] else 0
        )

    # 填充缺失值
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        df[col] = df[col].fillna(df[col].median())
    
    return df


# ==================== 主函数 ====================

def main(df, use_param_optimization=True, optimize_n_calls=30):
    """
    主函数：对终端数据进行评分
    
    参数:
    - df: 包含以下列的DataFrame
        - RUN_YEARS: 使用年限
        - COMM_TIME_LOC: 本地通讯时长
        - COMM_TIME_DIST: 远程通讯时长
        - CPU_RATE, CPU_RATE_AVG, DISK_RATE, DISK_RATE_AVG, TEMP_ERR_RATE, ONLINE_DUR, 
          ONLINE_TIME, SIG_STR, ONOFF_NUM, ONOFF_30D_NUM, OFFSET_TIME: 终端自身特征
        - FLOW_STAT, METER_NET_RATE, CUST_NUM_FLAG, COLL_FAIL_RATE_7D, 
          METER_FAIL_RATE, POWEROFF_NUM_30D, TASK_SUCC_RATE: 下挂设备特征
        - MFR: 生产厂商（可选）
        - is_removed: 是否已拆除 (1=拆除, 0=运行中)
        - meter_id: 终端ID (可选)
    - use_param_optimization: 是否启用超参数优化
    - optimize_n_calls: 优化迭代次数
    """
    
    print("=" * 70)
    print("终端健康评分系统")
    print("=" * 70)
    print(f"超参数优化: {'启用' if use_param_optimization else '禁用'}")
    if use_param_optimization:
        print(f"优化迭代次数: {optimize_n_calls}")
    
    # 数据预处理
    df = preprocess_features(df)
    
    # ========== 模块1：使用年限评分 ==========
    print("\n[模块1] 使用年限评分...")
    if 'RUN_YEARS' in df.columns:
        df['score_years'] = df['RUN_YEARS'].apply(score_RUN_YEARS)
        print(f"  完成，平均分: {df['score_years'].mean():.1f}")
    else:
        print("  ⚠️ 缺少 RUN_YEARS 列，使用默认分100")
        df['score_years'] = 100
    
    # ========== 模块2：通讯模块评分 ==========
    print("\n[模块2] 通信模块评分...")
    # 需要 COMM_TIME_LOC 和 COMM_TIME_DIST 两个字段
    has_loc = 'COMM_TIME_LOC' in df.columns
    has_dist = 'COMM_TIME_DIST' in df.columns
    if has_loc and has_dist:
        df['score_comm'] = df.apply(
            lambda row: score_comm_combined(row['COMM_TIME_LOC'], row['COMM_TIME_DIST']), axis=1
        )
        print(f"  完成，平均分: {df['score_comm'].mean():.1f}")
    elif has_loc:
        df['score_comm'] = df['COMM_TIME_LOC'].apply(score_comm_time)
        print(f"  ⚠️ 缺少 COMM_TIME_DIST，仅用 COMM_TIME_LOC 打分，平均分: {df['score_comm'].mean():.1f}")
    elif has_dist:
        df['score_comm'] = df['COMM_TIME_DIST'].apply(score_comm_time)
        print(f"  ⚠️ 缺少 COMM_TIME_LOC，仅用 COMM_TIME_DIST 打分，平均分: {df['score_comm'].mean():.1f}")
    else:
        print("  ⚠️ 缺少 COMM_TIME_LOC 和 COMM_TIME_DIST 列，使用默认分100")
        df['score_comm'] = 100
    
    # ========== 模块3：终端自身特征异常检测 ==========
    print("\n[模块3] 终端自身特征异常检测...")
    features_module3 = ['CPU_RATE', 'CPU_RATE_AVG', 'DISK_RATE', 'DISK_RATE_AVG', 
                        'TEMP_ERR_RATE', 'ONLINE_DUR', 'ONLINE_TIME', 'SIG_STR', 
                        'ONOFF_NUM', 'ONOFF_30D_NUM', 'OFFSET_TIME']
    
    missing_features3 = [f for f in features_module3 if f not in df.columns]
    if missing_features3:
        print(f"  ⚠️ 缺少特征 {missing_features3}，跳过模块3")
        df['score_module3'] = 100
        module3_model = None
    else:
        X3 = df[features_module3].copy()
        
        # 处理缺失值
        X3 = X3.fillna(X3.median())
        
        # 创建并训练模型
        module3_scorer = IsolationForestScorer(
            features_module3, 
            module_name="终端自身特征检测",
            n_estimators=250, 
            max_samples=0.8, 
            max_features=0.7,
            use_optimization=use_param_optimization,
            optimize_n_calls=optimize_n_calls
        )
        
        if 'is_removed' in df.columns and use_param_optimization:
            df['score_module3'] = module3_scorer.train(X3, df['is_removed'].values)
        else:
            df['score_module3'] = module3_scorer.train(X3)
        
        # 交叉验证和阈值校准
        if 'is_removed' in df.columns:
            module3_scorer.cross_validate(X3, df['is_removed'].values, n_folds=5)
            module3_scorer.calibrate_thresholds(X3, df['is_removed'].values)
            plot_score_distribution(df['score_module3'], df['is_removed'], "模块3 - 终端自身特征")
        
        module3_model = module3_scorer
        
        print(f"  模块3完成，平均健康分: {df['score_module3'].mean():.1f}")
    
    # ========== 模块4：下挂设备特征检测 ==========
    print("\n[模块4] 下挂设备（电表）特征检测...")
    features_module4 = ['FLOW_STAT', 'METER_NET_RATE', 'CUST_NUM_FLAG', 
                        'COLL_FAIL_RATE_7D', 'METER_FAIL_RATE', 
                        'POWEROFF_NUM_30D', 'TASK_SUCC_RATE']
    missing_features4 = [f for f in features_module4 if f not in df.columns]
    if missing_features4:
        print(f"  ⚠️ 缺少特征 {missing_features4}，跳过模块4")
        df['score_module4'] = 100
        module4_model = None
    else:
        X4 = df[features_module4].copy()
        X4 = X4.fillna(X4.median())
        
        module4_scorer = IsolationForestScorer(
            features_module4,
            module_name="下挂设备特征检测",
            n_estimators=200, 
            max_samples=0.8, 
            max_features=1.0,
            use_optimization=use_param_optimization,
            optimize_n_calls=optimize_n_calls
        )
        
        if 'is_removed' in df.columns and use_param_optimization:
            df['score_module4'] = module4_scorer.train(X4, df['is_removed'].values)
        else:
            df['score_module4'] = module4_scorer.train(X4)
        
        if 'is_removed' in df.columns:
            module4_scorer.cross_validate(X4, df['is_removed'].values, n_folds=5)
            module4_scorer.calibrate_thresholds(X4, df['is_removed'].values)
            plot_score_distribution(df['score_module4'], df['is_removed'], "模块4 - 下挂设备特征")
        
        module4_model = module4_scorer
        
        print(f"  模块4完成，平均健康分: {df['score_module4'].mean():.1f}")
    
    # ========== 模块5：生产厂商质量评估 ==========
    print("\n[模块5] 生产厂商质量评估...")
    MFR_analyzer = MFRAnalyzer(MFR_col='MFR')
    
    if 'MFR' in df.columns:
        MFR_analyzer.analyze_MFRs(df, 'is_removed')
        df = MFR_analyzer.calculate_quality_score(df, 'is_removed', 
                                                           use_health_score=True, 
                                                           use_removal_rate=True)
        MFR_analyzer.cluster_MFRs(df, n_clusters=3)
        MFR_analyzer.plot_MFR_analysis(df, 'is_removed')
    else:
        print("  ⚠️ 数据中没有生产厂商信息，跳过厂商质量评估模块")
        df['score_MFR'] = 100
        df['MFR_cluster'] = -1
    
    # ========== 综合评分 ==========
    print("\n[综合评分] 计算总分...")
    
    # 权重配置
    weights = {
        'score_years': 0.25,
        'score_comm': 0.10,
        'score_module3': 0.30,
        'score_module4': 0.15,
        'score_MFR': 0.20
    }
    
    # 检查哪些模块实际存在
    available_weights = {k: v for k, v in weights.items() 
                        if k in df.columns and v > 0}
    
    # 重新归一化权重
    total_weight = sum(available_weights.values())
    if total_weight > 0:
        available_weights = {k: v/total_weight for k, v in available_weights.items()}
    
    print(f"\n  实际使用的权重:")
    for col, w in available_weights.items():
        print(f"    {col}: {w:.2%}")
    
    # 计算加权总分
    total_score = 0
    for col, w in available_weights.items():
        total_score += df[col] * w
    
    df['total_score'] = total_score
    
    # 分级
    def get_grade(score):
        if score < 60:
            return 'D - 建议维修/拆换'
        elif score < 80:
            return 'C - 重点关注'
        else:
            return 'B - 运行良好'
    
    df['grade'] = df['total_score'].apply(get_grade)
    
    # 超龄强制判定：模块1为0分（使用超过8年）直接建议拆除
    if 'score_years' in df.columns:
        df.loc[df['score_years'] == 0, 'grade'] = 'E - 超龄建议直接拆除'
    
    # ========== 输出结果 ==========
    print("\n" + "=" * 70)
    print("评分结果统计")
    print("=" * 70)
    
    score_cols = ['score_years', 'score_comm', 'score_module3', 
                  'score_module4', 'score_MFR', 'total_score']
    score_cols = [c for c in score_cols if c in df.columns]
    
    print("\n各模块评分统计:")
    for col in score_cols:
        print(f"  {col}: 均值={df[col].mean():.1f}, 标准差={df[col].std():.1f}, "
              f"min={df[col].min():.1f}, max={df[col].max():.1f}")
    
    print(f"\n健康等级分布:")
    grade_counts = df['grade'].value_counts()
    for grade, count in grade_counts.items():
        print(f"  {grade}: {count} ({count/len(df)*100:.1f}%)")
    
    # 绘制总分分布
    if 'is_removed' in df.columns:
        plot_score_distribution(df['total_score'], df['is_removed'], "综合评分")
    
    '''# 展示最需要关注的10个终端
    print(f"\n最需要关注的10个终端:")
    display_cols = ['meter_id', 'MFR', 'total_score', 'grade', 
                    'score_years','score_comm', 'score_module3', 'score_module4', 'score_MFR']
    display_cols = [c for c in display_cols if c in df.columns]
    
    if len(display_cols) > 0 and 'meter_id' in df.columns:
        print(df[display_cols].nsmallest(10, 'total_score').to_string(index=False))'''
    
    # 各厂商平均综合评分
    if 'MFR' in df.columns:
        print(f"\n各厂商平均综合评分:")
        MFR_total = df.groupby('MFR')['total_score'].agg(['mean', 'count', 'std'])
        print(MFR_total.sort_values('mean', ascending=False).round(1).to_string())
    
    # ========== 保存最佳模型 ==========
    best_model_storage = BestModelStorage()
    
    if module3_model or module4_model:
        best_model_storage.save_all(
            module3_model, 
            module4_model, 
            MFR_analyzer,
            available_weights
        )
        
        # 保存到文件
        import pickle
        save_data = {
            'module3_model': module3_model.model if module3_model else None,
            'module3_scaler': module3_model.scaler if module3_model else None,
            'module3_params': module3_model.best_params if module3_model else None,
            'module4_model': module4_model.model if module4_model else None,
            'module4_scaler': module4_model.scaler if module4_model else None,
            'module4_params': module4_model.best_params if module4_model else None,
            'MFR_scores': MFR_analyzer.MFR_quality_score if MFR_analyzer else {},
            'weights': available_weights
        }
        
        with open('best_model.pkl', 'wb') as f:
            pickle.dump(save_data, f)
        print("\n✅ 最佳模型已保存到 best_model.pkl")
        
        best_model_storage.print_summary()
    
    return df, best_model_storage



# ==================== 预测函数（使用保存的模型）====================

def predict_with_best_model(df, model_path='best_model.pkl'):
    """
    使用保存的最佳模型进行预测
    """
    import pickle
    
    # 加载模型
    with open(model_path, 'rb') as f:
        saved_model = pickle.load(f)
    
    # 数据预处理
    df = preprocess_features(df)
    
    # 模块1：年限评分
    if 'RUN_YEARS' in df.columns:
        df['score_years'] = df['RUN_YEARS'].apply(score_RUN_YEARS)
    else:
        df['score_years'] = 100
    
    # 模块2：通讯评分
    has_loc = 'COMM_TIME_LOC' in df.columns
    has_dist = 'COMM_TIME_DIST' in df.columns
    if has_loc and has_dist:
        df['score_comm'] = df.apply(
            lambda row: score_comm_combined(row['COMM_TIME_LOC'], row['COMM_TIME_DIST']), axis=1
        )
    elif has_loc:
        df['score_comm'] = df['COMM_TIME_LOC'].apply(score_comm_time)
    elif has_dist:
        df['score_comm'] = df['COMM_TIME_DIST'].apply(score_comm_time)
    else:
        df['score_comm'] = 100
    
    
    # 模块3预测
    if saved_model['module3_model'] is not None:
        module3_scaler = saved_model['module3_scaler']
        module3_model = saved_model['module3_model']
        
        features_module3 = ['CPU_RATE', 'CPU_RATE_AVG', 'DISK_RATE', 'DISK_RATE_AVG', 
                            'TEMP_ERR_RATE', 'ONLINE_DUR', 'ONLINE_TIME', 'SIG_STR', 
                            'ONOFF_NUM', 'ONOFF_30D_NUM', 'OFFSET_TIME']
        
        X3 = df[features_module3].copy()
        X3 = X3.fillna(X3.median())
        X3_scaled = module3_scaler.transform(X3)
        anomaly_scores3 = module3_model.decision_function(X3_scaled)
        
        # 转换为健康分
        min_score = np.percentile(anomaly_scores3, 5)
        max_score = np.percentile(anomaly_scores3, 95)
        if max_score - min_score < 0.01:
            health_scores3 = np.ones_like(anomaly_scores3) * 50
        else:
            health_scores3 = (anomaly_scores3 - min_score) / (max_score - min_score) * 100
        df['score_module3'] = np.clip(health_scores3, 0, 100)
    else:
        df['score_module3'] = 100
    
    # 模块4预测
    if saved_model['module4_model'] is not None:
        module4_scaler = saved_model['module4_scaler']
        module4_model = saved_model['module4_model']
        
        features_module4 = ['FLOW_STAT', 'METER_NET_RATE', 'CUST_NUM_FLAG', 
                            'COLL_FAIL_RATE_7D', 'METER_FAIL_RATE', 
                            'POWEROFF_NUM_30D', 'TASK_SUCC_RATE']
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
    
    # 厂商评分
    MFR_scores = saved_model.get('MFR_scores', {})
    if 'MFR' in df.columns and MFR_scores:
        df['score_MFR'] = df['MFR'].map(MFR_scores)
        df['score_MFR'] = df['score_MFR'].fillna(100)
    else:
        df['score_MFR'] = 100
    
    # 总分计算
    weights = saved_model['weights']
    total_score = 0
    for col, w in weights.items():
        if col in df.columns:
            total_score += df[col] * w
    df['total_score'] = total_score
    
    # 分级
    def get_grade(score):
        if score < 60:
            return 'D - 建议维修/拆换'
        elif score < 80:
            return 'C - 重点关注'
        else:
            return 'B - 运行良好'
    
    df['grade'] = df['total_score'].apply(get_grade)
    
    # 超龄强制判定：模块1为0分（使用超过8年）直接建议拆除
    if 'score_years' in df.columns:
        df.loc[df['score_years'] == 0, 'grade'] = 'E - 超龄建议直接拆除'
    
    return df



