"""业务编号常量类

编号格式：年月日 + 业务编号 + 3位序列号。
业务编号用于区分不同类型的业务实体，避免同一天新增的业务出现相同编号。
"""


class BizCode:
    """业务编号常量类

    各业务编号对应关系：
      高质量样本集（s_sample_set.set_no）       → 01
      原始样本集（s_original_sample_set.set_no） → 02
      数据采集任务（s_data_collect_task.task_no） → 03
      数据清洗任务（s_data_clean_task.task_no）   → 04
      样本批量导入任务（s_sample_import_task.task_no） → 05
    """
    HIGH_QUALITY_SAMPLE_SET = "01"  # 高质量样本集
    ORIGINAL_SAMPLE_SET = "02"      # 原始样本集
    DATA_COLLECT_TASK = "03"        # 数据采集任务
    DATA_CLEAN_TASK = "04"          # 数据清洗任务
    BATCH_IMPORT_TASK = "05"        # 样本批量导入任务