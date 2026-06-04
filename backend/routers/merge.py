from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from services.file_manager import FileManager
from services.data_merger import DataMerger
from services.csv_parser import CSVParser
from models.schemas import (
    MergeRequest, 
    MergedFileListResponse, 
    ProcessStatusResponse, 
    FileStatus,
    HeaderResponse
)
import os

router = APIRouter(prefix="/api/merge", tags=["merge"])

# 初始化文件管理器
file_manager = FileManager()

# 导入process路由中的file_registry
from routers.process import file_registry


@router.get("/available-files")
async def get_available_files():
    """获取已处理文件列表（可用于整合）"""
    try:
        files = file_manager.list_processed_files()
        return {
            "files": files,
            "total": len(files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")


@router.post("/{file_id}/headers", response_model=HeaderResponse)
async def get_file_headers(file_id: str):
    """获取文件表头（用于配置关联字段）"""
    try:
        # 查找文件
        processed_dir = file_manager.processed_dir
        file_path = None
        
        for filename in os.listdir(processed_dir):
            if file_id in filename or filename.startswith(file_id):
                file_path = os.path.join(processed_dir, filename)
                break
        
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 解析表头
        headers = CSVParser.parse_csv_headers(file_path)
        
        return HeaderResponse(
            file_id=file_id,
            headers=headers,
            suggested_time_columns=[],
            suggested_hour_columns=[]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取表头失败: {str(e)}")


@router.post("/execute", response_model=ProcessStatusResponse)
async def execute_merge(merge_request: MergeRequest):
    """执行表关联"""
    try:
        print(f"[样本整合] 开始执行整合")
        print(f"[样本整合] 主表: {merge_request.main_table.file_name}")
        print(f"[样本整合] 次表数量: {len(merge_request.secondary_tables)}")
        print(f"[样本整合] 关联方式: {merge_request.join_type}")
        
        # 生成整合文件路径
        output_path = file_manager.get_merged_path(merge_request.main_table.file_name)
        
        # 执行数据关联
        result_path = DataMerger.merge_tables(
            merge_request,
            file_manager.processed_dir,
            file_manager.merged_dir
        )
        
        print(f"[样本整合] 整合完成: {result_path}")
        
        return ProcessStatusResponse(
            file_id=os.path.basename(result_path),
            status=FileStatus.COMPLETED,
            message="样本整合完成"
        )
    except Exception as e:
        print(f"[样本整合] 整合失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"样本整合失败: {str(e)}")


@router.get("/list", response_model=MergedFileListResponse)
async def list_merged_files():
    """获取整合文件列表"""
    try:
        files = file_manager.list_merged_files()
        return MergedFileListResponse(
            files=files,
            total=len(files)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取整合文件列表失败: {str(e)}")


@router.get("/download/{file_id}")
async def download_merged_file(file_id: str):
    """下载整合文件"""
    try:
        # 查找文件
        merged_dir = file_manager.merged_dir
        file_path = None
        
        for filename in os.listdir(merged_dir):
            if file_id in filename or filename == file_id:
                file_path = os.path.join(merged_dir, filename)
                break
        
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        return FileResponse(
            path=file_path,
            filename=os.path.basename(file_path),
            media_type='text/csv'
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")
