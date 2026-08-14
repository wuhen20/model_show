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
    _get_next_sequence_batch,
    _now,
)


# ==================== 标注任务（s_label_task）====================

def create_label_task(task_name: str, original_sample_set_no: str, sample_labels: str):
    """创建标注任务，同时批量初始化任务明细。

    task_no 格式：YYYYMMDD + 06 + 3位序号
    record_id 格式：YYYYMMDD + 3位序号

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

            # 3. 批量插入任务明细（分批，每批1000条）
            if samples:
                total = len(samples)
                batch_size = 1000
                start_seq = _get_next_sequence_batch('LABEL_DET_NO', date_key, total)

                sql_det = f"""
                    INSERT INTO s_label_task_det (record_id, task_no, sample_no, sample_name, file_path, label_flag, create_time, update_time)
                    VALUES (%s, %s, %s, %s, %s, '0', {_now()}, {_now()})
                """

                for batch_start in range(0, total, batch_size):
                    batch_end = min(batch_start + batch_size, total)
                    records = []
                    for i in range(batch_start, batch_end):
                        seq_val = start_seq + i
                        record_id = f"{date_key}{seq_val:03d}"
                        s = samples[i]
                        sample_no = s.get('sample_no') if isinstance(s, dict) else s[0]
                        sample_name = s.get('sample_name') if isinstance(s, dict) else s[1]
                        file_path = s.get('file_path') if isinstance(s, dict) else s[2]
                        records.append((record_id, task_no, sample_no, sample_name, file_path))
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
                    CASE t.task_status WHEN '01' THEN '进行中' WHEN '02' THEN '已完成' ELSE '未知' END AS task_status_name,
                    {_date_format('t.create_time')} as create_time,
                    {_date_format('t.finish_time')} as finish_time,
                    (SELECT COUNT(*) FROM s_label_task_det d WHERE d.task_no = t.task_no) AS total_count,
                    (SELECT COUNT(*) FROM s_label_task_det d WHERE d.task_no = t.task_no AND d.label_flag = '1') AS labeled_count
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
                    (SELECT COUNT(*) FROM s_label_task_det d WHERE d.task_no = t.task_no AND d.label_flag = '1') AS labeled_count
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
    """更新任务状态（01进行中/02已完成）"""
    finish_time_expr = _now() if status == '02' else "NULL"
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
                sql = """
                    UPDATE s_label_task
                    SET task_status = %s, finish_time = NULL
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
            sql = "SELECT COUNT(*) AS cnt FROM s_label_task_det WHERE task_no = %s AND label_flag = '1'"
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


def get_label_sample(record_id: str):
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


def save_label_content(record_id: str, label_content: str, label_flag: str):
    """保存标注内容

    label_content: YOLO格式字符串（每行 class_id cx cy w h）
    label_flag: '0'未标注 / '1'已标注
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
            sql = "SELECT COUNT(*) AS cnt FROM s_label_task_det WHERE task_no = %s AND label_flag = '1'"
            _execute(cursor, sql, (task_no,))
            row = cursor.fetchone()
            return int(row.get('cnt', 0)) if isinstance(row, dict) else int(row[0])
    finally:
        conn.close()
