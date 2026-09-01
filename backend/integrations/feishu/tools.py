from __future__ import annotations

from typing import Any, Callable

from backend.integrations.feishu.client import FeishuClient, active_access_token
from backend.integrations.feishu.repository import FeishuConnectionRepository


def execute_feishu_tool(username: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute an Agent-facing, read-only Feishu MCP tool for one user."""
    repository = FeishuConnectionRepository()
    client = FeishuClient()
    try:
        token = active_access_token(repository, client, username)
        if token is None:
            return {"error": "飞书尚未连接。请先在 MCP 页面连接飞书后再使用该工具。"}
        handler = _HANDLERS.get(tool_name)
        if handler is None:
            return {"error": f"未知飞书工具：{tool_name}"}
        result = handler(client, token, arguments)
        repository.touch_connection(username)
        repository.audit(username, tool_name, True)
        return result.get("data", result)
    except Exception as exc:
        repository.audit(username, tool_name, False, str(exc))
        return {"error": str(exc)}


def _search_docs(client: FeishuClient, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return client.search_docs(token, _required(arguments, "query"), _page_size(arguments))


def _get_doc_content(client: FeishuClient, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return client.get_doc_content(token, _required(arguments, "document_id"))


def _get_bitable_metadata(client: FeishuClient, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return client.get_bitable_metadata(token, _required(arguments, "app_token"))


def _list_bitable_records(client: FeishuClient, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return client.list_bitable_records(
        token, _required(arguments, "app_token"), _required(arguments, "table_id"), _page_size(arguments)
    )


def _list_chats(client: FeishuClient, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return client.list_chats(token, _page_size(arguments))


def _list_messages(client: FeishuClient, token: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return client.list_messages(token, _required(arguments, "chat_id"), _page_size(arguments))


_HANDLERS: dict[str, Callable[[FeishuClient, str, dict[str, Any]], dict[str, Any]]] = {
    "feishu_search_docs": _search_docs,
    "feishu_get_doc_content": _get_doc_content,
    "feishu_get_bitable_metadata": _get_bitable_metadata,
    "feishu_list_bitable_records": _list_bitable_records,
    "feishu_list_chats": _list_chats,
    "feishu_list_messages": _list_messages,
}


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