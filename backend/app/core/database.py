import re
from datetime import datetime
from app.core.config import settings


# ==================== 数据库类型判断 ====================

_db_type_cache = None

def _is_oracle() -> bool:
    global _db_type_cache
    if _db_type_cache is None:
        _db_type_cache = getattr(settings, "db_type", "mysql").lower()
    return _db_type_cache == "oracle"


def _is_mysql() -> bool:
    return not _is_oracle()


# ==================== 大小写不敏感字典（Oracle 列名兼容） ====================

class _CiDict(dict):
    """大小写不敏感的字典，用于兼容 Oracle 大写列名和 MySQL 小写列名"""

    def _find_key(self, key):
        if not isinstance(key, str):
            return key
        if super().__contains__(key):
            return key
        lower_key = key.lower()
        for k in self.keys():
            if isinstance(k, str) and k.lower() == lower_key:
                return k
        return key

    def __getitem__(self, key):
        return super().__getitem__(self._find_key(key))

    def get(self, key, default=None):
        actual_key = self._find_key(key)
        return super().get(actual_key, default)

    def __contains__(self, key):
        return super().__contains__(self._find_key(key))


def _to_camel(obj):
    """将字典的键从下划线转为驼峰（支持单个字典或字典列表）"""
    if obj is None:
        return obj
    if isinstance(obj, list):
        return [_to_camel(item) for item in obj]
    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            key_str = str(k) if k is not None else ''
            # 已有下划线，直接转驼峰
            if '_' in key_str:
                parts = key_str.split('_')
                camel_key = parts[0] + ''.join(word.capitalize() for word in parts[1:])
            else:
                # 没有下划线的全小写键，尝试识别常见后缀并转换
                # setcount → setCount, samplecount → sampleCount, typename → typeName, qualityname → qualityName
                if key_str == 'setcount':
                    camel_key = 'setCount'
                elif key_str == 'samplecount':
                    camel_key = 'sampleCount'
                elif key_str == 'typename':
                    camel_key = 'typeName'
                elif key_str == 'qualityname':
                    camel_key = 'qualityName'
                else:
                    camel_key = key_str
            result[camel_key] = v
        return result
    return obj


# ==================== 连接管理 ====================

def _oracle_mode():
    """根据配置的 db_mode 返回 oracledb 权限模式常量，未配置则返回 None"""
    mode = getattr(settings, "db_mode", "").lower().strip()
    if not mode:
        return None
    import oracledb
    if mode == "sysdba":
        return oracledb.SYSDBA
    if mode == "sysoper":
        return oracledb.SYSOPER
    return None


def get_connection():
    if _is_oracle():
        import oracledb
        dsn = f"{settings.db_host}:{settings.db_port or 1521}/{settings.db_name}"
        kwargs = dict(user=settings.db_user, password=settings.db_password, dsn=dsn)
        mode = _oracle_mode()
        if mode is not None:
            kwargs["mode"] = mode
        conn = oracledb.connect(**kwargs)
        # 切换默认 schema，使无 schema 前缀的表名指向 db_schema 对应的 schema
        schema = getattr(settings, "db_schema", "").strip().upper()
        if schema:
            with conn.cursor() as cur:
                cur.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {schema}")
        return conn
    else:
        import pymysql
        return pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )


def get_connection_by_config(db_type: str, host: str, port: str, user: str, pwd: str, database: str, auth: str = "NONE"):
    """根据传入的配置参数建立数据库连接（用于测试连接）

    支持 MySQL、Oracle、Hive 等多种数据库类型。
    """
    db_type_upper = db_type.upper()

    if db_type_upper == "MYSQL":
        import pymysql
        return pymysql.connect(
            host=host,
            port=int(port) if port else 3306,
            user=user,
            password=pwd or "",
            database=database or "",
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
    elif db_type_upper == "ORACLE":
        import oracledb
        dsn = f"{host}:{port or 1521}/{database}"
        kwargs = dict(user=user, password=pwd or "", dsn=dsn)
        # auth 参数支持 SYSDBA/SYSOPER
        if auth.upper() == "SYSDBA":
            kwargs["mode"] = oracledb.SYSDBA
        elif auth.upper() == "SYSOPER":
            kwargs["mode"] = oracledb.SYSOPER
        return oracledb.connect(**kwargs)
    elif db_type_upper == "HIVE":
        # Hive 通过 pyhive 连接
        from pyhive import hive
        return hive.connect(
            host=host,
            port=int(port) if port else 10000,
            username=user,
            database=database or "default",
            auth=auth.upper() if auth else "NONE",
        )
    else:
        raise ValueError(f"不支持的数据库类型: {db_type}")


# ==================== SQL 执行包装器 ====================

def _oracle_sanitize_params(params):
    """Oracle 参数预处理：空字符串 → None（Oracle 将 '' 视为 NULL，显式传 None 更安全）
    CLOB / VARCHAR2 列直接使用 str；BLOB 列需要 bytes，调用方需在传参前自行 .encode()。
    """
    if params is None:
        return None
    if isinstance(params, dict):
        return {k: (None if isinstance(v, str) and v == "" else v) for k, v in params.items()}
    if isinstance(params, (list, tuple)):
        return [None if isinstance(v, str) and v == "" else v for v in params]
    return params


def _execute(cursor, sql, params=None):
    """统一执行 SQL，自动处理占位符差异（MySQL %s / Oracle :n）"""
    if _is_oracle():
        sql = _convert_sql_for_oracle(sql, params)
        params = _oracle_sanitize_params(params)
        if params is not None:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        # 设置 rowfactory 返回大小写不敏感的字典
        # Oracle 默认列名全大写，这里统一转成小写，使后续下划线转驼峰逻辑与 MySQL 一致
        if cursor.description:
            col_names = [col[0].lower() for col in cursor.description]
            def _factory(*row):
                d = {}
                for i in range(len(col_names)):
                    v = row[i]
                    # BLOB 列读出 bytes/oracledb.LOB，转回字符串
                    if isinstance(v, bytes):
                        v = v.decode("utf-8", errors="replace")
                    elif hasattr(v, "read"):
                        # oracledb.LOB 对象
                        v = v.read()
                        if isinstance(v, bytes):
                            v = v.decode("utf-8", errors="replace")
                    d[col_names[i]] = v
                return _CiDict(d)
            cursor.rowfactory = _factory
    else:
        if params is not None:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)


def _executemany(cursor, sql, seq_of_params):
    """批量执行，兼容两种数据库"""
    if _is_oracle():
        sql = _convert_sql_for_oracle(sql, list(seq_of_params)[0] if seq_of_params else {})
        seq_of_params = [_oracle_sanitize_params(p) for p in seq_of_params]
        cursor.executemany(sql, seq_of_params)
    else:
        cursor.executemany(sql, seq_of_params)


def _convert_sql_for_oracle(sql: str, params=None) -> str:
    """将 MySQL 风格 SQL 转换为 Oracle 兼容格式"""
    # 1. 把 %% 替换为临时占位符（MySQL 转义的 %）
    tmp = sql.replace("%%", "\x00")
    # 2. 处理参数占位符
    if isinstance(params, dict):
        # 命名参数：%(name)s → :name
        tmp = re.sub(r"%\((\w+)\)s", lambda m: f":{m.group(1)}", tmp)
    else:
        # 位置参数：%s → :1, :2, ...
        idx = [0]
        def _replace_s(m):
            idx[0] += 1
            return f":{idx[0]}"
        tmp = re.sub(r"%s", _replace_s, tmp)
    # 3. 恢复 %%
    tmp = tmp.replace("\x00", "%")
    # 4. 去掉反引号（Oracle 不支持）
    tmp = tmp.replace("`", "")
    return tmp


# ==================== SQL 片段辅助函数 ====================

def _date_format(expr: str, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """日期格式化 SQL 片段。
    fmt 使用 Python strftime 风格的占位符，内部按数据库类型转换为对应格式。
    """
    if _is_oracle():
        oracle_fmt = (fmt
            .replace("%Y", "YYYY").replace("%m", "MM").replace("%d", "DD")
            .replace("%H", "HH24").replace("%M", "MI").replace("%S", "SS"))
        return f"TO_CHAR({expr}, '{oracle_fmt}')"
    else:
        # MySQL DATE_FORMAT 的分钟用 %i，%M 是月份全名（与 Python strftime 相反）
        mysql_fmt = fmt.replace("%M", "%i").replace("%", "%%")
        return f"date_format({expr}, '{mysql_fmt}')"


def _date_format_month(expr: str) -> str:
    """日期格式化为年月：YYYY-MM / %Y-%m"""
    if _is_oracle():
        return f"TO_CHAR({expr}, 'YYYY-MM')"
    else:
        return f"DATE_FORMAT({expr}, '%%Y-%%m')"


def _now() -> str:
    return "SYSDATE" if _is_oracle() else "NOW()"


def _curdate() -> str:
    return "TRUNC(SYSDATE)" if _is_oracle() else "CURDATE()"


def _date_sub_month(months: int) -> str:
    if _is_oracle():
        return f"ADD_MONTHS(SYSDATE, -{months})"
    else:
        return f"DATE_SUB(CURDATE(), INTERVAL {months} MONTH)"


def _limit_sql(sql: str, n: int = 1) -> str:
    """在 SQL 末尾添加 LIMIT n 语义"""
    if _is_oracle():
        return f"SELECT * FROM ({sql}) WHERE ROWNUM <= {n}"
    else:
        return f"{sql} LIMIT {n}"


def _quote_ident(name: str) -> str:
    """标识符引用：MySQL 用反引号，Oracle 不加引号"""
    if _is_oracle():
        return name
    else:
        return f"`{name}`"


def _show_tables_sql() -> str:
    if _is_oracle():
        return "SELECT table_name FROM all_tables WHERE owner = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') ORDER BY table_name"
    else:
        return "SHOW TABLES"


def _show_columns_sql(table_name: str) -> str:
    if _is_oracle():
        return (
            f"SELECT column_name AS field, data_type AS col_type, "
            f"NULL AS key_col, NULL AS extra, NULL AS col_comment "
            f"FROM all_tab_columns WHERE table_name = '{table_name.upper()}' "
            f"AND owner = SYS_CONTEXT('USERENV', 'CURRENT_SCHEMA') ORDER BY column_id"
        )
    else:
        return f"SHOW COLUMNS FROM `{table_name}`"


def _field_order_expr(field: str, *values) -> str:
    """FIELD() 函数的兼容写法"""
    if _is_oracle():
        cases = " ".join(f"WHEN {field} = '{v}' THEN {i}" for i, v in enumerate(values, 1))
        return f"CASE {cases} ELSE {len(values) + 1} END"
    else:
        vals = ", ".join(f"'{v}'" for v in values)
        return f"FIELD({field}, {vals})"


def _cast_text_as_char(expr: str) -> str:
    """将 TEXT/CLOB 字段转为字符串"""
    if _is_oracle():
        return f"DBMS_LOB.SUBSTR({expr}, 4000, 1)"
    else:
        return f"CAST({expr} AS CHAR)"


def _select_all_from(table_name: str) -> str:
    """SELECT * FROM table 的兼容写法"""
    if _is_oracle():
        return f"SELECT * FROM {table_name}"
    else:
        return f"SELECT * FROM `{table_name}`"


# ==================== 公共业务（字典查询）====================

def query_code_dict(sort_no_list: list[str]):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            placeholders = ",".join(["%s"] * len(sort_no_list))
            sql = (
                f"SELECT SORT_NO, CODE_VALUE, CODE_NAME "
                f"FROM sys_code_dict "
                f"WHERE SORT_NO IN ({placeholders}) "
                f"ORDER BY SORT_NO, ORDER_INDEX, RECORD_ID"
            )
            _execute(cursor, sql, sort_no_list)
            return cursor.fetchall()
    finally:
        conn.close()


# ==================== 编号生成（横切多业务模块，集中保留）====================

def _get_next_sequence(counter_type: str, date_key: str) -> int:
    """获取下一个序列号（永不复用）

    使用 s_sequence_counter 表记录每个日期已使用的最大序列号。
    即使删除了任务，序列号也不会回退。

    Args:
        counter_type: 计数器类型，如 'TASK_NO'、'CLEAN_TASK_NO'
        date_key: 日期键，如 '20260701'

    Returns:
        下一个序列号（已递增后的值）
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if _is_oracle():
                # Oracle: 使用 MERGE INTO
                sql = """
                    MERGE INTO s_sequence_counter t
                    USING (SELECT :1 as counter_type, :2 as date_key, 1 as counter_value FROM dual) s
                    ON (t.counter_type = s.counter_type AND t.date_key = s.date_key)
                    WHEN MATCHED THEN UPDATE SET t.counter_value = t.counter_value + 1, t.update_time = SYSDATE
                    WHEN NOT MATCHED THEN INSERT (counter_type, date_key, counter_value, update_time)
                        VALUES (s.counter_type, s.date_key, s.counter_value, SYSDATE)
                """
                _execute(cursor, sql, (counter_type, date_key))
            else:
                # MySQL: 使用 INSERT ... ON DUPLICATE KEY UPDATE
                sql = """
                    INSERT INTO s_sequence_counter (counter_type, date_key, counter_value, update_time)
                    VALUES (%s, %s, 1, NOW())
                    ON DUPLICATE KEY UPDATE counter_value = counter_value + 1, update_time = NOW()
                """
                _execute(cursor, sql, (counter_type, date_key))

            # 查询当前值
            sql = "SELECT counter_value FROM s_sequence_counter WHERE counter_type = %s AND date_key = %s"
            _execute(cursor, sql, (counter_type, date_key))
            row = cursor.fetchone()
            conn.commit()
            return row['counter_value'] if row else 1
    finally:
        conn.close()


def _get_next_sequence_batch(counter_type: str, date_key: str, count: int) -> int:
    """批量获取下一个序列号区间，返回起始值（含），共 count 个：[start, start+count-1]

    一次更新增加 count，再读取更新后的值，返回 start = value - count + 1。
    保证批量插入时序列号连续且原子分配，避免并发冲突。
    """
    if count <= 0:
        return 0
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if _is_oracle():
                sql = """
                    MERGE INTO s_sequence_counter t
                    USING (SELECT :1 as counter_type, :2 as date_key, :3 as counter_value FROM dual) s
                    ON (t.counter_type = s.counter_type AND t.date_key = s.date_key)
                    WHEN MATCHED THEN UPDATE SET t.counter_value = t.counter_value + s.counter_value, t.update_time = SYSDATE
                    WHEN NOT MATCHED THEN INSERT (counter_type, date_key, counter_value, update_time)
                        VALUES (s.counter_type, s.date_key, s.counter_value, SYSDATE)
                """
                _execute(cursor, sql, (counter_type, date_key, count))
            else:
                sql = """
                    INSERT INTO s_sequence_counter (counter_type, date_key, counter_value, update_time)
                    VALUES (%s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE counter_value = counter_value + VALUES(counter_value), update_time = NOW()
                """
                _execute(cursor, sql, (counter_type, date_key, count))
            sql = "SELECT counter_value FROM s_sequence_counter WHERE counter_type = %s AND date_key = %s"
            _execute(cursor, sql, (counter_type, date_key))
            row = cursor.fetchone()
            conn.commit()
            current = row['counter_value'] if row else count
            return current - count + 1
    finally:
        conn.close()


def generate_task_no():
    """生成数据采集任务编号：年月日+业务编号+3位序列号，如 2026080403001

    业务编号 03 为数据采集任务。
    使用独立计数器表 s_sequence_counter，确保序列号永不复用。
    即使删除了任务，新任务的序列号也会继续递增。
    """
    from app.core.biz_constants import BizCode
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    seq = _get_next_sequence('TASK_NO', today)
    return f"{today}{BizCode.DATA_COLLECT_TASK}{seq:03d}"


def generate_sample_set_no(biz_code: str):
    """生成样本集编号：年月日+业务编号+3位序列号，如 2026080401001

    业务编号：
      01 - 高质量样本集
      02 - 原始样本集
    使用独立计数器表 s_sequence_counter，确保序列号永不复用。
    """
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    seq = _get_next_sequence('SAMPLE_SET_NO', today)
    return f"{today}{biz_code}{seq:03d}"


def generate_sample_no():
    """生成样本编号：年月日+3位序列号，如 20260701001

    使用独立计数器表 s_sequence_counter，确保序列号永不复用。
    """
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    seq = _get_next_sequence('SAMPLE_NO', today)
    return f"{today}{seq:03d}"


def generate_clean_task_no():
    """生成数据清洗任务编号：年月日+业务编号+3位序列号，如 2026080404001

    业务编号 04 为数据清洗任务。
    使用独立计数器表 s_sequence_counter，确保序列号永不复用。
    即使删除了任务，新任务的序列号也会继续递增。
    """
    from app.core.biz_constants import BizCode
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    seq = _get_next_sequence('CLEAN_TASK_NO', today)
    return f"{today}{BizCode.DATA_CLEAN_TASK}{seq:03d}"


def generate_import_task_no():
    """生成样本导入任务编号：年月日+业务编号+3位序列号，如 2026080405001

    业务编号 05 为样本批量导入任务。
    用于分片上传 + 异步导入任务，序列号永不复用。
    """
    from app.core.biz_constants import BizCode
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    seq = _get_next_sequence('IMPORT_TASK_NO', today)
    return f"{today}{BizCode.BATCH_IMPORT_TASK}{seq:03d}"


def generate_directory_no():
    """生成样本目录编号：年月日+3位序列号，如 20260701001

    用于 s_sample_directory 表的主键，序列号永不复用。
    """
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    seq = _get_next_sequence('DIRECTORY_NO', today)
    return f"{today}{seq:03d}"


# ==================== 工具函数 ====================

def save_query_result_to_desktop(columns: list, rows: list):
    """将查询结果保存到桌面，文件名格式：测试查询_时分秒"""
    import csv
    import os
    from datetime import datetime

    desktop = r"C:\Users\Joey\Desktop"
    if not os.path.exists(desktop):
        os.makedirs(desktop, exist_ok=True)

    timestamp = datetime.now().strftime("%H%M%S")
    filename = f"测试查询_{timestamp}.csv"
    filepath = os.path.join(desktop, filename)

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        writer.writerows(rows)

    return filepath
