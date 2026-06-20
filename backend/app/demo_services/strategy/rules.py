"""
规则研判（17 场景）

每条规则都是纯函数：tables -> list[Recommendation]
对应 v4 设计文档的 17 个场景。
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta

import pandas as pd

from .models import Recommendation, SCENARIO_META


_REC_COUNTER = {"n": 0}
_GROUP = {"id": ""}


def _reset_counter(group_id: str | None = None):
    _REC_COUNTER["n"] = 0
    _GROUP["id"] = group_id or f"GRP_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _new_rec(sid: str, today: str, **kwargs) -> Recommendation:
    _REC_COUNTER["n"] += 1
    name, cat, typ = SCENARIO_META[sid]
    base = dict(
        rec_id=f"REC_{_REC_COUNTER['n']:06d}",
        group_id=_GROUP["id"],
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        target_type="user",
        matched_scenario_id=sid,
        matched_scenario_name=name,
        action_category=cat,
        action_type=typ,
        effective_from=today + " 00:00:00",
        effective_to=(datetime.strptime(today, "%Y-%m-%d") + timedelta(days=7)).strftime("%Y-%m-%d") + " 23:59:59",
        status="pending",
    )
    base.update(kwargs)
    return Recommendation(**base)


# =============== 17 条规则 =================================================

def rule_sc01_pv(t: dict, today: str) -> list[Recommendation]:
    out = []
    users, lcs, meters = t["users"], t["load_curve_summary"], t["meters"]
    bind, strat = t["terminal_strategy_bind"], t["collection_strategy_master"]
    last_curve = lcs[lcs["stat_date"] == lcs["stat_date"].max()]
    pv_users = users[users["user_type"] == "光伏"]
    for _, u in pv_users.iterrows():
        cur = last_curve[last_curve["user_id"] == u["user_id"]]
        if cur.empty: continue
        comp = float(cur.iloc[0]["completeness"])
        cur_strat = bind[bind["terminal_id"] == u["terminal_id"]]
        cur_sid = cur_strat.iloc[0]["strategy_id"] if not cur_strat.empty else "S001"
        if cur_sid == "S003": continue
        orig = strat[strat["strategy_id"] == cur_sid].iloc[0]
        new = strat[strat["strategy_id"] == "S003"].iloc[0]
        m = meters[meters["user_id"] == u["user_id"]].head(1)
        out.append(_new_rec(
            "SC-01", today,
            terminal_id=u["terminal_id"], user_id=u["user_id"], area_id=u["area_id"], user_type=u["user_type"],
            measure_point_id=m["measure_point_id"].iloc[0] if not m.empty else "",
            meter_id=m["meter_id"].iloc[0] if not m.empty else "",
            trigger_condition_desc=f"用户类型为光伏，但当前策略 {orig['strategy_name']} 未覆盖反向有功；当前曲线完整度 {comp:.2%}",
            match_confidence=0.95,
            action_summary=f"将策略由 {orig['strategy_name']} 切换为 {new['strategy_name']}（覆盖双向）",
            original_strategy_id=orig["strategy_id"], original_strategy_name=orig["strategy_name"],
            original_freq=orig["freq"], original_run_period=orig["run_period"], original_data_items=orig["data_items"],
            suggested_strategy_id=new["strategy_id"], suggested_strategy_name=new["strategy_name"],
            freq_change=f"{orig['freq']} → {new['freq']}",
            data_item_change=f"{orig['data_items']} → {new['data_items']}",
            run_period_change=f"{orig['run_period']} → {new['run_period']}",
            decision_reason="光伏户需采集反向有功/无功，当前策略不满足业务诉求",
            expected_benefit="曲线完整度预计提升至 95%+ ，满足光伏结算口径",
            rollback_plan="若 7 天观察期内反向数据连续异常，自动回滚到 S001",
        ))
    return out


def rule_sc02_zero(t: dict, today: str) -> list[Recommendation]:
    out = []
    dc, users = t["daily_consumption"], t["users"]
    bind, strat = t["terminal_strategy_bind"], t["collection_strategy_master"]
    recent = dc[dc["stat_date"] >= (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=14)).strftime("%Y-%m-%d")]
    agg = recent.groupby("user_id")["kwh"].mean().reset_index(name="avg_kwh")
    zero_users = agg[agg["avg_kwh"] < 0.1]["user_id"].tolist()
    for uid in zero_users:
        u = users[users["user_id"] == uid].iloc[0]
        cur_strat = bind[bind["terminal_id"] == u["terminal_id"]]
        cur_sid = cur_strat.iloc[0]["strategy_id"] if not cur_strat.empty else "S001"
        if cur_sid == "S007": continue
        orig = strat[strat["strategy_id"] == cur_sid].iloc[0]
        new = strat[strat["strategy_id"] == "S007"].iloc[0]
        out.append(_new_rec(
            "SC-02", today,
            terminal_id=u["terminal_id"], user_id=uid, area_id=u["area_id"], user_type=u["user_type"],
            trigger_condition_desc=f"近 14 天日均电量 {agg[agg['user_id']==uid]['avg_kwh'].iloc[0]:.3f} kWh，疑似长期零电量",
            match_confidence=0.90,
            action_summary="切换到零电量降频模板 S007（按周采集）",
            original_strategy_id=orig["strategy_id"], original_strategy_name=orig["strategy_name"],
            original_freq=orig["freq"], original_run_period=orig["run_period"], original_data_items=orig["data_items"],
            suggested_strategy_id=new["strategy_id"], suggested_strategy_name=new["strategy_name"],
            freq_change=f"{orig['freq']} → {new['freq']}",
            decision_reason="降低无效采集开销，腾出主站信道",
            expected_benefit="信道资源节省约 85%",
            rollback_plan="用户日电量恢复 > 0.5 kWh 持续 3 天即回滚",
        ))
    return out


def rule_sc03_special(t: dict, today: str) -> list[Recommendation]:
    out = []
    users, tags = t["users"], t["user_tags"]
    strat, bind = t["collection_strategy_master"], t["terminal_strategy_bind"]
    special = tags[tags["tags"].str.contains("特护", na=False)]["user_id"].tolist()
    for uid in special:
        u = users[users["user_id"] == uid].iloc[0]
        cur_strat = bind[bind["terminal_id"] == u["terminal_id"]]
        cur_sid = cur_strat.iloc[0]["strategy_id"] if not cur_strat.empty else "S001"
        if cur_sid == "S006": continue
        orig = strat[strat["strategy_id"] == cur_sid].iloc[0]
        new = strat[strat["strategy_id"] == "S006"].iloc[0]
        out.append(_new_rec(
            "SC-03", today,
            terminal_id=u["terminal_id"], user_id=uid, area_id=u["area_id"], user_type=u["user_type"],
            trigger_condition_desc="用户被标记为负荷管理特护，需要 18-22 加密曲线",
            match_confidence=0.92,
            action_summary="切到特护-15min加密模板 S006",
            original_strategy_id=orig["strategy_id"], original_strategy_name=orig["strategy_name"],
            suggested_strategy_id=new["strategy_id"], suggested_strategy_name=new["strategy_name"],
            run_period_change=f"{orig['run_period']} → {new['run_period']}",
            decision_reason="保障晚高峰负荷数据精度",
            expected_benefit="高峰时段曲线完整度 >= 98%",
            rollback_plan="标签解除即自动回滚",
        ))
    return out


def rule_sc04_threephase(t: dict, today: str) -> list[Recommendation]:
    out = []
    users, strat, bind = t["users"], t["collection_strategy_master"], t["terminal_strategy_bind"]
    three = users[users["user_type"] == "三相工业"]
    for _, u in three.iterrows():
        cur_strat = bind[bind["terminal_id"] == u["terminal_id"]]
        cur_sid = cur_strat.iloc[0]["strategy_id"] if not cur_strat.empty else "S001"
        if cur_sid == "S004": continue
        orig = strat[strat["strategy_id"] == cur_sid].iloc[0]
        new = strat[strat["strategy_id"] == "S004"].iloc[0]
        out.append(_new_rec(
            "SC-04", today,
            terminal_id=u["terminal_id"], user_id=u["user_id"], area_id=u["area_id"], user_type=u["user_type"],
            trigger_condition_desc="三相工业用户，当前策略只采正向有功，缺三相电压/电流/功率数据项",
            match_confidence=0.93,
            action_summary="切到三相-完整数据项模板 S004",
            original_strategy_id=orig["strategy_id"], original_strategy_name=orig["strategy_name"],
            suggested_strategy_id=new["strategy_id"], suggested_strategy_name=new["strategy_name"],
            data_item_change=f"{orig['data_items']} → {new['data_items']}",
            decision_reason="三相设备需要 ABC 三相全量数据用于负荷诊断与不平衡分析",
            expected_benefit="可支持三相不平衡分析、谐波分析等业务",
            rollback_plan="无业务诉求即回滚",
        ))
    return out


def rule_sc05_change(t: dict, today: str) -> list[Recommendation]:
    out = []
    bc, users = t["business_changes"], t["users"]
    strat, bind = t["collection_strategy_master"], t["terminal_strategy_bind"]
    for _, c in bc.iterrows():
        uid = c["user_id"]
        u = users[users["user_id"] == uid].iloc[0]
        cur_strat = bind[bind["terminal_id"] == u["terminal_id"]]
        cur_sid = cur_strat.iloc[0]["strategy_id"] if not cur_strat.empty else "S001"
        orig = strat[strat["strategy_id"] == cur_sid].iloc[0]
        new = strat[strat["strategy_id"] == "S008"].iloc[0]
        out.append(_new_rec(
            "SC-05", today,
            terminal_id=u["terminal_id"], user_id=uid, area_id=u["area_id"], user_type=u["user_type"],
            trigger_condition_desc=f"近期发生业扩变更（{c['change_type']}），需 7 天临时加密观察",
            match_confidence=0.88,
            action_summary="临时切到 S008，加密 7 天后自动回滚",
            original_strategy_id=orig["strategy_id"], original_strategy_name=orig["strategy_name"],
            suggested_strategy_id=new["strategy_id"], suggested_strategy_name=new["strategy_name"],
            exit_condition="切换 7 天且无异常 → 回到原策略",
            decision_reason="业扩变更后需密切跟踪表计运行状况",
            expected_benefit="及时发现安装错误/接线异常",
            rollback_plan="7 天后自动回滚",
        ))
    return out


def rule_sc06_resident(t: dict, today: str) -> list[Recommendation]:
    out = []
    users, tags = t["users"], t["user_tags"]
    strat, bind = t["collection_strategy_master"], t["terminal_strategy_bind"]
    target = tags[tags["tags"].str.contains("居民低谷", na=False)]["user_id"].tolist()
    for uid in target:
        u = users[users["user_id"] == uid].iloc[0]
        cur_strat = bind[bind["terminal_id"] == u["terminal_id"]]
        cur_sid = cur_strat.iloc[0]["strategy_id"] if not cur_strat.empty else "S001"
        orig = strat[strat["strategy_id"] == cur_sid].iloc[0]
        new = strat[strat["strategy_id"] == "S005"].iloc[0]
        out.append(_new_rec(
            "SC-06", today,
            terminal_id=u["terminal_id"], user_id=uid, area_id=u["area_id"], user_type=u["user_type"],
            trigger_condition_desc="居民户在低谷（00-06）成功率低，需要叠加低谷采集策略",
            match_confidence=0.86,
            action_summary="叠加 S005 居民低谷模板（00-06 加密）",
            original_strategy_id=orig["strategy_id"], original_strategy_name=orig["strategy_name"],
            suggested_strategy_id=new["strategy_id"], suggested_strategy_name=new["strategy_name"],
            run_period_change=f"{orig['run_period']} + {new['run_period']}",
            decision_reason="低谷时段曲线完整度偏低",
            expected_benefit="低谷段成功率从 70% 提升至 95%+",
            rollback_plan="若连续 14 天低谷完整度仍未达标则升级至单独排程",
        ))
    return out


def rule_sc07_offline(t: dict, today: str) -> list[Recommendation]:
    out = []
    hb, terms = t["terminal_heartbeat"], t["terminals"]
    offline = hb[hb["offline_days"] >= 3]
    for _, h in offline.iterrows():
        tt = terms[terms["terminal_id"] == h["terminal_id"]].iloc[0]
        out.append(_new_rec(
            "SC-07", today,
            target_type="terminal",
            terminal_id=tt["terminal_id"], terminal_addr=tt["terminal_addr"], area_id=tt["area_id"],
            trigger_condition_desc=f"终端离线 {int(h['offline_days'])} 天，超过 3 天阈值",
            match_confidence=0.97,
            action_summary="派发现场处理工单（远程→排查→现场）",
            workflow_id="WF_TERMINAL_OFFLINE", workflow_name="终端离线处理流程",
            workflow_steps="远程复位 → 信道检测 → 派单运维上门 → 设备更换/通信修复 → 回访",
            expected_duration_min=240,
            pre_conditions="终端最后心跳已超过 72h",
            post_verification="终端恢复在线后连续 24h 心跳正常",
            execution_window="工作日 9:00-18:00",
            decision_reason="离线超过 3 天，远程已尝试失败",
            expected_benefit="终端恢复在线，数据采集恢复",
            rollback_plan="无需回滚（流程类）",
        ))
    return out


def rule_sc08_fixed_time_fail(t: dict, today: str) -> list[Recommendation]:
    out = []
    cs, terms = t["collection_stats"], t["terminals"]
    suspects = cs[(cs["success_rate_7d"] < 0.80) & (cs["failed_concentrate_slot"] >= 0)]
    for _, s in suspects.iterrows():
        tt = terms[terms["terminal_id"] == s["terminal_id"]].iloc[0]
        hour = int(s["failed_concentrate_slot"]) * 15 / 60
        out.append(_new_rec(
            "SC-08", today,
            target_type="terminal",
            terminal_id=tt["terminal_id"], terminal_addr=tt["terminal_addr"], area_id=tt["area_id"],
            trigger_condition_desc=f"近 7 天采集成功率 {s['success_rate_7d']:.1%}，失败集中在 {hour:.1f}h 附近时段",
            match_confidence=0.91,
            action_summary="下发动态补召排程（待 scheduler 写入具体时段）",
            recall_schedule_id="PENDING",
            recall_schedule_summary="按所属簇的预测成功率挑选 Top-K 高分时段补召",
            decision_reason="固定时段失败可通过错峰补召规避信道拥塞",
            expected_benefit="补召一次的预期成功率从 60% 提升到 85%+",
            rollback_plan="排程连续 3 天命中率 < 70% 自动停用",
        ))
    return out


def rule_sc09_area_fail(t: dict, today: str) -> list[Recommendation]:
    out = []
    acs = t["area_collection_stats"]
    bad = acs[acs["success_rate_7d"] < 0.70]
    for _, a in bad.iterrows():
        out.append(_new_rec(
            "SC-09", today,
            target_type="area", area_id=a["area_id"],
            trigger_condition_desc=f"台区近 7 天采集成功率 {a['success_rate_7d']:.1%}，整片偏低",
            match_confidence=0.94,
            action_summary="派发台区级信道排查流程",
            workflow_id="WF_AREA_BATCH_FAIL", workflow_name="台区批量失败排查流程",
            workflow_steps="信道质量诊断 → 集中器/路由器排查 → 现场上门 → 信号优化",
            expected_duration_min=480,
            decision_reason="整个台区低 = 共性问题（多数为通信而非单点故障）",
            expected_benefit="整片成功率提升 25 pp 以上",
            rollback_plan="工单关闭即结束",
        ))
    return out


def rule_sc10_param(t: dict, today: str) -> list[Recommendation]:
    out = []
    pc, users = t["param_consistency"], t["users"]
    bad = pc[pc["is_consistent"] == False]
    for _, p in bad.iterrows():
        u = users[users["user_id"] == p["user_id"]].iloc[0]
        out.append(_new_rec(
            "SC-10", today,
            terminal_id=u["terminal_id"], user_id=p["user_id"], area_id=u["area_id"], user_type=u["user_type"],
            trigger_condition_desc=f"营销/主站/表端参数不一致，差异字段：{p['diff_fields']}",
            match_confidence=0.96,
            action_summary="派发参数同步流程",
            workflow_id="WF_PARAM_SYNC", workflow_name="参数一致性修复",
            workflow_steps="拉取四方参数 → 比对差异 → 以营销为准下发 → 复核",
            expected_duration_min=60,
            decision_reason="参数不一致会导致后续数据无法正确解析",
            expected_benefit="电量计算口径恢复一致",
            rollback_plan="下发失败回滚到原表端值",
        ))
    return out


def rule_sc11_cross(t: dict, today: str) -> list[Recommendation]:
    out = []
    cc, users = t["cross_conn_suspects"], t["users"]
    for _, c in cc.iterrows():
        u = users[users["user_id"] == c["user_id"]].iloc[0]
        out.append(_new_rec(
            "SC-11", today,
            terminal_id=u["terminal_id"], user_id=c["user_id"], area_id=u["area_id"], user_type=u["user_type"],
            trigger_condition_desc=f"串户疑似分 {c['suspect_score']:.2f}，证据：{c['evidence']}",
            match_confidence=float(c["suspect_score"]),
            action_summary="派发串户现场核对流程",
            workflow_id="WF_CROSS_CONN_CHECK", workflow_name="串户核对",
            workflow_steps="现场抄表 → 物理接线核对 → 档案校正 → 复采",
            expected_duration_min=180,
            decision_reason="高度疑似串户，须现场核实",
            expected_benefit="档案准确、电量归户正确",
            rollback_plan="无误即关闭",
        ))
    return out


def rule_sc12_anomaly(t: dict, today: str) -> list[Recommendation]:
    out = []
    aa, users = t["anomaly_alerts"], t["users"]
    grp = aa.groupby("user_id").size().reset_index(name="n").query("n >= 2")
    for _, g in grp.iterrows():
        u = users[users["user_id"] == g["user_id"]].iloc[0]
        out.append(_new_rec(
            "SC-12", today,
            terminal_id=u["terminal_id"], user_id=g["user_id"], area_id=u["area_id"], user_type=u["user_type"],
            trigger_condition_desc=f"近 7 天用电异常告警 {int(g['n'])} 次",
            match_confidence=0.87,
            action_summary="提升事件上报优先级 + 增加异常事件订阅",
            event_types="突增,突降,失压,功率方向异常",
            report_mode="实时", report_priority="高",
            upstream_consumer="反窃电系统/计量诊断",
            decision_reason="高频异常告警，需细化事件上报供下游进一步分析",
            expected_benefit="反窃电线索发现时延降低",
            rollback_plan="30 天无异常自动降回普通优先级",
        ))
    return out


def rule_sc13_event_uncfg(t: dict, today: str) -> list[Recommendation]:
    out = []
    er, users = t["event_report_task_existing"], t["users"]
    cfg = er.groupby("user_id")["event_type"].apply(set).to_dict()
    for _, u in users.iterrows():
        evs = cfg.get(u["user_id"], set())
        missing = {"掉电", "开盖"} - evs
        if not missing: continue
        out.append(_new_rec(
            "SC-13", today,
            terminal_id=u["terminal_id"], user_id=u["user_id"], area_id=u["area_id"], user_type=u["user_type"],
            trigger_condition_desc=f"用户未配置以下事件上报：{','.join(sorted(missing))}",
            match_confidence=0.90,
            action_summary="补配缺失事件上报任务",
            event_types=",".join(sorted(missing)),
            report_mode="实时", report_priority="中",
            decision_reason="缺少事件上报会导致掉电/开盖等关键事件丢失",
            expected_benefit="事件覆盖率达到 100%",
            rollback_plan="无（属于补齐配置）",
        ))
    return out


def rule_sc14_fee(t: dict, today: str) -> list[Recommendation]:
    out = []
    fc, users = t["fee_control_status"], t["users"]
    bad = fc[(fc["last_op"] == "复电") & (fc["result"] == "失败")]
    for _, f in bad.iterrows():
        u = users[users["user_id"] == f["user_id"]].iloc[0]
        out.append(_new_rec(
            "SC-14", today,
            terminal_id=u["terminal_id"], user_id=f["user_id"], area_id=u["area_id"], user_type=u["user_type"],
            trigger_condition_desc=f"费控复电失败，已重试 {int(f['retry_count'])} 次，失败原因：{f['fail_reason']}",
            match_confidence=0.93,
            action_summary="派发复电二次处理流程",
            workflow_id="WF_FEE_RECOVER", workflow_name="费控复电二次处理",
            workflow_steps="重发复电报文 → 失败则切到信道B → 仍失败派单现场",
            expected_duration_min=120,
            decision_reason="费控复电直接影响用户体验，必须闭环",
            expected_benefit="用户复电时延 < 30min",
            rollback_plan="无（属补救流程）",
        ))
    return out


def rule_sc15_incomplete(t: dict, today: str) -> list[Recommendation]:
    out = []
    lcs, users, meters = t["load_curve_summary"], t["users"], t["meters"]
    last_date = lcs["stat_date"].max()
    recent = lcs[lcs["stat_date"] >= (datetime.strptime(last_date, "%Y-%m-%d") - timedelta(days=6)).strftime("%Y-%m-%d")]
    agg = recent.groupby("user_id")["completeness"].mean().reset_index(name="comp7")
    bad = agg[agg["comp7"] < 0.90]
    for _, g in bad.iterrows():
        u = users[users["user_id"] == g["user_id"]].iloc[0]
        m = meters[meters["user_id"] == g["user_id"]].head(1)
        out.append(_new_rec(
            "SC-15", today,
            terminal_id=u["terminal_id"], user_id=g["user_id"], area_id=u["area_id"], user_type=u["user_type"],
            measure_point_id=m["measure_point_id"].iloc[0] if not m.empty else "",
            meter_id=m["meter_id"].iloc[0] if not m.empty else "",
            trigger_condition_desc=f"近 7 天 96 点曲线完整度均值 {g['comp7']:.1%}，低于 90%",
            match_confidence=0.89,
            action_summary="下发动态补召排程（待 scheduler 写入具体时段）",
            recall_schedule_id="PENDING",
            recall_schedule_summary="按所属簇的预测成功率挑选 Top-K 高分时段补召",
            decision_reason="曲线缺点 → 错峰补召比定时硬刷更有效",
            expected_benefit="曲线完整度从 ~80% 拉到 ≥95%",
            rollback_plan="排程连续 3 天命中率 < 70% 自动停用",
        ))
    return out


def rule_sc16_high_loss(t: dict, today: str) -> list[Recommendation]:
    out = []
    alr = t["area_loss_rates"]
    bad = alr[alr["loss_rate"] > 0.10]
    for _, a in bad.iterrows():
        out.append(_new_rec(
            "SC-16", today,
            target_type="area", area_id=a["area_id"],
            trigger_condition_desc=f"台区线损率 {a['loss_rate']:.1%}，超过 10% 红线",
            match_confidence=0.95,
            action_summary="推送高损告警 + 派发反窃电排查",
            alert_type="线损异常", alert_priority="高", alert_target="线损治理岗",
            alert_content=f"{a['area_id']} 当日线损 {a['loss_rate']:.2%}，请关注",
            follow_up_action="反窃电排查工单",
            decision_reason="高损 = 经济损失/疑似窃电",
            expected_benefit="线损降至 6% 以下",
            rollback_plan="线损连续 7 天 < 6% 解除告警",
        ))
    return out


def rule_sc17_complaint(t: dict, today: str) -> list[Recommendation]:
    out = []
    risk, users = t["user_risk_tags"], t["users"]
    high = risk[risk["risk_level"] == "高"]
    for _, r in high.iterrows():
        u = users[users["user_id"] == r["user_id"]].iloc[0]
        out.append(_new_rec(
            "SC-17", today,
            terminal_id=u["terminal_id"], user_id=r["user_id"], area_id=u["area_id"], user_type=u["user_type"],
            trigger_condition_desc=f"用户被标记为高风险投诉户：{r['risk_reason']}",
            match_confidence=0.92,
            action_summary="推送客服重点关注告警 + 数据采集优先级提升",
            alert_type="高风险用户", alert_priority="高", alert_target="客服中心/营销服务",
            alert_content="该用户存在投诉风险，请优先响应",
            follow_up_action="客服首次沟通 + 现场回访",
            decision_reason="高风险投诉户 → 防止再次投诉/舆情",
            expected_benefit="降低重复投诉率",
            rollback_plan="30 天无新增投诉自动解除",
        ))
    return out


ALL_RULES = [
    rule_sc01_pv, rule_sc02_zero, rule_sc03_special, rule_sc04_threephase,
    rule_sc05_change, rule_sc06_resident, rule_sc07_offline, rule_sc08_fixed_time_fail,
    rule_sc09_area_fail, rule_sc10_param, rule_sc11_cross, rule_sc12_anomaly,
    rule_sc13_event_uncfg, rule_sc14_fee, rule_sc15_incomplete, rule_sc16_high_loss,
    rule_sc17_complaint,
]


def run_all_rules(tables: dict, today: str, group_id: str | None = None) -> list[Recommendation]:
    """跑全部 17 条规则，返回 Recommendation 列表"""
    _reset_counter(group_id)
    all_recs: list[Recommendation] = []
    for fn in ALL_RULES:
        all_recs.extend(fn(tables, today))
    return all_recs
