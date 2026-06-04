import pandas as pd
import os
from datetime import datetime
from typing import List
from models.schemas import MergeRequest, MergeJoinType


class DataMerger:
    """数据关联服务"""
    
    @staticmethod
    def merge_tables(merge_request: MergeRequest, processed_dir: str, merged_dir: str) -> str:
        """
        执行多表关联
        返回：合并后的文件路径
        """
        try:
            # 1. 读取主表
            main_file_path = os.path.join(processed_dir, merge_request.main_table.file_name)
            print(f"[数据关联] 读取主表: {main_file_path}")
            
            main_df = pd.read_csv(main_file_path, encoding='utf-8-sig')
            print(f"[数据关联] 主表行数: {len(main_df)}, 列数: {len(main_df.columns)}")
            
            # 2. 依次关联次表
            result_df = main_df
            table_count = 1  # 主表
            
            for idx, secondary_table in enumerate(merge_request.secondary_tables, 1):
                print(f"[数据关联] 关联第{idx}个次表: {secondary_table.file_name}")
                
                # 读取次表
                secondary_file_path = os.path.join(processed_dir, secondary_table.file_name)
                secondary_df = pd.read_csv(secondary_file_path, encoding='utf-8-sig')
                
                print(f"[数据关联] 次表行数: {len(secondary_df)}, 列数: {len(secondary_df.columns)}")
                print(f"[数据关联] 主表关联字段: {secondary_table.main_join_columns}")
                print(f"[数据关联] 次表关联字段: {secondary_table.secondary_join_columns}")
                
                # 验证关联字段是否存在
                for col in secondary_table.main_join_columns:
                    if col not in result_df.columns:
                        raise ValueError(f"主表关联字段 '{col}' 不存在于主表中，可用字段: {list(result_df.columns)}")
                
                for col in secondary_table.secondary_join_columns:
                    if col not in secondary_df.columns:
                        raise ValueError(f"次表关联字段 '{col}' 不存在于次表中，可用字段: {list(secondary_df.columns)}")
                
                # 打印关联字段的示例数据用于调试
                if len(result_df) > 0:
                    print(f"[数据关联] 主表关联字段示例数据: {result_df[secondary_table.main_join_columns].head(5).to_dict()}")
                if len(secondary_df) > 0:
                    print(f"[数据关联] 次表关联字段示例数据: {secondary_df[secondary_table.secondary_join_columns].head(5).to_dict()}")
                
                # 重命名列：原表名.字段名（关联字段不重命名）
                table_name = os.path.splitext(secondary_table.file_name)[0]
                renamed_columns = {}
                
                for col in secondary_df.columns:
                    # 如果该列不在次表关联字段中，则需要重命名
                    if col not in secondary_table.secondary_join_columns:
                        renamed_columns[col] = f"{table_name}.{col}"
                
                print(f"[数据关联] 重命名列: {renamed_columns}")
                secondary_df = secondary_df.rename(columns=renamed_columns)
                
                # 重命名后的次表关联字段
                renamed_secondary_join_columns = []
                for col in secondary_table.secondary_join_columns:
                    if col in renamed_columns:
                        renamed_secondary_join_columns.append(renamed_columns[col])
                    else:
                        renamed_secondary_join_columns.append(col)
                
                print(f"[数据关联] 重命名后的次表关联字段: {renamed_secondary_join_columns}")
                
                # 执行关联前检查：验证关联字段的数据类型是否一致
                for main_col, sec_col in zip(secondary_table.main_join_columns, renamed_secondary_join_columns):
                    main_dtype = result_df[main_col].dtype
                    sec_dtype = secondary_df[sec_col].dtype
                    print(f"[数据关联] 字段类型检查: {main_col}({main_dtype}) <-> {sec_col}({sec_dtype})")
                    
                    # 如果类型不一致，尝试统一转换为字符串
                    if main_dtype != sec_dtype:
                        print(f"[数据关联] 警告: 字段类型不一致，自动转换为字符串类型")
                        result_df[main_col] = result_df[main_col].astype(str)
                        secondary_df[sec_col] = secondary_df[sec_col].astype(str)
                
                # 执行关联
                join_type = merge_request.join_type.value
                result_df = pd.merge(
                    result_df,
                    secondary_df,
                    left_on=secondary_table.main_join_columns,
                    right_on=renamed_secondary_join_columns,
                    how=join_type
                )
                
                table_count += 1
                print(f"[数据关联] 关联后行数: {len(result_df)}, 列数: {len(result_df.columns)}")
                
                # 如果使用INNER JOIN且结果为空，给出警告
                if join_type == 'inner' and len(result_df) == 0:
                    print(f"[数据关联] ⚠️ 警告: INNER JOIN结果为空！")
                    print(f"[数据关联] 可能原因: 关联字段的数据值不匹配")
                    print(f"[数据关联] 主表关联字段 '{secondary_table.main_join_columns}' 的样本值: {result_df[secondary_table.main_join_columns].head(3).tolist() if len(result_df) > 0 else '无数据'}")
            
            # 3. 保存结果
            # 生成整合文件名：主表名_merge.csv
            main_table_name = os.path.splitext(merge_request.main_table.file_name)[0]
            # 移除_new后缀
            if main_table_name.endswith('_new'):
                main_table_name = main_table_name[:-4]
            # 加时间戳，避免同名整合结果相互覆盖（保留历史文件）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_filename = f"{main_table_name}_{timestamp}_merge.csv"
            output_path = os.path.join(merged_dir, output_filename)
            result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            print(f"[数据关联] 整合完成: {output_path}")
            print(f"[数据关联] 最终行数: {len(result_df)}, 列数: {len(result_df.columns)}")
            print(f"[数据关联] 表数量: {table_count}")
            
            return output_path
            
        except Exception as e:
            import traceback
            error_msg = f"数据关联失败: {str(e)}\n详细错误:\n{traceback.format_exc()}"
            print(error_msg)
            raise Exception(error_msg)
