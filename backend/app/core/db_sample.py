"""高质量样本管理 + 原始样本管理 业务 SQL

从 core/database.py 拆分而来。操作表：
- 高质量样本管理：s_sample_set / s_sample_info / s_audio_text / s_sample_version_record
- 原始样本管理：s_original_sample_set / s_original_sample_info

仅做位置迁移，不改动任何函数实现逻辑。
"""
from app.core.database import (
    get_connection,
    _execute,
    _executemany,
    _date_format,
    _limit_sql,
    _is_oracle,
    _quote_ident,
    _show_columns_sql,
    _get_next_sequence,
    _get_next_sequence_batch,
    generate_directory_no,
)


# ==================== 高质量样本管理（s_sample_set / s_sample_info / s_audio_text / s_sample_version_record）====================

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
                    s.set_path,
                    {_date_format('s.update_time')} as update_time,
                    {_date_format('s.create_time')} as create_time,
                    s.version,
                    s.sample_labels,
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


def query_sample_info(set_no: str, dir_id: str = None):
    """查询高质量样本列表。

    dir_id 为 None 时不筛选目录，返回样本集下所有样本。
    dir_id 为空字符串 '' 时筛选根目录下的样本（dir_id IS NULL）。
    dir_id 为具体值时筛选该目录下的样本。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            where_extra = ""
            params: tuple
            if dir_id is not None:
                if dir_id == "":
                    where_extra = " AND s.dir_id IS NULL"
                    params = (set_no,)
                else:
                    where_extra = " AND s.dir_id = %s"
                    params = (set_no, dir_id)
            else:
                params = (set_no,)
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
                    s.label_think,
                    s.label_content,
                    s.dir_id
                from
                    s_sample_info s
                where
                    set_no = %s{where_extra}
                order by update_time desc, create_time desc
            """
            _execute(cursor, sql, params)
            return cursor.fetchall()
    finally:
        conn.close()


def save_sample_set(data: dict):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_sample_set (set_no, set_name, set_description, business_system, type_code, sample_field, set_path, sample_labels)
                VALUES (%(setCode)s, %(setName)s, %(description)s, %(businessSystem)s, %(sampleTypeCode)s, %(sampleFieldCode)s, %(setPath)s, %(sampleLabels)s)
            """
            _execute(cursor, sql, data)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def update_sample_set(data: dict):
    """更新样本集（不允许修改 set_name 和 type_code，不更新 version）

    可修改字段：set_description, business_system, sample_field, sample_labels
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE s_sample_set
                SET set_description = %(description)s,
                    business_system = %(businessSystem)s,
                    sample_field = %(sampleFieldCode)s,
                    sample_labels = %(sampleLabels)s
                WHERE set_no = %(setNo)s
            """
            _execute(cursor, sql, data)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def update_sample_set_labels(set_no: str, sample_labels: str):
    """仅更新样本集的 sample_labels 字段（上传 classes.txt 时调用）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "UPDATE s_sample_set SET sample_labels = %s WHERE set_no = %s"
            _execute(cursor, sql, (sample_labels, set_no))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def get_annotation_by_sample_no(sample_no: str):
    """通过 sample_no 查询样本的标注信息：返回 {label_content, sample_labels}

    用于 /get-annotations 接口：从 DB 读取 label_content（图片同名 txt 内容）
    和 sample_labels（classes.txt 内容），替代原磁盘读取逻辑。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT s.label_content, ss.sample_labels
                FROM s_sample_info s
                JOIN s_sample_set ss ON s.set_no = ss.set_no
                WHERE s.sample_no = %s
            """
            _execute(cursor, sql, (sample_no,))
            return cursor.fetchone()
    finally:
        conn.close()


def get_sample_set_path(set_no: str):
    """查询样本集的 set_path"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT set_path, set_name, sample_labels, type_code FROM s_sample_set WHERE set_no = %s"
            _execute(cursor, sql, (set_no,))
            return cursor.fetchone()
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


def insert_sample_info(set_no: str, sample_name: str, suffix: str, type_code: str, file_path: str, file_size: int, label_flag: int = 0, label_content: str = "", dir_id: str = None):
    """插入样本信息到 s_sample_info 表，自动生成 sample_no（set_no + 5位序列号）

    label_flag: 0-未标注, 1-已标注（图片有同名txt标注文件时为1）
    label_content: 图片同名 txt 标注文件的原始内容（仅图片类型，保持原内容不变形）
    dir_id: 所属目录编号（NULL 表示样本集根目录）
    """
    # 生成 sample_no: set_no + 5位序列号
    seq = _get_next_sequence(f'SAMPLE_NO_{set_no}', set_no)
    sample_no = f"{set_no}{seq:05d}"

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_sample_info (sample_no, set_no, sample_name, suffix, type_code, file_path, file_size, label_flag, label_content, dir_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            _execute(cursor, sql, (sample_no, set_no, sample_name, suffix, type_code, file_path, file_size, label_flag, label_content, dir_id))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def random_sample_images(set_no: str, count: int = 30):
    """从高质量样本集中随机抽取 count 张图片样本（type_code='05'）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            if _is_oracle():
                sql = """
                    SELECT * FROM (
                        SELECT sample_no, sample_name, suffix, file_path, file_size, label_think
                        FROM s_sample_info
                        WHERE set_no = %s AND type_code = '05'
                        ORDER BY DBMS_RANDOM.VALUE()
                    ) WHERE ROWNUM <= %s
                """
                _execute(cursor, sql, (set_no, count))
            else:
                sql = """
                    SELECT sample_no, sample_name, suffix, file_path, file_size, label_think
                    FROM s_sample_info
                    WHERE set_no = %s AND type_code = '05'
                    ORDER BY RAND()
                    LIMIT %s
                """
                _execute(cursor, sql, (set_no, count))
            return cursor.fetchall()
    finally:
        conn.close()


def update_sample_set_quality_level(set_no: str, quality_level: str):
    """更新样本集质量等级"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "UPDATE s_sample_set SET quality_level = %s WHERE set_no = %s"
            _execute(cursor, sql, (quality_level, set_no))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def reset_sample_set_quality_level(set_no: str):
    """清空样本集质量等级（导入新图片后调用）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "UPDATE s_sample_set SET quality_level = NULL WHERE set_no = %s"
            _execute(cursor, sql, (set_no,))
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


def _parse_version(version_str) -> tuple[int, int]:
    """解析版本号字符串 'major.minor' → (major_int, minor_int)。

    空值或异常时回退为 (1, 0)。小版本号按字符串解析，支持任意位数（如 1.555）。
    """
    try:
        s = str(version_str).strip()
        if not s:
            return 1, 0
        # 去掉可能的前缀 V/v
        if s[:1] in ("v", "V"):
            s = s[1:]
        parts = s.split(".")
        major = int(parts[0]) if parts[0].lstrip("-").isdigit() else 1
        if len(parts) > 1 and parts[1].isdigit():
            minor = int(parts[1])
        else:
            minor = 0
        return major, minor
    except Exception:
        return 1, 0


def apply_sample_set_version_change(
    set_no: str,
    set_name: str,
    added_count: int,
    manual_major: bool = False,
    manual_remark: str = "",
    apply_threshold: bool = True,
    sample_label: str = "图片",
):
    """计算并记录样本集版本变更，写入 s_sample_version_record 并更新 s_sample_set.version。

    added_count 为本次成功新增的样本数量。
    版本号以字符串 "major.minor" 形式存储，小版本号每次 +1，可任意位数（1.10、1.555）。

    规则：
    - 手动变更（manual_major=True）：无论增量多少，大版本号 +1、小版本号归 0。
      manual_remark 非空则用其作为 remark，否则生成默认说明。
    - 自动变更（manual_major=False）：
      * apply_threshold=True（默认，图片批量导入场景）：若 (next_num // 阈值) - (pre_num // 阈值) >= 1，
        则大版本号 +1、小版本号归 0；否则小版本号 +1。阈值取自 SAMPLE_MAJOR_VERSION_THRESHOLD。
      * apply_threshold=False（时序清洗结果入库等场景）：不参考阈值，直接小版本号 +1。

    sample_label 用于生成默认 remark 中的样本计量单位文案（如"图片"/"样本"）。

    返回: {pre_num, next_num, pre_version, next_version, remark, change_flag}
    """
    from app.core.config import settings

    threshold = getattr(settings, "sample_major_version_threshold", 100) or 100
    if threshold <= 0:
        threshold = 100

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 查询当前版本号
            _execute(cursor, "SELECT version FROM s_sample_set WHERE set_no = %s", (set_no,))
            row = cursor.fetchone()
            pre_version_raw = (row.get("version") if row else None)
            if isinstance(pre_version_raw, bytes):
                pre_version_raw = pre_version_raw.decode("utf-8")
            pre_version_str = str(pre_version_raw).strip() if pre_version_raw else ""
            if not pre_version_str:
                pre_version_str = "1.0"

            major, minor = _parse_version(pre_version_str)

            # 2. 查询当前样本总数（本次上传后的实际总量）
            _execute(cursor, "SELECT COUNT(*) AS cnt FROM s_sample_info WHERE set_no = %s", (set_no,))
            cnt_row = cursor.fetchone()
            next_num = int(cnt_row.get("cnt", 0)) if cnt_row else 0
            pre_num = next_num - added_count
            if pre_num < 0:
                pre_num = 0

            # 3. 计算新版本号与变更说明
            if manual_major:
                new_major = major + 1
                new_minor = 0
                change_flag = 1
                remark = (manual_remark or "").strip()
                if not remark:
                    remark = f"本次新增{sample_label}{added_count}条，总数{next_num}条，手动变更大版本"
            else:
                change_flag = 0
                crossed = ((next_num // threshold) - (pre_num // threshold)) if apply_threshold else 0
                if crossed >= 1:
                    new_major = major + 1
                    new_minor = 0
                    remark = f"本次新增{sample_label}{added_count}条，总数{next_num}条，达到了大版本变更阈值，大版本号+1"
                else:
                    new_major = major
                    new_minor = minor + 1
                    remark = f"本次新增{sample_label}{added_count}条，小版本号加1"

            next_version_str = f"{new_major}.{new_minor}"

            # 4. 插入版本变更记录
            sql_insert = """
                INSERT INTO s_sample_version_record
                    (sample_set_no, sample_set_name, change_flag, pre_num, next_num,
                     pre_version, next_version, remark)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            _execute(cursor, sql_insert, (
                set_no, set_name, change_flag, pre_num, next_num,
                pre_version_str, next_version_str, remark,
            ))

            # 5. 更新样本集版本号
            _execute(cursor, "UPDATE s_sample_set SET version = %s WHERE set_no = %s",
                     (next_version_str, set_no))
        conn.commit()

        return {
            "pre_num": pre_num,
            "next_num": next_num,
            "pre_version": pre_version_str,
            "next_version": next_version_str,
            "remark": remark,
            "change_flag": change_flag,
        }
    except Exception:
        conn.rollback()
        raise
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
                    s.set_path,
                    s.binding_table,
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
                    (select count(*) from s_original_sample_info si where si.set_no = s.set_no and (si.clean_flag = '0' or si.clean_flag is null)) as sample_count
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
                SELECT set_no, set_name, set_description, type_code, business_system, binding_table
                FROM s_original_sample_set
                WHERE type_code = %s
                ORDER BY update_time DESC, create_time DESC
            """
            _execute(cursor, sql, (type_code,))
            return cursor.fetchall()
    finally:
        conn.close()


def save_original_sample_set(data: dict):
    """新增原始样本集（binding_table 仅时序类型样本集使用，创建时可空）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_original_sample_set (set_no, set_name, set_description, business_system, type_code, sample_field, set_path, binding_table)
                VALUES (%(setCode)s, %(setName)s, %(description)s, %(businessSystem)s, %(sampleTypeCode)s, %(sampleFieldCode)s, %(setPath)s, %(bindingTable)s)
            """
            _execute(cursor, sql, data)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def update_original_sample_set(data: dict):
    """更新原始样本集（不允许修改 set_name 和 type_code，不更新 version）

    可修改字段：set_description, business_system, sample_field
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE s_original_sample_set
                SET set_description = %(description)s,
                    business_system = %(businessSystem)s,
                    sample_field = %(sampleFieldCode)s
                WHERE set_no = %(setNo)s
            """
            _execute(cursor, sql, data)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def query_original_sample_info(set_no: str, dir_id: str = None):
    """查询原始样本集下的样本列表。

    dir_id 为 None 时不筛选目录，返回样本集下所有样本。
    dir_id 为空字符串 '' 时筛选根目录下的样本（dir_id IS NULL）。
    dir_id 为具体值时筛选该目录下的样本。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            where_extra = ""
            params: tuple
            if dir_id is not None:
                if dir_id == "":
                    where_extra = " AND s.dir_id IS NULL"
                    params = (set_no,)
                else:
                    where_extra = " AND s.dir_id = %s"
                    params = (set_no, dir_id)
            else:
                params = (set_no,)
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
                    s.label_think,
                    s.dir_id
                from
                    s_original_sample_info s
                where
                    set_no = %s
                    AND (s.clean_flag = '0' OR s.clean_flag IS NULL)
                    {where_extra}
                order by update_time desc, create_time desc
            """
            _execute(cursor, sql, params)
            return cursor.fetchall()
    finally:
        conn.close()


def query_time_series_data_by_set_no(set_no: str, page: int = 1, page_size: int = 20):
    """时序类型原始样本集：直接根据样本集绑定的目标表（binding_table）分页查询数据

    不再通过"关联采集任务 → 任务明细目标表"链路取表，
    避免多个采集任务关联同一样本集且目标表不同时查询异常。
    返回: {target_table, total, rows, columns}
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 查询样本集绑定的目标表
            sql_set = _limit_sql("""
                SELECT binding_table FROM s_original_sample_set
                WHERE set_no = %s
            """, 1)
            _execute(cursor, sql_set, (set_no,))
            set_row = cursor.fetchone()
            if not set_row:
                return {"target_table": None, "total": 0, "rows": [], "columns": []}
            target_table = set_row.get("binding_table") if isinstance(set_row, dict) else set_row[0]
            if not target_table:
                return {"target_table": None, "total": 0, "rows": [], "columns": []}

            # 2. 查询总记录数
            sql_count = f"SELECT COUNT(*) AS cnt FROM {_quote_ident(target_table)}"
            _execute(cursor, sql_count, ())
            count_row = cursor.fetchone()
            total = count_row.get("cnt", 0) if isinstance(count_row, dict) else count_row[0]

            # 3. 分页查询数据
            offset = (page - 1) * page_size
            if _is_oracle():
                sql_data = f"""
                    SELECT * FROM (
                        SELECT t.*, ROWNUM AS rn FROM {target_table} t
                        WHERE ROWNUM <= {offset + page_size}
                    ) WHERE rn > {offset}
                """
            else:
                sql_data = f"SELECT * FROM {_quote_ident(target_table)} LIMIT {page_size} OFFSET {offset}"
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


def get_original_sample_set_binding(set_no: str):
    """查询原始样本集的样本类型与绑定表信息（用于绑定/导入前校验）"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = _limit_sql("""
                SELECT set_no, type_code, binding_table
                FROM s_original_sample_set
                WHERE set_no = %s
            """, 1)
            _execute(cursor, sql, (set_no,))
            return cursor.fetchone()
    finally:
        conn.close()


def bind_original_sample_set_table(set_no: str, table_name: str):
    """首次绑定原始样本集的目标表（binding_table 一旦绑定永久锁定，仅允许从空值绑定）

    返回 {success, reason}
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 仅允许 binding_table 为空时绑定（防止并发/重复绑定覆盖）
            sql = """
                UPDATE s_original_sample_set
                SET binding_table = %s
                WHERE set_no = %s
                  AND (binding_table IS NULL OR binding_table = '')
            """
            _execute(cursor, sql, (table_name, set_no))
            rowcount = cursor.rowcount
        conn.commit()
        if rowcount == 0:
            return {"success": False, "reason": "该样本集已绑定目标表，绑定后不可更改"}
        return {"success": True}
    finally:
        conn.close()


def _list_table_columns(cursor, table_name: str) -> list[str]:
    """查询指定表的全部列名（忽略大小写返回实际列名）"""
    _execute(cursor, _show_columns_sql(table_name))
    rows = cursor.fetchall()
    cols = []
    for col in rows:
        if isinstance(col, dict):
            name = col.get("field") or col.get("Field") or ""
        else:
            name = col[0]
        if name:
            cols.append(name)
    return cols


def import_time_series_data(set_no: str, binding_table: str, df):
    """将 CSV/Excel 解析出的数据按列名匹配（忽略大小写）追加写入样本集绑定的目标表。

    - 只写入目标表中实际存在的列，文件中匹配不到表列名的字段直接忽略
    - 整体事务：任一批次写入失败则全部回滚
    - 返回 {insert_count, matched_columns, ignored_columns}
    """
    import pandas as pd

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 查询目标表实际列名（Oracle 返回大写，MySQL 返回实际大小写）
            table_cols = _list_table_columns(cursor, binding_table)
            if not table_cols:
                raise ValueError(f"目标表 {binding_table} 不存在或没有字段")

            # 2. 列名匹配（忽略大小写）：文件列 → 表列
            table_cols_lower = {}
            for c in table_cols:
                table_cols_lower.setdefault(c.lower(), c)
            matched = {}  # 文件列名 -> 表列名
            for file_col in df.columns:
                key = str(file_col).strip().lower()
                if key in table_cols_lower and table_cols_lower[key] not in matched.values():
                    matched[str(file_col)] = table_cols_lower[key]

            if not matched:
                raise ValueError(
                    f"文件列与目标表 {binding_table} 的字段无匹配"
                    f"（文件列: {list(map(str, df.columns))}，表字段: {table_cols}）"
                )

            # 3. 构建追加 INSERT（只包含匹配到的列）
            target_columns = list(matched.values())
            col_names = ", ".join(_quote_ident(c) for c in target_columns)
            placeholders = ", ".join(["%s"] * len(target_columns))
            insert_sql = f"INSERT INTO {_quote_ident(binding_table)} ({col_names}) VALUES ({placeholders})"

            # 4. 组装数据行（NaN/NaT → None），整体事务批量写入
            batch_values = []
            for _, row in df.iterrows():
                values = []
                for file_col in matched.keys():
                    v = row[file_col]
                    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NaT:
                        v = None
                    values.append(v)
                batch_values.append(tuple(values))

            if batch_values:
                _executemany(cursor, insert_sql, batch_values)
        conn.commit()

        ignored = [str(c) for c in df.columns if str(c) not in matched]
        return {
            "insert_count": len(batch_values),
            "matched_columns": target_columns,
            "ignored_columns": ignored,
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_original_sample_info(set_no: str, sample_name: str, suffix: str, type_code: str, file_path: str, file_size: int, label_flag: int = 0, label_content: str = "", dir_id: str = None):
    """插入原始样本信息，自动生成 sample_no（set_no + 5位序列号）

    label_flag: 0-未标注, 1-已标注（图片有同名txt标注文件时为1）
    label_content: 接受该参数以与 insert_sample_info 保持一致的回调签名，但原始样本不写标注内容，直接忽略。
    dir_id: 所属目录编号（NULL 表示样本集根目录）
    """
    # 生成 sample_no: set_no + 5位序列号
    seq = _get_next_sequence(f'SAMPLE_NO_{set_no}', set_no)
    sample_no = f"{set_no}{seq:05d}"

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_original_sample_info (sample_no, set_no, sample_name, suffix, type_code, file_path, file_size, label_flag, dir_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            _execute(cursor, sql, (sample_no, set_no, sample_name, suffix, type_code, file_path, file_size, label_flag, dir_id))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def batch_insert_original_sample_info(records: list[dict]):
    """批量插入原始样本信息，预生成 sample_no（set_no + 5位序列号）

    records 字段：set_no, sample_name, suffix, type_code, file_path, file_size, dir_id(可选)
    返回插入条数。

    注意：为避免并发序列号冲突，sample_no 在本函数内一次性顺序生成，调用方无需传入。
    """
    if not records:
        return 0
    set_no = records[0].get("set_no", "")
    # 一次性申请 len(records) 个序列号
    start_seq = _get_next_sequence_batch(f'SAMPLE_NO_{set_no}', set_no, len(records))
    prepared = []
    for idx, r in enumerate(records):
        sample_no = f"{set_no}{start_seq + idx:05d}"
        prepared.append({
            "sample_no": sample_no,
            "sample_name": r.get("sample_name", ""),
            "set_no": set_no,
            "type_code": r.get("type_code", "05"),
            "suffix": r.get("suffix", ""),
            "file_path": r.get("file_path", ""),
            "file_size": r.get("file_size", 0),
            "dir_id": r.get("dir_id"),
        })
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO s_original_sample_info (sample_no, set_no, sample_name, suffix, type_code, file_path, file_size, label_flag, dir_id)
                VALUES (%(sample_no)s, %(set_no)s, %(sample_name)s, %(suffix)s, %(type_code)s, %(file_path)s, %(file_size)s, 0, %(dir_id)s)
            """
            _executemany(cursor, sql, prepared)
        conn.commit()
        return len(prepared)
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


def get_original_sample_set_path(set_no: str):
    """查询原始样本集的 set_path 和 type_code"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "SELECT set_no, set_name, set_path, type_code FROM s_original_sample_set WHERE set_no = %s"
            _execute(cursor, sql, (set_no,))
            return cursor.fetchone()
    finally:
        conn.close()


def query_original_sample_file_paths(set_no: str):
    """查询原始样本集下所有样本的 file_path(用于获取图片目录)"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # Oracle中空字符串''等同于NULL，IS NOT NULL即可过滤；MySQL中正常数据file_path不为空字符串
            sql = """
                SELECT file_path FROM s_original_sample_info
                WHERE set_no = %s AND file_path IS NOT NULL
            """
            _execute(cursor, sql, (set_no,))
            return cursor.fetchall()
    finally:
        conn.close()


def query_original_samples(set_no: str):
    """查询原始样本集下所有样本的完整信息（用于图像清洗）

    返回 list[dict]：{sample_no, sample_name, file_path}
    仅返回 file_path 不为空且未被清洗（CLEAN_FLAG='0' 或 NULL）的记录。
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT sample_no, sample_name, file_path
                FROM s_original_sample_info
                WHERE set_no = %s AND file_path IS NOT NULL
                  AND (clean_flag = '0' OR clean_flag IS NULL)
            """
            _execute(cursor, sql, (set_no,))
            return cursor.fetchall()
    finally:
        conn.close()


def delete_original_sample_info_by_path(file_path: str):
    """根据 file_path 删除 s_original_sample_info 中的对应记录"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = "DELETE FROM s_original_sample_info WHERE file_path = %s"
            _execute(cursor, sql, (file_path,))
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def batch_update_clean_flag(sample_nos: list[str], flag: str):
    """批量更新原始样本的清洗标记（CLEAN_FLAG）

    Args:
        sample_nos: 样本编号列表
        flag: '1' 标记为已清洗, '0' 恢复为未清洗
    """
    if not sample_nos:
        return 0
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 分批处理，避免 IN 列表过长
            batch_size = 500
            total = 0
            for i in range(0, len(sample_nos), batch_size):
                batch = sample_nos[i:i + batch_size]
                placeholders = ",".join(["%s"] * len(batch))
                sql = f"UPDATE s_original_sample_info SET clean_flag = %s WHERE sample_no IN ({placeholders})"
                _execute(cursor, sql, (flag, *batch))
                total += cursor.rowcount
        conn.commit()
        return total
    finally:
        conn.close()


# ==================== 样本目录管理（s_sample_directory）====================

def create_directory(set_no: str, parent_id: str, dir_name: str) -> dict:
    """创建目录，返回新目录信息 {dir_id, set_no, parent_id, dir_name, dir_path}

    parent_id 为空字符串或 None 时，创建样本集根目录下的第一级子目录。
    dir_path 自动构建：父目录 dir_path + '/' + dir_name（根目录下则为 dir_name）。
    """
    dir_id = generate_directory_no()
    parent_id = parent_id or None

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 查父目录的 dir_path
            parent_path = ""
            if parent_id:
                _execute(cursor, "SELECT dir_path FROM s_sample_directory WHERE dir_id = %s", (parent_id,))
                row = cursor.fetchone()
                if row:
                    parent_path = row["dir_path"] if isinstance(row, dict) else row[0]

            dir_path = f"{parent_path}/{dir_name}" if parent_path else dir_name

            sql = """
                INSERT INTO s_sample_directory (dir_id, set_no, parent_id, dir_name, dir_path)
                VALUES (%s, %s, %s, %s, %s)
            """
            _execute(cursor, sql, (dir_id, set_no, parent_id, dir_name, dir_path))
        conn.commit()
        return {"dir_id": dir_id, "set_no": set_no, "parent_id": parent_id, "dir_name": dir_name, "dir_path": dir_path}
    finally:
        conn.close()


def query_directory_tree(set_no: str) -> list[dict]:
    """查询样本集下所有目录（扁平列表），前端构建树结构"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT dir_id, set_no, parent_id, dir_name, dir_path,
                       {_date_format('create_time')} as create_time
                FROM s_sample_directory
                WHERE set_no = %s
                ORDER BY dir_path
            """
            _execute(cursor, sql, (set_no,))
            return cursor.fetchall()
    finally:
        conn.close()


def query_directory_by_id(dir_id: str) -> dict:
    """查询单个目录信息"""
    if not dir_id:
        return None
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            sql = f"""
                SELECT dir_id, set_no, parent_id, dir_name, dir_path,
                       {_date_format('create_time')} as create_time
                FROM s_sample_directory
                WHERE dir_id = %s
            """
            _execute(cursor, sql, (dir_id,))
            rows = cursor.fetchall()
            return rows[0] if rows else None
    finally:
        conn.close()


def query_directory_path(dir_id: str) -> list[dict]:
    """查询目录的祖先链（面包屑导航），从根到当前目录。

    返回 [{dir_id, dir_name, dir_path}, ...]，dir_id 为空时返回空列表。
    """
    if not dir_id:
        return []
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 逐级向上查询（目录树一般不深，递归查询即可）
            chain = []
            current_id = dir_id
            while current_id:
                sql = "SELECT dir_id, parent_id, dir_name, dir_path FROM s_sample_directory WHERE dir_id = %s"
                _execute(cursor, sql, (current_id,))
                row = cursor.fetchone()
                if not row:
                    break
                chain.append({
                    "dir_id": row["dir_id"],
                    "dir_name": row["dir_name"],
                    "dir_path": row["dir_path"],
                })
                current_id = row["parent_id"]
            chain.reverse()
            return chain
    finally:
        conn.close()


def delete_directory(dir_id: str, table: str = "s_sample_info") -> dict:
    """删除目录。

    table: "s_sample_info" 或 "s_original_sample_info"，用于检查目录下是否有样本。
    非空目录（含样本或子目录）拒绝删除，返回 {success: False, reason: ...}。
    空目录直接删除，返回 {success: True}。
    """
    if not dir_id:
        return {"success": False, "reason": "dir_id 不能为空"}

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 检查是否有子目录
            _execute(cursor, "SELECT COUNT(*) AS cnt FROM s_sample_directory WHERE parent_id = %s", (dir_id,))
            row = cursor.fetchone()
            child_count = row["cnt"] if isinstance(row, dict) else row[0]
            if child_count > 0:
                return {"success": False, "reason": f"目录下有 {child_count} 个子目录，请先删除子目录"}

            # 检查是否有样本
            _execute(cursor, f"SELECT COUNT(*) AS cnt FROM {table} WHERE dir_id = %s", (dir_id,))
            row = cursor.fetchone()
            sample_count = row["cnt"] if isinstance(row, dict) else row[0]
            if sample_count > 0:
                return {"success": False, "reason": f"目录下有 {sample_count} 个样本，请先移除或删除样本"}

            # 空目录，直接删除
            _execute(cursor, "DELETE FROM s_sample_directory WHERE dir_id = %s", (dir_id,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


def get_dir_path_by_id(dir_id: str) -> str:
    """通过 dir_id 查询目录的完整路径（dir_path），用于构建 file_path。

    dir_id 为空或 None 时返回空字符串（根目录）。
    """
    if not dir_id:
        return ""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            _execute(cursor, "SELECT dir_path FROM s_sample_directory WHERE dir_id = %s", (dir_id,))
            row = cursor.fetchone()
            if row:
                return row["dir_path"] if isinstance(row, dict) else row[0]
            return ""
    finally:
        conn.close()


def delete_sample_set(set_no: str) -> dict:
    """删除高质量样本集（仅允许删除空样本集）。

    检查项：
      1. s_sample_info 中是否有样本
    通过后删除 s_sample_set 记录及 s_sample_directory 中的目录记录，并返回 set_path 用于清理存储。
    返回: {success: bool, reason?: str, set_path?: str}
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 检查是否有样本
            _execute(cursor, "SELECT COUNT(*) AS cnt FROM s_sample_info WHERE set_no = %s", (set_no,))
            row = cursor.fetchone()
            sample_count = row["cnt"] if isinstance(row, dict) else row[0]
            if sample_count > 0:
                return {"success": False, "reason": f"样本集下有 {sample_count} 个样本，请先删除所有样本"}

            # 查询 set_path 用于清理存储
            _execute(cursor, "SELECT set_path FROM s_sample_set WHERE set_no = %s", (set_no,))
            row = cursor.fetchone()
            set_path = row["set_path"] if isinstance(row, dict) else row[0] if row else None

            # 删除目录记录
            _execute(cursor, "DELETE FROM s_sample_directory WHERE set_no = %s", (set_no,))

            # 删除样本集记录
            _execute(cursor, "DELETE FROM s_sample_set WHERE set_no = %s", (set_no,))
        conn.commit()
        return {"success": True, "set_path": set_path}
    finally:
        conn.close()


def delete_original_sample_set(set_no: str) -> dict:
    """删除原始样本集（仅允许删除空样本集）。

    检查项：
      1. s_original_sample_info 中是否有样本
      2. s_data_collect_task 中是否有关联的采集任务
    通过后删除 s_original_sample_set 记录及 s_sample_directory 中的目录记录，并返回 set_path 用于清理存储。
    返回: {success: bool, reason?: str, set_path?: str}
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 检查是否有样本
            _execute(cursor, "SELECT COUNT(*) AS cnt FROM s_original_sample_info WHERE set_no = %s", (set_no,))
            row = cursor.fetchone()
            sample_count = row["cnt"] if isinstance(row, dict) else row[0]
            if sample_count > 0:
                return {"success": False, "reason": f"样本集下有 {sample_count} 个样本，请先删除所有样本"}

            # 检查是否被采集任务引用
            _execute(cursor, "SELECT COUNT(*) AS cnt FROM s_data_collect_task WHERE original_sample_set_no = %s", (set_no,))
            row = cursor.fetchone()
            task_count = row["cnt"] if isinstance(row, dict) else row[0]
            if task_count > 0:
                return {"success": False, "reason": f"该样本集被 {task_count} 个采集任务引用，请先删除相关采集任务"}

            # 查询 set_path 用于清理存储
            _execute(cursor, "SELECT set_path FROM s_original_sample_set WHERE set_no = %s", (set_no,))
            row = cursor.fetchone()
            set_path = row["set_path"] if isinstance(row, dict) else row[0] if row else None

            # 删除目录记录
            _execute(cursor, "DELETE FROM s_sample_directory WHERE set_no = %s", (set_no,))

            # 删除原始样本集记录
            _execute(cursor, "DELETE FROM s_original_sample_set WHERE set_no = %s", (set_no,))
        conn.commit()
        return {"success": True, "set_path": set_path}
    finally:
        conn.close()


def clear_time_series_data(set_no: str) -> dict:
    """清空时序样本集绑定的目标表数据

    仅允许时序类型（02）且已绑定目标表的样本集操作。
    返回: {success: bool, reason?: str, count?: int}
    """
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 校验样本集
            _execute(cursor, "SELECT binding_table, type_code FROM s_original_sample_set WHERE set_no = %s", (set_no,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "reason": "样本集不存在"}
            binding_table = row["binding_table"] if isinstance(row, dict) else row[0]
            type_code = row["type_code"] if isinstance(row, dict) else row[1]
            if type_code != "02":
                return {"success": False, "reason": "仅时序类型样本集支持此操作"}
            if not binding_table:
                return {"success": False, "reason": "该样本集尚未绑定目标表，无数据可清除"}

            # 2. 清空数据
            # 注意：不做 user_tables 之类的存在性预检。系统通过 CURRENT_SCHEMA 切换 schema，
            # 绑定表可能位于其它 schema（user_tables 查不到，导致误报"表不存在"），
            # 因此直接按表名执行 DELETE，表不存在时由数据库抛错，由接口层返回错误信息。
            del_sql = f"DELETE FROM {_quote_ident(binding_table)}"
            _execute(cursor, del_sql, ())
            deleted = cursor.rowcount
        conn.commit()
        return {"success": True, "count": deleted}
    finally:
        conn.close()
