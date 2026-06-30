"""
电表安装作业识别引擎 — 从电能表拆表/meter_install.py 重构
双 YOLO 模型 + PaddleOCR + 状态机

状态流转: recognizing_nameplate -> installing_meter -> wiring_terminal -> installation_complete
"""
from __future__ import annotations

import base64
import os
from collections import defaultdict, Counter
from pathlib import Path
from typing import Callable, Optional
import re

import cv2
import numpy as np

# ===================== 配置 =====================
_BACKEND_DIR = Path(__file__).parent.parent.parent.parent
_MODELS_POOL = _BACKEND_DIR / "models_pool" / "XC" / "meter_install"
_MAIN_MODEL_PATH = str(_MODELS_POOL / "best.pt")
_NAMEPLATE_MODEL_PATH = str(_MODELS_POOL / "nameplate_best.pt")

CONF_THRESH = 0.15
NEED_SEC = 3
BUFFER_FRAMES = 15

CLASS_ID = {
    "meter": 0,
    "cover": 1,
    "terminal": 2,
    "glove": 3,
    "screwdriver": 4,
    "wire": 5,
}

NAMEPLATE_CLASS_ID = {"nameplate": 0}


# ===================== 辅助函数 =====================

def calculate_iou(box1, box2):
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
    s_x1, s_y1, s_x2, s_y2 = screw_box
    t_x1, t_y1, t_x2, t_y2 = terminal_box
    new_t_x2 = t_x2 + (t_x2 - t_x1) * 0.25
    head_x = s_x1
    head_y = s_y1
    return t_x1 < head_x < new_t_x2 and t_y1 < head_y < t_y2


def is_cover_opened(meter_box, cover_box):
    m_x1, m_y1, m_x2, m_y2 = meter_box
    c_x1, c_y1, c_x2, c_y2 = cover_box
    meter_bottom = m_y2
    cover_bottom = c_y2
    cover_height = c_y2 - c_y1
    distance = meter_bottom - cover_bottom
    return distance > cover_height * 0.125


def _frame_to_base64_jpeg(frame, quality=80):
    ok, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode('ascii')


def _draw_annotations(frame, meters, terminals, screwdrivers, covers, gloves, wires,
                      nameplates, meter_cover_status, meter_fixed_terminal_count,
                      meter_terminal_count, meter_terminal_slot_order,
                      meter_terminal_slot_contact_time, meter_terminal_slot_wired,
                      meter_wiring_status, meter_verified_status,
                      screwdriver_meter_contact_time, SCREWDRIVER_INSTALL_TIME,
                      global_state, recognized_nameplate_text=""):
    """在帧上绘制标注框和文字"""
    # 绘制 meter 框
    for m_id, m_box in meters.items():
        if meter_wiring_status[m_id] == "success":
            meter_color = (0, 255, 0)
        else:
            meter_color = (255, 0, 0)
        cv2.rectangle(frame, (int(m_box[0]), int(m_box[1])), (int(m_box[2]), int(m_box[3])),
                      meter_color, 2)
        cover_status_text = meter_cover_status.get(m_id, "unknown")
        status_label = "Open" if cover_status_text == "open" else "Closed"
        if meter_fixed_terminal_count[m_id] > 0:
            wired_count = sum(1 for s in meter_terminal_slot_wired[m_id].values() if s)
            total_slots = meter_fixed_terminal_count[m_id]
            slot_text = f"Slots: {wired_count}/{total_slots} wired"
        else:
            terminal_count = meter_terminal_count.get(m_id, 0)
            slot_text = f"Slots: -- / Terminals: {terminal_count}"
        if meter_verified_status[m_id] == "verified":
            status_text = f"M{m_id} [VERIFIED]"
        elif meter_wiring_status[m_id] == "success":
            status_text = f"M{m_id} [SUCCESS]"
        else:
            status_text = f"M{m_id} [{status_label}]"
        cv2.putText(frame, status_text, (int(m_box[0]), int(m_box[1]) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, meter_color, 2)
        cv2.putText(frame, slot_text, (int(m_box[0]), int(m_box[1]) - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        contact_time = screwdriver_meter_contact_time.get(m_id, 0)
        contact_text = f"Screwdriver contact: {contact_time:.1f}s/{SCREWDRIVER_INSTALL_TIME}s"
        cv2.putText(frame, contact_text, (int(m_box[0]), int(m_box[1]) - 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    # 绘制 terminal 框
    for t_id, t_box in terminals.items():
        assigned_meter = None
        slot_index = None
        for m_id, slot_map in meter_terminal_slot_order.items():
            if t_id in slot_map:
                assigned_meter = m_id
                slot_index = slot_map[t_id]
                break
        if assigned_meter is not None and slot_index is not None:
            cumulative_time = meter_terminal_slot_contact_time[assigned_meter][slot_index]
            is_wired = meter_terminal_slot_wired[assigned_meter][slot_index]
            if is_wired:
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

    # 绘制 cover 框
    for c_id, c_box in covers.items():
        cv2.rectangle(frame, (int(c_box[0]), int(c_box[1])), (int(c_box[2]), int(c_box[3])),
                      (255, 255, 0), 2)
        cv2.putText(frame, f"Cover {c_id}", (int(c_box[0]), int(c_box[1]) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 1)

    # 绘制 glove 框
    for g_id, g_box in gloves.items():
        cv2.rectangle(frame, (int(g_box[0]), int(g_box[1])), (int(g_box[2]), int(g_box[3])),
                      (255, 0, 255), 2)
        cv2.putText(frame, f"Glove {g_id}", (int(g_box[0]), int(g_box[1]) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 1)

    # 绘制 wire 框
    for w_id, w_box in wires.items():
        cv2.rectangle(frame, (int(w_box[0]), int(w_box[1])), (int(w_box[2]), int(w_box[3])),
                      (0, 255, 255), 2)
        cv2.putText(frame, f"Wire {w_id}", (int(w_box[0]), int(w_box[1]) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

    # 绘制 nameplate 框
    for n_id, n_box in nameplates.items():
        cv2.rectangle(frame, (int(n_box[0]), int(n_box[1])), (int(n_box[2]), int(n_box[3])),
                      (128, 0, 128), 2)
        cv2.putText(frame, f"Nameplate {n_id}", (int(n_box[0]), int(n_box[1]) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 0, 128), 1)

    # 全局状态
    cv2.putText(frame, f"State: {global_state}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
    if recognized_nameplate_text:
        cv2.putText(frame, f"Nameplate: {recognized_nameplate_text}", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

    return frame


# ===================== 主分析函数 =====================

def analyze_video(
    video_path: str,
    output_dir: str,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> dict:
    """
    分析电表安装视频，返回标注视频路径 + 结构化报告 + 关键帧。
    """
    from ultralytics import YOLO

    model = YOLO(_MAIN_MODEL_PATH)
    nameplate_model = YOLO(_NAMEPLATE_MODEL_PATH)

    # PaddleOCR 懒加载
    ocr = None
    try:
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(lang="ch", ocr_version="PP-OCRv5", device="cpu",
                        use_doc_orientation_classify=True,
                        use_doc_unwarping=True,
                        use_textline_orientation=True)
    except Exception as e:
        print(f"[meter_install] PaddleOCR 初始化失败，将跳过 OCR: {e}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"status": "error", "message": f"无法打开视频: {video_path}"}

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    os.makedirs(output_dir, exist_ok=True)
    annotated_path = os.path.join(output_dir, "annotated_install.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_writer = cv2.VideoWriter(annotated_path, fourcc, fps, (frame_width, frame_height))

    # ---- 状态变量 ----
    global_state = "recognizing_nameplate"
    nameplate_recognized = False
    meter_installed = False
    recognized_nameplate_text = ""

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
    meter_terminal_slot_wired = defaultdict(lambda: defaultdict(bool))
    meter_terminal_slot_reached_threshold = defaultdict(lambda: defaultdict(bool))
    meter_terminal_slot_separate_frames = defaultdict(lambda: defaultdict(int))

    meter_cover_closed_aspect_stable_frame = defaultdict(int)
    METER_COVER_CLOSED_ASPECT_STABLE_FRAMES = 10

    nameplate_verify_frames = 0
    NAMEPLATE_VERIFY_FRAMES = 5

    ocr_text_history = []
    OCR_INTERVAL_FRAMES = 10
    OCR_RECOGNIZE_COUNT = 10
    last_ocr_frame = 0
    ocr_recognize_times = 0

    terminal_track = defaultdict(lambda: {"contact_frame": 0, "wired": False, "lost_frame": 0})

    meter_wiring_status = defaultdict(str)
    meter_verified_status = defaultdict(str)
    meter_wire_installation_time = {}
    meter_verified_time = {}

    any_meter_wiring_success = False
    global_success_slot_count = 0

    screwdriver_meter_contact_time = defaultdict(float)
    SCREWDRIVER_INSTALL_TIME = 5

    meter_screwdriver_contact_frames = defaultdict(int)
    METER_ASSOCIATE_FRAMES = 10

    # active wiring state（处理视角转动）
    active_wiring_state = None
    active_wiring_meter_id = None

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
        nameplate_results = nameplate_model.track(frame, conf=0.6, tracker="botsort.yaml",
                                                   persist=True, verbose=False, iou=0.4)

        res = results[0]
        nameplate_res = nameplate_results[0]
        if res.boxes is None or res.boxes.id is None:
            out_writer.write(frame)
            if progress_callback and frame_counter % 30 == 0:
                progress_callback(frame_counter, total_frames, global_state)
            continue

        # 解析检测结果
        nameplates, meters, terminals, screwdrivers, covers, gloves, wires = {}, {}, {}, {}, {}, {}, {}
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
            elif cls == CLASS_ID["wire"]:
                wires[tid] = xyxy

        if nameplate_res.boxes is not None and nameplate_res.boxes.id is not None:
            for box in nameplate_res.boxes:
                cls = int(box.cls[0])
                tid = int(box.id[0])
                xyxy = box.xyxy[0].cpu().numpy()
                if cls == NAMEPLATE_CLASS_ID["nameplate"]:
                    nameplates[tid] = xyxy

        # cover 与 meter 匹配
        meter_cover_status = {}
        used_covers = set()
        for m_id, m_box in meters.items():
            for c_id, c_box in covers.items():
                if c_id in used_covers:
                    continue
                c_center_x = (c_box[0] + c_box[2]) / 2
                c_center_y = (c_box[1] + c_box[3]) / 2
                if m_box[0] <= c_center_x <= m_box[2] and m_box[1] <= c_center_y <= m_box[3]:
                    used_covers.add(c_id)
                    if is_cover_opened(m_box, c_box):
                        meter_cover_status[m_id] = "open"
                    else:
                        meter_cover_status[m_id] = "closed"

        # ---- 状态机: recognizing_nameplate ----
        if global_state == "recognizing_nameplate":
            if len(nameplates) > 0:
                nameplate_verify_frames += 1
                if ocr is not None and frame_counter - last_ocr_frame >= OCR_INTERVAL_FRAMES and ocr_recognize_times < OCR_RECOGNIZE_COUNT:
                    last_ocr_frame = frame_counter
                    for n_id, n_box in nameplates.items():
                        x1, y1, x2, y2 = map(int, n_box)
                        nameplate_roi = frame[y1:y2, x1:x2]
                        if nameplate_roi.size > 0:
                            try:
                                ocr_result = ocr.predict(nameplate_roi)
                                if ocr_result:
                                    for ocr_res in ocr_result:
                                        if isinstance(ocr_res, dict) and 'rec_texts' in ocr_res and 'rec_scores' in ocr_res:
                                            for text, score in zip(ocr_res['rec_texts'], ocr_res['rec_scores']):
                                                if score > 0.8:
                                                    match = re.search(r'No\.\d+', text)
                                                    if match:
                                                        ocr_text_history.append(match.group())
                                        elif hasattr(ocr_res, 'rec_texts') and hasattr(ocr_res, 'rec_scores'):
                                            for text, score in zip(ocr_res.rec_texts, ocr_res.rec_scores):
                                                if score > 0.8:
                                                    match = re.search(r'No\.\d+', text)
                                                    if match:
                                                        ocr_text_history.append(match.group())
                            except Exception:
                                pass
                    ocr_recognize_times += 1
                if ocr_recognize_times >= OCR_RECOGNIZE_COUNT and not recognized_nameplate_text:
                    if ocr_text_history:
                        most_common = Counter(ocr_text_history).most_common(1)
                        if most_common:
                            recognized_nameplate_text = most_common[0][0]
                            global_state = "installing_meter"
                            nameplate_recognized = True
                            add_key_frame(frame.copy(), f"铭牌识别成功: {recognized_nameplate_text}", frame_counter)
            else:
                nameplate_verify_frames = 0
            # 如果没有 OCR，简化：检测到铭牌即跳过
            if ocr is None and len(nameplates) > 0 and not recognized_nameplate_text:
                recognized_nameplate_text = "OCR not available"
                global_state = "installing_meter"
                nameplate_recognized = True

        # ---- 状态机: installing_meter ----
        elif global_state == "installing_meter":
            for m_id, m_box in meters.items():
                if meter_installed:
                    continue
                screwdriver_in_meter = False
                for s_id, s_box in screwdrivers.items():
                    if m_box[0] <= s_box[0] <= m_box[2] and m_box[1] <= s_box[1] <= m_box[3]:
                        screwdriver_in_meter = True
                        break
                if screwdriver_in_meter:
                    screwdriver_meter_contact_time[m_id] += 1.0 / fps
                if screwdriver_meter_contact_time[m_id] > SCREWDRIVER_INSTALL_TIME:
                    meter_installed = True
                    global_state = "wiring_terminal"
                    add_key_frame(frame.copy(), f"电表安装完成 (M{m_id})", frame_counter)

        # ---- 状态机: wiring_terminal ----
        elif global_state == "wiring_terminal":
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

            # 端子槽分配
            for m_id in meters.keys():
                if meter_fixed_terminal_count[m_id] == 0:
                    continue
                m_box = meters[m_id]
                total_slots = meter_fixed_terminal_count[m_id]
                meter_terminals = [(t_id, terminals[t_id]) for t_id, assigned_m in terminal_assigned_to_meter.items() if assigned_m == m_id and t_id in terminals]
                meter_terminals.sort(key=lambda x: x[1][0])
                for slot_idx, (t_id, _) in enumerate(meter_terminals):
                    if slot_idx >= total_slots:
                        break
                    meter_terminal_slot_order[m_id][t_id] = slot_idx

            # 统计端子数
            for m_id in meters.keys():
                meter_terminal_count[m_id] = sum(1 for t_id, assigned_m in terminal_assigned_to_meter.items() if assigned_m == m_id)

            # 端子槽数量固定
            for m_id, m_box in meters.items():
                if meter_fixed_terminal_count[m_id] > 0:
                    continue
                if meter_cover_status.get(m_id) == "open" and meter_aspect_ratio_stable[m_id]:
                    meter_cover_closed_aspect_stable_frame[m_id] += 1
                    if meter_cover_closed_aspect_stable_frame[m_id] >= METER_COVER_CLOSED_ASPECT_STABLE_FRAMES:
                        meter_fixed_terminal_count[m_id] = meter_terminal_count[m_id]
                        meter_terminals = [(t_id, terminals[t_id]) for t_id, assigned_m in terminal_assigned_to_meter.items() if assigned_m == m_id and t_id in terminals]
                        meter_terminals.sort(key=lambda x: x[1][0])
                        for idx, (t_id, _) in enumerate(meter_terminals):
                            meter_terminal_slot_order[m_id][t_id] = idx
                        add_key_frame(frame.copy(), f"M{m_id} 端子槽数量固定 ({meter_fixed_terminal_count[m_id]}个)", frame_counter)
                else:
                    if meter_cover_status.get(m_id) != "open":
                        meter_cover_closed_aspect_stable_frame[m_id] = 0

            # 核心接触判断
            for t_id, t_box in terminals.items():
                if t_id not in terminal_assigned_to_meter:
                    continue
                assigned_meter = terminal_assigned_to_meter[t_id]
                if assigned_meter not in meter_terminal_slot_order or t_id not in meter_terminal_slot_order[assigned_meter]:
                    continue
                slot_index = meter_terminal_slot_order[assigned_meter][t_id]
                if meter_terminal_slot_wired[assigned_meter][slot_index]:
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
                    if meter_terminal_slot_reached_threshold[assigned_meter][slot_index] and not meter_terminal_slot_wired[assigned_meter][slot_index]:
                        meter_terminal_slot_separate_frames[assigned_meter][slot_index] += 1
                        if meter_terminal_slot_separate_frames[assigned_meter][slot_index] >= 15:
                            meter_terminal_slot_wired[assigned_meter][slot_index] = True
                            terminal_track[t_id]["wired"] = True
                            add_key_frame(frame.copy(), f"M{assigned_meter} 端子槽{slot_index} 接线成功", frame_counter)
                    terminal_track[t_id]["lost_frame"] += 1
                    if terminal_track[t_id]["lost_frame"] > BUFFER_FRAMES:
                        if not terminal_track[t_id]["wired"]:
                            terminal_track[t_id]["contact_frame"] = 0

            # 电表接线状态
            for m_id in meters.keys():
                if meter_fixed_terminal_count[m_id] == 0:
                    continue
                total_slots = meter_fixed_terminal_count[m_id]
                wired_count = sum(1 for s in meter_terminal_slot_wired[m_id].values() if s)
                if wired_count >= total_slots and meter_wiring_status[m_id] != "success":
                    meter_wiring_status[m_id] = "success"
                    meter_wire_installation_time[m_id] = frame_counter / fps
                    if not any_meter_wiring_success:
                        any_meter_wiring_success = True
                        global_success_slot_count = total_slots
                    add_key_frame(frame.copy(), f"M{m_id} 接线成功", frame_counter)

            if global_state == "wiring_terminal" and any_meter_wiring_success:
                global_state = "installation_complete"

        # ---- 状态机: installation_complete ----
        elif global_state == "installation_complete":
            for m_id in meters.keys():
                if meter_verified_status[m_id] == "verified":
                    continue
                if len(wires) == global_success_slot_count and global_success_slot_count > 0:
                    meter_verified_status[m_id] = "verified"
                    meter_verified_time[m_id] = frame_counter / fps
                    add_key_frame(frame.copy(), f"M{m_id} 安装验证通过", frame_counter)

        # 绘制标注并写入
        annotated = _draw_annotations(frame.copy(), meters, terminals, screwdrivers, covers,
                                      gloves, wires, nameplates, meter_cover_status,
                                      meter_fixed_terminal_count, meter_terminal_count,
                                      meter_terminal_slot_order, meter_terminal_slot_contact_time,
                                      meter_terminal_slot_wired, meter_wiring_status,
                                      meter_verified_status, screwdriver_meter_contact_time,
                                      SCREWDRIVER_INSTALL_TIME, global_state, recognized_nameplate_text)
        out_writer.write(annotated)

        if progress_callback and frame_counter % 30 == 0:
            progress_callback(frame_counter, total_frames, global_state)

    cap.release()
    out_writer.release()

    if progress_callback:
        progress_callback(total_frames, total_frames, "completed")

    # 构建报告
    all_meter_ids = set(list(meter_wire_installation_time.keys()) + list(meter_verified_time.keys()))
    meters_report = []
    for m_id in sorted(all_meter_ids):
        wire_time = meter_wire_installation_time.get(m_id)
        verified_time = meter_verified_time.get(m_id)
        meters_report.append({
            "meter_id": m_id,
            "wire_installation_time": round(wire_time, 2) if wire_time is not None else None,
            "verified_time": round(verified_time, 2) if verified_time is not None else None,
        })

    return {
        "status": "ok",
        "annotated_video_path": annotated_path,
        "report": {
            "final_state": global_state,
            "recognized_nameplate_text": recognized_nameplate_text if recognized_nameplate_text and recognized_nameplate_text != "OCR not available" else None,
            "meters": meters_report,
        },
        "key_frames": key_frames,
        "total_frames": frame_counter,
        "fps": round(fps, 2),
        "duration_seconds": round(frame_counter / fps, 2) if fps > 0 else 0,
    }
