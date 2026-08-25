from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from backend.integrations.feishu.client import FeishuClient
from backend.integrations.feishu.repository import FeishuConnectionRepository


def execute_feishu_tool(username: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute an Agent-facing, read-only Feishu MCP tool for one user."""
    repository = FeishuConnectionRepository()
    connection = repository.get_connection(username, include_tokens=True)
    if not connection:
        return {"error": "飞书尚未连接。请先在 MCP 页面连接飞书后再使用该工具。"}
    try:
        client = FeishuClient()
        expires_at = connection.get("expires_at")
        if isinstance(expires_at, datetime) and expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc) + timedelta(minutes=2):
            repository.upsert_connection(username, {**connection, **client.refresh_token(connection["refresh_token"])})
            connection = repository.get_connection(username, include_tokens=True)
            if not connection:
                return {"error": "飞书连接已失效，请重新连接。"}
        token = connection["access_token"]
        if tool_name == "feishu_search_docs":
            result = client.search_docs(token, _required(arguments, "query"), _page_size(arguments))
        elif tool_name == "feishu_get_doc_content":
            result = client.get_doc_content(token, _required(arguments, "document_id"))
        elif tool_name == "feishu_get_bitable_metadata":
            result = client.get_bitable_metadata(token, _required(arguments, "app_token"))
        elif tool_name == "feishu_list_bitable_records":
            result = client.list_bitable_records(token, _required(arguments, "app_token"), _required(arguments, "table_id"), _page_size(arguments))
        elif tool_name == "feishu_list_chats":
            result = client.list_chats(token, _page_size(arguments))
        elif tool_name == "feishu_list_messages":
            result = client.list_messages(token, _required(arguments, "chat_id"), _page_size(arguments))
        else:
            return {"error": f"未知飞书工具：{tool_name}"}
        repository.touch_connection(username)
        repository.audit(username, tool_name, True)
        return result.get("data", result)
    except Exception as exc:
        repository.audit(username, tool_name, False, str(exc))
        return {"error": str(exc)}


def _required(arguments: dict[str, Any], name: str) -> str:
    value = str(arguments.get(name) or "").strip()
    if not value:
        raise ValueError(f"缺少参数：{name}")
    return value


def _page_size(arguments: dict[str, Any]) -> int:
    try:
        return max(1, min(int(arguments.get("page_size") or 50), 100))
    except (TypeError, ValueError):
        return 50
