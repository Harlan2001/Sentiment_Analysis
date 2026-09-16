"""账号级个人记忆基础版测试。"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.config.config import API_PREFIX
from backend.services.user_memory_service import (
    contains_sensitive_data,
    extract_memory_intent,
)

TEST_JWT_SECRET = "test-memory-secret-at-least-32-bytes"


def _token(username: str = "memory-user") -> str:
    from backend.auth.auth import create_jwt_token

    return create_jwt_token(username, is_admin=False, role="member")


@pytest.fixture
def memory_client():
    from backend.app import app

    repository = MagicMock()
    previous_repository = getattr(app.state, "user_memory_repository", None)
    app.state.user_memory_repository = repository
    with (
        patch("backend.auth.dependencies.AUTH_ENABLED", True),
        patch("backend.auth.auth.JWT_SECRET_KEY", TEST_JWT_SECRET),
        patch(
            "backend.auth.dependencies._load_current_identity",
            return_value={"is_active": True, "is_admin": False, "role": "member"},
        ),
    ):
        yield TestClient(app), repository
    if previous_repository is None:
        del app.state.user_memory_repository
    else:
        app.state.user_memory_repository = previous_repository


def test_explicit_remember_becomes_active():
    intent, candidates = extract_memory_intent("记住，我以后喜欢先看结论再看分析")

    assert intent == "remember"
    assert len(candidates) == 1
    assert candidates[0].status == "active"
    assert candidates[0].source_type == "explicit_chat"
    assert candidates[0].category == "response_preference"


def test_inferred_preference_requires_confirmation():
    intent, candidates = extract_memory_intent("我喜欢用表格查看分析结果")

    assert intent == "remember"
    assert candidates[0].status == "pending"
    assert candidates[0].source_type == "inferred_chat"


def test_common_preference_uses_semantic_key_for_conflict_detection():
    _, chinese = extract_memory_intent("记住以后回答默认使用中文")
    _, english = extract_memory_intent("记住以后回答默认使用英文")

    assert chinese[0].normalized_key == "response.language"
    assert english[0].normalized_key == "response.language"


def test_one_off_request_is_not_remembered():
    assert extract_memory_intent("帮我分析一下今天的市场") == ("none", [])


@pytest.mark.parametrize(
    "text",
    [
        "记住我的密码是 abc123",
        "记住我的身份证是 110101199001011234",
        "记住我的手机号是 13800138000",
    ],
)
def test_sensitive_information_is_rejected(text):
    assert contains_sensitive_data(text)
    assert extract_memory_intent(text) == ("none", [])


def test_memory_api_uses_authenticated_identity(memory_client):
    client, repository = memory_client
    repository.list_user_memories.return_value = {"items": []}

    response = client.get(
        f"{API_PREFIX}/workbench/memories",
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 200
    repository.list_user_memories.assert_called_once_with(
        "memory-user", None, None, None, 100
    )


def test_memory_write_requires_login(memory_client):
    client, repository = memory_client

    response = client.post(
        f"{API_PREFIX}/workbench/memories",
        json={"category": "response_preference", "title": "回答偏好", "content": "先给结论"},
    )

    assert response.status_code == 401
    repository.create_user_memory.assert_not_called()


def test_memory_update_never_accepts_owner_from_client(memory_client):
    client, repository = memory_client
    repository.update_user_memory.return_value = {
        "id": "memory-1",
        "owner_username": "memory-user",
        "status": "active",
    }

    response = client.patch(
        f"{API_PREFIX}/workbench/memories/memory-1",
        json={"status": "active"},
        headers={"Authorization": f"Bearer {_token()}"},
    )

    assert response.status_code == 200
    repository.update_user_memory.assert_called_once_with(
        "memory-user", "memory-1", {"status": "active"}
    )
