import pymysql
from app.core.config import settings


def get_connection():
    return pymysql.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


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
            cursor.execute(sql, sort_no_list)
            return cursor.fetchall()
    finally:
        conn.close()


def query_sample_set():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
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
                        and scd.sort_no = 'SAMPLE_TYPE') as typeName,
                    s.quality_level,
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = s.quality_level
                        and scd.sort_no = 'QUALITY_LEVEL') as qualityLevelName,
                    s.business_system,
                    date_format(s.update_time, '%%Y-%%m-%%d %%H:%%i:%%s') as updateTime,
                    date_format(s.create_time, '%%Y-%%m-%%d %%H:%%i:%%s') as createTime,
                    s.version,
                    s.sample_field as sampleFieldCode,
                    (
                    select
                        scd.code_name
                    from
                        sys_code_dict scd
                    where
                        scd.code_value = s.sample_field
                        and scd.sort_no = 'SAMPLE_FIELD') as sampleField,
                    (select count(*) from s_sample_info si where si.set_no = s.set_no) as sampleCount
                from
                    s_sample_set s
                order by update_time desc, create_time desc
            """
            cursor.execute(sql, ())
            return cursor.fetchall()
    finally:
        conn.close()


def query_sample_info(set_no: str):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
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
                        and scd.sort_no = 'SAMPLE_TYPE') as typeName,
                    s.file_path,
                    s.file_size,
                    date_format(s.update_time, '%%Y-%%m-%%d %%H:%%i:%%s') as updateTime,
                    date_format(s.create_time, '%%Y-%%m-%%d %%H:%%i:%%s') as createTime,
                    s.label_flag as labelFlagCode,
	                case s.label_flag when 1 then '已标注' else '未标注' end as labelFlag,
                    s.sample_score
                from
                    s_sample_info s
                where
                    set_no = %s
                order by update_time desc, create_time desc
            """
            cursor.execute(sql, (set_no,))
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
            cursor.execute(sql, data)
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
            cursor.execute("SELECT COUNT(*) AS setCount FROM s_sample_set")
            result["setCount"] = cursor.fetchone()["setCount"]

            # 样本总量
            cursor.execute("SELECT COUNT(*) AS sampleCount FROM s_sample_info")
            result["sampleCount"] = cursor.fetchone()["sampleCount"]

            # 已标注样本数量（label_flag = 1 表示已标注）
            cursor.execute("SELECT COUNT(*) AS labeledCount FROM s_sample_info WHERE label_flag = 1")
            result["labeledCount"] = cursor.fetchone()["labeledCount"]

            # 高质量样本数量（sample_score = '01' 表示优质）
            cursor.execute("SELECT COUNT(*) AS highQualityCount FROM s_sample_info WHERE sample_score = '01'")
            result["highQualityCount"] = cursor.fetchone()["highQualityCount"]

            # 本月新增样本
            cursor.execute("SELECT COUNT(*) AS monthNewCount FROM s_sample_info WHERE DATE_FORMAT(create_time, '%%Y-%%m') = DATE_FORMAT(CURDATE(), '%%Y-%%m')", ())
            result["monthNewCount"] = cursor.fetchone()["monthNewCount"]

            # 本月高质量样本
            cursor.execute("SELECT COUNT(*) AS monthQualityCount FROM s_sample_info WHERE DATE_FORMAT(create_time, '%%Y-%%m') = DATE_FORMAT(CURDATE(), '%%Y-%%m') AND sample_score = '01'", ())
            result["monthQualityCount"] = cursor.fetchone()["monthQualityCount"]

            # 平均样本质量（数值映射法：01→100, 02→85, 03→70, 04→50）
            cursor.execute("""
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
            cursor.execute("SELECT COUNT(DISTINCT sample_field) AS domainCount FROM s_sample_set WHERE sample_field IS NOT NULL AND sample_field != ''")
            result["domainCount"] = cursor.fetchone()["domainCount"]

            # 领域分布
            cursor.execute("""
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
            cursor.execute("""
                SELECT
                    CASE sample_score
                        WHEN '01' THEN '优质'
                        WHEN '02' THEN '良好'
                        WHEN '03' THEN '一般'
                        WHEN '04' THEN '较差'
                        ELSE '未评分'
                    END AS qualityName,
                    COUNT(*) AS count
                FROM s_sample_info
                GROUP BY qualityName
                ORDER BY FIELD(qualityName, '优质', '良好', '一般', '较差', '未评分')
            """)
            result["qualityDistribution"] = cursor.fetchall()

            # 样本类型分布（按s_sample_set的type_code关联s_sample_info统计）
            cursor.execute("""
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
            cursor.execute("""
                SELECT
                    DATE_FORMAT(create_time, '%%Y-%%m') AS month,
                    COUNT(*) AS count
                FROM s_sample_info
                WHERE create_time >= DATE_SUB(CURDATE(), INTERVAL 5 MONTH)
                GROUP BY month
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
            sql = """
                SELECT audio_text
                FROM s_audio_text
                WHERE sample_no = %s AND sample_name = %s
                LIMIT 1
            """
            cursor.execute(sql, (sample_no, sample_name))
            row = cursor.fetchone()
            return row["audio_text"] if row else None
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
            cursor.execute(sql, (score_code, sample_no, sample_name))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
