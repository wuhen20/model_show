"""样本批量导入分片上传 + 异步导入接口。

针对大文件（如 8GB ZIP）批量导入场景：
1. 前端将 ZIP 分片（默认 50MB/片），逐片上传到后端临时目录
2. 所有分片上传完成后，前端调用合并接口
3. 后端创建"合并中"状态记录，启动后台线程：合并分片 → 解压导入 → 更新状态
4. 前端轮询任务状态，直到完成/失败

兼容本地存储与 MinIO 存储两种模式（由 is_minio_enabled() 决定）。
兼容 MySQL 与 Oracle（使用 _execute / _now 等工具函数）。
"""
import logging
import os
import threading
import zipfile

from fastapi import APIRouter, Form, File, UploadFile, Query

from app.core.config import settings
from app.core.database import generate_import_task_no
from app.core.db_import import (
    create_import_task,
    get_import_task_by_no,
    get_import_task_by_id,
    query_import_tasks,
    update_task_status,
    increment_uploaded_chunks,
    update_import_result,
    delete_import_task,
    STATUS_PENDING, STATUS_UPLOADING, STATUS_MERGING,
    STATUS_IMPORTING, STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELED,
)
from app.services.sample_minio_service import is_minio_enabled

logger = logging.getLogger("app.upload_chunk")

router = APIRouter()


# 分片默认大小（50MB），前端可按此值切片
DEFAULT_CHUNK_SIZE = 50 * 1024 * 1024


def _get_chunk_dir(task_no: str) -> str:
    """获取任务分片临时存储目录"""
    import tempfile
    base = getattr(settings, "upload_tmp_dir", "") or tempfile.gettempdir()
    chunk_dir = os.path.join(base, "chunk_upload", task_no)
    os.makedirs(chunk_dir, exist_ok=True)
    return chunk_dir


def _get_merged_path(task_no: str, file_name: str) -> str:
    """获取合并后 ZIP 文件路径"""
    import tempfile
    base = getattr(settings, "upload_tmp_dir", "") or tempfile.gettempdir()
    merged_dir = os.path.join(base, "chunk_merged")
    os.makedirs(merged_dir, exist_ok=True)
    # 使用 task_no 作为文件名前缀，避免并发任务文件名冲突
    safe_name = file_name or "upload.zip"
    return os.path.join(merged_dir, f"{task_no}_{safe_name}")


# ==================== 任务状态查询辅助 ====================

def _task_to_dict(task: dict) -> dict:
    """将任务记录转为前端友好的 camelCase 字典"""
    if not task:
        return {}
    status = str(task.get("task_status") or "")
    status_name = {
        "01": "待上传", "02": "上传中", "03": "合并中", "04": "导入中",
        "05": "已完成", "06": "失败", "07": "已取消",
    }.get(status, "未知")
    return {
        "recordId": task.get("record_id"),
        "taskNo": task.get("task_no", ""),
        "setNo": task.get("set_no", ""),
        "setName": task.get("set_name", ""),
        "typeCode": task.get("type_code", ""),
        "source": task.get("source", ""),
        "totalChunks": task.get("total_chunks", 0),
        "uploadedChunks": task.get("uploaded_chunks", 0),
        "fileName": task.get("file_name", ""),
        "fileSize": task.get("file_size", 0),
        "taskStatusCode": status,
        "taskStatusName": status_name,
        "majorVersionChange": task.get("major_version_change", 0),
        "versionRemark": task.get("version_remark", ""),
        "imageCount": task.get("image_count", 0),
        "txtCount": task.get("txt_count", 0),
        "skippedCount": task.get("skipped_count", 0),
        "errorMessage": task.get("error_message", "") or "",
        "createTime": task.get("create_time", ""),
        "startTime": task.get("start_time", ""),
        "finishTime": task.get("finish_time", ""),
    }


# ==================== 接口 ====================

@router.post("/init")
async def init_chunk_upload(
    setNo: str = Form(...),
    setName: str = Form(...),
    typeCode: str = Form(...),
    fileName: str = Form(...),
    fileSize: int = Form(...),
    totalChunks: int = Form(...),
    source: str = Form(..., description="sample=高质量样本, original=原始样本"),
    majorVersionChange: str = Form("false"),
    versionRemark: str = Form(""),
):
    """初始化分片上传任务，返回 taskNo

    前端计算分片总数后调用此接口，后端创建任务记录并准备接收分片。
    """
    if typeCode != "05":
        return {"code": 1, "message": "批量导入仅支持图片类型（05）样本集"}
    if source not in ("sample", "original"):
        return {"code": 1, "message": "source 参数无效，应为 sample 或 original"}
    if totalChunks <= 0:
        return {"code": 1, "message": "分片总数必须大于 0"}

    # 校验变更说明长度
    version_remark = (versionRemark or "").strip()
    if len(version_remark) > 150:
        return {"code": 1, "message": "变更说明不能超过 150 个字"}

    manual_major = 1 if (majorVersionChange or "").strip().lower() in ("true", "1", "on", "yes") else 0

    try:
        task_no = generate_import_task_no()
        create_import_task(
            task_no=task_no,
            set_no=setNo,
            set_name=setName,
            type_code=typeCode,
            total_chunks=totalChunks,
            file_name=fileName,
            file_size=fileSize,
            source=source,
            major_version_change=manual_major,
            version_remark=version_remark,
        )
        # 预创建分片目录
        _get_chunk_dir(task_no)
        return {
            "code": 0,
            "message": "任务已初始化",
            "data": {"taskNo": task_no, "chunkSize": DEFAULT_CHUNK_SIZE},
        }
    except Exception as e:
        logger.exception("初始化分片上传任务失败")
        return {"code": 1, "message": f"初始化失败: {str(e)}"}


@router.post("/upload")
async def upload_chunk(
    taskNo: str = Form(...),
    chunkIndex: int = Form(..., description="分片序号，从 0 开始"),
    chunks: int = Form(..., description="分片总数"),
    file: UploadFile = File(..., description="分片数据"),
):
    """上传单个分片（同步接收，写入临时文件）

    前端可并行上传多个分片，每个分片独立保存为 chunk_{index} 文件。
    """
    task = get_import_task_by_no(taskNo)
    if not task:
        return {"code": 1, "message": "任务不存在"}
    if str(task.get("task_status") or "") in (STATUS_MERGING, STATUS_IMPORTING, STATUS_COMPLETED):
        return {"code": 1, "message": "任务已进入后续阶段，无法上传分片"}
    if str(task.get("task_status") or "") == STATUS_CANCELED:
        return {"code": 1, "message": "任务已取消"}

    # 首次上传时将状态从"待上传"改为"上传中"
    if str(task.get("task_status") or "") == STATUS_PENDING:
        update_task_status(taskNo, STATUS_UPLOADING)

    if chunkIndex < 0 or chunkIndex >= chunks:
        return {"code": 1, "message": f"分片序号无效：{chunkIndex}"}

    chunk_dir = _get_chunk_dir(taskNo)
    chunk_path = os.path.join(chunk_dir, f"chunk_{chunkIndex:06d}")

    try:
        # 流式写入分片文件
        received = 0
        with open(chunk_path, "wb") as f:
            while True:
                buf = await file.read(1024 * 1024)  # 1MB
                if not buf:
                    break
                f.write(buf)
                received += len(buf)

        # 累加已上传分片数
        uploaded = increment_uploaded_chunks(taskNo)
        return {
            "code": 0,
            "message": f"分片 {chunkIndex} 上传成功",
            "data": {
                "chunkIndex": chunkIndex,
                "received": received,
                "uploadedChunks": uploaded,
                "totalChunks": chunks,
            },
        }
    except Exception as e:
        logger.exception(f"分片 {chunkIndex} 上传失败: taskNo={taskNo}")
        return {"code": 1, "message": f"分片上传失败: {str(e)}"}


@router.post("/merge")
async def merge_chunks(
    taskNo: str = Form(...),
):
    """合并所有分片并触发异步导入

    1. 校验所有分片是否已上传完整
    2. 更新任务状态为"合并中"
    3. 启动后台线程：合并 → 解压导入 → 更新状态
    4. 立即返回，前端轮询任务状态
    """
    task = get_import_task_by_no(taskNo)
    if not task:
        return {"code": 1, "message": "任务不存在"}

    status = str(task.get("task_status") or "")
    if status in (STATUS_MERGING, STATUS_IMPORTING):
        return {"code": 1, "message": "任务正在处理中，请勿重复触发"}
    if status == STATUS_COMPLETED:
        return {"code": 1, "message": "任务已完成"}
    if status == STATUS_CANCELED:
        return {"code": 1, "message": "任务已取消"}

    total_chunks = int(task.get("total_chunks") or 0)
    uploaded_chunks = int(task.get("uploaded_chunks") or 0)
    if uploaded_chunks < total_chunks:
        return {
            "code": 1,
            "message": f"分片未上传完整（{uploaded_chunks}/{total_chunks}），请继续上传",
        }

    # 更新为"合并中"
    update_task_status(taskNo, STATUS_MERGING)

    # 启动后台线程执行合并 + 导入
    thread = threading.Thread(
        target=_merge_and_import,
        args=(taskNo,),
        name=f"chunk_import_{taskNo}",
        daemon=True,
    )
    thread.start()
    logger.info(f"分片合并导入任务 {taskNo} 已启动后台线程 {thread.ident}")

    return {
        "code": 0,
        "message": "任务已开始合并导入，请通过状态查询接口查看进度",
        "data": {"taskNo": taskNo, "async": True},
    }


@router.get("/status")
def query_chunk_status(
    taskNo: str = Query(..., description="任务编号"),
):
    """查询分片上传/导入任务状态"""
    task = get_import_task_by_no(taskNo)
    if not task:
        return {"code": 1, "message": "任务不存在"}
    return {"code": 0, "data": _task_to_dict(task)}


@router.get("/list")
def query_chunk_list(
    setNo: str = Query("", description="样本集编号，为空则返回全部"),
):
    """查询导入任务列表"""
    rows = query_import_tasks(setNo)
    return {"code": 0, "data": [_task_to_dict(r) for r in rows]}


@router.post("/cancel")
def cancel_chunk_upload(
    taskNo: str = Form(...),
):
    """取消导入任务

    仅允许在"待上传/上传中"阶段取消；合并中/导入中阶段无法取消（后台线程正在处理）。
    取消后清理临时分片文件。
    """
    task = get_import_task_by_no(taskNo)
    if not task:
        return {"code": 1, "message": "任务不存在"}

    status = str(task.get("task_status") or "")
    if status in (STATUS_MERGING, STATUS_IMPORTING):
        return {"code": 1, "message": "任务正在处理中，无法取消"}
    if status == STATUS_COMPLETED:
        return {"code": 1, "message": "任务已完成，无法取消"}
    if status == STATUS_CANCELED:
        return {"code": 0, "message": "任务已取消"}

    # 更新状态为已取消
    update_task_status(taskNo, STATUS_CANCELED)
    # 清理临时分片文件
    try:
        chunk_dir = _get_chunk_dir(taskNo)
        import shutil
        if os.path.isdir(chunk_dir):
            shutil.rmtree(chunk_dir, ignore_errors=True)
    except Exception:
        pass

    return {"code": 0, "message": "任务已取消"}


@router.post("/delete")
def delete_chunk_task(
    taskNo: str = Form(...),
):
    """删除导入任务记录（仅允许删除已完成/失败/已取消的任务）"""
    task = get_import_task_by_no(taskNo)
    if not task:
        return {"code": 1, "message": "任务不存在"}

    status = str(task.get("task_status") or "")
    if status in (STATUS_PENDING, STATUS_UPLOADING, STATUS_MERGING, STATUS_IMPORTING):
        return {"code": 1, "message": "任务进行中，无法删除"}

    delete_import_task(taskNo)
    return {"code": 0, "message": "任务已删除"}


# ==================== 后台线程：合并 + 导入 ====================

def _merge_and_import(task_no: str):
    """后台线程：合并分片 → 解压导入 → 更新任务状态

    失败时更新任务状态为"失败"并记录错误信息，确保前端轮询能感知。
    """
    task = get_import_task_by_no(task_no)
    if not task:
        logger.error(f"合并导入任务 {task_no} 不存在")
        return

    file_name = task.get("file_name", "") or "upload.zip"
    set_no = task.get("set_no", "")
    set_name = task.get("set_name", "")
    type_code = task.get("type_code", "")
    source = task.get("source", "")
    total_chunks = int(task.get("total_chunks") or 0)
    major_version_change = int(task.get("major_version_change") or 0)
    version_remark = task.get("version_remark", "") or ""

    chunk_dir = _get_chunk_dir(task_no)
    merged_path = _get_merged_path(task_no, file_name)

    try:
        # ========== 阶段一：合并分片（边合并边删除分片，峰值空间 = 分片总量 + 合并后 ZIP ≈ ZIP×1） ==========
        # 优化：合并每个分片后立即删除该分片文件，避免同时占用"分片 + 合并后 ZIP"双倍空间
        logger.info(f"任务 {task_no} 开始合并分片（共 {total_chunks} 片）")
        with open(merged_path, "wb") as out_f:
            for i in range(total_chunks):
                chunk_path = os.path.join(chunk_dir, f"chunk_{i:06d}")
                if not os.path.isfile(chunk_path):
                    raise FileNotFoundError(f"分片 {i} 不存在: {chunk_path}")
                with open(chunk_path, "rb") as in_f:
                    while True:
                        buf = in_f.read(4 * 1024 * 1024)  # 4MB
                        if not buf:
                            break
                        out_f.write(buf)
                # 合并完一个分片后立即删除，释放磁盘空间
                try:
                    os.remove(chunk_path)
                except OSError:
                    pass

        logger.info(f"任务 {task_no} 分片合并完成: {merged_path}")

        # 清理分片目录（此时目录内应已基本为空）
        try:
            import shutil
            if os.path.isdir(chunk_dir):
                shutil.rmtree(chunk_dir, ignore_errors=True)
        except Exception:
            pass

        # 校验 ZIP 有效性
        if not zipfile.is_zipfile(merged_path):
            raise ValueError("合并后的文件不是有效的 ZIP 文件")

        # ========== 阶段二：解压导入 ==========
        update_task_status(task_no, STATUS_IMPORTING)
        logger.info(f"任务 {task_no} 开始解压导入")

        use_minio = is_minio_enabled()
        target_dir = None if use_minio else os.path.join(settings.sample_upload_dir, set_name)

        from app.services.sample_import_service import extract_zip_and_import

        if source == "sample":
            # 高质量样本：txt 标注写入 DB，更新样本集标签
            from app.core.db_sample import (
                insert_sample_info,
                update_sample_set_labels,
                apply_sample_set_version_change,
            )
            result = extract_zip_and_import(
                target_dir=target_dir,
                set_no=set_no,
                set_name=set_name,
                type_code=type_code,
                insert_callback=insert_sample_info,
                zip_path=merged_path,
                use_minio=use_minio,
                write_txt_to_db=True,
                update_set_labels_callback=update_sample_set_labels,
            )
        else:
            # 原始样本：仅导入图片，跳过 txt
            from app.core.db_sample import insert_original_sample_info
            result = extract_zip_and_import(
                target_dir=target_dir,
                set_no=set_no,
                set_name=set_name,
                type_code=type_code,
                insert_callback=insert_original_sample_info,
                zip_path=merged_path,
                use_minio=use_minio,
                write_txt_to_db=False,
                update_set_labels_callback=None,
            )

        image_count = result.get("image_count", 0)
        txt_count = result.get("txt_count", 0)
        skipped_count = result.get("skipped_count", 0)
        errors = result.get("errors", []) or []

        # ========== 阶段三：版本变更（仅高质量样本） ==========
        version_msg = ""
        if source == "sample" and image_count > 0:
            try:
                ver = apply_sample_set_version_change(
                    set_no=set_no,
                    set_name=set_name,
                    added_count=image_count,
                    manual_major=bool(major_version_change),
                    manual_remark=version_remark,
                )
                version_msg = f"，版本 {ver.get('pre_version', '')} → {ver.get('next_version', '')}"
            except Exception as ve:
                logger.exception(f"任务 {task_no} 版本变更记录写入失败")
                version_msg = f"（版本变更记录写入失败: {ve}）"

        # ========== 阶段四：更新任务状态为完成 ==========
        error_msg = ""
        if errors:
            error_msg = f"失败 {len(errors)} 个: {'; '.join(str(e) for e in errors[:10])}"

        update_import_result(
            task_no=task_no,
            status=STATUS_COMPLETED,
            image_count=image_count,
            txt_count=txt_count,
            skipped_count=skipped_count,
            error_message=error_msg if error_msg else None,
        )
        logger.info(
            f"任务 {task_no} 导入完成: 图片 {image_count}, 标注 {txt_count}, "
            f"跳过 {skipped_count}{version_msg}"
        )

    except Exception as e:
        logger.exception(f"任务 {task_no} 合并导入失败")
        update_import_result(
            task_no=task_no,
            status=STATUS_FAILED,
            error_message=str(e),
        )
    finally:
        # 清理合并后的 ZIP 文件
        try:
            if os.path.isfile(merged_path):
                os.remove(merged_path)
        except Exception:
            pass
