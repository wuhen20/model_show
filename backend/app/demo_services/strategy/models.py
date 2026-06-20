"""
数据结构定义（Recommendation 对齐 v4 中间表 schema）
"""

from __future__ import annotations

from dataclasses import dataclass, asdict


# 17 场景元数据
SCENARIO_META = {
    "SC-01": ("光伏户曲线异常",       "C1", "T01"),
    "SC-02": ("零电量户",             "C1", "T02"),
    "SC-03": ("负荷管理特护户",       "C1", "T03"),
    "SC-04": ("三相表数据项扩展",     "C1", "T04"),
    "SC-05": ("业扩变更",             "C1", "T05"),
    "SC-06": ("居民低谷采集",         "C1", "T06"),
    "SC-07": ("终端长时间离线",       "C3", "T20"),
    "SC-08": ("固定时段采集失败",     "C1", "T07"),
    "SC-09": ("台区批量采集失败",     "C3", "T21"),
    "SC-10": ("参数不一致",           "C3", "T22"),
    "SC-11": ("串户疑似",             "C3", "T23"),
    "SC-12": ("用电异常",             "C2", "T10"),
    "SC-13": ("掉电/开盖事件未配置",  "C2", "T11"),
    "SC-14": ("费控复电失败",         "C3", "T24"),
    "SC-15": ("曲线不完整",           "C1", "T07"),
    "SC-16": ("高损台区",             "C4", "T30"),
    "SC-17": ("高风险投诉户",         "C4", "T31"),
}


@dataclass
class Recommendation:
    # 主键
    rec_id: str
    group_id: str
    generated_at: str
    # 目标定位
    target_type: str
    terminal_id: str = ""
    terminal_addr: str = ""
    measure_point_id: str = ""
    meter_id: str = ""
    user_id: str = ""
    area_id: str = ""
    user_type: str = ""
    # 场景识别
    matched_scenario_id: str = ""
    matched_scenario_name: str = ""
    trigger_condition_desc: str = ""
    match_confidence: float = 0.0
    # 动作
    action_category: str = ""
    action_type: str = ""
    action_summary: str = ""
    # C1 策略调整
    original_strategy_id: str = ""
    original_strategy_name: str = ""
    original_freq: str = ""
    original_run_period: str = ""
    original_data_items: str = ""
    suggested_strategy_id: str = ""
    suggested_strategy_name: str = ""
    freq_change: str = ""
    data_item_change: str = ""
    run_period_change: str = ""
    recall_schedule_id: str = ""
    recall_schedule_summary: str = ""
    # C2 事件上报
    event_types: str = ""
    report_mode: str = ""
    report_priority: str = ""
    target_event_task_id: str = ""
    upstream_consumer: str = ""
    # C3 处理流程
    workflow_id: str = ""
    workflow_name: str = ""
    workflow_steps: str = ""
    expected_duration_min: int = 0
    pre_conditions: str = ""
    post_verification: str = ""
    execution_window: str = ""
    # C4 告警通知
    alert_type: str = ""
    alert_priority: str = ""
    alert_target: str = ""
    alert_content: str = ""
    follow_up_action: str = ""
    # 生命周期
    effective_from: str = ""
    effective_to: str = ""
    exit_condition: str = ""
    # 解释
    decision_reason: str = ""
    expected_benefit: str = ""
    rollback_plan: str = ""
    # 状态机
    status: str = "pending"
    approve_time: str = ""
    approver: str = ""
    reject_reason: str = ""
    applied_time: str = ""
    completed_time: str = ""
    execution_result: str = ""
    revoked_time: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
