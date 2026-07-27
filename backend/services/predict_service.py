"""
Chronos2 数据预测服务
集成 Chronos2 模型进行时间序列预测

延迟导入策略：chronos_predict_api 移到方法内部按需加载，避免启动时加载 900MB 模型依赖
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import pandas as pd

# 添加 predict_api_chronos2 到路径（仅添加路径，不导入模块）
project_root = Path(__file__).parent.parent
chronos_api_path = project_root / "predict_api_chronos2" / "Api"
if str(chronos_api_path) not in sys.path:
    sys.path.insert(0, str(chronos_api_path))

# === 延迟导入：chronos_predict_api 在方法内部按需加载 ===

from models.schemas import PredictRequest, FileStatus
from fastapi import HTTPException


class PredictService:
    """数据预测服务"""
    
    def __init__(self):
        self.pipeline = None
    
    def _load_pipeline(self):
        """加载 Chronos2 模型（延迟导入 chronos_predict_api）"""
        # 延迟导入
        from chronos_predict_api import get_pipeline

        if self.pipeline is None:
            try:
                self.pipeline = get_pipeline()
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"模型加载失败: {str(e)}"
                )
        return self.pipeline
    
    def _load_csv_data(self, file_path: str) -> List[Dict[str, Any]]:
        """加载CSV文件数据"""
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"文件不存在: {file_path}")
        
        try:
            # 尝试多种编码方式读取CSV文件
            encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'utf-8-sig', 'latin1']
            df = None
            last_error = None
            
            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    print(f"[预测服务] 使用 {encoding} 编码成功读取文件")
                    break
                except UnicodeDecodeError as e:
                    last_error = e
                    continue
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"CSV文件读取失败: {str(e)}")
            
            if df is None:
                raise HTTPException(
                    status_code=500, 
                    detail=f"CSV文件读取失败：无法解码文件。尝试了编码: {', '.join(encodings)}。最后错误: {str(last_error)}"
                )
            
            return df.to_dict(orient="records")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"CSV文件读取失败: {str(e)}")
    
    def _merge_timestamp_columns(self, data: List[Dict[str, Any]], timestamp_columns: List[str], id_column: str, value_fields: List[str]) -> List[Dict[str, Any]]:
        """
        合并多个时间列，并过滤掉不需要的字段
        
        Args:
            data: 原始数据
            timestamp_columns: 时间列名列表
            id_column: 时序ID列名
            value_fields: 需要保留的数值字段列表（可以是target_fields或related_target_fields）
            
        Returns:
            合并后的数据，仅包含 id_column、timestamp、value_fields
        """
        if len(timestamp_columns) == 1:
            final_timestamp_column = timestamp_columns[0]
        else:
            final_timestamp_column = 'timestamp'
        
        merged_data = []
        for row in data:
            new_row = {}
            
            if id_column in row:
                new_row[id_column] = row[id_column]
            
            if len(timestamp_columns) == 1:
                new_row[final_timestamp_column] = row.get(timestamp_columns[0], "")
            else:
                try:
                    from datetime import timedelta
                    date_str = str(row.get(timestamp_columns[0], "")).strip()
                    time_str = str(row.get(timestamp_columns[1], "")).strip()
                    
                    if date_str and time_str:
                        if time_str == '24:00:00' or time_str.startswith('24:'):
                            date_part = pd.to_datetime(date_str) + timedelta(days=1)
                            time_part = pd.Timestamp('00:00:00').time()
                        else:
                            date_part = pd.to_datetime(date_str)
                            time_part = pd.to_datetime(time_str).time()
                        
                        combined_dt = pd.Timestamp.combine(date_part.date(), time_part)
                        new_row['timestamp'] = combined_dt.isoformat()
                    else:
                        new_row['timestamp'] = f"{date_str}T{time_str}"
                except Exception as e:
                    print(f"[预测服务] 时间解析失败: {row.get(timestamp_columns[0], '')} {row.get(timestamp_columns[1], '')}, 错误: {e}")
                    new_row['timestamp'] = f"{date_str}T{time_str}"
            
            for field in value_fields:
                if field in row:
                    new_row[field] = row[field]
            
            merged_data.append(new_row)
        
        return merged_data
    
    def _infer_time_interval(self, data: List[Dict[str, Any]], timestamp_column: str, id_column: str) -> Optional[pd.Timedelta]:
        """
        从数据中推断时间间隔
        
        Args:
            data: 已处理的数据列表
            timestamp_column: 时间列名
            id_column: 时序ID列名
            
        Returns:
            推断的时间间隔，如果无法推断则返回None
        """
        try:
            df = pd.DataFrame(data)
            if df.empty or timestamp_column not in df.columns:
                return None
            df[timestamp_column] = pd.to_datetime(df[timestamp_column], errors="coerce")
            if id_column in df.columns:
                first_id = df[id_column].iloc[0]
                df = df[df[id_column] == first_id]
            df = df.sort_values(timestamp_column).reset_index(drop=True)
            diffs = df[timestamp_column].diff().dropna()
            positive_diffs = diffs[diffs > pd.Timedelta(0)]
            if positive_diffs.empty:
                return None
            mode_diff = positive_diffs.mode().iloc[0]
            print(f"[预测服务] 推断时间间隔: {mode_diff}")
            return mode_diff
        except Exception as e:
            print(f"[预测服务] 推断时间间隔失败: {e}")
            return None

    def _filter_data_by_time(self, data: List[Dict[str, Any]], timestamp_column: str, cutoff_time: str, include_cutoff: bool = False) -> List[Dict[str, Any]]:
        """
        按时间过滤数据行
        
        Args:
            data: 已处理的数据列表（每行包含timestamp_column字段）
            timestamp_column: 时间列名
            cutoff_time: 截止时间字符串
            include_cutoff: 是否包含等于截止时间的行
            
        Returns:
            过滤后的数据
        """
        try:
            cutoff_dt = pd.to_datetime(cutoff_time)
            filtered = []
            for row in data:
                try:
                    row_dt = pd.to_datetime(row.get(timestamp_column, ""))
                    if include_cutoff:
                        if row_dt > cutoff_dt:
                            continue
                    else:
                        if row_dt >= cutoff_dt:
                            continue
                    filtered.append(row)
                except Exception:
                    filtered.append(row)
            print(f"[预测服务] 时间过滤: 截止时间={cutoff_time}, 包含截止={include_cutoff}, 过滤前={len(data)}条, 过滤后={len(filtered)}条")
            return filtered
        except Exception as e:
            print(f"[预测服务] 时间过滤失败: {e}, 返回原始数据")
            return data
    
    def execute_prediction(self, request: PredictRequest) -> Dict[str, Any]:
        """
        执行预测任务（延迟导入 chronos_predict_api）
        
        Args:
            request: 预测请求参数
            
        Returns:
            预测结果字典
        """
        # 延迟导入 chronos_predict_api
        from chronos_predict_api import ChronosPredictRequest, run_chronos_prediction

        try:
            # 1. 确定文件路径
            if request.file_type == "uploaded":
                # 上传文件，使用file_id从upload_file_registry查找
                from routers.upload import file_registry as upload_file_registry
                if request.file_id not in upload_file_registry:
                    raise HTTPException(status_code=404, detail="上传文件不存在")
                file_path = upload_file_registry[request.file_id]['file_path']
            elif request.file_type == "processed":
                base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'processed')
                file_path = os.path.join(base_dir, request.file_name)
            elif request.file_type == "merged":
                base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'merged')
                file_path = os.path.join(base_dir, request.file_name)
            else:
                raise HTTPException(status_code=400, detail="不支持的文件类型")
            
            # 2. 加载历史数据
            history_data = self._load_csv_data(file_path)
            
            if not history_data:
                raise HTTPException(status_code=400, detail="历史数据为空")
            
            # 3. 合并时间列并过滤字段
            timestamp_column = request.timestamp_columns[0] if len(request.timestamp_columns) == 1 else 'timestamp'
            
            # 4. 构建关联数据（related_data）
            related_data = None
            if request.related_target_fields:
                related_data = self._merge_timestamp_columns(
                    history_data,
                    request.timestamp_columns,
                    request.id_column,
                    request.related_target_fields
                )
                if request.prediction_start_time:
                    time_interval = self._infer_time_interval(related_data, timestamp_column, request.id_column)
                    if time_interval:
                        start_dt = pd.to_datetime(request.prediction_start_time)
                        end_dt = start_dt + (request.prediction_length - 1) * time_interval
                        end_time_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")
                        print(f"[预测服务] 关联数据截止时间: {end_time_str} (预测起始={request.prediction_start_time}, 间隔={time_interval}, 长度={request.prediction_length})")
                        related_data = self._filter_data_by_time(
                            related_data,
                            timestamp_column,
                            end_time_str,
                            include_cutoff=True
                        )
                    else:
                        print(f"[预测服务] 无法推断时间间隔，关联数据不进行时间过滤")
                print(f"[预测服务] 构建关联数据: 关联字段={request.related_target_fields}, 数据条数={len(related_data) if related_data else 0}")
            elif request.related_data_file and os.path.exists(request.related_data_file):
                related_data = self._load_csv_data(request.related_data_file)
            
            # 5. 构建 history_data（如果有关联字段且指定了预测起始时间，需过滤history_data到预测起始时间之前）
            processed_history_data = self._merge_timestamp_columns(
                history_data, 
                request.timestamp_columns,
                request.id_column,
                request.target_fields
            )
            if request.related_target_fields and request.prediction_start_time:
                processed_history_data = self._filter_data_by_time(
                    processed_history_data,
                    timestamp_column,
                    request.prediction_start_time,
                    include_cutoff=False
                )
            
            # 6. 构建 Chronos 预测请求
            chronos_request = ChronosPredictRequest(
                history_data=processed_history_data,
                related_data=related_data,
                target_fields=request.target_fields,
                prediction_length=request.prediction_length,
                id_column=request.id_column,
                timestamp_column=timestamp_column,
                quantile_levels=request.quantile_levels,
                predict_strategy=request.predict_strategy,
                model_path=request.model_path,  # 透传用户选择的模型路径
            )
            
            # 7. 执行预测
            print(f"[预测服务] 开始执行预测: {request.file_name}")
            print(f"[预测服务] 目标字段: {request.target_fields}")
            print(f"[预测服务] 关联字段: {request.related_target_fields}")
            print(f"[预测服务] 历史数据条数: {len(processed_history_data)}")
            print(f"[预测服务] 关联数据条数: {len(related_data) if related_data else 0}")
            print(f"[预测服务] 预测长度: {request.prediction_length}")
            print(f"[预测服务] 预测策略: {request.predict_strategy}")
            if request.prediction_start_time:
                print(f"[预测服务] 预测起始时间: {request.prediction_start_time}")
            
            prediction_result = run_chronos_prediction(chronos_request)
            
            # 8. 如果指定了预测起始时间，重新生成预测时间索引
            if request.prediction_start_time:
                print(f"[预测服务] 开始调整预测时间索引...")
                prediction_result = self._adjust_prediction_timestamps(
                    prediction_result,
                    request.prediction_start_time,
                    request.prediction_length,
                    timestamp_column,
                    processed_history_data
                )
                print(f"[预测服务] 预测时间索引调整完成")
            
            print(f"[预测服务] 预测完成")
            
            # 9. 返回结果
            return prediction_result
            
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            error_detail = f"预测失败: {str(e)}\n\n详细错误:\n{traceback.format_exc()}"
            print(error_detail)
            raise HTTPException(status_code=500, detail=error_detail)
    
    def save_prediction_result(
        self, 
        prediction_result: Dict[str, Any], 
        source_file_name: str,
        prediction_start_time: str = None,
        quantile_levels: List[float] = None,
        output_dir: str = None
    ) -> str:
        """
        保存预测结果为CSV文件，并保存元数据
        
        Args:
            prediction_result: 预测结果字典
            source_file_name: 源文件名
            prediction_start_time: 预测起始时间
            quantile_levels: 分位数水平列表
            output_dir: 输出目录（默认为 data/predicted）
            
        Returns:
            输出文件路径
        """
        if output_dir is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), 
                'data', 
                'predicted'
            )
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 生成输出文件名
        name_without_ext = os.path.splitext(source_file_name)[0]
        # 移除 _new 或 _merge 后缀
        if name_without_ext.endswith('_new'):
            name_without_ext = name_without_ext[:-4]
        elif name_without_ext.endswith('_merge'):
            name_without_ext = name_without_ext[:-6]
        
        # 加时间戳，避免同名预测结果相互覆盖（保留历史文件）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"{name_without_ext}_{timestamp}_predicted.csv"
        output_path = os.path.join(output_dir, output_filename)
        
        try:
            # 从预测结果中提取数据并保存为CSV
            # 预测结果格式: {"prediction_result": {"0.1_wide": [...], "0.5_wide": [...], "0.9_wide": [...]}}
            # 或者对于 0.1/0.5/0.9 有特殊别名: {"short_wide": [...], "median_wide": [...], "long_wide": [...]}
            prediction_data = prediction_result.get("prediction_result", {})
            
            print(f"[预测服务] 预测结果中的分位数键: {list(prediction_data.keys())}")
            
            # 获取配置的分位数水平
            actual_quantile_levels = quantile_levels or [0.1, 0.5, 0.9]
            print(f"[预测服务] 配置的分位数水平: {actual_quantile_levels}")
            
            # 获取所有分位数的数据
            quantile_data_map = {}
            for q in actual_quantile_levels:
                # 修复浮点数精度问题：0.15 -> "0.15", 0.55 -> "0.55"
                q_key = f"{q:.2f}".rstrip('0').rstrip('.')  # 0.15 -> "0.15", 0.50 -> "0.5"
                
                # 尝试多种可能的键名
                # 0.1/0.5/0.9 有特殊别名，其他分位数使用 {q}_wide 或 q{q}_wide 格式
                data = None
                if q == 0.1:
                    data = prediction_data.get("short_wide")
                elif q == 0.5:
                    data = prediction_data.get("median_wide")
                elif q == 0.9:
                    data = prediction_data.get("long_wide")
                
                # 如果没有特殊别名，尝试多种通用格式
                if not data:
                    # 尝试格式1: 0.18_wide
                    data = prediction_data.get(f"{q_key}_wide")
                    # 尝试格式2: q0.18_wide（Chronos2 的另一种格式）
                    if not data:
                        data = prediction_data.get(f"q{q_key}_wide")
                    # 如果都没找到，返回空列表
                    if not data:
                        data = []
                
                print(f"[预测服务] 分位数 {q} (键: {q_key}_wide 或 q{q_key}_wide): 获取到 {len(data) if data else 0} 条数据")
                quantile_data_map[q] = data
            
            # 使用第一个分位数的数据作为基准
            first_quantile = actual_quantile_levels[0]
            base_data = quantile_data_map.get(first_quantile, [])
            
            if not base_data:
                raise HTTPException(status_code=500, detail="预测结果为空")
            
            # 打印保存前的前3条记录的时间戳
            print(f"[预测服务] 保存CSV前的数据（前3条）：")
            for idx in range(min(3, len(base_data))):
                record = base_data[idx]
                # 尝试获取时间列
                time_val = record.get('timestamp') or record.get('data_date') or record.get('时间') or '未知'
                print(f"[预测服务]   [{idx}] 时间: {time_val}")
            
            # 合并所有分位数的数据到同一张表
            merged_data = []
            
            # 获取 ID 列和时间列的名称
            id_column_name = None
            timestamp_column_name = None
            
            if base_data and len(base_data) > 0:
                # 从第一条记录中识别 ID 列和时间列
                first_record = base_data[0]
                # 常见的 ID 列名
                for col_name in ['series_id', 'city', '城市']:
                    if col_name in first_record:
                        id_column_name = col_name
                        break
                # 常见的时间列名
                for col_name in ['timestamp', 'data_date', '时间']:
                    if col_name in first_record:
                        timestamp_column_name = col_name
                        break
            
            # 遍历基准数据，合并所有分位数
            for i, base_record in enumerate(base_data):
                merged_record = {}
                
                # 1. 添加 ID 列（只保留一份，不分位数）
                if id_column_name and id_column_name in base_record:
                    merged_record[id_column_name] = base_record[id_column_name]
                
                # 2. 添加时间列（只保留一份，不分位数）
                if timestamp_column_name and timestamp_column_name in base_record:
                    merged_record[timestamp_column_name] = base_record[timestamp_column_name]
                
                # 3. 添加所有目标字段的各个分位数
                # 遍历基准数据中的所有列，排除 ID 列和时间列
                for key, value in base_record.items():
                    # 跳过 ID 列和时间列
                    if key == id_column_name or key == timestamp_column_name:
                        continue
                    
                    # 这是目标字段，为每个配置的分位数生成一列
                    for q in actual_quantile_levels:
                        q_data = quantile_data_map.get(q, [])
                        q_value = q_data[i].get(key) if i < len(q_data) else None
                        # 列名格式: 字段名_分位数（如 光电出力_0.1、光电出力_0.5）
                        # 将分位数转换为字符串，保留两位小数
                        q_str = f"{q:.2f}".rstrip('0').rstrip('.')  # 0.10 -> 0.1, 0.50 -> 0.5
                        merged_record[f"{key}_{q_str}"] = q_value
                
                merged_data.append(merged_record)
            
            # 转换为DataFrame并保存
            df = pd.DataFrame(merged_data)
            df.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            # 保存元数据文件
            metadata_path = output_path.replace('_predicted.csv', '_predicted_meta.json')
            metadata = {
                'source_file': source_file_name,
                'predict_time': prediction_start_time,  # 预测起始时间
                'generate_time': datetime.now().isoformat(),  # 文件生成时间
                'quantile_levels': quantile_levels or [0.1, 0.5, 0.9],
                'prediction_length': len(merged_data),
                'columns': list(df.columns)
            }
            
            import json
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
            
            print(f"[预测服务] 预测结果已保存: {output_path}")
            print(f"[预测服务] 元数据已保存: {metadata_path}")
            return output_path
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"保存预测结果失败: {str(e)}")
    
    def _adjust_prediction_timestamps(
        self,
        prediction_result: Dict[str, Any],
        prediction_start_time: str,
        prediction_length: int,
        timestamp_column: str,
        history_data: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        根据用户指定的预测起始时间，重新生成预测结果的时间索引
        
        Args:
            prediction_result: 原始预测结果
            prediction_start_time: 用户指定的预测起始时间（YYYY-MM-DD HH:mm:ss）
            prediction_length: 预测长度
            timestamp_column: 时间列名
            history_data: 历史数据（用于推断时间间隔）
            
        Returns:
            调整后的预测结果
        """
        try:
            import pandas as pd
            from datetime import timedelta
            
            print(f"[预测服务] 开始调整预测时间索引")
            print(f"[预测服务] 预测起始时间: {prediction_start_time}")
            
            # 解析用户指定的起始时间
            try:
                start_dt = pd.to_datetime(prediction_start_time)
            except Exception as e:
                print(f"[预测服务] 时间解析失败: {prediction_start_time}, 错误: {e}")
                # 如果解析失败，返回原始结果
                return prediction_result
            
            # 从历史数据中推断时间间隔
            time_interval = timedelta(minutes=15)  # 默认 15 分钟
            if history_data and len(history_data) > 1:
                try:
                    # 提取最后几条记录的时间
                    last_times = []
                    for record in history_data[-10:]:  # 取最后10条
                        if timestamp_column in record:
                            time_val = pd.to_datetime(record[timestamp_column])
                            last_times.append(time_val)
                    
                    if len(last_times) > 1:
                        # 计算平均时间间隔
                        time_diffs = []
                        for i in range(1, len(last_times)):
                            diff = (last_times[i] - last_times[i-1]).total_seconds()
                            if diff > 0:  # 忽略负值
                                time_diffs.append(diff)
                        
                        if time_diffs:
                            avg_diff = sum(time_diffs) / len(time_diffs)
                            time_interval = timedelta(seconds=avg_diff)
                            print(f"[预测服务] 推断时间间隔: {time_interval}")
                except Exception as e:
                    print(f"[预测服务] 推断时间间隔失败: {e}，使用默认 15 分钟")
            
            # 获取预测结果中的数据
            prediction_data = prediction_result.get("prediction_result", {})
            
            print(f"[预测服务] 预测结果中的分位数键: {list(prediction_data.keys())}")
            
            # 处理所有分位数的数据（short_wide, median_wide, long_wide）
            for key in ["short_wide", "median_wide", "long_wide"]:
                if key not in prediction_data:
                    print(f"[预测服务] 分位数 {key} 不存在，跳过")
                    continue
                
                data_list = prediction_data[key]
                if not data_list:
                    print(f"[预测服务] 分位数 {key} 数据为空，跳过")
                    continue
                
                print(f"[预测服务] 调整分位数 {key} 的时间戳，共 {len(data_list)} 条记录")
                
                # 打印调整前的前3条记录的时间
                for idx in range(min(3, len(data_list))):
                    record = data_list[idx]
                    if timestamp_column in record:
                        print(f"[预测服务]   调整前[{idx}]: {record[timestamp_column]}")
                
                # 为每条记录重新生成时间
                for i, record in enumerate(data_list):
                    if timestamp_column in record:
                        # 计算新的时间：起始时间 + i * 时间间隔
                        new_time = start_dt + (i * time_interval)
                        # 格式化为 YYYY-MM-DD HH:MM:SS 格式
                        record[timestamp_column] = new_time.strftime("%Y-%m-%d %H:%M:%S")
                
                # 打印调整后的前3条记录的时间
                for idx in range(min(3, len(data_list))):
                    record = data_list[idx]
                    if timestamp_column in record:
                        print(f"[预测服务]   调整后[{idx}]: {record[timestamp_column]}")
            
            print(f"[预测服务] 预测时间索引调整完成")
            return prediction_result
            
        except Exception as e:
            print(f"[预测服务] 调整预测时间失败: {e}")
            # 如果调整失败，返回原始结果
            return prediction_result