from fastapi import APIRouter, HTTPException
from services.file_manager import FileManager
from services.csv_parser import CSVParser
from models.schemas import (
    AnalysisFileListResponse,
    AnalysisFileItem,
    AnalysisDataRequest,
    AnalysisDataResponse,
    AnalysisMetricsRequest,
    MetricItem,
    AnalysisMetricsResponse
)
import os
from pydantic import BaseModel, Field
from typing import List, Optional

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# 初始化文件管理器
file_manager = FileManager()

# 导入upload路由中的file_registry
from routers.upload import file_registry as upload_file_registry


@router.get("/available-files", response_model=AnalysisFileListResponse)
async def get_available_files():
    """获取可用于数据分析的文件列表（已上传、已处理、已整合、已预测）"""
    try:
        # 获取已上传文件
        uploaded_files = []
        for file_id, file_info in upload_file_registry.items():
            if file_info['original_name'].endswith(('.csv', '.xlsx', '.xls')):
                uploaded_files.append(AnalysisFileItem(
                    file_id=file_info['file_id'],
                    file_name=file_info['original_name'],
                    original_name=file_info['original_name'],
                    file_type="uploaded",
                    file_size=file_info.get('file_size', 0),
                    upload_time=file_info.get('upload_time', '')
                ))
        
        # 获取已处理文件
        processed_files_list = file_manager.list_processed_files()
        processed_files = [
            AnalysisFileItem(
                file_id=f.file_id,
                file_name=f.new_name,
                original_name=f.original_name,
                file_type="processed",
                file_size=f.file_size
            )
            for f in processed_files_list
        ]
        
        # 获取已整合文件
        merged_files_list = file_manager.list_merged_files()
        merged_files = [
            AnalysisFileItem(
                file_id=f.file_id,
                file_name=f.merged_name,
                original_name=f.main_table_name,
                file_type="merged",
                file_size=f.file_size
            )
            for f in merged_files_list
        ]
        
        # 获取已预测文件
        predicted_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data',
            'predicted'
        )
        predicted_files = []
        if os.path.exists(predicted_dir):
            for filename in os.listdir(predicted_dir):
                file_path = os.path.join(predicted_dir, filename)
                if os.path.isfile(file_path) and filename.endswith('_predicted.csv'):
                    stat = os.stat(file_path)
                    predicted_files.append(AnalysisFileItem(
                        file_id=filename,
                        file_name=filename,
                        original_name=filename.replace('_predicted.csv', '_new.csv'),
                        file_type="predicted",
                        file_size=stat.st_size
                    ))
        
        total = len(uploaded_files) + len(processed_files) + len(merged_files) + len(predicted_files)
        
        return AnalysisFileListResponse(
            uploaded_files=uploaded_files,
            processed_files=processed_files,
            merged_files=merged_files,
            predicted_files=predicted_files,
            total=total
        )
    except Exception as e:
        import traceback
        error_detail = f"获取文件列表失败: {str(e)}\n\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)


def _resolve_file_path(file_type: str, file_id: str, file_name: str):
    if file_type == "uploaded":
        if file_id not in upload_file_registry:
            raise HTTPException(status_code=404, detail="上传文件不存在")
        return upload_file_registry[file_id]['file_path']
    elif file_type == "processed":
        return os.path.join(file_manager.processed_dir, file_name)
    elif file_type == "merged":
        return os.path.join(file_manager.merged_dir, file_name)
    elif file_type == "predicted":
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'data', 'predicted', file_name
        )
    else:
        raise HTTPException(status_code=400, detail="不支持的文件类型")


def _read_csv_auto(file_path: str):
    import pandas as pd
    df = None
    for encoding in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']:
        try:
            df = pd.read_csv(file_path, encoding=encoding)
            break
        except (UnicodeDecodeError, Exception):
            continue
    if df is None:
        raise HTTPException(status_code=500, detail="无法读取CSV文件")
    return df


def _normalize_time_str(time_str):
    if not time_str:
        return ''
    s = str(time_str).replace('/', '-')
    if ':' not in s:
        s += ' 00:00:00'
    parts = s.split(' ')
    if len(parts) == 2:
        time_parts = parts[1].split(':')
        if len(time_parts) == 3:
            time_parts[0] = time_parts[0].zfill(2)
            time_parts[1] = time_parts[1].zfill(2)
            time_parts[2] = time_parts[2].zfill(2)
            parts[1] = ':'.join(time_parts)
            s = ' '.join(parts)
    return s


def _load_and_prepare_df(request_data, is_real=True):
    import pandas as pd
    file_path = _resolve_file_path(
        request_data.real_file_type if is_real else request_data.predict_file_type,
        request_data.real_file_id if is_real else request_data.predict_file_id,
        request_data.real_file_name if is_real else request_data.predict_file_name,
    )
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="文件不存在")

    df = _read_csv_auto(file_path)

    time_col = request_data.real_time_column if is_real else request_data.predict_time_column
    time_col_2 = request_data.real_time_column_2 if is_real else None
    value_cols = request_data.real_value_columns if is_real else request_data.predict_value_columns
    time_range = request_data.real_time_range if is_real else request_data.predict_time_range

    if time_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"时间列 '{time_col}' 不存在")

    datetime_column = time_col
    if is_real and time_col_2 and time_col_2 in df.columns:
        date_str = df[time_col].astype(str)
        t_str = df[time_col_2].astype(str)
        combined = date_str + ' ' + t_str
        combined = combined.str.replace(' 24:00:00', ' 00:00:00')
        mask_24h = (date_str.str.strip() + ' ' + t_str.str.strip()).str.contains(' 24:', regex=False)
        try:
            parsed = pd.to_datetime(combined, format='mixed', dayfirst=False)
        except TypeError:
            parsed = pd.to_datetime(combined, dayfirst=False)
        if mask_24h.any():
            parsed.loc[mask_24h] = parsed.loc[mask_24h] + pd.Timedelta(days=1)
        df['datetime'] = parsed.dt.strftime('%Y-%m-%d %H:%M:%S')
        datetime_column = 'datetime'

    for col in value_cols:
        if col not in df.columns:
            raise HTTPException(status_code=400, detail=f"数值列 '{col}' 不存在")

    selected_columns = [datetime_column] + value_cols
    result_df = df[selected_columns].copy()

    result_df['_time_normalized'] = result_df[datetime_column].apply(_normalize_time_str)

    if time_range and len(time_range) == 2:
        start_time, end_time = time_range
        mask = (result_df['_time_normalized'] >= start_time) & (result_df['_time_normalized'] <= end_time)
        result_df = result_df[mask]

    for col in value_cols:
        result_df[col] = pd.to_numeric(result_df[col], errors='coerce')

    return result_df, value_cols, '_time_normalized'


@router.post("/calculate-metrics", response_model=AnalysisMetricsResponse)
async def calculate_metrics(request: AnalysisMetricsRequest):
    import pandas as pd
    import numpy as np
    try:
        real_df, real_value_cols, real_time_col = _load_and_prepare_df(request, is_real=True)
        predict_df, predict_value_cols, predict_time_col = _load_and_prepare_df(request, is_real=False)

        real_time_map = {}
        for _, row in real_df.iterrows():
            t = row[real_time_col]
            if t:
                vals = {}
                for col in real_value_cols:
                    v = row[col]
                    vals[col] = v if pd.notna(v) else None
                real_time_map[t] = vals

        predict_time_map = {}
        for _, row in predict_df.iterrows():
            t = row[predict_time_col]
            if t:
                vals = {}
                for col in predict_value_cols:
                    v = row[col]
                    vals[col] = v if pd.notna(v) else None
                predict_time_map[t] = vals

        common_times = set(real_time_map.keys()) & set(predict_time_map.keys())

        metrics = []
        for real_col in real_value_cols:
            for pred_col in predict_value_cols:
                y_true = []
                y_pred = []
                for t in common_times:
                    rv = real_time_map[t].get(real_col)
                    pv = predict_time_map[t].get(pred_col)
                    if rv is not None and pv is not None:
                        y_true.append(float(rv))
                        y_pred.append(float(pv))

                if len(y_true) < 2:
                    metrics.append(MetricItem(
                        real_column=real_col,
                        predict_column=pred_col,
                        r2=None,
                        mape=None,
                        sample_count=len(y_true)
                    ))
                    continue

                y_true_arr = np.array(y_true)
                y_pred_arr = np.array(y_pred)

                ss_res = np.sum((y_true_arr - y_pred_arr) ** 2)
                ss_tot = np.sum((y_true_arr - np.mean(y_true_arr)) ** 2)
                r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else None

                non_zero_mask = y_true_arr != 0
                if non_zero_mask.any():
                    mape = np.mean(np.abs((y_true_arr[non_zero_mask] - y_pred_arr[non_zero_mask]) / y_true_arr[non_zero_mask])) * 100
                else:
                    mape = None

                metrics.append(MetricItem(
                    real_column=real_col,
                    predict_column=pred_col,
                    r2=round(r2, 4) if r2 is not None else None,
                    mape=round(mape, 2) if mape is not None else None,
                    sample_count=len(y_true)
                ))

        return AnalysisMetricsResponse(metrics=metrics)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"计算指标失败: {str(e)}\n\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)


@router.post("/{file_type}/{file_id}/headers")
async def get_file_headers(file_type: str, file_id: str):
    """获取文件表头（用于配置分析参数）"""
    try:
        file_path = None
        
        # 确定文件路径
        if file_type == "uploaded":
            if file_id not in upload_file_registry:
                raise HTTPException(status_code=404, detail="上传文件不存在")
            file_path = upload_file_registry[file_id]['file_path']
        elif file_type == "processed":
            base_dir = file_manager.processed_dir
            file_path = os.path.join(base_dir, file_id)
        elif file_type == "merged":
            base_dir = file_manager.merged_dir
            file_path = os.path.join(base_dir, file_id)
        elif file_type == "predicted":
            base_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data',
                'predicted'
            )
            file_path = os.path.join(base_dir, file_id)
        else:
            raise HTTPException(status_code=400, detail="不支持的文件类型")
        
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 解析表头
        headers = CSVParser.parse_csv_headers(file_path)
        
        # 智能推荐列
        suggested_time_columns = []
        suggested_value_columns = []
        
        # 读取少量数据判断列类型
        import pandas as pd
        try:
            sample_df = None
            for enc in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']:
                try:
                    sample_df = pd.read_csv(file_path, encoding=enc, nrows=5)
                    break
                except:
                    continue
        except:
            sample_df = None
        
        for header in headers:
            header_lower = header.lower()
            is_time = any(keyword in header_lower for keyword in ['date', 'time', 'timestamp'])
            # 推荐时间列
            if is_time:
                suggested_time_columns.append(header)
            # 推荐数值列（排除ID列、时间列、和非数值列）
            is_id_or_series = any(keyword in header_lower for keyword in ['id', 'series'])
            is_numeric = True
            if sample_df is not None and header in sample_df.columns:
                is_numeric = pd.api.types.is_numeric_dtype(sample_df[header])
            if not is_id_or_series and not is_time and is_numeric:
                suggested_value_columns.append(header)
        
        return {
            "file_id": file_id,
            "headers": headers,
            "suggested_time_columns": suggested_time_columns,
            "suggested_value_columns": suggested_value_columns
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取表头失败: {str(e)}")


@router.post("/get-data", response_model=AnalysisDataResponse)
async def get_analysis_data(request: AnalysisDataRequest):
    """获取文件数据用于分析"""
    try:
        file_path = None
        
        # 确定文件路径
        if request.file_type == "uploaded":
            if request.file_id not in upload_file_registry:
                raise HTTPException(status_code=404, detail="上传文件不存在")
            file_path = upload_file_registry[request.file_id]['file_path']
        elif request.file_type == "processed":
            base_dir = file_manager.processed_dir
            file_path = os.path.join(base_dir, request.file_name)
        elif request.file_type == "merged":
            base_dir = file_manager.merged_dir
            file_path = os.path.join(base_dir, request.file_name)
        elif request.file_type == "predicted":
            base_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                'data',
                'predicted'
            )
            file_path = os.path.join(base_dir, request.file_name)
        else:
            raise HTTPException(status_code=400, detail="不支持的文件类型")
        
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 读取CSV数据
        import pandas as pd
        
        # 尝试多种编码
        df = None
        for encoding in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']:
            try:
                df = pd.read_csv(file_path, encoding=encoding)
                print(f"[数据分析] 使用{encoding}编码成功读取文件")
                break
            except (UnicodeDecodeError, Exception) as e:
                continue
        
        if df is None:
            raise HTTPException(status_code=500, detail="无法读取CSV文件")
        
        # 验证列是否存在
        if request.time_column not in df.columns:
            raise HTTPException(status_code=400, detail=f"时间列 '{request.time_column}' 不存在")
        
        # 如果有第二时间列，验证并合并
        datetime_column = request.time_column
        if request.time_column_2 and request.time_column_2 in df.columns:
            print(f"[数据分析] 检测到双时间列，正在合并: {request.time_column} + {request.time_column_2}")
            # 合并日期和时间列
            date_str = df[request.time_column].astype(str)
            time_str = df[request.time_column_2].astype(str)
            combined = date_str + ' ' + time_str
            
            # 尝试标准化为 YYYY-MM-DD HH:mm:ss 格式
            try:
                # 先处理 24:00:00 这种非标准时间（替换为 23:59:59 以保持同日）
                # 注意：24:00:00 在 ISO 标准中表示当日最后一刻，等价于次日 00:00:00
                combined = combined.str.replace(' 24:00:00', ' 00:00:00')
                
                # 对于包含 24:xx:00 的行，需要加一天
                mask_24h = date_str.str.strip() + ' ' + time_str.str.strip()
                is_24h = mask_24h.str.contains(' 24:', regex=False)
                
                # 先尝试解析各种日期格式
                try:
                    parsed = pd.to_datetime(combined, format='mixed', dayfirst=False)
                except TypeError:
                    # 旧版pandas不支持format='mixed'
                    parsed = pd.to_datetime(combined, dayfirst=False)
                
                # 对原本是 24:00:00 的行加一天
                if is_24h.any():
                    parsed.loc[is_24h] = parsed.loc[is_24h] + pd.Timedelta(days=1)
                
                combined = parsed.dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                print(f"[数据分析] 时间标准化失败，使用原始格式: {e}")
            
            df['datetime'] = combined
            datetime_column = 'datetime'
            print(f"[数据分析] 合并后的时间示例: {df['datetime'].iloc[0]}")
        
        for col in request.value_columns:
            if col not in df.columns:
                raise HTTPException(status_code=400, detail=f"数值列 '{col}' 不存在")
        
        # 提取需要的列
        selected_columns = [datetime_column] + request.value_columns
        result_df = df[selected_columns].copy()
        
        # 转换为字典列表
        data = result_df.to_dict(orient="records")
        
        return AnalysisDataResponse(
            headers=list(result_df.columns),
            data=data,
            total_rows=len(data)
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = f"获取数据失败: {str(e)}\n\n{traceback.format_exc()}"
        print(error_detail)
        raise HTTPException(status_code=500, detail=error_detail)
