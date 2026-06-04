import pandas as pd
import re
import os
from typing import List, Dict, Optional
from models.schemas import TimeType, ProcessConfig


class DataTransformer:
    """数据转换核心服务（支持CSV和XLSX输入，统一输出CSV）"""
    
    @staticmethod
    def _detect_real_format(file_path: str) -> str:
        """
        检测文件的真实格式（不依赖扩展名）
        返回: 'csv', 'excel', 或 'unknown'
        """
        try:
            with open(file_path, 'rb') as f:
                # 读取文件头
                header = f.read(100)
                
                # 检查是否是ZIP格式（xlsx本质是ZIP）
                if header[:4] == b'\x50\x4b\x03\x04':
                    return 'excel'  # xlsx
                
                # 检查是否是OLE2格式（xls）
                if header[:4] == b'\xd0\xcf\x11\xe0':
                    return 'excel'  # xls
                
                # 检查是否是文本文件（CSV）
                # UTF-8 BOM
                if header[:3] == b'\xef\xbb\xbf':
                    return 'csv'
                
                # 尝试解码为文本
                try:
                    text = header.decode('utf-8')
                    # 检查是否包含逗号或制表符
                    if ',' in text or '\t' in text:
                        return 'csv'
                except:
                    pass
                
                # 尝试GBK解码
                try:
                    text = header.decode('gbk')
                    if ',' in text or '\t' in text:
                        return 'csv'
                except:
                    pass
                
                return 'unknown'
        except Exception as e:
            print(f"文件格式检测失败: {e}")
            return 'unknown'
    
    @staticmethod
    def transform_csv(config: ProcessConfig, input_path: str, output_path: str) -> str:
        """
        根据配置转换数据（支持CSV和XLSX输入）
        统一输出为CSV格式
        返回输出文件路径
        """
        try:
            # 根据文件类型读取数据
            ext = os.path.splitext(input_path)[1].lower()
            
            # 智能检测真实文件格式
            actual_format = DataTransformer._detect_real_format(input_path)
            print(f"文件扩展名: {ext}, 实际格式: {actual_format}")
            
            if actual_format == 'csv':
                # 实际是CSV文件（即使扩展名是xlsx）
                df = None
                for encoding in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']:
                    try:
                        df = pd.read_csv(input_path, encoding=encoding)
                        print(f"使用{encoding}编码成功读取CSV文件")
                        break
                    except (UnicodeDecodeError, Exception) as e:
                        print(f"{encoding}编码失败: {e}")
                        continue
                
                if df is None:
                    df = pd.read_csv(input_path, encoding='utf-8', errors='ignore')
                    print("使用utf-8 ignore模式读取")
            elif actual_format == 'excel':
                # 真正的Excel文件
                df = None
                last_error = None
                
                # 尝试openpyxl引擎
                try:
                    df = pd.read_excel(input_path, engine='openpyxl')
                except Exception as e1:
                    last_error = e1
                    print(f"openpyxl引擎失败: {str(e1)}")
                    # 尝试xlrd引擎
                    try:
                        df = pd.read_excel(input_path, engine='xlrd')
                    except Exception as e2:
                        last_error = e2
                        print(f"xlrd引擎失败: {str(e2)}")
                        # 最后尝试自动检测
                        try:
                            df = pd.read_excel(input_path)
                        except Exception as e3:
                            last_error = e3
                            print(f"自动检测失败: {str(e3)}")
                
                if df is None:
                    raise Exception(f"无法读取Excel文件。最后错误: {str(last_error)}")
            else:
                raise Exception(f"不支持的文件格式: {actual_format}")
            
            # 根据时间类型进行不同的转换
            if config.time_type == TimeType.DATE:
                result_df = DataTransformer._transform_date_type(df, config)
            elif config.time_type == TimeType.HOUR:
                result_df = DataTransformer._transform_hour_type(df, config)
            elif config.time_type == TimeType.DATETIME:
                result_df = DataTransformer._transform_datetime_type(df, config)
            else:
                raise ValueError(f"不支持的时间类型: {config.time_type}")
            
            # 统一输出为CSV格式
            result_df.to_csv(output_path, index=False, encoding='utf-8-sig')
            return output_path
            
        except Exception as e:
            import traceback
            error_msg = f"数据转换失败: {str(e)}\n详细错误:\n{traceback.format_exc()}"
            print(error_msg)
            raise Exception(error_msg)
    
    @staticmethod
    def _transform_date_type(df: pd.DataFrame, config: ProcessConfig) -> pd.DataFrame:
        """
        处理日期类型(YYYY-MM-DD)
        如果有TIME_DATE列,则扩展为多行
        其他字段保持原有名称
        """
        result_rows = []
        
        # 获取公共列
        common_cols = config.common_columns or []
        time_col = config.time_column
        
        # 检查是否有TIME_DATE列
        time_date_col = None
        for col in df.columns:
            if col.upper() == 'TIME_DATE':
                time_date_col = col
                break
        
        # 获取值列（除了公共列、时间列、TIME_DATE列）
        value_cols = [col for col in df.columns 
                     if col not in common_cols 
                     and col != time_col 
                     and col != time_date_col]
        
        print(f"[日期类型转换] 值列: {value_cols}")
        
        for idx, row in df.iterrows():
            if time_date_col and time_date_col in row:
                # 如果已经有TIME_DATE,直接保留
                new_row = {}
                for col in common_cols:
                    new_row[col] = row[col]
                new_row[time_col] = row[time_col]
                new_row['TIME_DATE'] = row[time_date_col]
                
                # 添加值列，保持原有字段名
                for val_col in value_cols:
                    new_row[val_col] = row[val_col]
                
                result_rows.append(new_row)
            else:
                # 没有时间列,只保留日期
                new_row = {}
                for col in common_cols:
                    new_row[col] = row[col]
                new_row[time_col] = row[time_col]
                
                # 添加值列，保持原有字段名
                for val_col in value_cols:
                    new_row[val_col] = row[val_col]
                
                result_rows.append(new_row)
        
        return pd.DataFrame(result_rows)
    
    @staticmethod
    def _transform_hour_type(df: pd.DataFrame, config: ProcessConfig) -> pd.DataFrame:
        """
        处理小时类型(X0000, P0100等格式)
        将多个小时列展开为多行,TIME_DATE存储时间
        如果有多个值列，使用VALUE1, VALUE2等命名
        如果只有一个值列，保持原有逻辑使用VALUE1
        """
        result_rows = []
        hour_columns = config.hour_columns or []
        common_cols = config.common_columns or []
        time_col = config.time_column
        
        # 确定值列（除了公共列、时间列、小时列之外的列）
        value_cols = [col for col in df.columns 
                     if col not in common_cols 
                     and col != time_col
                     and col not in hour_columns]
        
        print(f"[小时类型转换] 值列: {value_cols}")
        print(f"[小时类型转换] 小时列: {hour_columns}")
        
        # 对每一行数据
        for idx, row in df.iterrows():
            # 对每个小时列
            for hour_col in hour_columns:
                if hour_col not in row:
                    continue
                
                # 解析小时列名为时间格式
                time_value = DataTransformer._parse_hour_column(hour_col)
                
                new_row = {}
                # 添加公共列
                for col in common_cols:
                    new_row[col] = row[col]
                
                # 添加日期列(如果有)
                if time_col and time_col in row:
                    new_row[time_col] = row[time_col]
                
                # 添加TIME_DATE
                new_row['TIME_DATE'] = time_value
                
                # 添加值列
                if len(value_cols) == 0:
                    # 没有额外的值列，小时列本身就是值
                    new_row['VALUE1'] = row[hour_col]
                elif len(value_cols) == 1:
                    # 只有一个值列，使用原字段名
                    new_row[value_cols[0]] = row[hour_col]
                else:
                    # 多个值列，使用VALUE1, VALUE2等
                    for i, val_col in enumerate(value_cols, 1):
                        new_row[f'VALUE{i}'] = row[val_col]
                
                result_rows.append(new_row)
        
        return pd.DataFrame(result_rows)
    
    @staticmethod
    def _transform_datetime_type(df: pd.DataFrame, config: ProcessConfig) -> pd.DataFrame:
        """
        处理日期时间类型(YYYY-MM-DD HH:MM:SS)
        拆分为DATE和TIME_DATE两列
        其他字段保持原有名称
        """
        result_rows = []
        time_col = config.time_column
        common_cols = config.common_columns or []
        
        # 获取值列（除了公共列和时间列）
        value_cols = [col for col in df.columns 
                     if col not in common_cols 
                     and col != time_col]
        
        print(f"[日期时间类型转换] 值列: {value_cols}")
        
        for idx, row in df.iterrows():
            if time_col and time_col in row:
                datetime_str = str(row[time_col])
                
                # 拆分日期和时间
                date_part, time_part = DataTransformer._split_datetime(datetime_str)
                
                new_row = {}
                for col in common_cols:
                    new_row[col] = row[col]
                
                new_row['DATE'] = date_part
                new_row['TIME_DATE'] = time_part
                
                # 添加值列，保持原有字段名
                for val_col in value_cols:
                    new_row[val_col] = row[val_col]
                
                result_rows.append(new_row)
        
        return pd.DataFrame(result_rows)
    
    @staticmethod
    def _parse_hour_column(column_name: str) -> str:
        """
        解析小时列名为时间格式
        支持多种前缀: X, P, T, H 以及无前缀
        X0000 -> 00:00:00
        T0015 -> 00:15:00
        P0100 -> 01:00:00
        H2345 -> 23:45:00
        0000 -> 00:00:00
        """
        # 去除前缀(X, P, T, H)
        time_str = re.sub(r'^[XPTH]', '', column_name.upper())
        
        # 解析为HH:MM:SS格式
        if len(time_str) == 4:
            hour = time_str[:2]
            minute = time_str[2:]
            return f"{hour}:{minute}:00"
        else:
            # 如果不是4位,尝试其他格式
            return time_str
    
    @staticmethod
    def _split_datetime(datetime_str: str) -> tuple:
        """
        拆分日期时间字符串为日期和时间两部分
        支持多种格式:
        - YYYY-MM-DD HH:MM:SS
        - YYYY-MM-DDTHH:MM:SS
        - YYYY/MM/DD HH:MM:SS
        - DD/MM/YYYY HH:MM:SS
        """
        datetime_str = str(datetime_str).strip()
        
        # 尝试常见的分隔符
        for separator in [' ', 'T']:
            if separator in datetime_str:
                parts = datetime_str.split(separator)
                if len(parts) == 2:
                    date_part = parts[0]
                    time_part = parts[1]
                    
                    # 标准化日期格式
                    date_part = DataTransformer._normalize_date(date_part)
                    
                    return date_part, time_part
        
        # 如果无法拆分,返回原字符串
        return datetime_str, "00:00:00"
    
    @staticmethod
    def _normalize_date(date_str: str) -> str:
        """
        标准化日期格式为YYYY-MM-DD
        支持:
        - YYYY-MM-DD (已经是标准格式)
        - YYYY/MM/DD
        - DD/MM/YYYY
        - MM/DD/YYYY
        """
        import pandas as pd
        try:
            # 使用pandas解析各种日期格式
            date_obj = pd.to_datetime(date_str)
            return date_obj.strftime('%Y-%m-%d')
        except:
            # 如果解析失败,返回原字符串
            return date_str
    
    @staticmethod
    def format_date_column(df: pd.DataFrame, column_name: str) -> pd.DataFrame:
        """
        格式化日期列为YYYY-MM-DD格式
        """
        if column_name in df.columns:
            try:
                df[column_name] = pd.to_datetime(df[column_name]).dt.strftime('%Y-%m-%d')
            except:
                # 如果转换失败,保持原样
                pass
        return df
