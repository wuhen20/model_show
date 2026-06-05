from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from services.file_manager import FileManager
from models.schemas import ProcessedFileListResponse, MergedFileListResponse
import os

router = APIRouter(prefix="/api/download", tags=["download"])

# 初始化文件管理器
file_manager = FileManager()


@router.get("/processed", response_model=ProcessedFileListResponse)
async def list_processed_files():
    """获取预处理文件列表"""
    try:
        files = file_manager.list_processed_files()
        return ProcessedFileListResponse(
            files=files,
            total=len(files)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取预处理文件列表失败: {str(e)}")


@router.get("/merged", response_model=MergedFileListResponse)
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
async def download_file(file_id: str):
    """下载处理后的文件"""
    try:
        # 查找文件
        processed_dir = file_manager.processed_dir
        file_path = None
        
        for filename in os.listdir(processed_dir):
            if file_id in filename:
                file_path = os.path.join(processed_dir, filename)
                break
        
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 返回文件
        return FileResponse(
            path=file_path,
            filename=os.path.basename(file_path),
            media_type='text/csv'
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"下载文件失败: {str(e)}")


@router.delete("/processed/{file_name}")
async def delete_processed_file(file_name: str):
    """删除预处理文件"""
    try:
        deleted = file_manager.delete_processed_file(file_name)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        return {
            "message": "预处理文件删除成功",
            "file_name": file_name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")


@router.delete("/merged/{file_name}")
async def delete_merged_file(file_name: str):
    """删除整合文件"""
    try:
        deleted = file_manager.delete_merged_file(file_name)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        return {
            "message": "整合文件删除成功",
            "file_name": file_name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")


@router.delete("/files/{file_id}")
async def delete_file(file_id: str):
    """删除文件"""
    try:
        # 尝试删除上传文件
        deleted = file_manager.delete_file(file_id, file_type='upload')
        
        # 尝试删除处理后的文件
        deleted_processed = file_manager.delete_file(file_id, file_type='processed')
        
        if not deleted and not deleted_processed:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        return {
            "message": "文件删除成功",
            "deleted_upload": deleted,
            "deleted_processed": deleted_processed
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")
