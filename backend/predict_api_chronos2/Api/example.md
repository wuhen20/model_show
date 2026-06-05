# Chronos2 通用时序预测接口 Postman 调用示例

## 1. 入参规则（已更新）

当前接口规则如下：

1. `history_data`：
   - 必填
   - **只允许包含**：`id_column`、`timestamp_column`、`target_fields` 对应字段
   - **不允许附加变量**（比如温度、天气等）

2. `related_data`：
   - 可为空（`null` 或 `[]`）
   - 用于承载附加变量（温度、天气等）
   - 若不为空，会按 `series_id + data_date`（即 `id_column + timestamp_column`）与 `history_data` 关联，构成 `future_df`

3. `target_fields`：
   - 必填
   - 需要预测的字段列表，如 `t0000,t0015,...`

4. `prediction_length`：
   - 必填且 > 0
   - 预测长度（24/96 等）

5. `predict_strategy`：
   - 可选，默认值为 `line`
   - **`line`**：整行预测，将所有 `target_fields` 一起预测（利用字段间的相关性）
   - **`col`**：逐列预测，对每个 `target_field` 单独预测，最后合并结果（适合字段间独立性较强的场景）

---

## 2. 是否可以直接在 Postman 调用？

可以，前提是服务已启动。

- 接口：`POST /api/chronos2/predict`
- 本地地址示例：`http://127.0.0.1:8000/api/chronos2/predict`

---

## 3. 启动方式

建议在项目根目录执行：

```bash
python -m uvicorn Chronos_Forecasting.Api.chronos_predict_api:app --host 0.0.0.0 --port 8000 --reload
```

如果你在 `Chronos_Forecasting/Api` 目录下执行：

```bash
python -m uvicorn chronos_predict_api:app --host 0.0.0.0 --port 8000 --reload
```

---

## 4. Postman 配置

- Method: `POST`
- URL: `http://127.0.0.1:8000/api/chronos2/predict`
- Headers:
  - `Content-Type: application/json`
- Body:
  - `raw`
  - `JSON`

---

## 5. 请求样例（含 related_data，整行预测）

> 注意：`history_data` 里不再放 `temp/weather` 等附加变量。
> 默认使用 `predict_strategy: "line"`（整行预测）

```json
{
  "history_data": [
    {
      "series_id": "cust_001",
      "data_date": "2025-04-01",
      "t0000": 120.5,
      "t0015": 118.2,
      "t0030": 116.9
    },
    {
      "series_id": "cust_001",
      "data_date": "2025-04-02",
      "t0000": 122.1,
      "t0015": 119.8,
      "t0030": 117.4
    },
    {
      "series_id": "cust_001",
      "data_date": "2025-04-03",
      "t0000": 121.4,
      "t0015": 120.2,
      "t0030": 118.7
    }
  ],
  "related_data": [
    {
      "series_id": "cust_001",
      "data_date": "2025-04-01",
      "temp": 18.3,
      "weather": "sunny"
    },
    {
      "series_id": "cust_001",
      "data_date": "2025-04-02",
      "temp": 17.9,
      "weather": "cloudy"
    },
    {
      "series_id": "cust_001",
      "data_date": "2025-04-03",
      "temp": 19.1,
      "weather": "sunny"
    }
  ],
  "target_fields": ["t0000", "t0015", "t0030"],
  "prediction_length": 2,
  "id_column": "series_id",
  "timestamp_column": "data_date",
  "quantile_levels": [0.1, 0.5, 0.9],
  "predict_strategy": "line"
}
```

---

## 5.1 请求样例（逐列预测）

> 使用 `predict_strategy: "col"` 逐列预测，适合字段间独立性较强的场景

```json
{
  "history_data": [
    {
      "series_id": "cust_001",
      "data_date": "2025-04-01",
      "t0000": 120.5,
      "t0015": 118.2,
      "t0030": 116.9
    },
    {
      "series_id": "cust_001",
      "data_date": "2025-04-02",
      "t0000": 122.1,
      "t0015": 119.8,
      "t0030": 117.4
    },
    {
      "series_id": "cust_001",
      "data_date": "2025-04-03",
      "t0000": 121.4,
      "t0015": 120.2,
      "t0030": 118.7
    }
  ],
  "related_data": null,
  "target_fields": ["t0000", "t0015", "t0030"],
  "prediction_length": 2,
  "id_column": "series_id",
  "timestamp_column": "data_date",
  "quantile_levels": [0.1, 0.5, 0.9],
  "predict_strategy": "col"
}
```

---

## 6. 请求样例（related_data 为空）

> 当 `related_data` 为空时，`future_df` 直接取 `history_data` 的目标字段数据。
> 可使用 `predict_strategy` 选择预测策略

```json
{
  "history_data": [
    {
      "series_id": "line_A",
      "data_date": "2025-01-01",
      "p1": 10.2,
      "p2": 11.5
    },
    {
      "series_id": "line_A",
      "data_date": "2025-01-02",
      "p1": 10.8,
      "p2": 11.9
    },
    {
      "series_id": "line_A",
      "data_date": "2025-01-03",
      "p1": 11.1,
      "p2": 12.3
    }
  ],
  "related_data": null,
  "target_fields": ["p1", "p2"],
  "prediction_length": 24,
  "id_column": "series_id",
  "timestamp_column": "data_date",
  "predict_strategy": "line"
}
```

---

## 7. 成功响应示例（节选）

> 不论使用 `line` 还是 `col` 策略，返回结果格式保持一致

```json
{
  "message": "预测成功",
  "used_related_data": true,
  "predict_strategy": "line",
  "prediction_length": 2,
  "target_fields": ["t0000", "t0015", "t0030"],
  "quantile_levels": [0.1, 0.5, 0.9],
  "history_df_size": 3,
  "model_df_size": 3,
  "future_df_size": 0,
  "prediction_result": {
    "short_wide": [
      {
        "series_id": "cust_001",
        "data_date": "2025-04-04T00:00:00",
        "t0000": 118.12,
        "t0015": 116.45,
        "t0030": 115.23
      }
    ],
    "median_wide": [
      {
        "series_id": "cust_001",
        "data_date": "2025-04-04T00:00:00",
        "t0000": 121.30,
        "t0015": 119.77,
        "t0030": 118.65
      }
    ],
    "long_wide": [
      {
        "series_id": "cust_001",
        "data_date": "2025-04-04T00:00:00",
        "t0000": 124.80,
        "t0015": 123.15,
        "t0030": 121.92
      }
    ]
  }
}
```

---

## 8. 常见报错

1. `history_data 不能为空`
2. `target_fields 不能为空`
3. `history_data 缺少必要字段`
4. `history_data 仅允许字段 ... 检测到附加字段 ...`
5. `related_data 缺少必要字段`
6. `predict_strategy 必须为 'line' 或 'col'`
7. `预测失败: ...`

---

## 9. 预测策略选择建议

### 何时使用 `line`（整行预测）

- **字段间存在相关性**：多个 target_fields 之间存在较强的关联性
- **需要利用交叉信息**：希望模型学习字段间的相互影响
- **性能要求较高**：一次预测所有字段，推理速度更快
- **典型场景**：电力负荷预测（不同时间点负荷相关）、多传感器数据预测

### 何时使用 `col`（逐列预测）

- **字段间独立性强**：各 target_fields 相对独立，相互影响小
- **需要独立建模**：希望每个字段独立使用其历史模式
- **内存限制**：单次预测单个字段，内存占用更小
- **典型场景**：多个独立产品的销量预测、不同设备的独立指标预测

### 性能对比

| 策略 | 推理速度 | 内存占用 | 适用场景 |
|------|---------|---------|---------|
| `line` | 快 | 较高 | 字段相关性强 |
| `col` | 慢 | 较低 | 字段独立性强 |

> **注意**：两种策略的返回结果格式完全一致，可以根据实际业务场景灵活选择。
