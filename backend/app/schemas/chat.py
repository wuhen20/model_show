from pydantic import BaseModel


class ModelInfo(BaseModel):
    id: str
    name: str
    type: str
    description: str


class ChatRequest(BaseModel):
    model_id: str = ""
    question: str = ""
    history: list[dict] | None = None
    stream: bool = True


class ChatResponse(BaseModel):
    content: str
    suggestions: list[str] = []
    tokens: int = 0
    model: str = ""
    timestamp: str = ""
    file: dict | None = None


class ApiResult(BaseModel):
    code: int = 0
    data: object | None = None
    message: str | None = None