from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from backend.config.config import API_PREFIX
from backend.integrations.feishu.client import FeishuApiError, FeishuClient
from backend.integrations.feishu.repository import FeishuConnectionError, FeishuConnectionRepository

router = APIRouter(prefix=f"{API_PREFIX}/mcp/feishu", tags=["feishu-mcp"])

TOOLS = [
    {"name": "search_feishu_docs", "description": "搜索已授权访问的飞书文档", "read_only": True},
    {"name": "get_feishu_doc_content", "description": "读取一篇飞书文档正文", "read_only": True},
    {"name": "get_bitable_metadata", "description": "读取飞书多维表格的表结构", "read_only": True},
    {"name": "list_bitable_records", "description": "读取飞书多维表格记录", "read_only": True},
    {"name": "list_feishu_chats", "description": "读取飞书群组列表", "read_only": True},
    {"name": "list_feishu_messages", "description": "读取指定飞书群的消息", "read_only": True},
]


class ToolRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


def _repository(request: Request) -> FeishuConnectionRepository:
    return request.app.state.feishu_mcp_repository


def _status(connection: dict[str, Any] | None) -> dict[str, Any]:
    if not connection:
        return {"id": "feishu", "connected": False, "last_sync": None, "account": None, "tools": TOOLS}
    return {
        "id": "feishu",
        "connected": True,
        "last_sync": _iso(connection.get("last_used_at") or connection.get("connected_at")),
        "account": {"user_id": connection.get("feishu_user_id"), "tenant_key": connection.get("tenant_key")},
        "tools": TOOLS,
    }


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


@router.get("")
def get_connection_status(request: Request):
    return {"data": _status(_repository(request).get_connection(request.state.username))}


@router.post("/authorize")
def authorize(request: Request):
    repository = _repository(request)
    state = repository.create_oauth_state(request.state.username)
    try:
        url = FeishuClient().authorize_url(state)
    except FeishuConnectionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"data": {"authorization_url": url}}


@router.get("/callback")
def oauth_callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None):
    if error or not code or not state:
        return RedirectResponse("/custom/mcp?feishu=failed")
    repository = _repository(request)
    username = repository.consume_oauth_state(state)
    if not username:
        return RedirectResponse("/custom/mcp?feishu=expired")
    try:
        repository.upsert_connection(username, FeishuClient().exchange_code(code))
    except FeishuConnectionError:
        return RedirectResponse("/custom/mcp?feishu=failed")
    return RedirectResponse("/custom/mcp?feishu=connected")


@router.delete("")
def disconnect(request: Request):
    return {"data": {"disconnected": _repository(request).delete_connection(request.state.username)}}


@router.get("/tools")
def list_tools():
    return {"data": TOOLS}


@router.post("/tools/{tool_name}")
def call_tool(request: Request, tool_name: Literal[
    "search_feishu_docs", "get_feishu_doc_content", "get_bitable_metadata",
    "list_bitable_records", "list_feishu_chats", "list_feishu_messages",
], body: ToolRequest, page_size: int = Query(default=50, ge=1, le=100)):
    repository = _repository(request)
    try:
        connection = repository.get_connection(request.state.username, include_tokens=True)
        if not connection:
            raise HTTPException(status_code=409, detail="请先连接飞书。")
        client = FeishuClient()
        expires_at = connection.get("expires_at")
        if isinstance(expires_at, datetime) and expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc) + timedelta(minutes=2):
            refreshed = client.refresh_token(connection["refresh_token"])
            repository.upsert_connection(request.state.username, {**connection, **refreshed})
            connection = repository.get_connection(request.state.username, include_tokens=True)
            if not connection:
                raise HTTPException(status_code=409, detail="飞书连接已失效，请重新连接。")
        token = connection["access_token"]
        args = body.arguments
        if tool_name == "search_feishu_docs":
            result = client.search_docs(token, _required(args, "query"), page_size)
        elif tool_name == "get_feishu_doc_content":
            result = client.get_doc_content(token, _required(args, "document_id"))
        elif tool_name == "get_bitable_metadata":
            result = client.get_bitable_metadata(token, _required(args, "app_token"))
        elif tool_name == "list_bitable_records":
            result = client.list_bitable_records(token, _required(args, "app_token"), _required(args, "table_id"), page_size)
        elif tool_name == "list_feishu_chats":
            result = client.list_chats(token, page_size)
        else:
            result = client.list_messages(token, _required(args, "chat_id"), page_size)
        repository.touch_connection(request.state.username)
        repository.audit(request.state.username, tool_name, True)
        return {"data": result.get("data", result)}
    except HTTPException:
        raise
    except (FeishuConnectionError, FeishuApiError) as exc:
        repository.audit(request.state.username, tool_name, False, str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc


def _required(arguments: dict[str, Any], key: str) -> str:
    value = str(arguments.get(key) or "").strip()
    if not value:
        raise HTTPException(status_code=422, detail=f"缺少参数：{key}")
    return value
