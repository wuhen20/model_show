"""
电表拆除作业识别引擎 — 从电能表拆表/meter_removal.py 重构
YOLO 目标检测 + BoT-SORT 跟踪 + 状态机

移除所有 GUI 代码 (cv2.imshow / cv2.waitKey)，改为函数化入口，
输出标注视频 + 结构化报告 + 关键帧。
"""
from __future__ import annotations

import base64
import os
import threading
from collections import defaultdict
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

# ===================== 配置 =====================
_BACKEND_DIR = Path(__file__).parent.parent.parent.parent
_MODELS_POOL = _BACKEND_DIR / "models_pool" / "XC" / "meter_remove"
_MODEL_PATH = str(_MODELS_POOL / "best.pt")

CONF_THRESH = 0.15
NEED_SEC = 3          # 螺丝刀接触端子累计时长阈值（秒）
BUFFER_FRAMES = 15     # 端子丢失缓冲帧数
GLOVE_VERIFY_FRAMES = 20

CLASS_ID = {
    "meter": 0,
    "cover": 1,
    "terminal": 2,
    "glove": 3,
    "screwdriver": 4,
}

CLASS_NAMES = {v: k for k, v in CLASS_ID.items()}


# ===================== 辅助函数 =====================

def calculate_iou(box1, box2):
    """计算两个框的交并比"""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    intersection_area = max(0, x2 - x1) * max(0, y2 - y1)
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union_area = box1_area + box2_area - intersection_area
    return intersection_area / union_area if union_area != 0 else 0


def screw_head_in_terminal(screw_box, terminal_box):
    """螺丝刀尖端检测：取左上角点判断是否在端子框内"""
    s_x1, s_y1, s_x2, s_y2 = screw_box
    t_x1, t_y1, t_x2, t_y2 = terminal_box
    head_w = (s_x2 - s_x1) * 0.05
    head_h = (s_y2 - s_y1) * 0.05
    new_t_x2 = t_x2 + (t_x2 - t_x1) * 0.25
    head_x = s_x1
    head_y = s_y1
    return t_x1 < head_x < new_t_x2 and t_y1 < head_y < t_y2


def is_cover_opened(meter_box, cover_box):
    """判断端子盖是否打开"""
    m_x1, m_y1, m_x2, m_y2 = meter_box
    c_x1, c_y1, c_x2, c_y2 = cover_box
    meter_height = m_y2 - m_y1
    meter_bottom = m_y2
    cover_center_y = (c_y1 + c_y2) / 2
    closed_threshold = meter_bottom - meter_height * 0.1
    opened_threshold_high = meter_bottom - meter_height * 0.20
    if cover_center_y <= opened_threshold_high:
        return True
    elif cover_center_y >= closed_threshold:
        return False
    else:
        return False


def get_meter_upper_3_4(meter_box):
    """获取电表框上方 3/4 区域"""
    m_x1, m_y1, m_x2, m_y2 = meter_box
    meter_height = m_y2 - m_y1
    upper_y2 = m_y1 + meter_height * 0.75
    return [m_x1, m_y1, m_x2, upper_y2]


def _frame_to_base64_jpeg(frame, quality=80):
    """将 OpenCV 帧编码为 base64 JPEG 字符串"""
    ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode('ascii')


def _draw_annotations(frame, meters, terminals, screwdrivers, covers, gloves,
                      cover_meter_match, meter_cover_status,
                      meter_fixed_terminal_count, meter_terminal_count,
                      meter_terminal_slot_order, meter_terminal_slot_contact_time,
                      meter_terminal_slot_removed, meter_removal_status,
                      meter_verified_status):
    """在帧上绘制标注框和文字"""
    # 绘制 meter 框
    for m_id, m_box in meters.items():
        if meter_removal_status[m_id] == "success":
            meter_color = (0, 255, 0)
        else:
            meter_color = (255, 0, 0)
        cv2.rectangle(frame, (int(m_box[0]), int(m_box[1])), (int(m_box[2]), int(m_box[3])),
                      meter_color, 2)
        cover_status_text = meter_cover_status.get(m_id, "unknown")
        status_label = "Open" if cover_status_text == "open" else "Closed"
        if meter_fixed_terminal_count[m_id] > 0:
            removed_count = sum(1 for s in meter_terminal_slot_removed[m_id].values() if s)
            total_slots = meter_fixed_terminal_count[m_id]
            slot_text = f"Slots: {removed_count}/{total_slots} removed"
        else:
            terminal_count = meter_terminal_count.get(m_id, 0)
            slot_text = f"Slots: -- / Terminals: {terminal_count}"
        if meter_verified_status[m_id] == "verified":
            status_text = f"M{m_id} [VERIFIED]"
        elif meter_removal_status[m_id] == "success":
            status_text = f"M{m_id} [SUCCESS]"
        else:
            status_text = f"M{m_id} [{status_label}]"
        cv2.putText(frame, status_text, (int(m_box[0]), int(m_box[1]) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, meter_color, 2)
        cv2.putText(frame, slot_text, (int(m_box[0]), int(m_box[1]) - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    # 绘制 cover 框
    for c_id, c_box in covers.items():
        if c_id in cover_meter_match:
            m_id = cover_meter_match[c_id]
            status = meter_cover_status.get(m_id, "unknown")
            if status == "open":
                color = (0, 255, 0)
                text = f"Cover {c_id}: Open"
            else:
                color = (0, 0, 255)
                text = f"Cover {c_id}: Closed"
        else:
            color = (128, 128, 128)
            text = f"Cover {c_id}: Unmatched"
        cv2.rectangle(frame, (int(c_box[0]), int(c_box[1])), (int(c_box[2]), int(c_box[3])),
                      color, 2)
        cv2.putText(frame, text, (int(c_box[0]), int(c_box[1]) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    # 绘制 terminal 框
    for t_id, t_box in terminals.items():
        if t_id in cover_meter_match if False else (t_id in {}):
            pass
        # 查找该端子所属电表
        assigned_meter = None
        slot_index = None
        for m_id, slot_map in meter_terminal_slot_order.items():
            if t_id in slot_map:
                assigned_meter = m_id
                slot_index = slot_map[t_id]
                break
        if assigned_meter is not None and slot_index is not None:
            cumulative_time = meter_terminal_slot_contact_time[assigned_meter][slot_index]
            is_removed = meter_terminal_slot_removed[assigned_meter][slot_index]
            if is_removed:
                text = f"T{t_id} Slot{slot_index}: Done {cumulative_time:.1f}s"
                color = (0, 255, 0)
            else:
                text = f"T{t_id} Slot{slot_index}: {cumulative_time:.1f}s/{NEED_SEC}s"
                color = (0, 165, 255) if cumulative_time > 0 else (0, 0, 255)
        else:
            text = f"T{t_id}: Unassigned"
            color = (128, 128, 128)
        cv2.rectangle(frame, (int(t_box[0]), int(t_box[1])), (int(t_box[2]), int(t_box[3])), color, 2)
        cv2.putText(frame, text, (int(t_box[0]), int(t_box[1]) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    # 绘制 screwdriver 框
    for s_id, s_box in screwdrivers.items():
        cv2.rectangle(frame, (int(s_box[0]), int(s_box[1])), (int(s_box[2]), int(s_box[3])),
                      (0, 255, 0), 2)
        cv2.putText(frame, f"Screwdriver {s_id}", (int(s_box[0]), int(s_box[1]) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    # 绘制 glove 框
    for g_id, g_box in gloves.items():
        cv2.rectangle(frame, (int(g_box[0]), int(g_box[1])), (int(g_box[2]), int(g_box[3])),
                      (255, 0, 255), 2)
        cv2.putText(frame, f"Glove {g_id}", (int(g_box[0]), int(g_box[1]) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

    return frame


# ===================== 主分析函数 =====================

def analyze_video(
    video_path: str,
    output_dir: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> dict:
    """
    分析电表拆除视频，返回标注视频路径 + 结构化报告 + 关键帧。

    Args:
        video_path: 输入视频文件路径
        output_dir: 输出目录（标注视频存放）
        progress_callback: 进度回调 (current_frame, total_frames, current_state)

    Returns:
        dict: 包含 status, annotated_video_path, report, key_frames, total_frames, fps, duration_seconds
    """
    from ultralytics import YOLO

    model = YOLO(_MODEL_PATH)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"status": "error", "message": f"无法打开视频: {video_path}"}

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # 输出标注视频
    os.makedirs(output_dir, exist_ok=True)
    annotated_path = os.path.join(output_dir, "annotated_removal.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_writer = cv2.VideoWriter(annotated_path, fourcc, fps, (frame_width, frame_height))

    # ---- 状态变量 ----
    terminal_track = defaultdict(lambda: {"contact_frame": 0, "removed": False, "lost_frame": 0})

    meter_aspect_ratio_history = defaultdict(list)
    meter_aspect_ratio_stable = defaultdict(bool)
    meter_aspect_ratio_stable_frame = defaultdict(int)
    ASPECT_RATIO_VARIANCE_THRESHOLD = 0.05
    ASPECT_RATIO_STABILITY_FRAMES = 10

    terminal_assigned_to_meter = {}
    meter_terminal_count = defaultdict(int)
    meter_fixed_terminal_count = defaultdict(int)

    meter_terminal_slot_order = defaultdict(dict)
    meter_terminal_slot_contact_time = defaultdict(lambda: defaultdict(float))
    meter_terminal_slot_removed = defaultdict(lambda: defaultdict(bool))
    meter_terminal_slot_reached_threshold = defaultdict(lambda: defaultdict(bool))
    meter_terminal_slot_separate_frames = defaultdict(lambda: defaultdict(int))

    meter_removal_status = defaultdict(str)
    meter_verified_status = defaultdict(str)
    meter_wire_removal_time = {}
    meter_verified_time = {}

    meter_glove_contact_frames = defaultdict(int)
    meter_cover_opened_aspect_stable_frame = defaultdict(int)
    METER_COVER_OPENED_ASPECT_STABLE_FRAMES = 10

    key_frames = []
    frame_counter = 0

    def add_key_frame(frame, title, frame_num):
        key_frames.append({
            "title": title,
            "frame": frame_num,
            "time_seconds": round(frame_num / fps, 2),
            "image": _frame_to_base64_jpeg(frame),
        })

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame_counter += 1

        results = model.track(frame, conf=CONF_THRESH, tracker="botsort.yaml",
                              persist=True, verbose=False)
        res = results[0]
        if res.boxes is None or res.boxes.id is None:
            out_writer.write(frame)
            if progress_callback and frame_counter % 30 == 0:
                progress_callback(frame_counter, total_frames, "processing")
            continue

        # 解析检测结果
        meters, terminals, screwdrivers, covers, gloves = {}, {}, {}, {}, {}
        for box in res.boxes:
            cls = int(box.cls[0])
            tid = int(box.id[0])
            xyxy = box.xyxy[0].cpu().numpy()
            if cls == CLASS_ID["meter"]:
                meters[tid] = xyxy
            elif cls == CLASS_ID["terminal"]:
                terminals[tid] = xyxy
            elif cls == CLASS_ID["screwdriver"]:
                screwdrivers[tid] = xyxy
            elif cls == CLASS_ID["cover"]:
                covers[tid] = xyxy
            elif cls == CLASS_ID["glove"]:
                gloves[tid] = xyxy

        # cover 与 meter 匹配
        cover_meter_match = {}
        meter_cover_status = {}
        used_covers = set()
        for m_id, m_box in meters.items():
            m_center_x = (m_box[0] + m_box[2]) / 2
            best_cover_id = None
            best_distance = float('inf')
            for c_id, c_box in covers.items():
                if c_id in used_covers:
                    continue
                c_center_x = (c_box[0] + c_box[2]) / 2
                distance_x = abs(m_center_x - c_center_x)
                if distance_x < (m_box[2] - m_box[0]) * 1.5:
                    if distance_x < best_distance:
                        best_distance = distance_x
                        best_cover_id = c_id
            if best_cover_id is not None:
                cover_meter_match[best_cover_id] = m_id
                used_covers.add(best_cover_id)
                if is_cover_opened(m_box, covers[best_cover_id]):
                    meter_cover_status[m_id] = "open"
                else:
                    meter_cover_status[m_id] = "closed"

        # 电表长宽比跟踪
        for m_id, m_box in meters.items():
            width = m_box[2] - m_box[0]
            height = m_box[3] - m_box[1]
            aspect_ratio = width / height if height != 0 else 1.0
            meter_aspect_ratio_history[m_id].append(aspect_ratio)
            if len(meter_aspect_ratio_history[m_id]) > ASPECT_RATIO_STABILITY_FRAMES:
                meter_aspect_ratio_history[m_id] = meter_aspect_ratio_history[m_id][-ASPECT_RATIO_STABILITY_FRAMES:]
            if len(meter_aspect_ratio_history[m_id]) >= ASPECT_RATIO_STABILITY_FRAMES:
                variance = np.var(meter_aspect_ratio_history[m_id])
                if variance < ASPECT_RATIO_VARIANCE_THRESHOLD:
                    meter_aspect_ratio_stable[m_id] = True
                    meter_aspect_ratio_stable_frame[m_id] += 1
                else:
                    meter_aspect_ratio_stable[m_id] = False
                    meter_aspect_ratio_stable_frame[m_id] = 0

        # 端子与电表关联
        for t_id, t_box in terminals.items():
            if t_id in terminal_assigned_to_meter:
                assigned_meter = terminal_assigned_to_meter[t_id]
                if assigned_meter in meters:
                    continue
                else:
                    del terminal_assigned_to_meter[t_id]
            t_center_x = (t_box[0] + t_box[2]) / 2
            t_center_y = (t_box[1] + t_box[3]) / 2
            for m_id, m_box in meters.items():
                if meter_cover_status.get(m_id) != "open":
                    continue
                if m_box[0] <= t_center_x <= m_box[2] and m_box[1] <= t_center_y <= m_box[3]:
                    terminal_assigned_to_meter[t_id] = m_id
                    break

        # 端子槽空闲匹配
        for m_id in meters.keys():
            if meter_fixed_terminal_count[m_id] == 0:
                continue
            m_box = meters[m_id]
            total_slots = meter_fixed_terminal_count[m_id]
            assigned_terminals = {t_id: terminals[t_id] for t_id, assigned_m in terminal_assigned_to_meter.items() if assigned_m == m_id and t_id in terminals}
            used_slots = set()
            for t_id in assigned_terminals:
                if t_id in meter_terminal_slot_order[m_id]:
                    used_slots.add(meter_terminal_slot_order[m_id][t_id])
            free_slots = [i for i in range(total_slots) if i not in used_slots and not meter_terminal_slot_removed[m_id][i]]
            terminals_needing_slot = [t_id for t_id in assigned_terminals if t_id not in meter_terminal_slot_order[m_id]]
            terminals_needing_slot.sort(key=lambda t_id: assigned_terminals[t_id][0])
            for t_id in terminals_needing_slot:
                if free_slots:
                    slot_idx = free_slots.pop(0)
                    meter_terminal_slot_order[m_id][t_id] = slot_idx
            unassigned_terminals = [(t_id, terminals[t_id]) for t_id in terminals.keys() if t_id not in terminal_assigned_to_meter]
            for t_id, t_box in unassigned_terminals:
                t_center_x = (t_box[0] + t_box[2]) / 2
                t_center_y = (t_box[1] + t_box[3]) / 2
                if m_box[0] <= t_center_x <= m_box[2] and m_box[1] <= t_center_y <= m_box[3] and free_slots:
                    slot_idx = free_slots.pop(0)
                    terminal_assigned_to_meter[t_id] = m_id
                    meter_terminal_slot_order[m_id][t_id] = slot_idx

        # 统计端子数
        for m_id in meters.keys():
            meter_terminal_count[m_id] = sum(1 for t_id, assigned_m in terminal_assigned_to_meter.items() if assigned_m == m_id)

        # 端子槽数量固定
        for m_id, m_box in meters.items():
            if meter_fixed_terminal_count[m_id] > 0:
                continue
            if meter_cover_status.get(m_id) == "open" and meter_aspect_ratio_stable[m_id]:
                meter_cover_opened_aspect_stable_frame[m_id] += 1
                if meter_cover_opened_aspect_stable_frame[m_id] >= METER_COVER_OPENED_ASPECT_STABLE_FRAMES:
                    meter_fixed_terminal_count[m_id] = meter_terminal_count[m_id]
                    meter_terminals = [(t_id, terminals[t_id]) for t_id, assigned_m in terminal_assigned_to_meter.items() if assigned_m == m_id and t_id in terminals]
                    meter_terminals.sort(key=lambda x: x[1][0])
                    for idx, (t_id, _) in enumerate(meter_terminals):
                        meter_terminal_slot_order[m_id][t_id] = idx
                    # 关键帧：端子槽数量固定
                    annotated = _draw_annotations(frame.copy(), meters, terminals, screwdrivers,
                                                  covers, gloves, cover_meter_match, meter_cover_status,
                                                  meter_fixed_terminal_count, meter_terminal_count,
                                                  meter_terminal_slot_order, meter_terminal_slot_contact_time,
                                                  meter_terminal_slot_removed, meter_removal_status,
                                                  meter_verified_status)
                    cv2.putText(annotated, f"State: slots_fixed (M{m_id}: {meter_fixed_terminal_count[m_id]} slots)",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    add_key_frame(annotated, f"M{m_id} 端子槽数量固定 ({meter_fixed_terminal_count[m_id]}个)", frame_counter)
            else:
                if meter_cover_status.get(m_id) != "open":
                    meter_cover_opened_aspect_stable_frame[m_id] = 0

        # 核心接触判断
        for t_id, t_box in terminals.items():
            if t_id not in terminal_assigned_to_meter:
                continue
            assigned_meter = terminal_assigned_to_meter[t_id]
            if assigned_meter not in meter_terminal_slot_order or t_id not in meter_terminal_slot_order[assigned_meter]:
                continue
            slot_index = meter_terminal_slot_order[assigned_meter][t_id]
            if meter_terminal_slot_removed[assigned_meter][slot_index]:
                continue
            in_contact = False
            for s_box in screwdrivers.values():
                if screw_head_in_terminal(s_box, t_box):
                    in_contact = True
                    break
            if in_contact:
                terminal_track[t_id]["lost_frame"] = 0
                terminal_track[t_id]["contact_frame"] += 1
                meter_terminal_slot_contact_time[assigned_meter][slot_index] += 1.0 / fps
                if meter_terminal_slot_contact_time[assigned_meter][slot_index] >= NEED_SEC:
                    meter_terminal_slot_reached_threshold[assigned_meter][slot_index] = True
                meter_terminal_slot_separate_frames[assigned_meter][slot_index] = 0
            else:
                if meter_terminal_slot_reached_threshold[assigned_meter][slot_index] and not meter_terminal_slot_removed[assigned_meter][slot_index]:
                    meter_terminal_slot_separate_frames[assigned_meter][slot_index] += 1
                    if meter_terminal_slot_separate_frames[assigned_meter][slot_index] >= 15:
                        meter_terminal_slot_removed[assigned_meter][slot_index] = True
                        terminal_track[t_id]["removed"] = True
                        # 关键帧：端子槽拆除成功
                        annotated = _draw_annotations(frame.copy(), meters, terminals, screwdrivers,
                                                      covers, gloves, cover_meter_match, meter_cover_status,
                                                      meter_fixed_terminal_count, meter_terminal_count,
                                                      meter_terminal_slot_order, meter_terminal_slot_contact_time,
                                                      meter_terminal_slot_removed, meter_removal_status,
                                                      meter_verified_status)
                        cv2.putText(annotated, f"State: slot_removed (M{assigned_meter} Slot{slot_index})",
                                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                        add_key_frame(annotated, f"M{assigned_meter} 端子槽{slot_index} 拆除成功", frame_counter)
                terminal_track[t_id]["lost_frame"] += 1
                if terminal_track[t_id]["lost_frame"] > BUFFER_FRAMES:
                    if not terminal_track[t_id]["removed"]:
                        terminal_track[t_id]["contact_frame"] = 0

        # 电表拆线成功判定
        for m_id in meters.keys():
            if meter_fixed_terminal_count[m_id] == 0:
                continue
            total_slots = meter_fixed_terminal_count[m_id]
            removed_count = sum(1 for s in meter_terminal_slot_removed[m_id].values() if s)
            if removed_count >= total_slots and meter_removal_status[m_id] != "success":
                meter_removal_status[m_id] = "success"
                meter_wire_removal_time[m_id] = frame_counter / fps
                # 关键帧：拆线成功
                annotated = _draw_annotations(frame.copy(), meters, terminals, screwdrivers,
                                              covers, gloves, cover_meter_match, meter_cover_status,
                                              meter_fixed_terminal_count, meter_terminal_count,
                                              meter_terminal_slot_order, meter_terminal_slot_contact_time,
                                              meter_terminal_slot_removed, meter_removal_status,
                                              meter_verified_status)
                cv2.putText(annotated, f"State: SUCCESS (M{m_id})", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                add_key_frame(annotated, f"M{m_id} 拆线成功", frame_counter)

        # glove 验证
        any_meter_success = any(status == "success" for status in meter_removal_status.values())
        if any_meter_success:
            for m_id in meters.keys():
                if meter_verified_status[m_id] == "verified":
                    continue
                meter_upper_3_4 = get_meter_upper_3_4(meters[m_id])
                glove_detected = False
                for g_id, g_box in gloves.items():
                    iou = calculate_iou(g_box, meter_upper_3_4)
                    if iou > 0:
                        glove_detected = True
                        break
                if glove_detected:
                    meter_glove_contact_frames[m_id] += 1
                    if meter_glove_contact_frames[m_id] >= GLOVE_VERIFY_FRAMES:
                        meter_verified_status[m_id] = "verified"
                        meter_verified_time[m_id] = frame_counter / fps
                        # 关键帧：拆除验证
                        annotated = _draw_annotations(frame.copy(), meters, terminals, screwdrivers,
                                                      covers, gloves, cover_meter_match, meter_cover_status,
                                                      meter_fixed_terminal_count, meter_terminal_count,
                                                      meter_terminal_slot_order, meter_terminal_slot_contact_time,
                                                      meter_terminal_slot_removed, meter_removal_status,
                                                      meter_verified_status)
                        cv2.putText(annotated, f"State: VERIFIED (M{m_id})", (10, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                        add_key_frame(annotated, f"M{m_id} 拆除验证通过", frame_counter)
                else:
                    meter_glove_contact_frames[m_id] = 0

        # 绘制标注并写入输出视频
        annotated = _draw_annotations(frame.copy(), meters, terminals, screwdrivers,
                                      covers, gloves, cover_meter_match, meter_cover_status,
                                      meter_fixed_terminal_count, meter_terminal_count,
                                      meter_terminal_slot_order, meter_terminal_slot_contact_time,
                                      meter_terminal_slot_removed, meter_removal_status,
                                      meter_verified_status)
        # 全局状态文字
        if any_meter_success:
            global_state = "verifying"
        elif any(meter_removal_status[m] == "success" for m in meters):
            global_state = "success"
        else:
            global_state = "processing"
        cv2.putText(annotated, f"State: {global_state}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        out_writer.write(annotated)

        if progress_callback and frame_counter % 30 == 0:
            progress_callback(frame_counter, total_frames, global_state)

    cap.release()
    out_writer.release()

    if progress_callback:
        progress_callback(total_frames, total_frames, "completed")

    # 构建报告
    all_meter_ids = set(list(meter_wire_removal_time.keys()) + list(meter_verified_time.keys()))
    meters_report = []
    for m_id in sorted(all_meter_ids):
        wire_time = meter_wire_removal_time.get(m_id)
        verified_time = meter_verified_time.get(m_id)
        meters_report.append({
            "meter_id": m_id,
            "wire_removal_time": round(wire_time, 2) if wire_time is not None else None,
            "verified_time": round(verified_time, 2) if verified_time is not None else None,
        })

    final_state = "meter_removed" if any(v == "verified" for v in meter_verified_status.values()) else \
                  ("removal_success" if any(s == "success" for s in meter_removal_status.values()) else "processing")

    return {
        "status": "ok",
        "annotated_video_path": annotated_path,
        "report": {
            "final_state": final_state,
            "meters": meters_report,
        },
        "key_frames": key_frames,
        "total_frames": frame_counter,
        "fps": round(fps, 2),
        "duration_seconds": round(frame_counter / fps, 2) if fps > 0 else 0,
    }
