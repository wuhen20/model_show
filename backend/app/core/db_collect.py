"""数据采集任务 + 样本中心 业务 SQL

从 core/database.py 拆分而来。操作表：
- 数据采集任务：s_data_collect_task / s_data_collect_task_det / s_data_collect_log / s_data_collect_col_map
- 样本中心：s_sample_set / s_sample_info（统计/趋势只读）

仅做位置迁移，不改动任何函数实现逻辑。
"""
from app.core.database import (
    get_connection,
    _execute,
    _executemany,
    _to_camel,
    _date_format,
    _date_format_month,
    _now,
    _curdate,
    _date_sub_month,
    _limit_sql,
    _quote_ident,
    _field_order_expr,
    _is_oracle,
)


# ==================== 样本中心（统计 / 趋势）====================

def sample_statistic():
    """统计样本中心顶部数据"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            result = {}

            # 样本集数量
            _execute(cursor, "SELECT COUNT(*) AS setCount FROM s_sample_set")
            result["setCount"] = cursor.fetchone()["setCount"]

            # 样本总量
            _execute(cursor, "SELECT COUNT(*) AS sampleCount FROM s_sample_info")
            result["sampleCount"] = cursor.fetchone()["sampleCount"]

            # 已标注样本数量（label_flag = 1 表示已标注）
            _execute(cursor, "SELECT COUNT(*) AS labeledCount FROM s_sample_info WHERE label_flag = 1")
            result["labeledCount"] = cursor.fetchone()["labeledCount"]

            # 高质量样本数量（sample_score = '01' 表示优质）
            _execute(cursor, "SELECT COUNT(*) AS highQualityCount FROM s_sample_info WHERE sample_score = '01'")
            result["highQualityCount"] = cursor.fetchone()["highQualityCount"]

            # 本月新增样本
            _execute(cursor, f"SELECT COUNT(*) AS monthNewCount FROM s_sample_info WHERE {_date_format_month('create_time')} = {_date_format_month(_curdate())}", ())
            result["monthNewCount"] = cursor.fetchone()["monthNewCount"]

            # 本月高质量样本
            _execute(cursor, f"SELECT COUNT(*) AS monthQualityCount FROM s_sample_info WHERE {_date_format_month('create_time')} = {_date_format_month(_curdate())} AND sample_score = '01'", ())
            result["monthQualityCount"] = cursor.fetchone()["monthQualityCount"]

            # 平均样本质量（数值映射法：01→100, 02→85, 03→70, 04→50）
            _execute(cursor, """
                SELECT AVG(CASE sample_score
                    WHEN '01' THEN 100
                    WHEN '02' THEN 85
                    WHEN '03' THEN 70
                    WHEN '04' THEN 50
                    ELSE NULL
                END) AS avgQualityScore
                FROM s_sample_info
                WHERE sample_score IN ('01', '02', '03', '04')
            """)
            avg_score = cursor.fetchone()["avgQualityScore"]
            result["avgQualityScore"] = round(avg_score, 1) if avg_score else 0

            # 根据平均分数映射回质量等级名称
            if avg_score is not None:
                if avg_score >= 90:
                    result["avgQualityName"] = "优质"
                elif avg_score >= 75:
                    result["avgQualityName"] = "良好"
                elif avg_score >= 60:
                    result["avgQualityName"] = "一般"
                else:
                    result["avgQualityName"] = "较差"
            else:
                result["avgQualityName"] = "未评分"

            # 样本覆盖领域（sample_field 去重计数）
            _execute(cursor, "SELECT COUNT(DISTINCT sample_field) AS domainCount FROM s_sample_set WHERE sample_field IS NOT NULL")
            result["domainCount"] = cursor.fetchone()["domainCount"]

            # 领域分布
            _execute(cursor, """
                SELECT
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = s.sample_field
                        and scd.sort_no = 'SAMPLE_FIELD') AS domain,
                    COUNT(DISTINCT s.set_no) AS setCount,
                    COUNT(si.sample_no) AS sampleCount
                FROM s_sample_set s
                LEFT JOIN s_sample_info si ON si.set_no = s.set_no
                WHERE s.sample_field IS NOT NULL
                GROUP BY s.sample_field
                ORDER BY sampleCount DESC
            """)
            result["domainDistribution"] = cursor.fetchall()

            # 质量等级分布（sample_score 为编码：01-优质/02-良好/03-一般/04-较差）
            quality_case = (
                "CASE sample_score "
                "WHEN '01' THEN '优质' "
                "WHEN '02' THEN '良好' "
                "WHEN '03' THEN '一般' "
                "WHEN '04' THEN '较差' "
                "ELSE '未评分' END"
            )
            _execute(cursor, f"""
                SELECT
                    {quality_case} AS qualityName,
                    COUNT(*) AS count
                FROM s_sample_info
                GROUP BY {quality_case}
                ORDER BY {_field_order_expr("qualityName", '优质', '良好', '一般', '较差', '未评分')}
            """)
            result["qualityDistribution"] = cursor.fetchall()

            # 样本类型分布（按s_sample_set的type_code关联s_sample_info统计）
            _execute(cursor, """
                SELECT
                    (SELECT scd.code_name FROM sys_code_dict scd
                     WHERE scd.code_value = s.type_code AND scd.sort_no = 'SAMPLE_TYPE') AS typeName,
                    COUNT(si.sample_no) AS count
                FROM s_sample_set s
                LEFT JOIN s_sample_info si ON si.set_no = s.set_no
                WHERE s.type_code IS NOT NULL
                GROUP BY s.type_code
                ORDER BY count DESC
            """)
            result["typeDistribution"] = cursor.fetchall()

            # 转换字段名为驼峰（兼容 Oracle 返回的全小写字段名）
            result["domainDistribution"] = _to_camel(result.get("domainDistribution"))
            result["qualityDistribution"] = _to_camel(result.get("qualityDistribution"))
            result["typeDistribution"] = _to_camel(result.get("typeDistribution"))

            return result
    finally:
        conn.close()


def sample_trend():
    """按月统计近5个月的样本数量"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            month_expr = _date_format_month('create_time')
            _execute(cursor, f"""
                SELECT
                    {month_expr} AS month,
                    COUNT(*) AS count
                FROM s_sample_info
                WHERE create_time >= {_date_sub_month(5)}
                GROUP BY {month_expr}
                ORDER BY month ASC
            """, ())
            rows = cursor.fetchall()
            return rows
    finally:
        conn.close()


# ==================== 数据源配置（s_database_config）====================

def query_database_config():
    """查询所有数据源配置（列表展示用，不返回密码）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT
                    c.record_id,
                    c.db_type as db_type_code,
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = c.db_type
                        and scd.sort_no = 'DATABASE_TYPE') as db_type_name,
                    c.db_alias,
                    c.db_host,
                    c.db_port,
                    c.db_usr,
                    c.db_auth,
                    c.db_name,
                    c.remark,
                    {_date_format('c.create_time')} as create_time
                FROM s_database_config c
                ORDER BY c.create_time DESC
            """
            _execute(cursor, sql, ())
            return cursor.fetchall()
    finally:
        conn.close()


def get_database_config_by_id(record_id: int):
    """按ID查询数据源配置（含密码密文，仅供后端内部连接使用）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT record_id, db_type, db_alias, db_host, db_port, db_usr, db_pwd, db_auth, db_name
                FROM s_database_config
                WHERE record_id = %s
            """
            _execute(cursor, sql, (record_id,))
            return cursor.fetchone()
    finally:
        conn.close()


def db_alias_exists(db_alias: str, exclude_record_id: int = None):
    """校验数据源名称是否已存在。exclude_record_id 用于编辑时排除自身"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if exclude_record_id is not None:
                sql = "SELECT COUNT(*) AS cnt FROM s_database_config WHERE db_alias = %s AND record_id != %s"
                _execute(cursor, sql, (db_alias, exclude_record_id))
            else:
                sql = "SELECT COUNT(*) AS cnt FROM s_database_config WHERE db_alias = %s"
                _execute(cursor, sql, (db_alias,))
            row = cursor.fetchone()
            return (row.get("cnt") or 0) > 0
    finally:
        conn.close()


def save_database_config(data: dict):
    """新增数据源配置。db_pwd 由调用方加密后传入"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_database_config
                    (db_type, db_alias, db_host, db_port, db_usr, db_pwd, db_auth, db_name, remark)
                VALUES
                    (%(dbType)s, %(dbAlias)s, %(dbHost)s, %(dbPort)s, %(dbUsr)s, %(dbPwd)s, %(dbAuth)s, %(dbName)s, %(remark)s)
            """
            _execute(cursor, sql, data)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def update_database_config(data: dict):
    """更新数据源配置。密码留空表示不修改（dbPwd 为空时不动 db_pwd 列）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if data.get("dbPwd"):
                sql = """
                    UPDATE s_database_config
                    SET db_alias = %(dbAlias)s,
                        db_host = %(dbHost)s,
                        db_port = %(dbPort)s,
                        db_usr = %(dbUsr)s,
                        db_pwd = %(dbPwd)s,
                        db_auth = %(dbAuth)s,
                        db_name = %(dbName)s,
                        remark = %(remark)s
                    WHERE record_id = %(recordId)s
                """
            else:
                sql = """
                    UPDATE s_database_config
                    SET db_alias = %(dbAlias)s,
                        db_host = %(dbHost)s,
                        db_port = %(dbPort)s,
                        db_usr = %(dbUsr)s,
                        db_auth = %(dbAuth)s,
                        db_name = %(dbName)s,
                        remark = %(remark)s
                    WHERE record_id = %(recordId)s
                """
            # Oracle oracledb 严格要求 dict 中的 key 与 SQL 占位符一一对应，
            # data 中可能含 dbType 等不在 SQL 中的 key，需过滤掉
            used_keys = {"dbAlias", "dbHost", "dbPort", "dbUsr", "dbAuth", "dbName", "remark", "recordId"}
            if data.get("dbPwd"):
                used_keys.add("dbPwd")
            filtered = {k: v for k, v in data.items() if k in used_keys}
            _execute(cursor, sql, filtered)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def count_db_config_ref(record_id: int):
    """统计数据源被采集任务明细引用的次数"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT COUNT(*) AS cnt FROM s_data_collect_task_det WHERE source_db_id = %s"
            _execute(cursor, sql, (record_id,))
            row = cursor.fetchone()
            return row.get("cnt") or 0
    finally:
        conn.close()


def delete_database_config(record_id: int):
    """删除数据源配置（调用方需先校验无任务引用）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            _execute(cursor, "DELETE FROM s_database_config WHERE record_id = %s", (record_id,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# ==================== 数据采集任务（s_data_collect_task / s_data_collect_task_det / s_data_collect_log / s_data_collect_col_map）====================

def query_data_collect_task():
    """查询所有数据采集任务"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT
                    s.task_no,
                    s.task_name,
                    s.remark,
                    {_date_format('s.create_time')} as create_time,
                    {_date_format('s.last_execute_time')} as last_execute_time,
                    s.last_execute_flag as last_execute_flag_code,
                    CASE
                        WHEN s.last_execute_flag = 0 THEN '未执行'
                        WHEN s.last_execute_flag = 1 THEN '成功'
                        WHEN s.last_execute_flag = 2 THEN '失败'
                        ELSE '未执行'
                    END as last_execute_flag_name,
                    s.task_status as task_status_code,
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = s.task_status
                        and scd.sort_no = 'DATA_COLLECT_TASK_STATUS') as task_status_name,
                    s.execute_type as execute_type_code,
                    CASE
                        WHEN s.execute_type = '01' THEN '手动'
                        WHEN s.execute_type = '02' THEN '定时'
                        ELSE '手动'
                    END as execute_type_name,
                    s.cron_formula as cron_formula,
                    s.sample_type as sample_type_code,
                    s.original_sample_set_no as sample_set_no,
                    oss.set_name as sample_set_name
                FROM s_data_collect_task s
                LEFT JOIN s_original_sample_set oss ON oss.set_no = s.original_sample_set_no
                ORDER BY s.create_time DESC
            """
            _execute(cursor, sql, ())
            return cursor.fetchall()
    finally:
        conn.close()


def save_data_collect_task(task_no: str, task_name: str, remark: str, execute_type: str = "01", cron_formula: str = "", sample_type: str = "", original_sample_set_no: str = ""):
    """新增数据采集任务。execute_type: 01-手动 02-定时"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_data_collect_task (task_no, task_name, remark, execute_type, cron_formula, sample_type, original_sample_set_no)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            _execute(cursor, sql, (task_no, task_name, remark, execute_type, cron_formula, sample_type, original_sample_set_no))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def save_data_collect_task_det(data: dict):
    """保存数据采集任务明细"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_data_collect_task_det
                    (task_no, source_db_id, target_table, collect_sql,
                     file_get_mode, bucket_name, file_id, file_name)
                VALUES
                    (%(taskNo)s, %(sourceDbId)s, %(targetTable)s, %(collectSql)s,
                     %(fileGetMode)s, %(bucketName)s, %(fileId)s, %(fileName)s)
            """
            _execute(cursor, sql, data)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def query_data_collect_task_det(task_no: str):
    """查询任务明细（JOIN 数据源配置返回源库展示信息，不含密码）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = _limit_sql(f"""
                SELECT
                    d.task_no,
                    d.source_db_id,
                    c.db_type as source_db_type,
                    c.db_alias as source_db_alias,
                    c.db_host as source_db_host,
                    c.db_port as source_db_port,
                    c.db_usr as source_db_usr,
                    c.db_auth as source_db_auth,
                    c.db_name as source_db_name,
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = c.db_type
                        and scd.sort_no = 'DATABASE_TYPE') as source_db_type_name,
                    d.target_table,
                    d.collect_sql,
                    d.file_get_mode,
                    d.bucket_name,
                    d.file_id,
                    d.file_name,
                    {_date_format('d.last_execute_time')} as last_execute_time,
                    d.last_execute_flag as last_execute_flag_code,
                    CASE
                        WHEN d.last_execute_flag = 0 THEN '未执行'
                        WHEN d.last_execute_flag = 1 THEN '成功'
                        WHEN d.last_execute_flag = 2 THEN '失败'
                        ELSE '未执行'
                    END as last_execute_flag_name,
                    t.execute_type as execute_type,
                    t.cron_formula as cron_formula,
                    t.sample_type as sample_type_code,
                    t.original_sample_set_no,
                    oss.binding_table
                FROM s_data_collect_task_det d
                LEFT JOIN s_data_collect_task t ON t.task_no = d.task_no
                LEFT JOIN s_database_config c ON c.record_id = d.source_db_id
                LEFT JOIN s_original_sample_set oss ON oss.set_no = t.original_sample_set_no
                WHERE d.task_no = %s
                ORDER BY d.record_id DESC
            """, 1)
            _execute(cursor, sql, (task_no,))
            return cursor.fetchone()
    finally:
        conn.close()


def query_task_sample_set_info(task_no: str):
    """查询采集任务关联的原始样本集信息（编号/名称/绑定表）

    直接从 s_data_collect_task 关联 s_original_sample_set 查询，
    不依赖 s_data_collect_task_det 明细行是否存在（新建任务首次进入明细页时明细可能尚未保存）。
    返回: {original_sample_set_no, set_name, binding_table}；无关联返回 None
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = _limit_sql("""
                SELECT t.original_sample_set_no,
                       oss.set_name,
                       oss.binding_table
                FROM s_data_collect_task t
                LEFT JOIN s_original_sample_set oss ON oss.set_no = t.original_sample_set_no
                WHERE t.task_no = %s
            """, 1)
            _execute(cursor, sql, (task_no,))
            return cursor.fetchone()
    finally:
        conn.close()


def update_data_collect_task_det(data: dict):
    """更新任务明细"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE s_data_collect_task_det
                SET source_db_id = %(sourceDbId)s,
                    target_table = %(targetTable)s,
                    collect_sql = %(collectSql)s,
                    file_get_mode = %(fileGetMode)s,
                    bucket_name = %(bucketName)s,
                    file_id = %(fileId)s,
                    file_name = %(fileName)s
                WHERE task_no = %(taskNo)s
            """
            _execute(cursor, sql, data)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# ==================== 任务执行相关 ====================

def get_task_det_raw(task_no: str):
    """查询任务明细原始数据（用于执行，不做日期格式化）。
    JOIN s_database_config 并以 source_db_* 别名返回源库连接信息（与旧表字段名一致，执行逻辑零改动），密码在此解密。
    """
    from app.core.crypto import sm4_decrypt
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = _limit_sql("""
                SELECT
                    d.task_no, d.source_db_id,
                    c.db_type as source_db_type, c.db_host as source_db_host, c.db_port as source_db_port,
                    c.db_usr as source_db_usr, c.db_pwd as source_db_pwd, c.db_name as source_db_name,
                    c.db_auth as source_db_auth, c.db_alias as source_db_alias,
                    d.target_table, d.collect_sql,
                    d.file_get_mode, d.bucket_name, d.file_id, d.file_name,
                    t.sample_type, t.original_sample_set_no,
                    s.set_path
                FROM s_data_collect_task_det d
                LEFT JOIN s_data_collect_task t ON t.task_no = d.task_no
                LEFT JOIN s_database_config c ON c.record_id = d.source_db_id
                LEFT JOIN s_original_sample_set s ON s.set_no = t.original_sample_set_no
                WHERE d.task_no = %s
                ORDER BY d.record_id DESC
            """, 1)
            _execute(cursor, sql, (task_no,))
            row = cursor.fetchone()
            if row and row.get("collect_sql") and isinstance(row["collect_sql"], bytes):
                row["collect_sql"] = row["collect_sql"].decode("utf-8")
            # 源库密码解密（SM4: 前缀密文解密，明文原样返回，兼容存量迁移数据）
            if row and row.get("source_db_pwd"):
                row["source_db_pwd"] = sm4_decrypt(row["source_db_pwd"])
            return row
    finally:
        conn.close()


def update_task_status(task_no: str, status: str, last_execute_flag: int = None):
    """更新任务执行状态。status: 01-未执行 02-执行中 03-已完成 04-已停止"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if last_execute_flag is not None:
                sql = f"""
                    UPDATE s_data_collect_task
                    SET task_status = %s, last_execute_time = {_now()}, last_execute_flag = %s
                    WHERE task_no = %s
                """
                _execute(cursor, sql, (status, last_execute_flag, task_no))
            else:
                sql = f"""
                    UPDATE s_data_collect_task
                    SET task_status = %s, last_execute_time = {_now()}
                    WHERE task_no = %s
                """
                _execute(cursor, sql, (status, task_no))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def insert_collect_log(task_no: str, log_content: str = None):
    """插入执行日志，返回 log_id。可同时写入初始日志内容"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if _is_oracle():
                sql = f"""
                    INSERT INTO s_data_collect_log (task_no, start_time, execute_status, execute_log)
                    VALUES (:1, {_now()}, 0, :2)
                    RETURNING record_id INTO :3
                """
                bind_var = cursor.var(int)
                cursor.execute(sql, [task_no, log_content, bind_var])
                new_id = bind_var.getvalue()[0]
            else:
                sql = f"""
                    INSERT INTO s_data_collect_log (task_no, start_time, execute_status, execute_log)
                    VALUES (%s, {_now()}, 0, %s)
                """
                _execute(cursor, sql, (task_no, log_content))
                new_id = cursor.lastrowid
        conn.commit()
        return new_id
    finally:
        conn.close()


def append_collect_log(log_id: int, log_content: str):
    """追加执行日志内容，在已有 execute_log 后追加新行"""
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y-%m-%d %H%M%S')
    new_line = f"[{timestamp}] {log_content}"
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT execute_log FROM s_data_collect_log WHERE record_id = %s
            """
            _execute(cursor, sql, (log_id,))
            row = cursor.fetchone()
            existing = row["execute_log"] if row and row["execute_log"] else ""
            if existing:
                updated = existing + "\n" + new_line
            else:
                updated = new_line
            sql = """
                UPDATE s_data_collect_log SET execute_log = %s WHERE record_id = %s
            """
            _execute(cursor, sql, (updated, log_id))
        conn.commit()
    finally:
        conn.close()


def finish_collect_log(log_id: int, success: bool, log_content: str = None):
    """更新执行日志：结束时间、执行结果、追加日志"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 先追加日志内容
            if log_content:
                from datetime import datetime
                timestamp = datetime.now().strftime('%Y-%m-%d %H%M%S')
                new_line = f"[{timestamp}] {log_content}"
                sql = """
                    SELECT execute_log FROM s_data_collect_log WHERE record_id = %s
                """
                _execute(cursor, sql, (log_id,))
                row = cursor.fetchone()
                existing = row["execute_log"] if row and row["execute_log"] else ""
                if existing:
                    updated = existing + "\n" + new_line
                else:
                    updated = new_line
                sql = f"""
                    UPDATE s_data_collect_log
                    SET end_time = {_now()}, execute_status = %s, execute_log = %s
                    WHERE record_id = %s
                """
                _execute(cursor, sql, (1 if success else 0, updated, log_id))
            else:
                sql = f"""
                    UPDATE s_data_collect_log
                    SET end_time = {_now()}, execute_status = %s
                    WHERE record_id = %s
                """
                _execute(cursor, sql, (1 if success else 0, log_id))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def query_collect_log(task_no: str):
    """查询任务执行记录列表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT
                    record_id,
                    task_no,
                    {_date_format('start_time')} as start_time,
                    {_date_format('end_time')} as end_time,
                    execute_status as execute_status_code,
                    CASE
                        WHEN execute_status = 1 THEN '成功'
                        WHEN end_time IS NULL THEN '执行中'
                        ELSE '失败'
                    END as execute_status_name,
                    execute_log
                FROM s_data_collect_log
                WHERE task_no = %s
                ORDER BY start_time DESC
            """
            _execute(cursor, sql, (task_no,))
            rows = cursor.fetchall()
            for row in rows:
                if row.get("execute_log") and isinstance(row["execute_log"], bytes):
                    row["execute_log"] = row["execute_log"].decode("utf-8")
            return rows
    finally:
        conn.close()


def query_all_scheduled_tasks():
    """查询所有定时执行方式（execute_type='02'）的采集任务，用于调度器加载"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT task_no, task_name, cron_formula
                FROM s_data_collect_task
                WHERE execute_type = '02'
                  AND cron_formula IS NOT NULL
            """
            _execute(cursor, sql, ())
            return cursor.fetchall()
    finally:
        conn.close()


def get_task_execute_type(task_no: str):
    """查询任务当前的执行方式和 cron 表达式"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT execute_type, cron_formula
                FROM s_data_collect_task
                WHERE task_no = %s
            """
            _execute(cursor, sql, (task_no,))
            return cursor.fetchone()
    finally:
        conn.close()


def update_task_execute_type(task_no: str, execute_type: str, cron_formula: str = ""):
    """更新任务的执行方式和 cron 表达式。execute_type: 01-手动 02-定时"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE s_data_collect_task
                SET execute_type = %s, cron_formula = %s
                WHERE task_no = %s
            """
            _execute(cursor, sql, (execute_type, cron_formula, task_no))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def delete_data_collect_task(task_no: str):
    """删除数据采集任务及其全部关联数据（明细、字段映射、执行日志）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            _execute(cursor, "DELETE FROM s_data_collect_col_map WHERE task_no = %s", (task_no,))
            _execute(cursor, "DELETE FROM s_data_collect_log WHERE task_no = %s", (task_no,))
            _execute(cursor, "DELETE FROM s_data_collect_task_det WHERE task_no = %s", (task_no,))
            _execute(cursor, "DELETE FROM s_data_collect_task WHERE task_no = %s", (task_no,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def execute_source_sql(db_type: str, host: str, port: str, user: str, pwd: str, database: str, sql: str, auth: str = ""):
    """连接源数据库执行SQL，返回 (columns, rows)。auth 仅 Hive 使用，可选 NONE/LDAP/PLAIN/KERBEROS/CUSTOM"""
    if db_type == "01":
        # MySQL
        import pymysql
        conn = pymysql.connect(
            host=host,
            port=int(port) if port else 3306,
            user=user,
            password=pwd,
            database=database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
        )
    elif db_type == "02":
        # Oracle
        import oracledb
        dsn = f"{host}:{port or 1521}/{database}" if database else f"{host}:{port or 1521}"
        kwargs = dict(user=user, password=pwd, dsn=dsn)
        # SYS 用户必须以 SYSDBA/SYSOPER 模式连接，默认 SYSDBA
        if user and user.upper() == "SYS":
            kwargs["mode"] = oracledb.SYSDBA
        conn = oracledb.connect(**kwargs)
    elif db_type == "03":
        # Hive
        from pyhive import hive
        _auth = auth or "NONE"
        _hive_kwargs = dict(
            host=host,
            port=int(port) if port else 10000,
            username=user,
            database=database or "default",
            auth=_auth,
        )
        # NONE 模式不允许传 password，LDAP/CUSTOM 模式才需要
        if _auth not in ("NONE", "NOSASL") and pwd:
            _hive_kwargs["password"] = pwd
        conn = hive.Connection(**_hive_kwargs)
    else:
        raise ValueError(f"不支持的数据库类型: {db_type}")

    try:
        with conn.cursor() as cursor:
            # 去掉末尾分号，Hive/pyhive 不支持分号结尾
            sql = sql.rstrip().rstrip(';').rstrip()
            cursor.execute(sql)
            rows = cursor.fetchall()
            if db_type == "01":
                # pymysql DictCursor
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                row_list = [tuple(row.values()) for row in rows]
            elif db_type == "03":
                # Hive 返回列名可能带表别名前缀如 a.col_name，去掉前缀
                columns = [desc[0].lower().split('.')[-1] for desc in cursor.description] if cursor.description else []
                row_list = [tuple(row) for row in rows]
            else:
                # Oracle 等返回 tuple 列表，列名统一转小写
                columns = [desc[0].lower() for desc in cursor.description] if cursor.description else []
                row_list = [tuple(row) for row in rows]
            return columns, row_list
    finally:
        conn.close()


def write_to_target_table(target_table: str, col_map: list[dict], columns: list, rows: list):
    """根据字段映射将数据追加写入本地数据库的目标表（纯 INSERT，不清空旧数据）。

    多个采集任务 / CSV 导入共用样本集绑定的同一张目标表，全量数据沉淀，
    因此写入前不再 DELETE 清空。同一任务重复执行会产生追加数据。
    col_map: [{source_column, target_colum}, ...]
    columns: 源SQL查询结果的列名列表
    rows: 源SQL查询结果的数据行（每行为tuple）
    返回成功写入的行数
    """
    if not col_map:
        raise ValueError("字段映射配置为空，请先配置字段映射")

    # 构建源列名的小写映射：lowercase列名 -> 原始索引（用于大小写不敏感匹配）
    columns_lower_map = {col.lower(): i for i, col in enumerate(columns)}

    # 构建映射关系：源列索引 -> 目标列名
    col_index_map = {}
    for m in col_map:
        src_col = m["source_column"]
        tgt_col = m["target_colum"]
        src_col_lower = src_col.lower()
        if src_col_lower in columns_lower_map:
            col_index_map[columns_lower_map[src_col_lower]] = tgt_col

    if not col_index_map:
        matched_info = f"映射配置的源列: {[m['source_column'] for m in col_map]}, SQL查询结果的列: {columns}"
        raise ValueError(f"字段映射中没有匹配到源SQL查询结果的列。{matched_info}")

    # 排序保证顺序一致
    sorted_indices = sorted(col_index_map.keys())
    target_columns = [col_index_map[i] for i in sorted_indices]

    # 构建INSERT语句
    col_names = ", ".join(_quote_ident(c) for c in target_columns)
    placeholders = ", ".join(["%s"] * len(target_columns))
    insert_sql = f"INSERT INTO {_quote_ident(target_table)} ({col_names}) VALUES ({placeholders})"

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 追加写入数据（不再清空目标表旧数据）
            batch_values = []
            for row in rows:
                values = tuple(row[i] if i < len(row) else None for i in sorted_indices)
                batch_values.append(values)
            _executemany(cursor, insert_sql, batch_values)
        conn.commit()
        return len(batch_values)
    finally:
        conn.close()


def query_target_table_columns(db_type: str, host: str, port: str, user: str, pwd: str, database: str, table_name: str, auth: str = ""):
    """查询目标表的字段信息，返回 [{column_name, column_type, column_comment}]。auth 仅 Hive 使用"""
    if db_type == "01":
        # MySQL
        import pymysql
        conn = pymysql.connect(
            host=host,
            port=int(port) if port else 3306,
            user=user,
            password=pwd,
            database=database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
        )
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT COLUMN_NAME as column_name, COLUMN_TYPE as column_type, COLUMN_COMMENT as column_comment
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                    ORDER BY ORDINAL_POSITION
                """
                cursor.execute(sql, (database, table_name))
                return cursor.fetchall()
        finally:
            conn.close()
    elif db_type == "02":
        # Oracle
        import oracledb
        kwargs = dict(user=user, password=pwd, dsn=f"{host}:{port or 1521}")
        if user and user.upper() == "SYS":
            kwargs["mode"] = oracledb.SYSDBA
        conn = oracledb.connect(**kwargs)
        try:
            with conn.cursor() as cursor:
                sql = """
                    SELECT COLUMN_NAME, DATA_TYPE, '' as COMMENTS
                    FROM ALL_TAB_COLUMNS
                    WHERE TABLE_NAME = :1 AND OWNER = USER
                    ORDER BY COLUMN_ID
                """
                cursor.execute(sql, (table_name.upper(),))
                rows = cursor.fetchall()
                return [{"column_name": r[0], "column_type": r[1], "column_comment": r[2]} for r in rows]
        finally:
            conn.close()
    elif db_type == "03":
        # Hive
        from pyhive import hive
        _auth = auth or "NONE"
        _hive_kwargs = dict(
            host=host,
            port=int(port) if port else 10000,
            username=user,
            database=database or "default",
            auth=_auth,
        )
        # NONE 模式不允许传 password，LDAP/CUSTOM 模式才需要
        if _auth not in ("NONE", "NOSASL") and pwd:
            _hive_kwargs["password"] = pwd
        conn = hive.Connection(**_hive_kwargs)
        try:
            with conn.cursor() as cursor:
                cursor.execute(f"DESCRIBE {database or 'default'}.{table_name}")
                rows = cursor.fetchall()
                result = []
                for r in rows:
                    # Hive DESCRIBE 返回: (col_name, data_type, comment)
                    if not r or not r[0] or r[0].startswith("#"):
                        continue
                    result.append({
                        "column_name": r[0],
                        "column_type": r[1] if len(r) > 1 else "",
                        "column_comment": r[2] if len(r) > 2 else "",
                    })
                return result
        finally:
            conn.close()
    else:
        raise ValueError(f"不支持的数据库类型: {db_type}")


def query_col_map(task_no: str):
    """查询任务字段映射配置"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT source_column, target_colum
                FROM s_data_collect_col_map
                WHERE task_no = %s
                ORDER BY record_id
            """
            _execute(cursor, sql, (task_no,))
            return cursor.fetchall()
    finally:
        conn.close()


def save_col_map(task_no: str, target_table: str, mappings: list[dict]):
    """保存任务字段映射配置（先删后插），同时更新目标表名。

    时序任务关联的原始样本集绑定规则（binding_table 一旦绑定永久锁定）：
    - 样本集未绑定表：保存时将目标表名同步写入样本集 binding_table（首次绑定）
    - 样本集已绑定表：目标表名必须与绑定表一致，否则报错
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 查询任务关联的样本集及已绑定表
            _execute(cursor, """
                SELECT t.original_sample_set_no, t.sample_type, s.binding_table
                FROM s_data_collect_task t
                LEFT JOIN s_original_sample_set s ON s.set_no = t.original_sample_set_no
                WHERE t.task_no = %s
            """, (task_no,))
            task_row = cursor.fetchone()
            if task_row:
                if isinstance(task_row, dict):
                    set_no = task_row.get("original_sample_set_no")
                    sample_type = task_row.get("sample_type")
                    binding_table = task_row.get("binding_table")
                else:
                    set_no, sample_type, binding_table = task_row[0], task_row[1], task_row[2]
                # 仅时序类型（02）任务且已关联样本集时处理绑定
                if set_no and sample_type == "02":
                    if binding_table:
                        if binding_table != target_table:
                            raise ValueError(f"样本集已绑定目标表 {binding_table}，目标表名不可更改")
                    else:
                        # 未绑定：首次绑定目标表名
                        _execute(cursor, """
                            UPDATE s_original_sample_set
                            SET binding_table = %s
                            WHERE set_no = %s
                              AND (binding_table IS NULL OR binding_table = '')
                        """, (target_table, set_no))
            # 更新目标表名
            _execute(cursor, "UPDATE s_data_collect_task_det SET target_table = %s WHERE task_no = %s", (target_table, task_no))
            # 删除旧的映射配置
            _execute(cursor, "DELETE FROM s_data_collect_col_map WHERE task_no = %s", (task_no,))
            # 插入新的映射配置
            for m in mappings:
                sql = """
                    INSERT INTO s_data_collect_col_map (task_no, source_column, target_colum)
                    VALUES (%s, %s, %s)
                """
                _execute(cursor, sql, (task_no, m.get("sourceColumn", ""), m.get("targetColumn", "")))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
