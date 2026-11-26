"""思维链流式透传与落库单元测试。"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.agent.agent_loop import _process_chunk
from backend.agent.chat_service import _trace_queue_var
from backend.app import app
from backend.config.config import API_PREFIX


def _chunk(content: str | None = None, reasoning_content: str | None = None, reasoning: str | None = None):
    delta = SimpleNamespace(
        content=content,
        reasoning_content=reasoning_content,
        reasoning=reasoning,
        tool_calls=None,
    )
    return SimpleNamespace(
        usage=None,
        choices=[SimpleNamespace(delta=delta, finish_reason=None)],
    )


def test_process_chunk_emits_reasoning_and_content_sse():
    acc = {"content_parts": [], "tool_calls": {}, "finish_reason": None, "usage": None}
    sse = _process_chunk(_chunk(content="结论", reasoning_content="先核对收益率"), acc)
    assert sse is not None
    frames = [json.loads(line[6:]) for line in sse.strip().split("\n\n") if line.startswith("data: ")]
    assert frames == [
        {"type": "reasoning", "content": "先核对收益率"},
        {"type": "content", "content": "结论"},
    ]
    assert acc["content_parts"] == ["结论"]


def test_process_chunk_supports_reasoning_fallback_field():
    acc = {"content_parts": [], "tool_calls": {}, "finish_reason": None, "usage": None}
    sse = _process_chunk(_chunk(reasoning="备用字段推理"), acc)
    assert sse is not None
    payload = json.loads(sse.strip()[6:])
    assert payload == {"type": "reasoning", "content": "备用字段推理"}


def test_send_message_streams_assistant_thinking_and_persists_to_repository():
    repository = MagicMock()
    repository.get_message_retry.return_value = None
    repository.prepare_message.return_value = {
        "created": True,
        "user_message": {"id": "u1", "role": "user", "content": "看下债市", "created_at": "2026-11-26T00:00:00"},
        "assistant_message": {"id": "a1", "role": "assistant", "content": "", "status": "streaming"},
    }
    repository.get_agent_history.return_value = [{"role": "user", "content": "看下债市"}]
    repository.get_chat_attachment_context.return_value = ""
    repository.get_conversation.return_value = {"id": "c1", "project_id": None}
    repository.finish_assistant_message.return_value = {
        "id": "a1",
        "role": "assistant",
        "content": "最终结论",
        "thinking": "分析步骤\n- 正在调用工具：`news_search`\n- 已完成：`news_search` (42ms)",
        "status": "completed",
    }

    async def mock_stream(*args, **kwargs):
        q = _trace_queue_var.get()
        assert q is not None
        q.put_nowait({"kind": "reasoning", "delta": "分析步骤"})
        q.put_nowait({"kind": "tool_start", "tool_name": "news_search"})
        q.put_nowait({"kind": "tool_done", "tool_name": "news_search", "duration_ms": 42})
        yield "最终结论"

    old_repo = getattr(app.state, "repository", None)
    old_mem = getattr(app.state, "user_memory_repository", None)
    app.state.repository = repository
    app.state.user_memory_repository = None
    try:
        client = TestClient(app)
        with patch("backend.auth.dependencies.AUTH_ENABLED", False), \
             patch("backend.routers.workbench_conversations.agent_chat_stream", mock_stream):
            response = client.post(
                f"{API_PREFIX}/workbench/conversations/c1/messages",
                json={"content": "看下债市", "client_message_id": "cm-think-1"},
            )
    finally:
        app.state.repository = old_repo
        app.state.user_memory_repository = old_mem

    assert response.status_code == 200
    assert "event: assistant.thinking" in response.text
    assert "分析步骤" in response.text
    assert "news_search" in response.text
    repository.finish_assistant_message.assert_called_once_with(
        "a1",
        "最终结论",
        "completed",
        thinking="分析步骤\n- 正在调用工具：`news_search`\n- 已完成：`news_search` (42ms)",
    )
