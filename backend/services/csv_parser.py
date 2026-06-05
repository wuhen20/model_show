from models.schemas import FileUpload
from typing import List, Dict
import pandas as pd
import re
import os


class CSVParser:
    """文件解析和表头格式化服务（支持CSV和XLSX）"""
    
    @staticmethod
    def _get_file_extension(file_path: str) -> str:
        """获取文件扩展名"""
        return os.path.splitext(file_path)[1].lower()
    
    @staticmethod
    def _detect_real_format(file_path: str) -> str:
        """
        检测文件的真实格式（不依赖扩展名）
        返回: 'csv', 'excel', 或 'unknown'
        """
        try:
            with open(file_path, 'rb') as f:
                header = f.read(100)
                
                # ZIP格式（xlsx）
                if header[:4] == b'\x50\x4b\x03\x04':
                    return 'excel'
                
                # OLE2格式（xls）
                if header[:4] == b'\xd0\xcf\x11\xe0':
                    return 'excel'
                
                # UTF-8 BOM
                if header[:3] == b'\xef\xbb\xbf':
                    return 'csv'
                
                # 尝试解码为文本
                try:
                    text = header.decode('utf-8')
                    if ',' in text or '\t' in text:
                        return 'csv'
                except:
                    pass
                
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
    def parse_csv_headers(file_path: str) -> List[str]:
        """解析文件的表头字段（支持CSV和XLSX）"""
        try:
            # 智能检测真实格式
            actual_format = CSVParser._detect_real_format(file_path)
            ext = CSVParser._get_file_extension(file_path)
            print(f"[解析表头] 扩展名: {ext}, 实际格式: {actual_format}")
            
            if actual_format == 'excel':
                # 真正的Excel文件
                df = None
                try:
                    df = pd.read_excel(file_path, nrows=0, engine='openpyxl')
                except Exception as e1:
                    try:
                        df = pd.read_excel(file_path, nrows=0, engine='xlrd')
                    except Exception as e2:
                        df = pd.read_excel(file_path, nrows=0)
                return df.columns.tolist()
            elif actual_format == 'csv':
                # CSV文件（即使扩展名是xlsx）
                for encoding in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']:
                    try:
                        df = pd.read_csv(file_path, nrows=0, encoding=encoding)
                        print(f"[解析表头] 使用{encoding}编码成功")
                        return df.columns.tolist()
                    except (UnicodeDecodeError, Exception):
                        continue
                df = pd.read_csv(file_path, nrows=0, encoding='utf-8', errors='ignore')
                return df.columns.tolist()
            else:
                raise Exception(f"不支持的文件格式")
        except Exception as e:
            raise Exception(f"解析文件失败: {str(e)}")
    
    @staticmethod
    def format_headers(headers: List[str]) -> List[str]:
        """
        格式化表头字段
        - 英文表头: 转换为大写,去除空格和特殊字符
        - 中文表头: 保持原样,不转换
        - 保证字段唯一性
        """
        import re
        formatted = []
        seen = {}
        
        for header in headers:
            # 检查是否包含中文字符
            has_chinese = any('\u4e00' <= char <= '\u9fff' for char in header)
            
            if has_chinese:
                # 中文表头: 保持原样,只去除首尾空格
                formatted_header = header.strip()
            else:
                # 英文表头: 转换为大写,去除空格和特殊字符
                formatted_header = re.sub(r'[^A-Z0-9_]', '', header.upper().replace(' ', '_'))
            
            # 保证唯一性
            if formatted_header in seen:
                seen[formatted_header] += 1
                formatted_header = f"{formatted_header}_{seen[formatted_header]}"
            else:
                seen[formatted_header] = 0
            
            formatted.append(formatted_header)
        
        return formatted
    
    @staticmethod
    def suggest_time_columns(headers: List[str]) -> List[str]:
        """智能识别潜在的时间列"""
        time_keywords = ['DATE', 'TIME', 'DATETIME', 'TIMESTAMP', '时间', '日期']
        suggested = []
        
        for header in headers:
            header_upper = header.upper()
            if any(keyword in header_upper for keyword in time_keywords):
                suggested.append(header)
        
        return suggested
    
    @staticmethod
    def suggest_hour_columns(headers: List[str]) -> List[str]:
        """智能识别潜在的小时列(如X0000, P0100, T0000等格式)"""
        # 支持更多前缀: X, P, T, H, 以及无前缀的纯数字
        hour_pattern = re.compile(r'^[XPTH]?\d{4}$')
        suggested = []
        
        for header in headers:
            if hour_pattern.match(header.upper()):
                suggested.append(header)
        
        return suggested
    
    @staticmethod
    def preview_csv_data(file_path: str, num_rows: int = 5) -> Dict:
        """预览文件数据（支持CSV和XLSX）"""
        try:
            actual_format = CSVParser._detect_real_format(file_path)
            ext = CSVParser._get_file_extension(file_path)
            print(f"[预览数据] 扩展名: {ext}, 实际格式: {actual_format}")
            df = None
            
            if actual_format == 'excel':
                # 真正的Excel文件
                try:
                    df = pd.read_excel(file_path, nrows=num_rows, engine='openpyxl')
                except Exception:
                    try:
                        df = pd.read_excel(file_path, nrows=num_rows, engine='xlrd')
                    except Exception:
                        df = pd.read_excel(file_path, nrows=num_rows)
            elif actual_format == 'csv':
                # CSV文件
                for encoding in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']:
                    try:
                        df = pd.read_csv(file_path, nrows=num_rows, encoding=encoding)
                        print(f"[预览数据] 使用{encoding}编码成功")
                        break
                    except (UnicodeDecodeError, Exception):
                        continue
                
                if df is None:
                    df = pd.read_csv(file_path, nrows=num_rows, encoding='utf-8', errors='ignore')
            else:
                raise Exception(f"不支持的文件格式")
            
            headers = df.columns.tolist()
            data = df.to_dict('records')
            
            # 转换所有值为字符串
            for row in data:
                for key in row:
                    row[key] = str(row[key])
            
            # 计算总行数
            if ext == '.xlsx' or ext == '.xls':
                # Excel文件 - 明确指定engine参数
                try:
                    total_rows = len(pd.read_excel(file_path, engine='openpyxl'))
                except Exception as e1:
                    try:
                        total_rows = len(pd.read_excel(file_path, engine='xlrd'))
                    except Exception as e2:
                        total_rows = len(pd.read_excel(file_path))
            else:
                total_rows = 0
                for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']:
                    try:
                        total_rows = len(pd.read_csv(file_path, encoding=encoding))
                        break
                    except UnicodeDecodeError:
                        continue
                
                if total_rows == 0:
                    total_rows = len(pd.read_csv(file_path, encoding='utf-8', errors='ignore'))
            
            return {
                'headers': headers,
                'data': data,
                'total_rows': total_rows
            }
        except Exception as e:
            raise Exception(f"预览数据失败: {str(e)}")
    
    @staticmethod
    def rename_csv_columns(file_path: str, output_path: str, new_headers: List[str]):
        """重命名文件的列名，统一输出为CSV格式"""
        try:
            ext = CSVParser._get_file_extension(file_path)
            df = None
            
            if ext == '.xlsx' or ext == '.xls':
                # Excel文件 - 明确指定engine参数
                df = None
                last_error = None
                
                try:
                    df = pd.read_excel(file_path, engine='openpyxl')
                except Exception as e1:
                    last_error = e1
                    try:
                        df = pd.read_excel(file_path, engine='xlrd')
                    except Exception as e2:
                        last_error = e2
                        try:
                            df = pd.read_excel(file_path)
                        except Exception as e3:
                            last_error = e3
                
                if df is None:
                    raise Exception(f"无法读取Excel文件: {str(last_error)}")
            else:
                # CSV文件 - 尝试多种编码读取
                for encoding in ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                if df is None:
                    df = pd.read_csv(file_path, encoding='utf-8', errors='ignore')
            
            df.columns = new_headers
            # 统一输出为utf-8-sig编码的CSV格式，兼容Excel
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
        except Exception as e:
            raise Exception(f"重命名列名失败: {str(e)}")
