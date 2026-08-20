"""
标注任务管理数据库操作。
操作表：
- s_label_task：标注任务表
- s_label_task_det：标注任务明细表
"""
from datetime import datetime
from app.core.database import (
    get_connection,
    _execute,
    _executemany,
    _date_format,
    _limit_sql,
    _is_oracle,
    _get_next_sequence,
    _now,
)


# ==================== 标注任务（s_label_task）====================

def create_label_task(task_name: str, original_sample_set_no: str, sample_labels: str):
    """创建标注任务，同时批量初始化任务明细。

    task_no 格式：YYYYMMDD + 06 + 3位序号
    record_id 为数据库自增主键，无需手动生成

    返回: task_no
    """
    date_key = datetime.now().strftime('%Y%m%d')
    seq = _get_next_sequence('LABEL_TASK_NO', date_key)
    task_no = f"{date_key}06{seq:03d}"

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 插入任务主表
            sql_task = f"""
                INSERT INTO s_label_task (task_no, task_name, original_sample_set_no, sample_labels, task_status, create_time)
                VALUES (%s, %s, %s, %s, '01', {_now()})
            """
            _execute(cursor, sql_task, (task_no, task_name, original_sample_set_no, sample_labels))

            # 2. 查询原始样本集下所有图片样本（type_code='05'，未清洗）
            sql_samples = """
                SELECT sample_no, sample_name, file_path
                FROM s_original_sample_info
                WHERE set_no = %s AND type_code = '05' AND (clean_flag = '0' OR clean_flag IS NULL)
                ORDER BY create_time ASC
            """
            _execute(cursor, sql_samples, (original_sample_set_no,))
            samples = cursor.fetchall()

            # 3. 批量插入任务明细（record_id 自增，无需插入）
            if samples:
                batch_size = 1000
                sql_det = f"""
                    INSERT INTO s_label_task_det (task_no, sample_no, sample_name, file_path, label_flag, create_time, update_time)
                    VALUES (%s, %s, %s, %s, 0, {_now()}, {_now()})
                """

                for batch_start in range(0, len(samples), batch_size):
                    batch_end = min(batch_start + batch_size, len(samples))
                    records = []
                    for i in range(batch_start, batch_end):
                        s = samples[i]
                        sample_no = s.get('sample_no') if isinstance(s, dict) else s[0]
                        sample_name = s.get('sample_name') if isinstance(s, dict) else s[1]
                        file_path = s.get('file_path') if isinstance(s, dict) else s[2]
                        records.append((task_no, sample_no, sample_name, file_path))
                    _executemany(cursor, sql_det, records)

        conn.commit()
        return task_no
    finally:
        conn.close()


def query_label_tasks():
    """查询所有标注任务列表（JOIN 原始样本集取名称，统计已标注数量）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT
                    t.task_no,
                    t.task_name,
                    t.original_sample_set_no,
                    os.set_name AS original_sample_set_name,
                    t.sample_labels,
                    t.task_status,
                    CASE t.task_status WHEN '01' THEN '进行中' WHEN '02' THEN '已完成' WHEN '03' THEN '已入库' ELSE '未知' END AS task_status_name,
                    {_date_format('t.create_time')} as create_time,
                    {_date_format('t.finish_time')} as finish_time,
                    (SELECT COUNT(*) FROM s_label_task_det d WHERE d.task_no = t.task_no) AS total_count,
                    (SELECT COUNT(*) FROM s_label_task_det d WHERE d.task_no = t.task_no AND d.label_flag IN (1, 2)) AS labeled_count
                FROM s_label_task t
                LEFT JOIN s_original_sample_set os ON t.original_sample_set_no = os.set_no
                ORDER BY t.create_time DESC
            """
            _execute(cursor, sql, ())
            return cursor.fetchall()
    finally:
        conn.close()


def get_label_task(task_no: str):
    """查询单个任务详情"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT
                    t.task_no,
                    t.task_name,
                    t.original_sample_set_no,
                    os.set_name AS original_sample_set_name,
                    t.sample_labels,
                    t.task_status,
                    {_date_format('t.create_time')} as create_time,
                    {_date_format('t.finish_time')} as finish_time,
                    (SELECT COUNT(*) FROM s_label_task_det d WHERE d.task_no = t.task_no) AS total_count,
                    (SELECT COUNT(*) FROM s_label_task_det d WHERE d.task_no = t.task_no AND d.label_flag IN (1, 2)) AS labeled_count
                FROM s_label_task t
                LEFT JOIN s_original_sample_set os ON t.original_sample_set_no = os.set_no
                WHERE t.task_no = %s
            """
            _execute(cursor, sql, (task_no,))
            return cursor.fetchone()
    finally:
        conn.close()


def update_label_task(task_no: str, task_name: str, sample_labels: str):
    """编辑任务（有标注后标签不可修改，由调用方校验）

    仅更新 task_name 和 sample_labels。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE s_label_task
                SET task_name = %s, sample_labels = %s
                WHERE task_no = %s
            """
            _execute(cursor, sql, (task_name, sample_labels, task_no))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def delete_label_task(task_no: str):
    """删除任务 + 级联删除明细"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 先删明细
            _execute(cursor, "DELETE FROM s_label_task_det WHERE task_no = %s", (task_no,))
            # 再删任务
            _execute(cursor, "DELETE FROM s_label_task WHERE task_no = %s", (task_no,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def update_label_task_status(task_no: str, status: str):
    """更新任务状态（01进行中/02已完成/03已入库）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if status == '02':
                sql = f"""
                    UPDATE s_label_task
                    SET task_status = %s, finish_time = {_now()}
                    WHERE task_no = %s
                """
            else:
                # '01' 进行中：清空 finish_time；'03' 已入库：不修改 finish_time
                if status == '01':
                    sql = """
                        UPDATE s_label_task
                        SET task_status = %s, finish_time = NULL
                        WHERE task_no = %s
                    """
                else:
                    # '03' 已入库：仅更新 task_status，保留原有 finish_time
                    sql = """
                        UPDATE s_label_task
                        SET task_status = %s
                        WHERE task_no = %s
                    """
            _execute(cursor, sql, (status, task_no))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def has_labeled_samples(task_no: str) -> bool:
    """检查任务是否有已标注的明细（用于编辑时锁定标签）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT COUNT(*) AS cnt FROM s_label_task_det WHERE task_no = %s AND label_flag = 1"
            _execute(cursor, sql, (task_no,))
            row = cursor.fetchone()
            cnt = row.get('cnt', 0) if isinstance(row, dict) else row[0]
            return int(cnt) > 0
    finally:
        conn.close()


# ==================== 标注任务明细（s_label_task_det）====================

def query_label_task_samples(task_no: str, page: int = 1, page_size: int = 50):
    """分页查询任务明细（左侧文件列表，支持几万张）

    返回: {total, rows}
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 查询总数
            _execute(cursor, "SELECT COUNT(*) AS cnt FROM s_label_task_det WHERE task_no = %s", (task_no,))
            count_row = cursor.fetchone()
            total = int(count_row.get('cnt', 0)) if isinstance(count_row, dict) else int(count_row[0])

            if total == 0:
                return {"total": 0, "rows": []}

            offset = (page - 1) * page_size
            if _is_oracle():
                sql = f"""
                    SELECT * FROM (
                        SELECT d.*,
                               {_date_format('d.update_time')} as update_time_fmt,
                               ROWNUM AS rn
                        FROM s_label_task_det d
                        WHERE d.task_no = %s AND ROWNUM <= {offset + page_size}
                        ORDER BY d.create_time ASC
                    ) WHERE rn > {offset}
                """
            else:
                sql = f"""
                    SELECT d.*,
                           {_date_format('d.update_time')} as update_time_fmt
                    FROM s_label_task_det d
                    WHERE d.task_no = %s
                    ORDER BY d.create_time ASC
                    LIMIT {page_size} OFFSET {offset}
                """
            _execute(cursor, sql, (task_no,))
            rows = cursor.fetchall()
            # 统一 update_time 字段名
            for r in rows:
                if isinstance(r, dict) and 'update_time_fmt' in r:
                    r['update_time'] = r.pop('update_time_fmt')
            return {"total": total, "rows": rows}
    finally:
        conn.close()


def get_label_sample(record_id: int):
    """获取单条明细（含 label_content）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT
                    record_id,
                    task_no,
                    sample_no,
                    sample_name,
                    file_path,
                    label_content,
                    label_flag,
                    {_date_format('update_time')} as update_time
                FROM s_label_task_det
                WHERE record_id = %s
            """
            _execute(cursor, sql, (record_id,))
            return cursor.fetchone()
    finally:
        conn.close()


def save_label_content(record_id: int, label_content: str, label_flag: int):
    """保存标注内容

    label_content: YOLO格式字符串（每行 class_id cx cy w h）
    label_flag: 0未标注 / 1已标注 / 2无缺陷
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                UPDATE s_label_task_det
                SET label_content = %s, label_flag = %s, update_time = {_now()}
                WHERE record_id = %s
            """
            _execute(cursor, sql, (label_content, label_flag, record_id))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def count_labeled_samples(task_no: str) -> int:
    """统计已标注数量"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT COUNT(*) AS cnt FROM s_label_task_det WHERE task_no = %s AND label_flag = 1"
            _execute(cursor, sql, (task_no,))
            row = cursor.fetchone()
            return int(row.get('cnt', 0)) if isinstance(row, dict) else int(row[0])
    finally:
        conn.close()


def query_labeled_samples_for_import(task_no: str):
    """查询任务下所有已标注的样本（label_flag IN 1,2），用于入库高质量样本集。

    返回字段：sample_name, file_path, label_content, label_flag
    - file_path 为原始样本的文件路径（本地路径或 minio:// 路径）
    - label_content 为 YOLO 格式标注内容（label_flag=2 时为空字符串）
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT sample_name, file_path, label_content, label_flag
                FROM s_label_task_det
                WHERE task_no = %s AND label_flag IN (1, 2)
                ORDER BY record_id ASC
            """
            _execute(cursor, sql, (task_no,))
            return cursor.fetchall()
    finally:
        conn.close()


def query_existing_sample_names(set_no: str, sample_names: list):
    """查询目标样本集中已存在的样本名称集合（用于判断同名文件）。

    返回已存在的 sample_name 集合。
    """
    if not sample_names:
        return set()
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ",".join(["%s"] * len(sample_names))
            sql = f"""
                SELECT sample_name FROM s_sample_info
                WHERE set_no = %s AND sample_name IN ({placeholders})
            """
            params = [set_no] + list(sample_names)
            _execute(cursor, sql, tuple(params))
            rows = cursor.fetchall()
            return {r.get('sample_name') if isinstance(r, dict) else r[0] for r in rows}
    finally:
        conn.close()


def update_sample_label_content(set_no: str, sample_name: str, label_content: str, label_flag: int):
    """更新目标样本集中同名样本的标注内容。

    label_flag: 1-已标注（有 YOLO 内容），0-无标注（无缺陷时 label_content 为空）
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE s_sample_info
                SET label_content = %s, label_flag = %s
                WHERE set_no = %s AND sample_name = %s
            """
            _execute(cursor, sql, (label_content, label_flag, set_no, sample_name))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
