from fastapi import APIRouter, HTTPException
from services.file_manager import FileManager
from services.csv_parser import CSVParser
from services.data_transformer import DataTransformer
from models.schemas import ProcessConfig, ProcessStatusResponse, FileStatus, BatchProcessRequest, BatchProcessResponse
import os
from typing import List

router = APIRouter(prefix="/api/process", tags=["process"])

# 初始化文件管理器
file_manager = FileManager()

# 导入upload路由中的file_registry
from routers.upload import file_registry

# 存储处理配置
process_configs = {}


@router.post("/configure", response_model=ProcessStatusResponse)
async def configure_process(config: ProcessConfig):
    """配置数据处理规则"""
    if config.file_id not in file_registry:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        # 验证配置
        file_info = file_registry[config.file_id]
        headers = file_info.get('formatted_headers', [])
        
        # 验证时间列是否存在
        if config.time_type in ['date', 'datetime'] and config.time_column:
            if config.time_column not in headers:
                raise ValueError(f"时间列 {config.time_column} 不存在于文件中")
        
        # 验证小时列是否存在
        if config.time_type == 'hour' and config.hour_columns:
            for col in config.hour_columns:
                if col not in headers:
                    raise ValueError(f"小时列 {col} 不存在于文件中")
        
        # 保存配置
        process_configs[config.file_id] = config
        
        # 更新文件状态
        file_info['status'] = 'configured'
        
        return ProcessStatusResponse(
            file_id=config.file_id,
            status=FileStatus.CONFIGURED,
            message="处理配置保存成功"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置保存失败: {str(e)}")


@router.post("/{file_id}/execute", response_model=ProcessStatusResponse)
async def execute_process(file_id: str):
    """执行数据处理"""
    if file_id not in file_registry:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    if file_id not in process_configs:
        raise HTTPException(status_code=400, detail="请先配置处理规则")
    
    try:
        file_info = file_registry[file_id]
        config = process_configs[file_id]
        
        # 更新状态为处理中
        file_info['status'] = 'processing'
        
        # 获取输入文件路径
        input_path = file_info['file_path']
        
        # 生成输出文件路径
        output_path = file_manager.get_processed_path(file_id, file_info['original_name'])
        
        # 先格式化表头
        formatted_headers = file_info.get('formatted_headers', [])
        if not formatted_headers:
            headers = CSVParser.parse_csv_headers(input_path)
            formatted_headers = CSVParser.format_headers(headers)
            file_info['formatted_headers'] = formatted_headers
        
        # 创建临时文件存储格式化后的数据
        import os
        file_ext = os.path.splitext(input_path)[1]
        temp_path = input_path.replace(file_ext, '_formatted' + file_ext)
        
        print(f"开始格式化文件: {input_path}")
        print(f"临时文件路径: {temp_path}")
        print(f"格式化表头: {formatted_headers}")
        
        CSVParser.rename_csv_columns(input_path, temp_path, formatted_headers)
        
        # 更新配置中的列名为格式化后的名称
        if config.time_column:
            config.time_column = CSVParser.format_headers([config.time_column])[0]
        if config.hour_columns:
            config.hour_columns = CSVParser.format_headers(config.hour_columns)
        if config.common_columns:
            config.common_columns = CSVParser.format_headers(config.common_columns)
        
        # 执行数据转换
        print(f"开始数据转换: {temp_path} -> {output_path}")
        DataTransformer.transform_csv(config, temp_path, output_path)
        print(f"数据转换完成: {output_path}")
        
        # 清理临时文件
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        # 更新文件状态
        file_info['status'] = 'completed'
        file_info['output_path'] = output_path
        
        return ProcessStatusResponse(
            file_id=file_id,
            status=FileStatus.COMPLETED,
            message="数据处理完成"
        )
    except Exception as e:
        # 更新状态为失败
        if file_id in file_registry:
            file_registry[file_id]['status'] = 'failed'
            file_registry[file_id]['error'] = str(e)
        
        import traceback
        error_detail = f"数据处理失败: {str(e)}\n\n详细错误:\n{traceback.format_exc()}"
        print(error_detail)
        
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/{file_id}/status", response_model=ProcessStatusResponse)
async def get_process_status(file_id: str):
    """获取处理状态"""
    if file_id not in file_registry:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    file_info = file_registry[file_id]
    status = file_info.get('status', 'uploaded')
    error = file_info.get('error')
    
    return ProcessStatusResponse(
        file_id=file_id,
        status=FileStatus(status),
        message=error
    )


@router.post("/batch-execute", response_model=BatchProcessResponse)
async def batch_execute_process(request: BatchProcessRequest):
    """批量处理多个文件"""
    if not request.file_ids:
        raise HTTPException(status_code=400, detail="请选择要处理的文件")
    
    results = []
    success_count = 0
    failed_count = 0
    
    for file_id in request.file_ids:
        try:
            if file_id not in file_registry:
                results.append({
                    "file_id": file_id,
                    "status": "failed",
                    "message": "文件不存在"
                })
                failed_count += 1
                continue
            
            if file_id not in process_configs:
                results.append({
                    "file_id": file_id,
                    "status": "failed",
                    "message": "未配置处理规则"
                })
                failed_count += 1
                continue
            
            file_info = file_registry[file_id]
            config = process_configs[file_id]
            
            # 更新状态为处理中
            file_info['status'] = 'processing'
            
            # 获取输入文件路径
            input_path = file_info['file_path']
            
            # 生成输出文件路径
            output_path = file_manager.get_processed_path(file_id, file_info['original_name'])
            
            # 先格式化表头
            formatted_headers = file_info.get('formatted_headers', [])
            if not formatted_headers:
                headers = CSVParser.parse_csv_headers(input_path)
                formatted_headers = CSVParser.format_headers(headers)
                file_info['formatted_headers'] = formatted_headers
            
            # 创建临时文件存储格式化后的数据
            temp_path = input_path.replace('.csv', '_formatted.csv')
            CSVParser.rename_csv_columns(input_path, temp_path, formatted_headers)
            
            # 更新配置中的列名为格式化后的名称
            if config.time_column:
                config.time_column = CSVParser.format_headers([config.time_column])[0]
            if config.hour_columns:
                config.hour_columns = CSVParser.format_headers(config.hour_columns)
            if config.common_columns:
                config.common_columns = CSVParser.format_headers(config.common_columns)
            
            # 执行数据转换
            DataTransformer.transform_csv(config, temp_path, output_path)
            
            # 清理临时文件
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
            # 更新文件状态
            file_info['status'] = 'completed'
            file_info['output_path'] = output_path
            
            results.append({
                "file_id": file_id,
                "status": "completed",
                "message": "处理成功"
            })
            success_count += 1
            
        except Exception as e:
            # 更新状态为失败
            if file_id in file_registry:
                file_registry[file_id]['status'] = 'failed'
                file_registry[file_id]['error'] = str(e)
            
            results.append({
                "file_id": file_id,
                "status": "failed",
                "message": str(e)
            })
            failed_count += 1
    
    return BatchProcessResponse(
        total=len(request.file_ids),
        success_count=success_count,
        failed_count=failed_count,
        results=results
    )
