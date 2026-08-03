"""样本批量导入任务数据库操作。

操作表：s_sample_import_task（分片上传 + 异步导入任务表）

兼容 MySQL 与 Oracle，统一使用 _execute / _now / _date_format 等工具函数。
"""
from datetime import datetime

from app.core.database import (
    get_connection,
    _execute,
    _date_format,
    _now,
    _is_oracle,
)


# ==================== 任务状态编码 ====================
# 01-待上传  02-上传中  03-合并中  04-导入中  05-已完成  06-失败  07-已取消
STATUS_PENDING = "01"
STATUS_UPLOADING = "02"
STATUS_MERGING = "03"
STATUS_IMPORTING = "04"
STATUS_COMPLETED = "05"
STATUS_FAILED = "06"
STATUS_CANCELED = "07"


def create_import_task(
    task_no: str,
    set_no: str,
    set_name: str,
    type_code: str,
    total_chunks: int,
    file_name: str,
    file_size: int,
    source: str,
    major_version_change: int = 0,
    version_remark: str = "",
    dir_id: str = "",
) -> int:
    """新增导入任务记录，返回 record_id

    Args:
        task_no: 任务编号（generate_import_task_no 生成）
        set_no: 样本集编号
        set_name: 样本集名称
        type_code: 样本类型编码（05-图片）
        total_chunks: 分片总数
        file_name: 原始 ZIP 文件名
        file_size: 文件总大小（字节）
        source: 任务来源（sample=高质量样本，original=原始样本）
        major_version_change: 是否大版本变更（0/1，仅 source=sample 有效）
        version_remark: 变更说明（仅 source=sample 有效）
        dir_id: 上传目标目录编号（空=样本集根目录）
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if _is_oracle():
                sql = f"""
                    INSERT INTO s_sample_import_task
                        (task_no, set_no, set_name, type_code, source,
                         total_chunks, uploaded_chunks, file_name, file_size,
                         task_status, major_version_change, version_remark, dir_id,
                         create_time, update_time)
                    VALUES (:1, :2, :3, :4, :5, :6, 0, :7, :8, :9, :10, :11, :12,
                            {_now()}, {_now()})
                    RETURNING record_id INTO :13
                """
                bind_var = cursor.var(int)
                cursor.execute(sql, [
                    task_no, set_no, set_name, type_code, source,
                    total_chunks, file_name, file_size,
                    STATUS_PENDING, major_version_change, version_remark, dir_id,
                    bind_var,
                ])
                new_id = bind_var.getvalue()[0]
            else:
                sql = f"""
                    INSERT INTO s_sample_import_task
                        (task_no, set_no, set_name, type_code, source,
                         total_chunks, uploaded_chunks, file_name, file_size,
                         task_status, major_version_change, version_remark, dir_id,
                         create_time, update_time)
                    VALUES (%s, %s, %s, %s, %s, %s, 0, %s, %s, %s, %s, %s, %s,
                            {_now()}, {_now()})
                """
                _execute(cursor, sql, (
                    task_no, set_no, set_name, type_code, source,
                    total_chunks, file_name, file_size,
                    STATUS_PENDING, major_version_change, version_remark, dir_id,
                ))
                new_id = cursor.lastrowid
        conn.commit()
        return new_id
    finally:
        conn.close()


def get_import_task_by_no(task_no: str) -> dict | None:
    """根据任务编号查询导入任务"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT
                    record_id, task_no, set_no, set_name, type_code, source,
                    total_chunks, uploaded_chunks, file_name, file_size,
                    task_status, major_version_change, version_remark, dir_id,
                    image_count, txt_count, skipped_count, error_message,
                    {_date_format('create_time')} as create_time,
                    {_date_format('start_time')} as start_time,
                    {_date_format('finish_time')} as finish_time,
                    {_date_format('update_time')} as update_time
                FROM s_sample_import_task
                WHERE task_no = %s
            """
            _execute(cursor, sql, (task_no,))
            return cursor.fetchone()
    finally:
        conn.close()


def get_import_task_by_id(record_id: int) -> dict | None:
    """根据记录 ID 查询导入任务"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT
                    record_id, task_no, set_no, set_name, type_code, source,
                    total_chunks, uploaded_chunks, file_name, file_size,
                    task_status, major_version_change, version_remark, dir_id,
                    image_count, txt_count, skipped_count, error_message,
                    {_date_format('create_time')} as create_time,
                    {_date_format('start_time')} as start_time,
                    {_date_format('finish_time')} as finish_time,
                    {_date_format('update_time')} as update_time
                FROM s_sample_import_task
                WHERE record_id = %s
            """
            _execute(cursor, sql, (record_id,))
            return cursor.fetchone()
    finally:
        conn.close()


def query_import_tasks(set_no: str = "") -> list[dict]:
    """查询导入任务列表，可按样本集编号过滤"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if set_no:
                sql = f"""
                    SELECT
                        record_id, task_no, set_no, set_name, type_code, source,
                        total_chunks, uploaded_chunks, file_name, file_size,
                        task_status, major_version_change, version_remark,
                        image_count, txt_count, skipped_count, error_message,
                        {_date_format('create_time')} as create_time,
                        {_date_format('start_time')} as start_time,
                        {_date_format('finish_time')} as finish_time,
                        {_date_format('update_time')} as update_time
                    FROM s_sample_import_task
                    WHERE set_no = %s
                    ORDER BY create_time DESC
                """
                _execute(cursor, sql, (set_no,))
            else:
                sql = f"""
                    SELECT
                        record_id, task_no, set_no, set_name, type_code, source,
                        total_chunks, uploaded_chunks, file_name, file_size,
                        task_status, major_version_change, version_remark,
                        image_count, txt_count, skipped_count, error_message,
                        {_date_format('create_time')} as create_time,
                        {_date_format('start_time')} as start_time,
                        {_date_format('finish_time')} as finish_time,
                        {_date_format('update_time')} as update_time
                    FROM s_sample_import_task
                    ORDER BY create_time DESC
                """
                _execute(cursor, sql, ())
            return cursor.fetchall()
    finally:
        conn.close()


def update_task_status(
    task_no: str,
    status: str,
    error_message: str = None,
):
    """更新任务状态（同时更新 update_time，失败/完成时写入 finish_time）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if status in (STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELED):
                sql = f"""
                    UPDATE s_sample_import_task
                    SET task_status = %s,
                        error_message = %s,
                        finish_time = {_now()},
                        update_time = {_now()}
                    WHERE task_no = %s
                """
                _execute(cursor, sql, (status, error_message, task_no))
            else:
                sql = f"""
                    UPDATE s_sample_import_task
                    SET task_status = %s,
                        update_time = {_now()}
                        {f", start_time = {_now()}" if status == STATUS_UPLOADING else ""}
                    WHERE task_no = %s
                """
                _execute(cursor, sql, (status, task_no))
        conn.commit()
    finally:
        conn.close()


def increment_uploaded_chunks(task_no: str) -> int:
    """分片上传成功后，uploaded_chunks +1，返回更新后的值"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                UPDATE s_sample_import_task
                SET uploaded_chunks = uploaded_chunks + 1,
                    update_time = {_now()}
                WHERE task_no = %s
            """
            _execute(cursor, sql, (task_no,))
            # 查询更新后的值
            _execute(cursor, "SELECT uploaded_chunks FROM s_sample_import_task WHERE task_no = %s", (task_no,))
            row = cursor.fetchone()
        conn.commit()
        return row["uploaded_chunks"] if row else 0
    finally:
        conn.close()


def update_import_result(
    task_no: str,
    status: str,
    image_count: int = 0,
    txt_count: int = 0,
    skipped_count: int = 0,
    error_message: str = None,
):
    """导入完成后更新任务结果"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                UPDATE s_sample_import_task
                SET task_status = %s,
                    image_count = %s,
                    txt_count = %s,
                    skipped_count = %s,
                    error_message = %s,
                    finish_time = {_now()},
                    update_time = {_now()}
                WHERE task_no = %s
            """
            _execute(cursor, sql, (
                status, image_count, txt_count, skipped_count, error_message, task_no
            ))
        conn.commit()
    finally:
        conn.close()


def delete_import_task(task_no: str):
    """删除导入任务记录"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            _execute(cursor, "DELETE FROM s_sample_import_task WHERE task_no = %s", (task_no,))
        conn.commit()
    finally:
        conn.close()
