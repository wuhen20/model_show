import os
import uuid
import shutil
from datetime import datetime
from typing import List, Optional
from models.schemas import FileUpload, ProcessedFile, MergedFile, FileStatus
import aiofiles


class FileManager:
    """文件管理服务"""
    
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        
        self.upload_dir = os.path.join(base_dir, 'uploads')
        self.processed_dir = os.path.join(base_dir, 'processed')
        self.merged_dir = os.path.join(base_dir, 'merged')
        
        # 确保目录存在
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.processed_dir, exist_ok=True)
        os.makedirs(self.merged_dir, exist_ok=True)
    
    def generate_file_id(self) -> str:
        """生成唯一的文件ID"""
        return str(uuid.uuid4())
    
    def save_uploaded_file(self, file_content: bytes, original_name: str) -> tuple:
        """
        保存上传的文件
        返回: (file_id, file_path)
        """
        file_id = self.generate_file_id()
        # 使用时间戳和原始文件名确保唯一性
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = f"{timestamp}_{original_name}"
        file_path = os.path.join(self.upload_dir, safe_name)
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        return file_id, file_path
    
    def get_upload_path(self, file_id: str, original_name: str) -> str:
        """获取上传文件路径"""
        # 查找文件
        for filename in os.listdir(self.upload_dir):
            if file_id in filename or original_name in filename:
                return os.path.join(self.upload_dir, filename)
        return None
    
    def get_processed_path(self, file_id: str, original_name: str) -> str:
        """获取处理后文件路径（统一输出为CSV格式）"""
        # 生成新文件名，统一使用.csv扩展名
        name_without_ext = os.path.splitext(original_name)[0]
        new_name = f"{name_without_ext}_new.csv"
        return os.path.join(self.processed_dir, new_name)
    
    def list_uploaded_files(self) -> List[FileUpload]:
        """列出所有上传的文件"""
        files = []
        for filename in os.listdir(self.upload_dir):
            file_path = os.path.join(self.upload_dir, filename)
            if os.path.isfile(file_path):
                stat = os.stat(file_path)
                files.append(FileUpload(
                    file_id=filename,
                    original_name=filename,
                    upload_time=datetime.fromtimestamp(stat.st_ctime),
                    file_size=stat.st_size
                ))
        return files
    
    def list_processed_files(self) -> List[ProcessedFile]:
        """列出所有处理后的文件"""
        files = []
        for filename in os.listdir(self.processed_dir):
            file_path = os.path.join(self.processed_dir, filename)
            if os.path.isfile(file_path) and filename.endswith('_new.csv'):
                stat = os.stat(file_path)
                # 从文件名提取原始名称（支持.xlsx和.csv）
                original_name = filename.replace('_new.csv', '.csv')
                # 检查是否有对应的xlsx文件
                original_xlsx = filename.replace('_new.csv', '.xlsx')
                if os.path.exists(os.path.join(self.upload_dir, original_xlsx)):
                    original_name = original_xlsx
                
                files.append(ProcessedFile(
                    file_id=filename,
                    original_name=original_name,
                    new_name=filename,
                    processed_time=datetime.fromtimestamp(stat.st_mtime),  # 使用修改时间
                    file_size=stat.st_size
                ))
        return files
    
    def delete_file(self, file_id: str, file_type: str = 'upload') -> bool:
        """删除文件"""
        if file_type == 'upload':
            directory = self.upload_dir
        elif file_type == 'processed':
            directory = self.processed_dir
        elif file_type == 'merged':
            directory = self.merged_dir
        else:
            return False
        
        for filename in os.listdir(directory):
            if file_id in filename or filename == file_id:
                file_path = os.path.join(directory, filename)
                os.remove(file_path)
                return True
        return False
    
    def delete_processed_file(self, file_name: str) -> bool:
        """删除预处理文件"""
        file_path = os.path.join(self.processed_dir, file_name)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    
    def delete_merged_file(self, file_name: str) -> bool:
        """删除整合文件"""
        file_path = os.path.join(self.merged_dir, file_name)
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    
    def get_file_size(self, file_path: str) -> Optional[int]:
        """获取文件大小"""
        if os.path.exists(file_path):
            return os.path.getsize(file_path)
        return None
    
    def get_merged_path(self, main_table_name: str) -> str:
        """获取整合文件路径"""
        name_without_ext = os.path.splitext(main_table_name)[0]
        # 移除_new后缀（如果有）
        if name_without_ext.endswith('_new'):
            name_without_ext = name_without_ext[:-4]
        new_name = f"{name_without_ext}_merge.csv"
        return os.path.join(self.merged_dir, new_name)
    
    def list_merged_files(self) -> List[MergedFile]:
        """列出所有整合后的文件"""
        files = []
        for filename in os.listdir(self.merged_dir):
            file_path = os.path.join(self.merged_dir, filename)
            if os.path.isfile(file_path) and filename.endswith('_merge.csv'):
                stat = os.stat(file_path)
                # 从文件名提取主表名称
                main_table_name = filename.replace('_merge.csv', '_new.csv')
                
                files.append(MergedFile(
                    file_id=filename,
                    main_table_name=main_table_name,
                    merged_name=filename,
                    merge_time=datetime.fromtimestamp(stat.st_mtime),  # 使用修改时间而非创建时间
                    file_size=stat.st_size,
                    join_type='left',  # 默认值，实际应从元数据中获取
                    table_count=1  # 默认值，实际应从元数据中获取
                ))
        return files
