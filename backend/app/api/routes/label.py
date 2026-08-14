"""标注任务管理 API 路由"""
from fastapi import APIRouter, Query
from pydantic import BaseModel
from app.core.db_label import (
    create_label_task, query_label_tasks, get_label_task,
    update_label_task, delete_label_task, update_label_task_status,
    has_labeled_samples,
    query_label_task_samples, get_label_sample, save_label_content,
    count_labeled_samples,
)
from app.core.database import _to_camel
import logging

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
    labelContent: str
    labelFlag: str


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
    # 标准化标签：支持逗号分隔和换行分隔，统一转为每行一个
    raw = req.sampleLabels or ""
    labels = []
    for part in raw.replace(',', '\n').splitlines():
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
    labels = []
    for part in raw.replace(',', '\n').splitlines():
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
    if req.status not in ('01', '02'):
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


@router.get("/samples/{recordId}")
def get_sample_api(recordId: str):
    """获取单条明细的标注内容"""
    try:
        row = get_label_sample(recordId)
        if not row:
            return {"code": 1, "message": "记录不存在"}
        return {"code": 0, "data": _to_camel(row)}
    except Exception as e:
        logger.exception("获取标注内容失败")
        return {"code": 1, "message": f"查询失败: {str(e)}"}


@router.put("/samples/{recordId}")
def save_sample_api(recordId: str, req: SaveLabelContentRequest):
    """保存标注内容（切换图片时自动调用）"""
    try:
        rowcount = save_label_content(recordId, req.labelContent, req.labelFlag)
        if rowcount == 0:
            return {"code": 1, "message": "记录不存在"}
        return {"code": 0, "message": "保存成功"}
    except Exception as e:
        logger.exception("保存标注内容失败")
        return {"code": 1, "message": f"保存失败: {str(e)}"}
