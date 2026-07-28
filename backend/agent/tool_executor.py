"""
工具执行器模块

所有工具通过 backend/agent/client.py 的 HTTP Client 调用后端 API。
返回 dict，异常返回 {"error": "..."}。

通过 SENTIMENT_INTERNAL_API_TOKEN 环境变量支持 auth 场景下的内部调用。
"""

import logging
import os

from backend.agent.spec import load_spec, filter_agent_operations, generate_tool_executors
from backend.agent.client import Client

logger = logging.getLogger(__name__)

_internal_url = os.environ.get("SENTIMENT_INTERNAL_API_URL", "http://127.0.0.1:8000")
_token = os.environ.get("SENTIMENT_INTERNAL_API_TOKEN", None)
_client = Client(base_url=_internal_url, token=_token, timeout=30.0)

_spec = load_spec()
_agent_ops = filter_agent_operations(_spec)

TOOL_EXECUTORS = generate_tool_executors(_agent_ops, _client)
