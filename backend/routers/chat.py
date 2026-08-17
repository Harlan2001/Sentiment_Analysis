from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.agent.agent_loop import run_agent_loop
from backend.agent.chat_service import CHAT_MODEL, CHAT_SYSTEM_PROMPT, kingstar_client
from backend.common.database import execute_query
from backend.config.config import API_PREFIX

router = APIRouter(prefix=f"{API_PREFIX}/chat", tags=["chat"])


# ── 请求模型 ──
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    stream: bool = True


# ── 路由 ──
@router.post("")
async def chat(request: ChatRequest, req: Request):
    """统一的 Agent 对话接口，支持 SSE 流式和非流式两种模式。"""

    # 解析用户身份
    username = getattr(req.state, "username", "anonymous")
    user_id = 0
    if username and username != "anonymous":
        try:
            r = execute_query(
                "SELECT id FROM users WHERE username=%s", (username,), one=True
            )
            if r:
                user_id = r[0]
        except Exception:
            pass

    if request.stream:

        async def event_stream():
            async for sse_event in run_agent_loop(
                messages=[m.model_dump() for m in request.messages],
                system_prompt=CHAT_SYSTEM_PROMPT,
                client=kingstar_client,
                model=CHAT_MODEL,
                model_name="glm",
                user_id=user_id,
                username=username or "anonymous",
            ):
                yield sse_event

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # 非流式模式：收集所有 SSE 事件，组装最终 JSON 响应
    content_parts: list[str] = []
    tool_results: list[dict] = []
    error_msg: str | None = None

    async for sse_event in run_agent_loop(
        messages=[m.model_dump() for m in request.messages],
        system_prompt=CHAT_SYSTEM_PROMPT,
        client=kingstar_client,
        model=CHAT_MODEL,
        model_name="glm",
        user_id=user_id,
        username=username or "anonymous",
    ):
        if sse_event.startswith("data: ") and not sse_event.startswith("data: [DONE]"):
            try:
                data = json.loads(sse_event[6:])
                if data.get("type") == "content":
                    content_parts.append(data["content"])
                elif data.get("type") == "tool_result":
                    tool_results.append(data)
                elif data.get("type") == "error":
                    error_msg = data.get("message", "未知错误")
            except json.JSONDecodeError:
                pass

    return {
        "content": "".join(content_parts),
        "tool_results": tool_results if tool_results else None,
        "error": error_msg,
    }
