"""
Agent 工具定义模块

所有工具由 backend/agent/spec.py 从 OpenAPI 规范动态生成。
工具均为 GET 查询，无副作用。
"""

from backend.agent.spec import (
    filter_agent_operations,
    generate_tool_definitions,
    load_spec,
)

_spec = load_spec()
_agent_ops = filter_agent_operations(_spec)

TOOL_DEFINITIONS = generate_tool_definitions(_agent_ops)

# Feishu is intentionally read-only in this first MCP release.  These tools are
# executed with the current chat user's OAuth connection, never an app-wide token.
TOOL_DEFINITIONS += [
    {"type": "function", "function": {"name": "feishu_search_docs", "description": "搜索当前用户已授权的飞书文档。", "parameters": {"type": "object", "properties": {"query": {"type": "string", "description": "搜索关键词"}, "page_size": {"type": "integer", "minimum": 1, "maximum": 100}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "feishu_get_doc_content", "description": "读取飞书文档正文。", "parameters": {"type": "object", "properties": {"document_id": {"type": "string", "description": "飞书 document_id"}}, "required": ["document_id"]}}},
    {"type": "function", "function": {"name": "feishu_get_bitable_metadata", "description": "读取飞书多维表格表结构。", "parameters": {"type": "object", "properties": {"app_token": {"type": "string", "description": "多维表格 app_token"}}, "required": ["app_token"]}}},
    {"type": "function", "function": {"name": "feishu_list_bitable_records", "description": "读取飞书多维表格记录。", "parameters": {"type": "object", "properties": {"app_token": {"type": "string"}, "table_id": {"type": "string"}, "page_size": {"type": "integer", "minimum": 1, "maximum": 100}}, "required": ["app_token", "table_id"]}}},
    {"type": "function", "function": {"name": "feishu_list_chats", "description": "列出当前用户有权访问的飞书群组。", "parameters": {"type": "object", "properties": {"page_size": {"type": "integer", "minimum": 1, "maximum": 100}}}}},
    {"type": "function", "function": {"name": "feishu_list_messages", "description": "读取指定飞书群组的消息。", "parameters": {"type": "object", "properties": {"chat_id": {"type": "string", "description": "飞书群 chat_id"}, "page_size": {"type": "integer", "minimum": 1, "maximum": 100}}, "required": ["chat_id"]}}},
]
