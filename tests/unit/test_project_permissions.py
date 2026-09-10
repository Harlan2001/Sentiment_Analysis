"""项目制的管理者/编辑者权限矩阵测试。"""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.project_management_repository import ProjectManagementRepository
from backend.repositories.workbench_repository import (
    WorkbenchPermissionError,
    WorkbenchRepository,
)


def test_only_manager_can_change_project_settings():
    WorkbenchRepository._require_project_write({"role": "manager"})
    WorkbenchRepository._require_project_write({"role": "owner"})
    with pytest.raises(WorkbenchPermissionError, match="只有项目管理者"):
        WorkbenchRepository._require_project_write({"role": "editor"})


def test_only_manager_can_edit_memories_and_members():
    ProjectManagementRepository._require_project_manager({"role": "manager"})
    ProjectManagementRepository._require_project_manager({"role": "owner"})
    with pytest.raises(WorkbenchPermissionError, match="只有项目管理者"):
        ProjectManagementRepository._require_project_manager({"role": "editor"})


@pytest.mark.parametrize("role", ["manager", "editor", "owner", "viewer"])
def test_manager_and_editor_can_create_own_project_conversations(role):
    WorkbenchRepository._require_project_conversation_create({"role": role})


@pytest.mark.parametrize("role", ["manager", "editor", "owner", "viewer"])
def test_manager_and_editor_can_mutate_their_own_project_conversations(role):
    WorkbenchRepository._require_conversation_write(
        {
            "project_id": "project-1",
            "project_role": role,
            "owner_username": "alice",
        },
        "alice",
    )


def test_manager_cannot_mutate_another_members_conversation():
    with pytest.raises(WorkbenchPermissionError, match="仅供管理者查看"):
        WorkbenchRepository._require_conversation_write(
            {
                "project_id": "project-1",
                "project_role": "manager",
                "owner_username": "editor-a",
            },
            "manager-a",
        )


def test_conversation_detail_query_allows_manager_or_the_conversation_creator():
    cursor = MagicMock()
    cursor.fetchone.return_value = None

    WorkbenchRepository._conversation_for_user(cursor, "editor-a", "conversation-1")

    sql, params = cursor.execute.call_args.args
    assert "pm.role IN ('manager', 'owner') OR c.owner_username = %s" in sql
    assert "pm.role IN ('manager', 'owner', 'editor', 'viewer')" in sql
    assert params == ("editor-a", "conversation-1", "editor-a", "editor-a")


def test_removed_conversation_creator_cannot_read_old_project_conversation():
    cursor = MagicMock()
    cursor.fetchone.return_value = {
        "id": "conversation-1",
        "project_id": "project-1",
        "project_role": None,
        "owner_username": "editor-a",
    }

    conversation = WorkbenchRepository._conversation_for_user(
        cursor,
        "editor-a",
        "conversation-1",
    )

    assert conversation is None


def test_non_project_conversation_is_writable_only_by_owner():
    WorkbenchRepository._require_conversation_write(
        {"project_id": None, "owner_username": "alice"},
        "alice",
    )
    with pytest.raises(WorkbenchPermissionError, match="会话写入权限"):
        WorkbenchRepository._require_conversation_write(
            {"project_id": None, "owner_username": "alice"},
            "bob",
        )


def _mock_list_connection(monkeypatch):
    cursor = MagicMock()
    cursor.fetchall.return_value = []
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    connection.cursor.return_value.__exit__.return_value = False

    @contextmanager
    def fake_connection(*args, **kwargs):
        yield connection

    monkeypatch.setattr("backend.repositories.base.get_repo_connection", fake_connection)
    return cursor


def test_editor_project_list_defaults_to_own_conversations(monkeypatch):
    cursor = _mock_list_connection(monkeypatch)
    repository = ConversationRepository()
    monkeypatch.setattr(repository, "get_project", lambda *_: {"role": "editor"})

    repository.list_conversations("editor-a", "project-1", 20)

    sql, params = cursor.execute.call_args.args
    assert "c.owner_username = %s" in sql
    assert params[:4] == ("project-1", "editor-a", "editor-a", "active")


def test_editor_cannot_filter_another_members_conversations(monkeypatch):
    repository = ConversationRepository()
    monkeypatch.setattr(repository, "get_project", lambda *_: {"role": "editor"})

    with pytest.raises(WorkbenchPermissionError, match="只能查看自己的项目会话"):
        repository.list_conversations(
            "editor-a",
            "project-1",
            20,
            conversation_owner="editor-b",
        )


def test_manager_can_list_all_members_conversations(monkeypatch):
    cursor = _mock_list_connection(monkeypatch)
    repository = ConversationRepository()
    monkeypatch.setattr(repository, "get_project", lambda *_: {"role": "manager"})

    repository.list_conversations(
        "manager-a",
        "project-1",
        20,
        include_all_members=True,
    )

    sql, params = cursor.execute.call_args.args
    assert "c.owner_username = %s" not in sql
    assert params[:3] == ("project-1", "manager-a", "active")


def test_removed_member_deleted_conversations_are_hidden_from_recycle_bin(monkeypatch):
    cursor = _mock_list_connection(monkeypatch)
    repository = ConversationRepository()

    repository.list_deleted_items("editor-a")

    sql, params = cursor.execute.call_args_list[1].args
    assert "LEFT JOIN workbench_project_members pm" in sql
    assert "pm.role IN ('manager', 'owner', 'editor', 'viewer')" in sql
    assert params == ("editor-a", "editor-a")
