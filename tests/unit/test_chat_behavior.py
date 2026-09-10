"""聊天鉴权边界测试：登录用户走持久化仓库，访客只能使用只读接口。

前端的访客临时会话另由 Vitest 覆盖；这里验证匿名请求不会进入任何写入逻辑。
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.config.config import API_PREFIX

PREFIX = API_PREFIX
TEST_JWT_SECRET = "test-chat-secret-at-least-32-bytes-long"


@pytest.fixture
def chat_client():
    from backend.app import app

    repository = MagicMock()
    previous_repository = getattr(app.state, "repository", None)
    app.state.repository = repository
    with patch("backend.auth.dependencies.AUTH_ENABLED", True), \
         patch("backend.auth.auth.JWT_SECRET_KEY", TEST_JWT_SECRET):
        yield TestClient(app), repository
    if previous_repository is None:
        del app.state.repository
    else:
        app.state.repository = previous_repository


def _token(username: str = "user1") -> str:
    from backend.auth.auth import create_jwt_token

    return create_jwt_token(username, is_admin=False, role="member")


def test_authenticated_user_sends_message_through_own_identity(chat_client):
    """登录用户的身份必须从 JWT 传到所有会话仓库调用。"""
    client, repository = chat_client
    repository.prepare_message.return_value = {
        "created": True,
        "user_message": {
            "id": "user-msg-001", "role": "user", "content": "测试消息",
            "status": "completed", "created_at": "2026-01-01T00:00:00",
        },
        "assistant_message": {
            "id": "assistant-msg-001", "role": "assistant", "content": "",
            "status": "streaming", "created_at": "2026-01-01T00:00:00",
        },
    }
    repository.get_agent_history.return_value = []
    repository.get_conversation.return_value = {"id": "conv-001", "project_id": None}
    repository.finish_assistant_message.return_value = {
        "id": "assistant-msg-001", "role": "assistant", "content": "测试回复",
        "status": "completed", "created_at": "2026-01-01T00:00:00",
    }
    repository.get_message_retry.return_value = None

    async def mock_stream(*args, **kwargs):
        yield "测试回复"

    skill_repository = MagicMock()
    skill_repository.list_chat_skills.return_value = []
    skill_repository.get_attachment_context.return_value = ""
    with patch("backend.routers.workbench_conversations.agent_chat_stream", mock_stream), \
         patch("backend.routers.workbench_conversations.SkillRepository.from_environment", return_value=skill_repository):
        response = client.post(
            f"{PREFIX}/workbench/conversations/conv-001/messages",
            json={"content": "测试消息", "client_message_id": "client-msg-001"},
            headers={"Authorization": f"Bearer {_token()}"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    repository.prepare_message.assert_called_once_with(
        "user1", "conv-001", "测试消息", "client-msg-001", []
    )
    repository.get_agent_history.assert_called_once()
    assert repository.get_agent_history.call_args.args[0] == "user1"
    assert repository.get_conversation.call_args.args[:2] == ("user1", "conv-001")
    skill_repository.get_attachment_context.assert_called_once_with("user1", [], "测试消息")


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/workbench/conversations", {"source": "home"}),
        ("/workbench/conversations/conv-001/messages", {"content": "访客消息", "client_message_id": "visitor-msg-001"}),
    ],
)
def test_anonymous_write_is_rejected_before_repository(chat_client, path, payload):
    client, repository = chat_client

    response = client.post(f"{PREFIX}{path}", json=payload)

    assert response.status_code == 401
    repository.create_conversation.assert_not_called()
    repository.prepare_message.assert_not_called()


def test_anonymous_read_uses_dedicated_anonymous_identity(chat_client):
    client, repository = chat_client
    repository.list_conversations.return_value = {"items": [], "next_cursor": None}

    response = client.get(f"{PREFIX}/workbench/conversations")

    assert response.status_code == 200
    repository.list_conversations.assert_called_once_with(
        "anonymous", None, 20, None, False
    )


def test_visitor_chat_streams_ai_without_persistence(chat_client):
    client, repository = chat_client

    async def mock_stream(messages, username, *args, **kwargs):
        assert username == "anonymous"
        assert messages[-1] == {"role": "user", "content": "访客问题"}
        yield "真实 AI 回复"

    with patch("backend.routers.workbench_conversations.agent_chat_stream", mock_stream):
        response = client.post(
            f"{PREFIX}/workbench/conversations/visitor-chat",
            json={"content": "访客问题", "history": []},
        )

    assert response.status_code == 200
    assert "真实 AI 回复" in response.text
    repository.prepare_message.assert_not_called()
    repository.create_conversation.assert_not_called()


def test_authenticated_create_uses_token_subject_as_owner(chat_client):
    client, repository = chat_client
    repository.create_conversation.return_value = {
        "id": "new-conv-001", "owner_username": "user1", "source": "home"
    }

    response = client.post(
        f"{PREFIX}/workbench/conversations",
        json={"source": "home"},
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 201
    repository.create_conversation.assert_called_once_with("user1", None, None, "home")


def test_auth_status_without_token_is_unauthenticated(chat_client):
    client, _ = chat_client
    with patch("backend.routers.auth.AUTH_ENABLED", True):
        response = client.get(f"{PREFIX}/auth/status")

    assert response.status_code == 200
    assert response.json() == {"auth_enabled": True, "authenticated": False}


def test_removing_token_changes_status_to_unauthenticated(chat_client):
    """服务端 JWT 无会话撤销表；退出的服务端效果来自后续请求不再携带 token。"""
    client, _ = chat_client
    cursor = MagicMock()
    cursor.fetchone.return_value = (1, "user1", "用户一", 1, 0, "user")
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    conn.cursor.return_value.__exit__.return_value = False

    with patch("backend.routers.auth.AUTH_ENABLED", True), \
         patch("backend.routers.auth.get_db_connection", return_value=conn):
        authenticated = client.get(
            f"{PREFIX}/auth/status",
            headers={"Authorization": f"Bearer {_token()}"},
        )
        logged_out = client.get(f"{PREFIX}/auth/status")

    assert authenticated.json()["authenticated"] is True
    assert logged_out.json()["authenticated"] is False


def test_auth_disabled_mode_reports_admin(chat_client):
    client, _ = chat_client
    with patch("backend.auth.dependencies.AUTH_ENABLED", False), \
         patch("backend.routers.auth.AUTH_ENABLED", False):
        response = client.get(f"{PREFIX}/auth/status")

    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert response.json()["is_admin"] is True
