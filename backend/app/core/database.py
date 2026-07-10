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


def query_sample_set():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                select
                    set_no,
                    set_name,
                    set_description,
                    type_code,
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = s.type_code
                        and scd.sort_no = 'SAMPLE_TYPE') as type_name,
                    s.quality_level,
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = s.quality_level
                        and scd.sort_no = 'QUALITY_LEVEL') as quality_level_name,
                    s.business_system,
                    {_date_format('s.update_time')} as update_time,
                    {_date_format('s.create_time')} as create_time,
                    s.version,
                    s.sample_field as sample_field_code,
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = s.sample_field
                        and scd.sort_no = 'SAMPLE_FIELD') as sample_field,
                    (select count(*) from s_sample_info si where si.set_no = s.set_no) as sample_count
                from
                    s_sample_set s
                order by update_time desc, create_time desc
            """
            _execute(cursor, sql, ())
            return cursor.fetchall()
    finally:
        conn.close()


def query_sample_info(set_no: str):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                select
                    sample_no,
                    sample_name,
                    suffix,
                    type_code,
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = s.type_code
                        and scd.sort_no = 'SAMPLE_TYPE') as type_name,
                    s.file_path,
                    s.file_size,
                    {_date_format('s.update_time')} as update_time,
                    {_date_format('s.create_time')} as create_time,
                    s.label_flag as label_flag_code,
	                case s.label_flag when 1 then '已标注' else '未标注' end as label_flag,
                    s.sample_score,
                    s.label_think
                from
                    s_sample_info s
                where
                    set_no = %s
                order by update_time desc, create_time desc
            """
            _execute(cursor, sql, (set_no,))
            return cursor.fetchall()
    finally:
        conn.close()


def save_sample_set(data: dict):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_sample_set (set_no, set_name, set_description, business_system, type_code, sample_field)
                VALUES (%(setCode)s, %(setName)s, %(description)s, %(businessSystem)s, %(sampleTypeCode)s, %(sampleFieldCode)s)
            """
            _execute(cursor, sql, data)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


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
            _execute(cursor, "SELECT COUNT(DISTINCT sample_field) AS domainCount FROM s_sample_set WHERE sample_field IS NOT NULL AND sample_field != ''")
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
                WHERE s.sample_field IS NOT NULL AND s.sample_field != ''
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
                WHERE s.type_code IS NOT NULL AND s.type_code != ''
                GROUP BY s.type_code
                ORDER BY count DESC
            """)
            result["typeDistribution"] = cursor.fetchall()

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


def query_audio_text(sample_no: str, sample_name: str):
    """查询语音样本的转写文字"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = _limit_sql("""
                SELECT audio_text
                FROM s_audio_text
                WHERE sample_no = %s AND sample_name = %s
            """, 1)
            _execute(cursor, sql, (sample_no, sample_name))
            row = cursor.fetchone()
            return row["audio_text"] if row else None
    finally:
        conn.close()


def insert_sample_info(set_no: str, sample_name: str, suffix: str, type_code: str, file_path: str, file_size: int):
    """插入样本信息到 s_sample_info 表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_sample_info (set_no, sample_name, suffix, type_code, file_path, file_size, label_flag)
                VALUES (%s, %s, %s, %s, %s, %s, 0)
            """
            _execute(cursor, sql, (set_no, sample_name, suffix, type_code, file_path, file_size))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def update_sample_score(sample_no: str, sample_name: str, score_code: str):
    """更新样本质量评分（编码：01-优质/02-良好/03-一般/04-较差）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE s_sample_info
                SET sample_score = %s
                WHERE sample_no = %s AND sample_name = %s
            """
            _execute(cursor, sql, (score_code, sample_no, sample_name))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def update_label_think(sample_no: str, sample_name: str, label_think: str):
    """更新样本思维链"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE s_sample_info
                SET label_think = %s
                WHERE sample_no = %s AND sample_name = %s
            """
            _execute(cursor, sql, (label_think, sample_no, sample_name))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


# ==================== 原始样本管理（s_original_sample_set / s_original_sample_info）====================

def query_original_sample_set():
    """查询所有原始样本集"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                select
                    set_no,
                    set_name,
                    set_description,
                    type_code,
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = s.type_code
                        and scd.sort_no = 'SAMPLE_TYPE') as type_name,
                    s.quality_level,
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = s.quality_level
                        and scd.sort_no = 'QUALITY_LEVEL') as quality_level_name,
                    s.business_system,
                    {_date_format('s.update_time')} as update_time,
                    {_date_format('s.create_time')} as create_time,
                    s.version,
                    s.sample_field as sample_field_code,
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = s.sample_field
                        and scd.sort_no = 'SAMPLE_FIELD') as sample_field,
                    (select count(*) from s_original_sample_info si where si.set_no = s.set_no) as sample_count
                from
                    s_original_sample_set s
                order by update_time desc, create_time desc
            """
            _execute(cursor, sql, ())
            return cursor.fetchall()
    finally:
        conn.close()


def query_original_sample_set_by_type(type_code: str):
    """按样本类型查询原始样本集（用于数据采集任务关联选择）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT set_no, set_name, set_description, type_code, business_system
                FROM s_original_sample_set
                WHERE type_code = %s
                ORDER BY update_time DESC, create_time DESC
            """
            _execute(cursor, sql, (type_code,))
            return cursor.fetchall()
    finally:
        conn.close()


def save_original_sample_set(data: dict):
    """新增原始样本集"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_original_sample_set (set_no, set_name, set_description, business_system, type_code, sample_field)
                VALUES (%(setCode)s, %(setName)s, %(description)s, %(businessSystem)s, %(sampleTypeCode)s, %(sampleFieldCode)s)
            """
            _execute(cursor, sql, data)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def query_original_sample_info(set_no: str):
    """查询原始样本集下的样本列表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                select
                    sample_no,
                    sample_name,
                    suffix,
                    type_code,
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = s.type_code
                        and scd.sort_no = 'SAMPLE_TYPE') as type_name,
                    s.file_path,
                    s.file_size,
                    {_date_format('s.update_time')} as update_time,
                    {_date_format('s.create_time')} as create_time,
                    s.label_flag as label_flag_code,
	                case s.label_flag when 1 then '已标注' else '未标注' end as label_flag,
                    s.sample_score,
                    s.label_think
                from
                    s_original_sample_info s
                where
                    set_no = %s
                order by update_time desc, create_time desc
            """
            _execute(cursor, sql, (set_no,))
            return cursor.fetchall()
    finally:
        conn.close()


def query_time_series_data_by_set_no(set_no: str, page: int = 1, page_size: int = 20):
    """时序类型原始样本集：通过样本集编号关联查询采集任务目标表数据
    链路：set_no → s_data_collect_task.original_sample_set_no → task_no
         → s_data_collect_task_det.target_table → 分页查询目标表
    返回: {target_table, total, rows, columns}
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 查询 task_no
            sql_task = _limit_sql("""
                SELECT task_no FROM s_data_collect_task
                WHERE original_sample_set_no = %s
                ORDER BY create_time DESC
            """, 1)
            _execute(cursor, sql_task, (set_no,))
            task_row = cursor.fetchone()
            if not task_row:
                return {"target_table": None, "total": 0, "rows": [], "columns": []}
            task_no = task_row.get("task_no") if isinstance(task_row, dict) else task_row[0]

            # 2. 查询 target_table
            sql_det = _limit_sql("""
                SELECT target_table FROM s_data_collect_task_det
                WHERE task_no = %s
                ORDER BY record_id DESC
            """, 1)
            _execute(cursor, sql_det, (task_no,))
            det_row = cursor.fetchone()
            if not det_row:
                return {"target_table": None, "total": 0, "rows": [], "columns": []}
            target_table = det_row.get("target_table") if isinstance(det_row, dict) else det_row[0]
            if not target_table:
                return {"target_table": None, "total": 0, "rows": [], "columns": []}

            # 3. 查询总记录数
            sql_count = f"SELECT COUNT(*) AS cnt FROM {target_table}"
            _execute(cursor, sql_count, ())
            count_row = cursor.fetchone()
            total = count_row.get("cnt", 0) if isinstance(count_row, dict) else count_row[0]

            # 4. 分页查询数据
            offset = (page - 1) * page_size
            if _is_oracle():
                sql_data = f"""
                    SELECT * FROM (
                        SELECT t.*, ROWNUM AS rn FROM {target_table} t
                        WHERE ROWNUM <= {offset + page_size}
                    ) WHERE rn > {offset}
                """
            else:
                sql_data = f"SELECT * FROM {target_table} LIMIT {page_size} OFFSET {offset}"
            _execute(cursor, sql_data, ())
            rows = cursor.fetchall()

            # 移除分页辅助列 rn
            clean_rows = []
            for r in rows:
                if isinstance(r, dict):
                    r = {k: v for k, v in r.items() if k.lower() != "rn"}
                clean_rows.append(r)

            # 提取列名
            columns = []
            if clean_rows:
                first = clean_rows[0]
                if isinstance(first, dict):
                    columns = list(first.keys())
                else:
                    columns = [col[0].lower() for col in cursor.description] if cursor.description else []

            return {
                "target_table": target_table,
                "total": total,
                "rows": clean_rows,
                "columns": columns,
            }
    finally:
        conn.close()


def insert_original_sample_info(set_no: str, sample_name: str, suffix: str, type_code: str, file_path: str, file_size: int):
    """插入原始样本信息"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_original_sample_info (set_no, sample_name, suffix, type_code, file_path, file_size, label_flag)
                VALUES (%s, %s, %s, %s, %s, %s, 0)
            """
            _execute(cursor, sql, (set_no, sample_name, suffix, type_code, file_path, file_size))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def insert_original_sample_info_for_collect(record: dict):
    """数据采集任务执行时，插入原始样本信息（图像类型）

    record 字段：sample_no, sample_name, set_no, type_code, suffix, file_path, file_size, collect_task_no
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_original_sample_info
                    (sample_no, sample_name, set_no, type_code, suffix, file_path, file_size, label_flag, collect_task_no)
                VALUES (%(sample_no)s, %(sample_name)s, %(set_no)s, %(type_code)s, %(suffix)s, %(file_path)s, %(file_size)s, 0, %(collect_task_no)s)
            """
            _execute(cursor, sql, record)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def update_original_sample_score(sample_no: str, sample_name: str, score_code: str):
    """更新原始样本质量评分"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE s_original_sample_info
                SET sample_score = %s
                WHERE sample_no = %s AND sample_name = %s
            """
            _execute(cursor, sql, (score_code, sample_no, sample_name))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def update_original_label_think(sample_no: str, sample_name: str, label_think: str):
    """更新原始样本思维链"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE s_original_sample_info
                SET label_think = %s
                WHERE sample_no = %s AND sample_name = %s
            """
            _execute(cursor, sql, (label_think, sample_no, sample_name))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


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


def generate_task_no():
    """生成任务编号：年月日+3位序列号，如 20260701001

    使用独立计数器表 s_sequence_counter，确保序列号永不复用。
    即使删除了任务，新任务的序列号也会继续递增。
    """
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    seq = _get_next_sequence('TASK_NO', today)
    return f"{today}{seq:03d}"


def generate_sample_set_no():
    """生成样本集编号：年月日+3位序列号，如 20260701001

    使用独立计数器表 s_sequence_counter，确保序列号永不复用。
    """
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    seq = _get_next_sequence('SAMPLE_SET_NO', today)
    return f"{today}{seq:03d}"


def generate_sample_no():
    """生成样本编号：年月日+3位序列号，如 20260701001

    使用独立计数器表 s_sequence_counter，确保序列号永不复用。
    """
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    seq = _get_next_sequence('SAMPLE_NO', today)
    return f"{today}{seq:03d}"


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
                    s.original_sample_set_no as sample_set_no
                FROM s_data_collect_task s
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
                    (task_no, source_db_type, source_db_host, source_db_port, source_db_usr, source_db_pwd,
                     source_db_name, target_table, collect_sql, source_db_auth,
                     file_get_mode, bucket_name, file_id, file_name)
                VALUES
                    (%(taskNo)s, %(sourceDbType)s, %(sourceDbHost)s, %(sourceDbPort)s, %(sourceDbUsr)s, %(sourceDbPwd)s,
                     %(sourceDbName)s, %(targetTable)s, %(collectSql)s, %(sourceDbAuth)s,
                     %(fileGetMode)s, %(bucketName)s, %(fileId)s, %(fileName)s)
            """
            _execute(cursor, sql, data)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def query_data_collect_task_det(task_no: str):
    """查询任务明细（含主表的执行方式信息和数据类型）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = _limit_sql(f"""
                SELECT
                    d.task_no,
                    d.source_db_type,
                    d.source_db_host,
                    d.source_db_port,
                    d.source_db_usr,
                    d.source_db_pwd,
                    d.source_db_name,
                    d.target_table,
                    d.collect_sql,
                    d.source_db_auth,
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
                    t.sample_type as sample_type_code
                FROM s_data_collect_task_det d
                LEFT JOIN s_data_collect_task t ON t.task_no = d.task_no
                WHERE d.task_no = %s
                ORDER BY d.record_id DESC
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
                SET source_db_type = %(sourceDbType)s,
                    source_db_host = %(sourceDbHost)s,
                    source_db_port = %(sourceDbPort)s,
                    source_db_usr = %(sourceDbUsr)s,
                    source_db_pwd = %(sourceDbPwd)s,
                    source_db_name = %(sourceDbName)s,
                    target_table = %(targetTable)s,
                    collect_sql = %(collectSql)s,
                    source_db_auth = %(sourceDbAuth)s,
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
    """查询任务明细原始数据（用于执行，不做日期格式化）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = _limit_sql("""
                SELECT
                    d.task_no, d.source_db_type, d.source_db_host, d.source_db_port,
                    d.source_db_usr, d.source_db_pwd, d.source_db_name, d.target_table,
                    d.collect_sql, d.source_db_auth,
                    d.file_get_mode, d.bucket_name, d.file_id, d.file_name,
                    t.sample_type, t.original_sample_set_no
                FROM s_data_collect_task_det d
                LEFT JOIN s_data_collect_task t ON t.task_no = d.task_no
                WHERE d.task_no = %s
                ORDER BY d.record_id DESC
            """, 1)
            _execute(cursor, sql, (task_no,))
            row = cursor.fetchone()
            if row and row.get("collect_sql") and isinstance(row["collect_sql"], bytes):
                row["collect_sql"] = row["collect_sql"].decode("utf-8")
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
                  AND cron_formula <> ''
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
        kwargs = dict(user=user, password=pwd, dsn=f"{host}:{port or 1521}")
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
    """根据字段映射将数据写入本地数据库的目标表。
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
            # 先清空目标表旧数据
            _execute(cursor, f"DELETE FROM {_quote_ident(target_table)}")
            # 批量插入数据
            batch_values = []
            for row in rows:
                values = tuple(row[i] if i < len(row) else None for i in sorted_indices)
                batch_values.append(values)
            _executemany(cursor, insert_sql, batch_values)
        conn.commit()
        return len(batch_values)
    finally:
        conn.close()


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


def query_clean_results():
    """查询清洗结果列表（execute_status=03 已完成的记录），关联任务表获取任务名称和数据类型"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT
                    l.record_id,
                    l.task_no,
                    t.task_name,
                    t.sample_type as sample_type_code,
                    {_date_format('l.start_time')} as start_time,
                    {_date_format('l.end_time')} as end_time,
                    l.result_count,
                    l.file_name,
                    l.file_path
                FROM s_data_clean_log l
                LEFT JOIN s_data_clean_task t ON l.task_no = t.task_no
                WHERE l.execute_status = '03'
                ORDER BY l.start_time DESC
            """
            _execute(cursor, sql, ())
            return cursor.fetchall()
    finally:
        conn.close()


def query_sample_set_options(type_code: str = ""):
    """查询样本集下拉选项（仅返回编号、名称、类型编码），可按类型过滤"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if type_code:
                sql = "SELECT set_no, set_name, type_code FROM s_sample_set WHERE type_code = %s ORDER BY create_time DESC"
                _execute(cursor, sql, (type_code,))
            else:
                sql = "SELECT set_no, set_name, type_code FROM s_sample_set ORDER BY create_time DESC"
                _execute(cursor, sql, ())
            return cursor.fetchall()
    finally:
        conn.close()


def batch_insert_sample_info(records: list[dict]):
    """批量插入样本信息到 s_sample_info"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_sample_info (sample_no, sample_name, set_no, type_code, suffix,
                    business_system, file_path, file_size, label_flag, sample_score, result_count)
                VALUES (%(sample_no)s, %(sample_name)s, %(set_no)s, %(type_code)s, %(suffix)s,
                    %(business_system)s, %(file_path)s, %(file_size)s, 0, '03', %(result_count)s)
            """
            _executemany(cursor, sql, records)
        conn.commit()
        return len(records)
    finally:
        conn.close()


def save_col_map(task_no: str, target_table: str, mappings: list[dict]):
    """保存任务字段映射配置（先删后插），同时更新目标表名"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
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
    finally:
        conn.close()


# ==================== 样本数据清理 ====================

def generate_clean_task_no():
    """生成清理任务编号：年月日+3位序列号，如 20260701001

    使用独立计数器表 s_sequence_counter，确保序列号永不复用。
    即使删除了任务，新任务的序列号也会继续递增。
    """
    from datetime import datetime
    today = datetime.now().strftime('%Y%m%d')
    seq = _get_next_sequence('CLEAN_TASK_NO', today)
    return f"{today}{seq:03d}"


def query_data_clean_tasks():
    """查询所有清理任务列表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT
                    task_no,
                    task_name,
                    remark,
                    task_status,
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
            _execute(cursor, "SELECT task_no, task_name FROM s_data_clean_task WHERE task_no = %s", (task_no,))
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


# ==================== 样本数据清理执行记录 ====================

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


def query_clean_log(task_no: str):
    """查询清理任务的执行记录列表"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
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
                    {_cast_text_as_char('execute_log')} as execute_log
                FROM s_data_clean_log
                WHERE task_no = %s
                ORDER BY start_time DESC
            """
            _execute(cursor, sql, (task_no,))
            return cursor.fetchall()
    finally:
        conn.close()
