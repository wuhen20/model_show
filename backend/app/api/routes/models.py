from fastapi import APIRouter, HTTPException
from app.core.config import settings
from app.schemas.chat import ModelInfo

router = APIRouter()

@router.get("", response_model=dict)
def get_models():
    model_list = [
        ModelInfo(
            id=m["id"],
            name=m["name"],
            type=m["type"],
            description=m["description"],
        )
        for m in settings.models
    ]
    return {"code": 0, "data": [m.model_dump() for m in model_list]}