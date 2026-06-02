import os
import json
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from app.core.config import settings
from app.schemas.chat import ChatRequest, ApiResult
from app.services.ai_service import stream_chat, chat_with_file

router = APIRouter()

@router.post("/chat", response_model=dict)
async def chat(req: ChatRequest):
    if not req.question:
        return {"code": -1, "message": "请输入问题内容"}

    if not req.stream:
        return {"code": -1, "message": "非流式模式暂不支持，请使用流式模式"}

    async def generate():
        try:
            for chunk in stream_chat(req.model_id, req.question, req.history):
                if isinstance(chunk, tuple):
                    _, tokens, model_name = chunk
                    meta = json.dumps({
                        "tokens": tokens,
                        "model": model_name,
                        "timestamp": datetime.now().isoformat(),
                    }, ensure_ascii=False)
                    yield f"\n\n---END---\n{meta}"
                else:
                    yield chunk
        except Exception as e:
            error_meta = json.dumps({"message": str(e)}, ensure_ascii=False)
            yield f"\n\n---ERROR---\n{error_meta}"

    return StreamingResponse(
        generate(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

@router.post("/chat/upload")
async def chat_upload(
    model_id: str = Form(""),
    question: str = Form(""),
    file: UploadFile | None = File(None),
):
    if not question and not file:
        return {"code": -1, "message": "请输入问题或上传文件"}

    if not file:
        return {"code": -1, "message": "请上传文件"}

    os.makedirs(settings.upload_dir, exist_ok=True)
    # 安全处理：去掉客户端传入的目录信息，使用 uuid 防重名 + 路径遍历
    raw_name = os.path.basename(file.filename or "")
    if not raw_name:
        return {"code": -1, "message": "文件名无效"}
    safe_name = f"{uuid.uuid4().hex}_{raw_name}"
    abs_upload_dir = os.path.abspath(settings.upload_dir)
    file_path = os.path.abspath(os.path.join(abs_upload_dir, safe_name))
    if not file_path.startswith(abs_upload_dir + os.sep):
        raise HTTPException(status_code=400, detail="非法的上传路径")

    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        mime_type = file.content_type or "application/octet-stream"
        result = chat_with_file(
            model_id=model_id,
            question=question,
            file_path=file_path,
            mime_type=mime_type,
            file_name=raw_name,
        )

        return {"code": 0, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")
    finally:
        # 注意：chat_with_file 当前为同步调用，确保 finally 在文件读取完成后执行。
        # 若未来改为异步（如流式上传处理），需将删除逻辑移至异步完成回调。
        if os.path.exists(file_path):
            os.remove(file_path)