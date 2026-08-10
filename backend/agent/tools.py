"""
Agent 工具定义模块

所有工具由 backend/agent/spec.py 从 OpenAPI 规范动态生成。
工具均为 GET 查询，无副作用。
"""

from backend.agent.spec import (
    filter_agent_operations,
    generate_display_metadata,
    generate_tool_definitions,
    load_spec,
)

_spec = load_spec()
_agent_ops = filter_agent_operations(_spec)

TOOL_DEFINITIONS = generate_tool_definitions(_agent_ops)
TOOL_DISPLAY_NAMES, TOOL_ICONS = generate_display_metadata(_agent_ops)
