import os
import json
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
    file_path = os.path.join(settings.upload_dir, file.filename)

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
            file_name=file.filename,
        )

        return {"code": 0, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件处理失败: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)