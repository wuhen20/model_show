"""标注任务管理 API 路由"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.core.db_label import (
    create_label_task, query_label_tasks, get_label_task,
    update_label_task, delete_label_task, update_label_task_status,
    has_labeled_samples,
    query_label_task_samples, get_label_sample, save_label_content,
    count_labeled_samples,
    query_labeled_samples_for_import, query_existing_sample_names,
    update_sample_label_content,
)
from app.core.database import _to_camel
import logging
import os
import re
import shutil

logger = logging.getLogger("app.label")

router = APIRouter()


# ==================== 请求模型 ====================

class CreateLabelTaskRequest(BaseModel):
    taskName: str
    originalSampleSetNo: str
    sampleLabels: str


class UpdateLabelTaskRequest(BaseModel):
    taskName: str
    sampleLabels: str


class SaveLabelContentRequest(BaseModel):
    recordId: int
    labelContent: str
    labelFlag: int


class UpdateTaskStatusRequest(BaseModel):
    status: str


# ==================== 标注任务 CRUD ====================

@router.post("/tasks")
def create_task_api(req: CreateLabelTaskRequest):
    """创建标注任务（同时初始化任务明细）"""
    if not req.taskName.strip():
        return {"code": 1, "message": "任务名称不能为空"}
    if not req.originalSampleSetNo:
        return {"code": 1, "message": "请选择原始样本集"}
    # 标准化标签：支持多种分隔符，统一转为每行一个
    raw = req.sampleLabels or ""
    # 替换所有分隔符为换行符：英文逗号、中文逗号、英文分号、中文分号、顿号
    normalized = re.sub(r'[,，;；]', '\n', raw)
    labels = []
    for part in normalized.splitlines():
        s = part.strip()
        if s:
            labels.append(s)
    if not labels:
        return {"code": 1, "message": "请填写至少一个标签"}
    sample_labels = '\n'.join(labels)
    try:
        task_no = create_label_task(req.taskName.strip(), req.originalSampleSetNo, sample_labels)
        return {"code": 0, "message": "创建成功", "data": {"taskNo": task_no}}
    except Exception as e:
        logger.exception("创建标注任务失败")
        return {"code": 1, "message": f"创建失败: {str(e)}"}


@router.get("/tasks")
def list_tasks_api():
    """查询标注任务列表"""
    try:
        rows = query_label_tasks()
        return {"code": 0, "data": _to_camel(rows)}
    except Exception as e:
        logger.exception("查询标注任务列表失败")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.get("/tasks/{taskNo}")
def get_task_api(taskNo: str):
    """查询任务详情"""
    try:
        row = get_label_task(taskNo)
        if not row:
            return {"code": 1, "message": "任务不存在"}
        return {"code": 0, "data": _to_camel(row)}
    except Exception as e:
        logger.exception("查询任务详情失败")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.put("/tasks/{taskNo}")
def update_task_api(taskNo: str, req: UpdateLabelTaskRequest):
    """编辑任务（有标注后标签不可修改）"""
    if not req.taskName.strip():
        return {"code": 1, "message": "任务名称不能为空"}
    # 标准化标签
    raw = req.sampleLabels or ""
    normalized = re.sub(r'[,，;；]', '\n', raw)
    labels = []
    for part in normalized.splitlines():
        s = part.strip()
        if s:
            labels.append(s)
    if not labels:
        return {"code": 1, "message": "请填写至少一个标签"}
    sample_labels = '\n'.join(labels)
    try:
        # 检查是否有已标注明细
        if has_labeled_samples(taskNo):
            # 有标注，只更新任务名称，标签保持不变
            row = get_label_task(taskNo)
            old_labels = row.get('sample_labels', '') if row else ''
            if sample_labels != old_labels:
                # 只更新名称
                update_label_task(taskNo, req.taskName.strip(), old_labels)
                return {"code": 0, "message": "任务已有标注，标签不可修改，仅更新了任务名称"}
        update_label_task(taskNo, req.taskName.strip(), sample_labels)
        return {"code": 0, "message": "更新成功"}
    except Exception as e:
        logger.exception("编辑标注任务失败")
        return {"code": 1, "message": f"更新失败: {str(e)}"}


@router.delete("/tasks/{taskNo}")
def delete_task_api(taskNo: str):
    """删除任务（级联删除明细）"""
    try:
        rowcount = delete_label_task(taskNo)
        if rowcount == 0:
            return {"code": 1, "message": "任务不存在"}
        return {"code": 0, "message": "删除成功"}
    except Exception as e:
        logger.exception("删除标注任务失败")
        return {"code": 1, "message": f"删除失败: {str(e)}"}


@router.put("/tasks/{taskNo}/status")
def update_status_api(taskNo: str, req: UpdateTaskStatusRequest):
    """更新任务状态"""
    if req.status not in ('01', '02', '03'):
        return {"code": 1, "message": "状态值无效"}
    try:
        rowcount = update_label_task_status(taskNo, req.status)
        if rowcount == 0:
            return {"code": 1, "message": "任务不存在"}
        return {"code": 0, "message": "状态更新成功"}
    except Exception as e:
        logger.exception("更新任务状态失败")
        return {"code": 1, "message": f"更新失败: {str(e)}"}


# ==================== 标注任务明细 ====================

@router.get("/tasks/{taskNo}/samples")
def list_samples_api(taskNo: str, page: int = Query(1, ge=1), pageSize: int = Query(50, ge=1, le=200)):
    """分页查询任务明细（左侧文件列表）"""
    try:
        result = query_label_task_samples(taskNo, page, pageSize)
        return {
            "code": 0,
            "data": {
                "total": result["total"],
                "rows": _to_camel(result["rows"]),
                "page": page,
                "pageSize": pageSize,
            }
        }
    except Exception as e:
        logger.exception("查询任务明细失败")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


class GetSampleInfoRequest(BaseModel):
    recordId: int


@router.post("/sampleInfo")
def get_sample_info_api(req: GetSampleInfoRequest):
    """获取单条明细的标注内容"""
    try:
        row = get_label_sample(req.recordId)
        if not row:
            return {"code": 1, "message": "记录不存在"}
        return {"code": 0, "data": _to_camel(row)}
    except Exception as e:
        logger.exception("获取标注内容失败")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.post("/saveLabels")
def save_sample_api(req: SaveLabelContentRequest):
    """保存标注内容（切换图片时自动调用）"""
    try:
        rowcount = save_label_content(req.recordId, req.labelContent, req.labelFlag)
        if rowcount == 0:
            return {"code": 1, "message": "记录不存在"}
        return {"code": 0, "message": "保存成功"}
    except Exception as e:
        logger.exception("保存标注内容失败")
        return {"code": 1, "message": f"保存失败: {str(e)}"}


# ==================== 已标注样本入库 ====================

class ImportLabeledSamplesRequest(BaseModel):
    taskNo: str
    setNo: str
    majorVersionChange: bool = False
    versionRemark: str = ""


@router.post("/import-to-sample")
def import_labeled_samples_api(req: ImportLabeledSamplesRequest):
    """将标注任务下已标注的图片入库到高质量样本集。

    逻辑：
    - 仅允许 task_status='02'（已完成）的任务入库
    - 入库 label_flag IN (1, 2) 的样本（已标注 + 无缺陷）
    - 同名文件：不覆盖文件，仅更新 s_sample_info.label_content
    - 新文件：复制图片到样本集目录（本地/MinIO），插入 s_sample_info
    - 入库后更新 task_status 为 '03'（已入库）
    - 记录版本变更到 s_sample_version_record
    """
    from app.core.config import settings
    from app.services.sample_minio_service import (
        is_minio_enabled, is_minio_path,
        upload_image as minio_upload_image,
        download_image as minio_download_image,
    )
    from app.core.db_sample import (
        insert_sample_info, get_sample_set_path,
        apply_sample_set_version_change, reset_sample_set_quality_level,
    )

    version_remark = (req.versionRemark or "").strip()
    if len(version_remark) > 150:
        return {"code": 1, "message": "变更说明不能超过 150 个字"}

    try:
        # 1. 校验任务存在
        task = get_label_task(req.taskNo)
        if not task:
            return {"code": 1, "message": "标注任务不存在"}

        # 2. 校验目标样本集存在且为图像类型
        set_row = get_sample_set_path(req.setNo)
        if not set_row:
            return {"code": 1, "message": "目标样本集不存在"}
        # get_sample_set_path 返回 set_path, set_name, sample_labels, type_code
        set_name = set_row.get("set_name", "") if isinstance(set_row, dict) else set_row["set_name"]
        set_type_code = set_row.get("type_code", "") if isinstance(set_row, dict) else set_row["type_code"]
        if set_type_code != "05":
            return {"code": 1, "message": "目标样本集不是图像类型，无法入库"}

        # 3. 查询所有已标注样本
        samples = query_labeled_samples_for_import(req.taskNo)
        if not samples:
            return {"code": 1, "message": "任务下没有已标注的样本"}

        # 3.1 校验标注进度完成：已标注数量 = 总数量
        total_count = task.get("total_count", 0)
        labeled_count = task.get("labeled_count", 0)
        if total_count == 0 or labeled_count < total_count:
            return {"code": 1, "message": "标注进度未完成，无法入库"}

        # 4. 批量查询目标样本集中已存在的同名样本
        all_sample_names = []
        for s in samples:
            name = s.get("sample_name") if isinstance(s, dict) else s["sample_name"]
            if name:
                all_sample_names.append(name)
        existing_names = query_existing_sample_names(req.setNo, all_sample_names)

        # 5. 逐个处理样本
        use_minio = is_minio_enabled()
        target_dir = None
        if not use_minio:
            target_dir = os.path.join(settings.sample_upload_dir, req.setNo)
            os.makedirs(target_dir, exist_ok=True)

        inserted_count = 0
        updated_count = 0
        errors = []

        # 图片后缀 → content_type 映射
        content_type_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
            ".bmp": "image/bmp", ".gif": "image/gif", ".webp": "image/webp",
            ".tif": "image/tiff", ".tiff": "image/tiff",
        }

        for s in samples:
            sample_name = s.get("sample_name") if isinstance(s, dict) else s["sample_name"]
            file_path = s.get("file_path") if isinstance(s, dict) else s["file_path"]
            label_content = s.get("label_content") if isinstance(s, dict) else s["label_content"]
            label_flag = s.get("label_flag") if isinstance(s, dict) else s["label_flag"]

            # 标准化 label_content：None → 空字符串
            if label_content is None:
                label_content = ""
            # label_flag: 1=已标注 → s_sample_info.label_flag=1; 2=无缺陷 → label_flag=0（无标注内容）
            target_label_flag = 1 if label_flag == 1 else 0

            if sample_name in existing_names:
                # 同名文件：仅更新 label_content，不覆盖文件
                try:
                    update_sample_label_content(req.setNo, sample_name, label_content, target_label_flag)
                    updated_count += 1
                except Exception as e:
                    errors.append(f"{sample_name}: 更新标注失败 - {e}")
            else:
                # 新文件：复制图片到目标目录/MinIO
                try:
                    ext = os.path.splitext(sample_name)[1].lower()

                    if use_minio:
                        # MinIO 模式：从源路径下载，上传到目标样本集
                        if is_minio_path(file_path):
                            content_bytes = minio_download_image(file_path)
                        elif os.path.exists(file_path):
                            with open(file_path, "rb") as f:
                                content_bytes = f.read()
                        else:
                            errors.append(f"{sample_name}: 源文件不存在 - {file_path}")
                            continue
                        ct = content_type_map.get(ext, "application/octet-stream")
                        target_file_path = minio_upload_image(req.setNo, sample_name, content_bytes, content_type=ct)
                    else:
                        # 本地模式：复制文件
                        if is_minio_path(file_path):
                            content_bytes = minio_download_image(file_path)
                            target_file_path = os.path.join(target_dir, sample_name)
                            with open(target_file_path, "wb") as f:
                                f.write(content_bytes)
                        elif os.path.exists(file_path):
                            target_file_path = os.path.join(target_dir, sample_name)
                            # 复制文件（覆盖同名文件）
                            shutil.copy2(file_path, target_file_path)
                        else:
                            errors.append(f"{sample_name}: 源文件不存在 - {file_path}")
                            continue
                        file_size_bytes = os.path.getsize(target_file_path)

                    if use_minio:
                        file_size_bytes = len(content_bytes)

                    # 插入 s_sample_info
                    insert_sample_info(
                        set_no=req.setNo,
                        sample_name=sample_name,
                        suffix=ext.lstrip("."),
                        type_code="05",
                        file_path=target_file_path,
                        file_size=file_size_bytes,
                        label_flag=target_label_flag,
                        label_content=label_content,
                        dir_id=None,
                    )
                    inserted_count += 1
                except Exception as e:
                    errors.append(f"{sample_name}: 入库失败 - {e}")

        # 6. 新增图片时重置质量等级
        if inserted_count > 0:
            try:
                reset_sample_set_quality_level(req.setNo)
            except Exception as e:
                logger.warning(f"重置样本集质量等级失败: {e}")

        # 7. 记录版本变更（仅统计新增数量）
        ver_info = {"pre_version": "", "next_version": ""}
        if inserted_count > 0:
            try:
                ver = apply_sample_set_version_change(
                    set_no=req.setNo,
                    set_name=set_name,
                    added_count=inserted_count,
                    manual_major=bool(req.majorVersionChange),
                    manual_remark=version_remark,
                    apply_threshold=True,
                    sample_label="图片",
                )
                ver_info["pre_version"] = ver.get("pre_version", "")
                ver_info["next_version"] = ver.get("next_version", "")
            except Exception as ve:
                logger.exception("入库版本变更记录写入失败")

        # 8. 更新任务状态为已入库
        update_label_task_status(req.taskNo, "03")

        # 9. 构造返回消息
        msg = f"入库完成：新增 {inserted_count} 张，更新 {updated_count} 张"
        if errors:
            msg += f"，失败 {len(errors)} 张"
        if ver_info["pre_version"] and ver_info["next_version"]:
            msg += f"，版本 {ver_info['pre_version']} → {ver_info['next_version']}"

        return {
            "code": 0,
            "message": msg,
            "data": {
                "insertedCount": inserted_count,
                "updatedCount": updated_count,
                "errorCount": len(errors),
                "errors": errors[:10],
                "preVersion": ver_info["pre_version"],
                "nextVersion": ver_info["next_version"],
            },
        }
    except Exception as e:
        logger.exception("已标注样本入库异常")
        return {"code": 1, "message": f"入库失败: {str(e)}"}
