from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from services.file_manager import FileManager
from services.csv_parser import CSVParser
from models.schemas import UploadResponse, HeaderResponse, PreviewResponse
import os

router = APIRouter(prefix="/api/upload", tags=["upload"])

# 初始化文件管理器
file_manager = FileManager()

# 存储文件信息的字典
file_registry = {}


@router.post("/", response_model=UploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """上传文件（支持CSV和XLSX）"""
    # 验证文件类型
    if not (file.filename.endswith('.csv') or file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="只支持CSV和XLSX格式的文件")
    
    try:
        # 读取文件内容
        content = await file.read()
        
        # 保存文件
        file_id, file_path = file_manager.save_uploaded_file(content, file.filename)
        
        # 注册文件信息
        file_registry[file_id] = {
            'file_id': file_id,
            'file_path': file_path,
            'original_name': file.filename,
            'file_size': len(content),
            'status': 'uploaded',
            'upload_time': __import__('datetime').datetime.now().isoformat()
        }
        
        return UploadResponse(
            file_id=file_id,
            original_name=file.filename,
            message="文件上传成功"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@router.post("/{file_id}/headers", response_model=HeaderResponse)
async def get_file_headers(file_id: str):
    """获取CSV文件的表头"""
    if file_id not in file_registry:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        file_info = file_registry[file_id]
        file_path = file_info['file_path']
        
        # 解析表头
        headers = CSVParser.parse_csv_headers(file_path)
        
        # 格式化表头
        formatted_headers = CSVParser.format_headers(headers)
        
        # 更新文件信息
        file_info['formatted_headers'] = formatted_headers
        
        # 智能识别时间列
        suggested_time = CSVParser.suggest_time_columns(formatted_headers)
        suggested_hour = CSVParser.suggest_hour_columns(formatted_headers)
        
        return HeaderResponse(
            file_id=file_id,
            headers=formatted_headers,
            suggested_time_columns=suggested_time,
            suggested_hour_columns=suggested_hour
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析表头失败: {str(e)}")


@router.post("/{file_id}/preview", response_model=PreviewResponse)
async def preview_file_data(file_id: str):
    """预览CSV文件数据"""
    if file_id not in file_registry:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        file_info = file_registry[file_id]
        file_path = file_info['file_path']
        
        # 预览数据
        preview_data = CSVParser.preview_csv_data(file_path, num_rows=5)
        
        return PreviewResponse(
            file_id=file_id,
            headers=preview_data['headers'],
            data=preview_data['data'],
            total_rows=preview_data['total_rows']
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览数据失败: {str(e)}")


@router.get("/list")
async def list_uploaded_files():
    """列出所有上传的文件"""
    try:
        # 从 file_registry 中获取文件信息
        files = []
        for file_id, file_info in file_registry.items():
            files.append({
                'file_id': file_info['file_id'],
                'original_name': file_info['original_name'],
                'file_size': file_info['file_size'],
                'upload_time': file_info.get('upload_time', ''),
                'status': file_info.get('status', 'uploaded')
            })
        
        return {
            "files": files,
            "total": len(files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取文件列表失败: {str(e)}")
