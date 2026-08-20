"""样本数据清洗 + 清洗结果 业务 SQL

从 core/database.py 拆分而来。操作表：
- 样本数据清洗：s_data_clean_task / s_data_clean_task_node / s_data_clean_log / s_data_clean_pic
- 清洗结果：s_data_clean_log（execute_status='03' 已完成记录）

仅做位置迁移，不改动任何函数实现逻辑。
"""
from datetime import datetime

from app.core.database import (
    get_connection,
    _execute,
    _executemany,
    _date_format,
    _now,
    _is_oracle,
    _show_tables_sql,
    _show_columns_sql,
    _cast_text_as_char,
)


# ==================== 样本数据清洗任务（s_data_clean_task / s_data_clean_task_node）====================

def query_data_clean_tasks():
    """查询所有清洗任务列表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT
                    task_no,
                    task_name,
                    remark,
                    task_status,
                    sample_type,
                    {_date_format('create_time')} as create_time,
                    {_date_format('last_execute_time')} as last_execute_time,
                    last_execute_flag
                FROM s_data_clean_task
                ORDER BY create_time DESC
            """
            _execute(cursor, sql, ())
            return cursor.fetchall()
    finally:
        conn.close()


def save_data_clean_task(task_no: str, task_name: str, remark: str, sample_type: str = ""):
    """新增清理任务"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_data_clean_task (task_no, task_name, remark, sample_type)
                VALUES (%s, %s, %s, %s)
            """
            _execute(cursor, sql, (task_no, task_name, remark, sample_type))
        conn.commit()
    finally:
        conn.close()


def save_data_clean_task_nodes(task_no: str, nodes: list[dict]):
    """保存清理任务流程节点（先删后插）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            _execute(cursor, "DELETE FROM s_data_clean_task_node WHERE task_no = %s", (task_no,))
            for node in nodes:
                sql = """
                    INSERT INTO s_data_clean_task_node
                        (task_no, node_id, node_type, node_name, node_config, pos_x, pos_y, prev_node_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                _execute(cursor, sql, (
                    task_no,
                    node.get("nodeId", ""),
                    node.get("nodeType", ""),
                    node.get("nodeName", ""),
                    node.get("nodeConfig", ""),
                    node.get("posX", 0),
                    node.get("posY", 0),
                    node.get("prevNodeId", None),
                ))
        conn.commit()
    finally:
        conn.close()


def query_data_clean_task_detail(task_no: str):
    """查询清理任务详情（含节点列表）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 查主表
            _execute(cursor, f"""
                SELECT
                    task_no,
                    task_name,
                    remark,
                    task_status,
                    {_date_format('create_time')} as create_time,
                    {_date_format('last_execute_time')} as last_execute_time,
                    last_execute_flag
                FROM s_data_clean_task
                WHERE task_no = %s
            """, (task_no,))
            task = cursor.fetchone()
            if not task:
                return None
            # 查节点
            _execute(cursor, """
                SELECT node_id, node_type, node_name, node_config, pos_x, pos_y, prev_node_id
                FROM s_data_clean_task_node
                WHERE task_no = %s
                ORDER BY record_id
            """, (task_no,))
            nodes = cursor.fetchall()
            task["nodes"] = nodes
            return task
    finally:
        conn.close()


def delete_data_clean_task(task_no: str):
    """删除清理任务及其节点"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            _execute(cursor, "DELETE FROM s_data_clean_task_node WHERE task_no = %s", (task_no,))
            _execute(cursor, "DELETE FROM s_data_clean_task WHERE task_no = %s", (task_no,))
        conn.commit()
    finally:
        conn.close()


def query_database_tables():
    """查询当前数据库所有表名"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            _execute(cursor, _show_tables_sql())
            rows = cursor.fetchall()
            # DictCursor 返回 {"Tables_in_xxx": "表名"}，取第一个 value
            return [list(r.values())[0] for r in rows]
    finally:
        conn.close()


def query_clean_table_columns(table_name: str):
    """查询指定表的字段列表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            _execute(cursor, _show_columns_sql(table_name))
            return cursor.fetchall()
    finally:
        conn.close()


def get_clean_task_raw(task_no: str):
    """查询清理任务原始数据+节点（执行用，不做日期格式化）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            _execute(cursor, "SELECT task_no, task_name, sample_type, task_status FROM s_data_clean_task WHERE task_no = %s", (task_no,))
            task = cursor.fetchone()
            if not task:
                return None
            _execute(cursor, """
                SELECT node_id, node_type, node_name, node_config, prev_node_id
                FROM s_data_clean_task_node
                WHERE task_no = %s
                ORDER BY record_id
            """, (task_no,))
            task["nodes"] = cursor.fetchall()
            return task
    finally:
        conn.close()


def update_clean_task_status(task_no: str, task_status: str, last_execute_flag: int = None):
    """更新清理任务状态"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if task_status == "03":
                _execute(cursor, f"""
                    UPDATE s_data_clean_task
                    SET task_status = %s, last_execute_time = {_now()}, last_execute_flag = %s
                    WHERE task_no = %s
                """, (task_status, last_execute_flag, task_no))
            else:
                _execute(cursor, """
                    UPDATE s_data_clean_task SET task_status = %s WHERE task_no = %s
                """, (task_status, task_no))
        conn.commit()
    finally:
        conn.close()


# ==================== 样本数据清洗执行记录（s_data_clean_log）====================

def insert_clean_log(task_no: str, log_content: str = None):
    """新增清理任务执行记录，返回 record_id。可同时写入初始日志内容"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if _is_oracle():
                sql = f"""
                    INSERT INTO s_data_clean_log (task_no, start_time, execute_status, execute_log)
                    VALUES (:1, {_now()}, '02', :2)
                    RETURNING record_id INTO :3
                """
                bind_var = cursor.var(int)
                cursor.execute(sql, [task_no, log_content, bind_var])
                new_id = bind_var.getvalue()[0]
            else:
                sql = f"""
                    INSERT INTO s_data_clean_log (task_no, start_time, execute_status, execute_log)
                    VALUES (%s, {_now()}, '02', %s)
                """
                _execute(cursor, sql, (task_no, log_content))
                new_id = cursor.lastrowid
        conn.commit()
        return new_id
    finally:
        conn.close()


def append_clean_log(record_id: int, log_content: str):
    """追加执行日志内容，在已有 execute_log 后追加新行（带时间戳）"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    new_line = f"[{timestamp}] {log_content}"
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT execute_log FROM s_data_clean_log WHERE record_id = %s"
            _execute(cursor, sql, (record_id,))
            row = cursor.fetchone()
            existing = row["execute_log"] if row and row["execute_log"] else ""
            updated = (existing + "\n" + new_line) if existing else new_line
            sql = "UPDATE s_data_clean_log SET execute_log = %s WHERE record_id = %s"
            _execute(cursor, sql, (updated, record_id))
        conn.commit()
    finally:
        conn.close()


def finish_clean_log(record_id: int, execute_status: str, total_count: int,
                     removed_count: int, result_count: int, log_content: str = "",
                     file_name: str = "", file_path: str = ""):
    """完成执行记录：更新状态、结束时间、统计数量，并追加最终日志

    Args:
        file_name: 清洗结果文件名（成功时传入）
        file_path: 清洗结果文件路径（成功时传入）
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 先追加日志内容
            if log_content:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                new_line = f"[{timestamp}] {log_content}"
                sql = "SELECT execute_log FROM s_data_clean_log WHERE record_id = %s"
                _execute(cursor, sql, (record_id,))
                row = cursor.fetchone()
                existing = row["execute_log"] if row and row["execute_log"] else ""
                updated = (existing + "\n" + new_line) if existing else new_line
                sql = f"""
                    UPDATE s_data_clean_log
                    SET end_time = {_now()},
                        execute_status = %s,
                        total_count = %s,
                        removed_count = %s,
                        result_count = %s,
                        execute_log = %s,
                        file_name = %s,
                        file_path = %s
                    WHERE record_id = %s
                """
                _execute(cursor, sql, (execute_status, total_count, removed_count, result_count, updated, file_name, file_path, record_id))
            else:
                sql = f"""
                    UPDATE s_data_clean_log
                    SET end_time = {_now()},
                        execute_status = %s,
                        total_count = %s,
                        removed_count = %s,
                        result_count = %s,
                        file_name = %s,
                        file_path = %s
                    WHERE record_id = %s
                """
                _execute(cursor, sql, (execute_status, total_count, removed_count, result_count, file_name, file_path, record_id))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def finish_clean_task_and_log(task_no: str, task_status: str, last_execute_flag: int,
                              record_id: int, execute_status: str,
                              total_count: int, removed_count: int, result_count: int,
                              log_content: str = "",
                              file_name: str = "", file_path: str = ""):
    """原子完成：在同一个事务中同时更新任务状态和日志状态

    确保前端轮询看到日志状态为"03"时，任务状态也一定已更新，
    避免两个独立事务之间的时间窗口导致前端看到不一致状态。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 更新任务状态
            if task_status == "03":
                _execute(cursor, f"""
                    UPDATE s_data_clean_task
                    SET task_status = %s, last_execute_time = {_now()}, last_execute_flag = %s
                    WHERE task_no = %s
                """, (task_status, last_execute_flag, task_no))
            else:
                _execute(cursor, """
                    UPDATE s_data_clean_task SET task_status = %s WHERE task_no = %s
                """, (task_status, task_no))

            # 2. 更新日志状态
            if log_content:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                new_line = f"[{timestamp}] {log_content}"
                sql = "SELECT execute_log FROM s_data_clean_log WHERE record_id = %s"
                _execute(cursor, sql, (record_id,))
                row = cursor.fetchone()
                existing = row["execute_log"] if row and row["execute_log"] else ""
                updated = (existing + "\n" + new_line) if existing else new_line
                _execute(cursor, f"""
                    UPDATE s_data_clean_log
                    SET end_time = {_now()},
                        execute_status = %s,
                        total_count = %s,
                        removed_count = %s,
                        result_count = %s,
                        execute_log = %s,
                        file_name = %s,
                        file_path = %s
                    WHERE record_id = %s
                """, (execute_status, total_count, removed_count, result_count, updated,
                      file_name, file_path, record_id))
            else:
                _execute(cursor, f"""
                    UPDATE s_data_clean_log
                    SET end_time = {_now()},
                        execute_status = %s,
                        total_count = %s,
                        removed_count = %s,
                        result_count = %s,
                        file_name = %s,
                        file_path = %s
                    WHERE record_id = %s
                """, (execute_status, total_count, removed_count, result_count,
                      file_name, file_path, record_id))

        conn.commit()
    finally:
        conn.close()


def query_clean_log(task_no: str):
    """查询清洗任务的执行记录列表

    execute_log 字段（CLOB）只截取前 1000 字符作为摘要，
    避免大 CLOB 在 Oracle 中触发 ORA-06502 缓冲区溢出。
    如需完整日志请调用 query_clean_log_detail。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if _is_oracle():
                log_expr = "DBMS_LOB.SUBSTR(execute_log, 1000, 1)"
            else:
                log_expr = "LEFT(execute_log, 1000)"
            sql = f"""
                SELECT
                    record_id,
                    task_no,
                    {_date_format('start_time')} as start_time,
                    {_date_format('end_time')} as end_time,
                    execute_status,
                    total_count,
                    removed_count,
                    result_count,
                    {log_expr} as execute_log
                FROM s_data_clean_log
                WHERE task_no = %s
                ORDER BY start_time DESC
            """
            _execute(cursor, sql, (task_no,))
            return cursor.fetchall()
    finally:
        conn.close()


# ==================== 清洗结果（s_data_clean_log execute_status）====================

def query_clean_results():
    """查询清洗结果列表（execute_status IN 03已完成/05已回滚/06文件已删除/07已入库），关联任务表获取任务名称和数据类型"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT
                    l.record_id,
                    l.task_no,
                    t.task_name,
                    t.sample_type as sample_type_code,
                    l.execute_status,
                    {_date_format('l.start_time')} as start_time,
                    {_date_format('l.end_time')} as end_time,
                    l.result_count,
                    l.removed_count,
                    l.file_name,
                    l.file_path
                FROM s_data_clean_log l
                LEFT JOIN s_data_clean_task t ON l.task_no = t.task_no
                WHERE l.execute_status IN ('03', '05', '06', '07')
                ORDER BY l.start_time DESC
            """
            _execute(cursor, sql, ())
            return cursor.fetchall()
    finally:
        conn.close()


def query_clean_status_dict():
    """查询数据清洗任务/执行记录状态字典（DATA_CLEAN_TASK_STATUS），返回 {code_value: code_name}

    同时用于 task_status 与 execute_status 的名称转码（两者共享同一套状态码）。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT CODE_VALUE, CODE_NAME
                FROM sys_code_dict
                WHERE SORT_NO = 'DATA_CLEAN_TASK_STATUS'
                  AND ACTIVE_FLAG = 1
            """
            _execute(cursor, sql, ())
            rows = cursor.fetchall()
            return {
                str(row.get("CODE_VALUE", row.get("code_value", ""))):
                str(row.get("CODE_NAME", row.get("code_name", "")))
                for row in rows
            }
    finally:
        conn.close()


# ==================== 图像清洗记录（s_data_clean_pic）====================

def query_pic_clean_type_dict():
    """查询图像清洗类型字典(PIC_CLEAN_TYPE)，返回含 SPARE1(cleanvision 编码)"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT CODE_VALUE, CODE_NAME, SPARE1
                FROM sys_code_dict
                WHERE SORT_NO = 'PIC_CLEAN_TYPE' AND ACTIVE_FLAG = 1
                ORDER BY ORDER_INDEX, RECORD_ID
            """
            _execute(cursor, sql, ())
            return cursor.fetchall()
    finally:
        conn.close()


def insert_clean_pic_record(task_no: str, clean_type: str, file_name: str, file_path: str,
                            clean_log_id: int = None,
                            repeat_file_name: str = "", repeat_file_path: str = "",
                            sample_no: str = None):
    """插入图像清洗记录到 s_data_clean_pic

    Args:
        clean_log_id: 关联的 s_data_clean_log.record_id，用于区分同一任务多次执行的结果
        repeat_file_name: 重复检测时对比图(被重复的保留图)的文件名，非重复检测为空串
        repeat_file_path: 重复检测时对比图(被重复的保留图)的路径，非重复检测为空串
        sample_no: 被清洗样本编号，回滚时按此定位 s_original_sample_info 记录恢复 CLEAN_FLAG
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_data_clean_pic
                    (task_no, clean_type, file_name, file_path, clean_log_id,
                     repeat_file_name, repeat_file_path, sample_no)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            _execute(cursor, sql, (
                task_no, clean_type, file_name, file_path, clean_log_id,
                repeat_file_name, repeat_file_path, sample_no,
            ))
        conn.commit()
    finally:
        conn.close()


def insert_clean_pic_records_batch(records: list[dict]) -> int:
    """批量插入图像清洗记录到 s_data_clean_pic（单连接单事务）

    使用 _executemany 替代循环调用 insert_clean_pic_record，显著减少连接和 commit 次数。
    Oracle 兼容由 _executemany 内部的 _convert_sql_for_oracle + _oracle_sanitize_params 处理
    （占位符 %s → :n，空串 → None）。

    Args:
        records: 记录字典列表，每个字典含字段:
            - task_no (str): 任务编号
            - clean_type (str): 清洗类型编码（多个逗号分隔）
            - file_name (str): 文件名
            - file_path (str): 原始文件路径（标记法下文件不移动，与原位置相同）
            - clean_log_id (int|None): 关联日志记录 ID
            - repeat_file_name (str): 对比图文件名（重复检测时有值）
            - repeat_file_path (str): 对比图路径（重复检测时有值）
            - sample_no (str|None): 被清洗样本编号，回滚时按此定位 s_original_sample_info 恢复 CLEAN_FLAG

    Returns:
        插入的记录数

    Raises:
        Exception: 批量插入失败时抛出，调用方应捕获并回退到逐条插入
    """
    if not records:
        return 0
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_data_clean_pic
                    (task_no, clean_type, file_name, file_path, clean_log_id,
                     repeat_file_name, repeat_file_path, sample_no)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            seq_of_params = [
                (
                    r.get("task_no", ""),
                    r.get("clean_type", ""),
                    r.get("file_name", ""),
                    r.get("file_path", ""),
                    r.get("clean_log_id"),
                    r.get("repeat_file_name", ""),
                    r.get("repeat_file_path", ""),
                    r.get("sample_no"),
                )
                for r in records
            ]
            _executemany(cursor, sql, seq_of_params)
        conn.commit()
        return len(records)
    finally:
        conn.close()


def query_clean_pic_records(task_no: str = None, clean_log_id: int = None):
    """查询图像清洗任务的被清洗图片记录，将逗号分隔的编码转换为中文名称

    Args:
        task_no: 按任务编号查询（兼容旧逻辑）
        clean_log_id: 按执行记录ID查询（精确查询某次执行的结果，优先级高于 task_no）
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 查询图片记录（优先用 clean_log_id 精确查询）
            if clean_log_id:
                sql1 = """
                    SELECT
                        record_id,
                        task_no,
                        clean_type,
                        file_name,
                        file_path,
                        clean_log_id,
                        repeat_file_name,
                        repeat_file_path,
                        sample_no
                    FROM s_data_clean_pic
                    WHERE clean_log_id = %s
                    ORDER BY record_id
                """
                _execute(cursor, sql1, (clean_log_id,))
            else:
                sql1 = """
                    SELECT
                        record_id,
                        task_no,
                        clean_type,
                        file_name,
                        file_path,
                        clean_log_id,
                        repeat_file_name,
                        repeat_file_path,
                        sample_no
                    FROM s_data_clean_pic
                    WHERE task_no = %s
                    ORDER BY record_id
                """
                _execute(cursor, sql1, (task_no,))
            records = cursor.fetchall()

            # 2. 查询 PIC_CLEAN_TYPE 字典
            sql2 = """
                SELECT CODE_VALUE, CODE_NAME
                FROM sys_code_dict
                WHERE SORT_NO = 'PIC_CLEAN_TYPE'
            """
            _execute(cursor, sql2)
            dict_rows = cursor.fetchall()

            # 3. 构建编码→名称映射
            code_map = {}
            for row in dict_rows:
                code_map[row.get("CODE_VALUE", "")] = row.get("CODE_NAME", "")

            # 4. 转换编码为中文名称
            result = []
            for row in records:
                clean_type = row.get("clean_type", "")
                # 将逗号分隔的编码转换为逗号分隔的中文名称
                type_names = []
                for code in clean_type.split(","):
                    code = code.strip()
                    if code and code in code_map:
                        type_names.append(code_map[code])
                    elif code:
                        type_names.append(code)  # 未找到映射则保留原编码
                clean_type_name = ",".join(type_names)

                result.append({
                    "record_id": row.get("record_id"),
                    "task_no": row.get("task_no", ""),
                    "clean_type": clean_type,
                    "clean_type_name": clean_type_name,
                    "file_name": row.get("file_name", ""),
                    "file_path": row.get("file_path", ""),
                    "repeat_file_name": row.get("repeat_file_name") or "",
                    "repeat_file_path": row.get("repeat_file_path") or "",
                    "sample_no": row.get("sample_no"),
                })

            return result
    finally:
        conn.close()


def update_clean_log_status(record_id: int, execute_status: str):
    """更新清洗执行记录的状态（如回滚后标记为 05-已回滚）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "UPDATE s_data_clean_log SET execute_status = %s WHERE record_id = %s"
            _execute(cursor, sql, (execute_status, record_id))
        conn.commit()
    finally:
        conn.close()


def delete_clean_pic_records(task_no: str = None, clean_log_id: int = None):
    """删除指定清洗任务的图片清洗记录

    Args:
        task_no: 按任务编号删除（兼容旧逻辑）
        clean_log_id: 按执行记录ID删除（优先级高于 task_no）
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if clean_log_id:
                sql = "DELETE FROM s_data_clean_pic WHERE clean_log_id = %s"
                _execute(cursor, sql, (clean_log_id,))
            else:
                sql = "DELETE FROM s_data_clean_pic WHERE task_no = %s"
                _execute(cursor, sql, (task_no,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
