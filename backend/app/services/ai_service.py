import os
import base64
from openai import OpenAI
from app.core.config import settings

client = OpenAI(
    api_key=settings.dashscope_api_key,
    base_url=settings.dashscope_base_url,
)


def get_model_config(model_id: str) -> dict:
    for model in settings.models:
        if model["id"] == model_id:
            return model
    return settings.models[0]


def build_messages(model_config: dict, question: str, history: list[dict] | None) -> list[dict]:
    messages = [{"role": "system", "content": model_config["system_prompt"]}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})
    return messages


def build_vision_messages(model_config: dict, question: str, image_base64: str, mime_type: str) -> list[dict]:
    messages = [{"role": "system", "content": model_config["system_prompt"]}]
    user_content = []

    if question:
        user_content.append({"type": "text", "text": question})

    user_content.append({
        "type": "image_url",
        "image_url": {"url": f"data:{mime_type};base64,{image_base64}"},
    })

    messages.append({"role": "user", "content": user_content})
    return messages


def stream_chat(model_id: str, question: str, history: list[dict] | None = None):
    model_config = get_model_config(model_id)
    messages = build_messages(model_config, question, history)

    completion = client.chat.completions.create(
        model=model_config["model_id"],
        messages=messages,
        max_tokens=model_config["max_tokens"],
        temperature=model_config["temperature"],
        stream=True,
    )

    tokens = 0
    for chunk in completion:
        content = chunk.choices[0].delta.content if chunk.choices else None
        if content:
            yield content
        if chunk.usage:
            tokens = chunk.usage.total_tokens

    yield ("__END__", tokens, model_config["name"])


def chat_with_file(model_id: str, question: str, file_path: str, mime_type: str | None, file_name: str) -> dict:
    model_config = get_model_config(model_id)
    allowed = settings.allowed_image_types_list
    is_image = mime_type in allowed

    if is_image:
        with open(file_path, "rb") as f:
            image_base64 = base64.b64encode(f.read()).decode("utf-8")
        messages = build_vision_messages(model_config, question or "请分析这张图片", image_base64, mime_type)
    else:
        full_question = f"[用户上传了文件: {file_name}]\n{question or '请分析这个文件'}"
        messages = build_messages(model_config, full_question, None)

    completion = client.chat.completions.create(
        model=model_config["model_id"],
        messages=messages,
        max_tokens=model_config["max_tokens"],
        temperature=model_config["temperature"],
    )

    content = completion.choices[0].message.content or ""

    return {
        "content": content,
        "suggestions": [],
        "tokens": completion.usage.total_tokens if completion.usage else 0,
        "model": model_config["name"],
        "timestamp": "",
        "file": {
            "name": file_name,
            "size": os.path.getsize(file_path),
            "url": "",
        },
    }