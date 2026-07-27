"""图像清洗 - cleanvision 实现备份（已废弃，不会被调用）

历史实现：使用 cleanvision 库进行图像质量检测，仅支持本地文件系统。
为兼容对象存储（MinIO）模式，已替换为 app.services.image_clean_service 中的自实现版本。

本文件保留作为参考与回滚备份，请勿在业务代码中导入。
"""
import logging
import os
import sys
import shutil

logger = logging.getLogger("app.clean_backup")


def _execute_image_clean_task_cleanvision(task: dict, task_no: str,
                                          update_clean_task_status=None,
                                          insert_clean_log=None,
                                          append_clean_log=None,
                                          finish_clean_log=None,
                                          query_pic_clean_type_dict=None,
                                          query_original_sample_file_paths=None,
                                          insert_clean_pic_record=None,
                                          delete_original_sample_info_by_path=None):
    """[已废弃] 使用 cleanvision 检测问题图片，移动到隔离目录

    保留原实现作为备份。参数通过依赖注入方式传入，便于独立测试与回滚。
    实际清洗任务请使用 app.services.image_clean_service.execute_image_clean_task。
    """
    raise NotImplementedError(
        "此为 cleanvision 备份实现，已废弃。请使用 app.services.image_clean_service.execute_image_clean_task"
    )


def _legacy_cleanvision_implementation():
    """原 cleanvision 实现代码片段（仅供参考，不会被执行）

    核心流程：
    1. 从清洗节点获取 set_no 与清洗类型编码
    2. 查询 PIC_CLEAN_TYPE 字典映射到 cleanvision issue 类型
    3. 查询原始样本文件路径，提取公共目录作为 data_path
    4. 创建 cleanvision.Imagelab(data_path=data_path)
    5. 配置 issue_types：
       - blurry: {"threshold": 0.45}
       - light: {"threshold": 0.47}
       - odd_size: {"threshold": 0.84}
    6. 调用 imagelab.find_issues(issue_types=issue_types, verbose=False, n_jobs=1)
    7. 从 imagelab.issues DataFrame 提取问题图片
    8. 重复类型处理：从 imagelab.info[spare1]["sets"] 获取分组，每组保留第一张
    9. 创建目标目录 base_dir/clean_result/{task_no}
    10. 遍历问题图片：shutil.move 到目标目录，插入清洗记录，删除原始样本记录

    局限性：
    - 仅支持本地文件系统，无法处理 MinIO 对象存储
    - cleanvision 内部使用 data_path 扫描目录，无法适配流式处理
    - 重复检测的分组信息依赖 cleanvision 内部结构，难以扩展
    """
    pass
