import re
import io
import json
import base64
from PIL import Image
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from openai import OpenAI

router = APIRouter()


def _get_image_size(image_bytes: bytes) -> tuple[int, int]:
    """获取图片宽高"""
    try:
        img = Image.open(io.BytesIO(image_bytes))
        return img.size  # (width, height)
    except Exception:
        return (1000, 1000)


def _normalize_detections(raw_data, image_width: int, image_height: int) -> list[dict]:
    """
    标准化检测结果:
    1. 兼容裸数组 [{"bbox_2d":...}] 和包装格式 {"detections": [...]}
    2. 将 bbox_2d (Qwen VL 0-1000相对坐标) 转换为 bbox (绝对像素坐标)
    3. 补充缺失的 confidence 字段
    """
    items = []

    if isinstance(raw_data, list):
        items = raw_data
    elif isinstance(raw_data, dict):
        items = raw_data.get("detections", [])
        if not isinstance(items, list):
            return []
    else:
        return []

    result = []
    for item in items:
        if not isinstance(item, dict):
            continue

        label = item.get("label", "未识别")
        confidence = item.get("confidence", 0.0)

        # 优先使用 bbox_2d（Qwen VL格式），回退到 bbox
        bbox_raw = item.get("bbox_2d") or item.get("bbox")
        if not bbox_raw or len(bbox_raw) < 4:
            continue

        # 判断是相对坐标(0-1000范围)还是绝对坐标
        # 如果所有值 <= 1000 且存在 bbox_2d 字段，视为相对坐标需要转换
        is_relative = "bbox_2d" in item and all(v <= 1000 for v in bbox_raw)

        if is_relative:
            x1 = int(bbox_raw[0] / 1000 * image_width)
            y1 = int(bbox_raw[1] / 1000 * image_height)
            x2 = int(bbox_raw[2] / 1000 * image_width)
            y2 = int(bbox_raw[3] / 1000 * image_height)
        else:
            x1, y1, x2, y2 = int(bbox_raw[0]), int(bbox_raw[1]), int(bbox_raw[2]), int(bbox_raw[3])

        entry = {
            "label": label,
            "confidence": confidence,
            "bbox": [x1, y1, x2, y2],
        }
        # 保留额外字段
        if "text" in item:
            entry["text"] = item["text"]
        if "severity" in item:
            entry["severity"] = item["severity"]

        result.append(entry)

    return result


def _parse_detections(text: str) -> tuple:
    """
    尝试从模型返回文本中解析JSON检测结果。
    返回 (raw_data, raw_text)，raw_data 可能是 list 或 dict。
    """
    # 尝试直接解析整个文本为 JSON
    try:
        data = json.loads(text.strip())
        if isinstance(data, (list, dict)):
            return data, text
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取
    patterns = [
        r'```json\s*\n?(.*?)\n?```',
        r'```\s*\n?(.*?)\n?```',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                raw = match.group(1) if match.lastindex else match.group(0)
                data = json.loads(raw)
                if isinstance(data, (list, dict)):
                    return data, text
            except (json.JSONDecodeError, IndexError):
                continue

    # 尝试匹配 JSON 对象或数组
    for pattern in [r'\[[\s\S]*\]', r'\{[\s\S]*\}']:
        match = re.search(pattern, text)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, (list, dict)):
                    return data, text
            except json.JSONDecodeError:
                continue

    return None, text


@router.post("/analyze")
async def analyze_image(
    file: UploadFile = File(...),
    endpoint: str = Form("http://localhost:11434/v1"),
    api_key: str = Form("ollama"),
    model_id: str = Form("qwen2.5-vl"),
    system_prompt: str = Form(""),
    user_prompt: str = Form("请检测这张图片中的目标，以JSON格式返回结果。"),
):
    """上传图片并调用大模型进行目标检测/分类"""
    try:
        content = await file.read()
        image_base64 = base64.b64encode(content).decode("utf-8")
        mime_type = file.content_type or "image/jpeg"

        # 获取图片实际尺寸
        image_width, image_height = _get_image_size(content)

        # 动态创建 OpenAI client
        client = OpenAI(api_key=api_key, base_url=endpoint)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt or "请分析这张图片"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
                },
            ],
        })

        completion = client.chat.completions.create(
            model=model_id,
            messages=messages,
            max_tokens=4096,
            temperature=0.3,
        )

        raw_content = completion.choices[0].message.content or ""
        raw_data, raw_text = _parse_detections(raw_content)

        # 标准化检测结果 + 坐标转换
        detections = []
        if raw_data is not None:
            detections = _normalize_detections(raw_data, image_width, image_height)

        result = {
            "detections": detections,
            "raw_response": raw_content,
            "tokens": completion.usage.total_tokens if completion.usage else 0,
            "model": model_id,
            "image_size": {"width": image_width, "height": image_height},
        }

        return {"code": 0, "data": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检测失败: {str(e)}")


@router.post("/test-connection")
async def test_connection(
    endpoint: str = Form("http://localhost:11434/v1"),
    api_key: str = Form("ollama"),
    model_id: str = Form("qwen2.5-vl"),
):
    """测试 API 连接是否正常"""
    try:
        client = OpenAI(api_key=api_key, base_url=endpoint)
        models = client.models.list()
        model_ids = [m.id for m in models.data] if hasattr(models, 'data') else []
        return {
            "code": 0,
            "message": "连接成功",
            "data": {"available_models": model_ids[:20]}
        }
    except Exception as e:
        return {"code": -1, "message": f"连接失败: {str(e)}"}
