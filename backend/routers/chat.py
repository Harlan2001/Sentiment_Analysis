from __future__ import annotations

import os
import json
from typing import Any, List

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from pydantic import BaseModel

from backend.config.config import API_PREFIX

router = APIRouter(prefix=f"{API_PREFIX}/chat", tags=["chat"])

kingstar_API_KEY = os.getenv("kingstar_API_KEY")
if not kingstar_API_KEY:
    raise ValueError("kingstar_API_KEY environment variable is not set. Please set it in your .env file.")
kingstar_BASE_URL = os.getenv("kingstar_BASE_URL")
kingstar_client = OpenAI(api_key=kingstar_API_KEY, base_url=kingstar_BASE_URL)

CHAT_SYSTEM_PROMPT = """你是一个专业的中国债券市场分析助手，擅长解读宏观经济数据、货币政策、债市行情等。\n\n你的职责：\n1. 解答用户关于债券市场、收益率、货币政策、宏观经济等方面的问题\n2. 分析新闻事件对债市的潜在影响\n3. 解释专业术语和市场逻辑\n4. 提供客观的市场分析，不提供具体的投资建议\n\n你可以使用工具来获取真实的金融新闻。当用户在查询新闻、事实、列表、最近发生的事件时，优先考虑使用工具。\n\n工具返回结果后：\n- 不要逐条复述新闻\n- 进行总结、归纳和重点提示\n- 如果工具没有结果，给出解释性回复，不要编造新闻\n\n回复要求：\n- 使用专业但易懂的语言\n- 结构清晰，可使用 Markdown 格式（标题、列表、加粗等）\n- 如涉及因果分析，使用"→"符号展示逻辑链\n- 保持客观中立，不做投资建议\n"""


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    stream: bool = True
    enable_tools: bool = False


@router.post("")
async def chat(request: ChatRequest):
    system_message: ChatCompletionSystemMessageParam = {"role": "system", "content": CHAT_SYSTEM_PROMPT}
    messages: list[
        ChatCompletionSystemMessageParam | ChatCompletionUserMessageParam | ChatCompletionAssistantMessageParam
    ] = [system_message]

    def _extract_message_content(message: Any) -> str:
        content = getattr(message, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                text = item.get("text") if isinstance(item, dict) else getattr(item, "text", None)
                if text:
                    parts.append(str(text))
            return "".join(parts)
        if content is None:
            return ""
        return str(content)

    for msg in request.messages:
        if msg.role == "assistant":
            messages.append({"role": "assistant", "content": msg.content})
        else:
            messages.append({"role": "user", "content": msg.content})

    try:
        response = kingstar_client.chat.completions.create(
            model="volcengine/doubao-seed-2-0-code-preview-260215",
            messages=messages,
            temperature=0.7,
        )
        content = _extract_message_content(response.choices[0].message)
        if request.stream:
            def event_stream():
                yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                event_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )

        return {
            "content": content,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            },
            "stream": False,
        }
    except Exception as exc:
        if request.stream:
            def error_stream():
                yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                error_stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
            )
        return {"error": str(exc)}
