from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from services.file_manager import FileManager
from services.predict_service import PredictService
from services.csv_parser import CSVParser
from models.schemas import (
    PredictRequest, 
    PredictResponse, 
    PredictFileListResponse,
    FileStatus,
    HeaderResponse
)
import os
import sys
import string
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

router = APIRouter(prefix="/api/predict", tags=["predict"])

# 添加 Chronos2 API 路径到 sys.path
project_root = Path(__file__).parent.parent
chronos_api_path = project_root / "predict_api_chronos2" / "Api"
if str(chronos_api_path) not in sys.path:
    sys.path.insert(0, str(chronos_api_path))

# 导入 Chronos2 原生接口
from chronos_predict_api import (
    ChronosPredictRequest,
    run_chronos_prediction,
    is_valid_model_dir,
    has_model_weights,
    default_model_dir,
)

# 模型根目录（用于扫描可选模型；可用环境变量 CHRONOS2_MODEL_ROOT 覆盖）
def _default_model_root() -> Path:
    return project_root / "predict_api_chronos2" / "Model"


def _dir_size_mb(d: Path) -> float:
    """统计目录内权重相关文件的大致体积（仅顶层文件，避免遍历 HF 缓存子目录重复计数）。"""
    try:
        total = 0
        for f in d.iterdir():
            if f.is_file():
                total += f.stat().st_size
        return total / 1024 / 1024
    except Exception:
        return 0.0


def _list_windows_drives() -> list:
    """Windows 下枚举可用盘符（如 C:/ D:/）；非 Windows 返回空。"""
    drives = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            root = f"{letter}:/"
            if os.path.exists(root):
                drives.append(root)
    return drives


class ModelBrowseRequest(BaseModel):
    path: Optional[str] = None

# 初始化服务
file_manager = FileManager()
predict_service = PredictService()

# 导入process路由中的file_registry
from routers.process import file_registry

# 导入upload路由中的upload_file_registry
from routers.upload import file_registry as upload_file_registry


@router.get("/models")
async def list_models(root: str = None):
    """
    列出可选的本机模型。

    扫描模型根目录（默认 backend/predict_api_chronos2/Model，或 ?root= 指定的目录），
    返回其中“含 config.json + 权重文件”的有效模型目录；根目录本身若是模型也会包含在内。
    """
    try:
        if root and root.strip():
            root_path = Path(root.strip()).expanduser().resolve()
        else:
            env_root = os.getenv("CHRONOS2_MODEL_ROOT", str(_default_model_root()))
            root_path = Path(env_root).expanduser().resolve()

        models = []
        if root_path.exists() and root_path.is_dir():
            candidates = []
            if is_valid_model_dir(root_path):
                candidates.append(root_path)
            try:
                for child in sorted(root_path.iterdir()):
                    if child.is_dir() and is_valid_model_dir(child):
                        candidates.append(child)
            except PermissionError:
                pass
            for c in candidates:
                models.append({
                    "name": c.name,
                    "path": str(c).replace("\\", "/"),
                    "size_mb": round(_dir_size_mb(c), 1),
                })

        # 当前默认选用的模型（环境变量或内置 chronos-2）
        default_path = os.getenv("CHRONOS2_MODEL_PATH", str(default_model_dir()))
        try:
            default_resolved = str(Path(default_path).expanduser().resolve()).replace("\\", "/")
        except Exception:
            default_resolved = str(default_path).replace("\\", "/")

        return {
            "root": str(root_path).replace("\\", "/"),
            "default": default_resolved,
            "models": models,
            "total": len(models),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取模型列表失败: {str(e)}")


@router.post("/models/browse")
async def browse_models(req: ModelBrowseRequest):
    """
    浏览本机文件系统，用于在前端选择模型目录。

    - path 为空：Windows 返回盘符列表，其它系统返回根目录内容。
    - path 非空：返回该目录下的子目录列表，并标注每个子目录是否为有效模型目录，
      同时返回当前目录是否为模型目录、其父级路径（便于“返回上一级”）。
    """
    try:
        raw = (req.path or "").strip()

        # 空路径：优先列盘符（Windows）
        if not raw:
            drives = _list_windows_drives()
            if drives:
                return {
                    "current": "",
                    "parent": None,
                    "is_model": False,
                    "dirs": [{"name": d, "path": d, "is_model": False} for d in drives],
                }
            raw = "/"

        current = Path(raw).expanduser().resolve()
        if not current.exists():
            raise HTTPException(status_code=404, detail=f"路径不存在: {current}")

        # 选中的是文件则回退到其所在目录
        if current.is_file():
            current = current.parent

        dirs = []
        try:
            for child in sorted(current.iterdir()):
                if child.is_dir():
                    try:
                        flag = is_valid_model_dir(child)
                    except Exception:
                        flag = False
                    dirs.append({
                        "name": child.name,
                        "path": str(child).replace("\\", "/"),
                        "is_model": flag,
                    })
        except PermissionError:
            raise HTTPException(status_code=403, detail=f"无权限访问目录: {current}")

        parent = None
        if current.parent != current:
            parent = str(current.parent).replace("\\", "/")

        return {
            "current": str(current).replace("\\", "/"),
            "parent": parent,
            "is_model": is_valid_model_dir(current),
            "dirs": dirs,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"浏览目录失败: {str(e)}")


@router.get("/available-files")
async def get_available_files():
    """获取可用于预测的文件列表（已上传、已处理和已整合的文件）"""
    try:
        # 获取已上传文件
        uploaded_files = []
        for file_id, file_info in upload_file_registry.items():
            # 只支持CSV和XLSX格式
            if file_info['original_name'].endswith(('.csv', '.xlsx', '.xls')):
                uploaded_files.append({
                    "file_id": file_info['file_id'],
                    "file_name": file_info['original_name'],
                    "original_name": file_info['original_name'],
                    "file_type": "uploaded",
                    "file_path": file_info['file_path'],
                    "file_size": file_info.get('file_size', 0),
                    "upload_time": file_info.get('upload_time', '')
                })
        
        processed_files = file_manager.list_processed_files()
        merged_files = file_manager.list_merged_files()
        
        return {
            "uploaded_files": uploaded_files,
            "processed_files": [
                {
                    "file_id": f.file_id,
                    "file_name": f.new_name,
                    "original_name": f.original_name,
                    "file_type": "processed"
                }
                for f in processed_files
            ],
            "merged_files": [
                {
                    "file_id": f.file_id,
                    "file_name": f.merged_name,
                    "original_name": f.main_table_name,
                    "file_type": "merged"
                }
                for f in merged_files
            ],
            "total": len(uploaded_files) + len(processed_files) + len(merged_files)
        }
    except Exception as e:
        import traceback
        error_detail = f"获取文件列表失败: {str(e)}\n\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)


@router.post("/{file_type}/{file_id}/headers", response_model=HeaderResponse)
async def get_file_headers(file_type: str, file_id: str):
    """获取文件表头（用于配置预测参数）"""
    try:
        file_path = None
        
        # 确定文件路径
        if file_type == "uploaded":
            # 从上传文件注册表中查找（使用file_id）
            if file_id not in upload_file_registry:
                raise HTTPException(status_code=404, detail="上传文件不存在")
            file_path = upload_file_registry[file_id]['file_path']
        elif file_type == "processed":
            base_dir = file_manager.processed_dir
            file_path = os.path.join(base_dir, file_id)
        elif file_type == "merged":
            base_dir = file_manager.merged_dir
            file_path = os.path.join(base_dir, file_id)
        else:
            raise HTTPException(status_code=400, detail="不支持的文件类型")
        
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 解析表头
        headers = CSVParser.parse_csv_headers(file_path)
        
        # 智能推荐列
        suggested_id_columns = []
        suggested_timestamp_columns = []
        suggested_target_columns = []
        
        for header in headers:
            header_lower = header.lower()
            # 推荐ID列
            if 'id' in header_lower or 'series' in header_lower:
                suggested_id_columns.append(header)
            # 推荐时间列
            if 'date' in header_lower or 'time' in header_lower or 'timestamp' in header_lower:
                suggested_timestamp_columns.append(header)
            # 推荐目标列（数值列）
            if any(keyword in header_lower for keyword in ['value', 'output', 'power', 'load']):
                suggested_target_columns.append(header)
        
        return HeaderResponse(
            file_id=file_id,
            headers=headers,
            suggested_time_columns=suggested_timestamp_columns,
            suggested_hour_columns=suggested_target_columns
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取表头失败: {str(e)}")


@router.post("/execute", response_model=PredictResponse)
async def execute_predict(predict_request: PredictRequest):
    """执行数据预测"""
    try:
        print(f"[数据预测] 开始执行预测")
        print(f"[数据预测] 文件: {predict_request.file_name}")
        print(f"[数据预测] 文件类型: {predict_request.file_type}")
        print(f"[数据预测] 目标字段: {predict_request.target_fields}")
        print(f"[数据预测] 预测长度: {predict_request.prediction_length}")
        
        # 1. 执行预测
        prediction_result = predict_service.execute_prediction(predict_request)
        
        # 2. 保存预测结果（传入预测起始时间和分位数）
        print(f"[数据预测] 开始保存预测结果...")
        print(f"[数据预测] 分位数水平: {predict_request.quantile_levels}")
        output_path = predict_service.save_prediction_result(
            prediction_result=prediction_result,
            source_file_name=predict_request.file_name,
            prediction_start_time=predict_request.prediction_start_time,
            quantile_levels=predict_request.quantile_levels
        )
        
        print(f"[数据预测] 预测完成: {output_path}")
        
        return PredictResponse(
            file_id=os.path.basename(output_path),
            status=FileStatus.COMPLETED,
            message="数据预测完成",
            output_file=output_path
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"预测失败: {str(e)}\n\n详细错误:\n{traceback.format_exc()}"
        print(f"[数据预测] {error_detail}")
        raise HTTPException(status_code=500, detail=error_detail)


@router.post("/chronos2/predict")
async def chronos2_predict(request: ChronosPredictRequest):
    """
    Chronos2 原生预测接口（可直接用 Postman 测试）
    
    直接接收历史数据，不依赖文件上传。
    完全兼容 Chronos2 原生接口规范。
    """
    try:
        print(f"[Chronos2预测] 开始执行预测")
        print(f"[Chronos2预测] 目标字段: {request.target_fields}")
        print(f"[Chronos2预测] 预测长度: {request.prediction_length}")
        print(f"[Chronos2预测] 预测策略: {request.predict_strategy}")
        print(f"[Chronos2预测] 历史数据条数: {len(request.history_data)}")
        
        # 直接调用 Chronos2 预测
        prediction_result = run_chronos_prediction(request)
        
        print(f"[Chronos2预测] 预测完成")
        print(f"[Chronos2预测] 结果分位数: {list(prediction_result.get('prediction_result', {}).keys())}")
        
        return prediction_result
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"预测失败: {str(e)}\n\n详细错误:\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)


@router.get("/list", response_model=PredictFileListResponse)
async def list_predicted_files():
    """获取预测文件列表"""
    try:
        predicted_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'data', 
            'predicted'
        )
        
        if not os.path.exists(predicted_dir):
            return PredictFileListResponse(files=[], total=0)
        
        files = []
        for filename in os.listdir(predicted_dir):
            file_path = os.path.join(predicted_dir, filename)
            if os.path.isfile(file_path) and filename.endswith('_predicted.csv'):
                stat = os.stat(file_path)
                # 从文件名提取源文件名称
                source_file = filename.replace('_predicted.csv', '_new.csv')
                
                # 尝试读取元数据文件
                metadata_file = file_path.replace('_predicted.csv', '_predicted_meta.json')
                predict_time = None
                generate_time = stat.st_mtime  # 文件生成时间（处理时间）
                
                if os.path.exists(metadata_file):
                    try:
                        import json
                        with open(metadata_file, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)
                            predict_time = metadata.get('predict_time')  # 预测起始时间
                    except:
                        pass
                
                files.append({
                    "file_id": filename,
                    "source_file": source_file,
                    "predict_name": filename,
                    "predict_time": predict_time,  # 预测起始时间
                    "generate_time": generate_time,  # 文件生成时间（处理时间）
                    "file_size": stat.st_size,
                    "prediction_length": 0,  # 需要从元数据中获取
                    "target_fields": []  # 需要从元数据中获取
                })
        
        return PredictFileListResponse(
            files=files,
            total=len(files)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取预测文件列表失败: {str(e)}")


@router.get("/download/{file_name}")
async def download_predicted_file(file_name: str):
    """下载预测文件"""
    try:
        predicted_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'data', 
            'predicted'
        )
        
        file_path = os.path.join(predicted_dir, file_name)
        
        if not os.path.exists(file_path):
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


@router.delete("/{file_name}")
async def delete_predicted_file(file_name: str):
    """删除预测文件"""
    try:
        predicted_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'data', 
            'predicted'
        )
        
        file_path = os.path.join(predicted_dir, file_name)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        os.remove(file_path)
        
        return {
            "message": "预测文件删除成功",
            "file_name": file_name
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除文件失败: {str(e)}")
