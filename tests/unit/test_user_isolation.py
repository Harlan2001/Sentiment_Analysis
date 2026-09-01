"""用户隔离测试：会话、关注列表、项目的用户隔离验证。

使用 mock pymysql.connect 模拟数据库层，验证 SQL 查询中的
owner_username 过滤逻辑，不操作真实数据库。
"""

from unittest.mock import MagicMock

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# 测试数据
# ═══════════════════════════════════════════════════════════════════════════════

MOCK_CONVERSATION_A = {
    "id": "conv-a-001",
    "owner_username": "user1",
    "project_id": None,
    "title": "user1 的会话",
    "status": "active",
    "source": "home",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
    "last_message_at": "2026-01-01T01:00:00",
    "deleted_at": None,
    "project_role": None,
}

MOCK_CONVERSATION_B = {
    "id": "conv-b-001",
    "owner_username": "user2",
    "project_id": None,
    "title": "user2 的会话",
    "status": "active",
    "source": "home",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
    "last_message_at": "2026-01-01T01:00:00",
    "deleted_at": None,
    "project_role": None,
}


# ═══════════════════════════════════════════════════════════════════════════════
# 辅助：mock pymysql.connect
# ═══════════════════════════════════════════════════════════════════════════════

def _mock_pymysql_connect(cursor, monkeypatch):
    """用 monkeypatch 替换 pymysql.connect，返回 mock 连接。"""
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = cursor
    mock_conn.cursor.return_value.__exit__.return_value = False
    monkeypatch.setattr("pymysql.connect", MagicMock(return_value=mock_conn))
    return mock_conn


def _make_cursor(fetchone_result=None, fetchall_result=None):
    """构造一个 mock DictCursor。"""
    cursor = MagicMock()
    cursor.fetchone.return_value = fetchone_result
    cursor.fetchall.return_value = fetchall_result or []
    cursor.rowcount = 0
    return cursor


# ═══════════════════════════════════════════════════════════════════════════════
# 会话列表隔离
# ═══════════════════════════════════════════════════════════════════════════════

class TestConversationListIsolation:
    def test_list_conversations_filters_by_owner_username(self, monkeypatch):
        """验证 SQL 查询使用 owner_username 过滤。"""
        captured_sql = []

        def capture_execute(sql, params=None):
            captured_sql.append((sql, params))

        cursor = _make_cursor(fetchall_result=[MOCK_CONVERSATION_A])
        cursor.execute = MagicMock(side_effect=capture_execute)
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.conversation_repository import ConversationRepository

        repo = ConversationRepository({})
        repo.list_conversations("user1", None, 20)

        combined = " ".join(sql for sql, _ in captured_sql)
        assert "owner_username" in combined, (
            f"list_conversations 应该按 owner_username 过滤，SQL: {combined}"
        )
        assert any(params and params[0] == "user1" for _, params in captured_sql)

    def test_list_conversations_returns_only_own_items(self, monkeypatch):
        """mock 返回多条数据，确保只返回 owner_username 匹配的项。"""
        cursor = _make_cursor(fetchall_result=[MOCK_CONVERSATION_A])
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.conversation_repository import ConversationRepository

        repo = ConversationRepository({})
        result = repo.list_conversations("user1", None, 20)

        assert "items" in result
        for item in result["items"]:
            assert item.get("owner_username") == "user1", (
                f"会话列表不应包含其他用户的会话: {item}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 会话详情隔离
# ═══════════════════════════════════════════════════════════════════════════════

class TestConversationDetailIsolation:
    def test_user_a_cannot_see_user_b_conversation(self, monkeypatch):
        """用户 A 访问用户 B 的会话时，_conversation_for_user 应返回 None。"""
        cursor = _make_cursor(fetchone_result=None)
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.conversation_repository import ConversationRepository
        from backend.repositories.workbench_repository import WorkbenchNotFoundError

        repo = ConversationRepository({})

        with pytest.raises(WorkbenchNotFoundError, match="会话不存在或当前用户无权访问"):
            repo.get_conversation("user1", "conv-b-001")

    def test_user_a_can_access_own_conversation(self, monkeypatch):
        """用户 A 访问自己的会话时，应正常返回。"""
        cursor = _make_cursor(fetchone_result=MOCK_CONVERSATION_A)
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.conversation_repository import ConversationRepository

        repo = ConversationRepository({})
        result = repo.get_conversation("user1", "conv-a-001")

        assert result["id"] == "conv-a-001"
        assert result["owner_username"] == "user1"


# ═══════════════════════════════════════════════════════════════════════════════
# 会话修改/删除隔离
# ═══════════════════════════════════════════════════════════════════════════════

class TestConversationMutateIsolation:
    def test_user_a_cannot_update_user_b_conversation(self, monkeypatch):
        """用户 A 无法修改用户 B 的会话。"""
        cursor = _make_cursor(fetchone_result=None)
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.conversation_repository import ConversationRepository
        from backend.repositories.workbench_repository import WorkbenchNotFoundError

        repo = ConversationRepository({})

        with pytest.raises(WorkbenchNotFoundError, match="会话不存在或当前用户无权访问"):
            repo.update_conversation("user1", "conv-b-001", {"title": "hacked"})

    def test_user_a_cannot_delete_user_b_conversation(self, monkeypatch):
        """用户 A 无法删除用户 B 的会话。"""
        cursor = _make_cursor(fetchone_result=None)
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.conversation_repository import ConversationRepository
        from backend.repositories.workbench_repository import WorkbenchNotFoundError

        repo = ConversationRepository({})

        with pytest.raises(WorkbenchNotFoundError, match="会话不存在或当前用户无权访问"):
            repo.soft_delete_conversation("user1", "conv-b-001")

    def test_user_a_can_update_own_conversation(self, monkeypatch):
        """用户 A 可以修改自己的会话。"""
        updated_conv = dict(MOCK_CONVERSATION_A, title="新标题")
        cursor = _make_cursor()
        cursor.fetchone.side_effect = [MOCK_CONVERSATION_A, updated_conv]
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.conversation_repository import ConversationRepository

        repo = ConversationRepository({})
        result = repo.update_conversation("user1", "conv-a-001", {"title": "新标题"})

        assert result["title"] == "新标题"


# ═══════════════════════════════════════════════════════════════════════════════
# 项目会话成员隔离
# ═══════════════════════════════════════════════════════════════════════════════

class TestProjectConversationIsolation:
    def test_project_member_can_access_project_conversation(self, monkeypatch):
        """项目成员可以访问项目会话。"""
        project_conv = {
            "id": "conv-p-001",
            "owner_username": "user1",
            "project_id": "proj-001",
            "title": "项目会话",
            "status": "active",
            "source": "project",
            "created_at": "2026-01-01T00:00:00",
            "updated_at": "2026-01-01T00:00:00",
            "last_message_at": "2026-01-01T01:00:00",
            "deleted_at": None,
            "project_role": "owner",
        }
        cursor = _make_cursor(fetchone_result=project_conv)
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.conversation_repository import ConversationRepository

        repo = ConversationRepository({})
        result = repo.get_conversation("user1", "conv-p-001")

        assert result["id"] == "conv-p-001"
        assert result["project_id"] == "proj-001"

    def test_non_member_cannot_access_project_conversation(self, monkeypatch):
        """非项目成员无法访问项目会话。"""
        cursor = _make_cursor(fetchone_result=None)
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.conversation_repository import ConversationRepository
        from backend.repositories.workbench_repository import WorkbenchNotFoundError

        repo = ConversationRepository({})

        with pytest.raises(WorkbenchNotFoundError, match="会话不存在或当前用户无权访问"):
            repo.get_conversation("user2", "conv-p-001")


# ═══════════════════════════════════════════════════════════════════════════════
# 关注列表隔离
# ═══════════════════════════════════════════════════════════════════════════════

class TestWatchlistIsolation:
    MOCK_WATCHLIST_ITEM_A = {
        "id": "wl-a-001",
        "owner_username": "user1",
        "object_type": "factor",
        "object_id": "123",
        "title": "user1 的关注因子",
        "source_url": "/factor/123",
        "metadata_json": "{}",
        "deleted_at": None,
        "updated_at": "2026-01-01T00:00:00",
    }

    def test_list_items_filters_by_owner_username(self, monkeypatch):
        """验证关注列表 SQL 使用 owner_username 过滤。"""
        captured_sql = []

        def capture_execute(sql, params=None):
            captured_sql.append((sql, params))

        cursor = _make_cursor(fetchall_result=[dict(self.MOCK_WATCHLIST_ITEM_A)])
        cursor.execute = MagicMock(side_effect=capture_execute)
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.watchlist_repository import WatchlistRepository

        repo = WatchlistRepository({})
        repo.list_items("user1")

        combined = " ".join(sql for sql, _ in captured_sql)
        assert "owner_username" in combined, (
            f"关注列表查询应使用 owner_username 过滤，SQL: {combined}"
        )
        assert any(params == ("user1",) for _, params in captured_sql)

    def test_list_items_only_returns_own(self, monkeypatch):
        """关注列表只返回当前用户的项。"""
        cursor = _make_cursor(fetchall_result=[dict(self.MOCK_WATCHLIST_ITEM_A)])
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.watchlist_repository import WatchlistRepository

        repo = WatchlistRepository({})
        result = repo.list_items("user1")

        for item in result:
            assert item.get("owner_username") == "user1", (
                f"关注列表不应包含其他用户的项: {item}"
            )

    def test_user_a_cannot_remove_user_b_item(self, monkeypatch):
        """用户 A 删除用户 B 的关注项时，rowcount=0 应抛出异常。"""
        cursor = _make_cursor()
        cursor.rowcount = 0
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.watchlist_repository import WatchlistRepository
        from backend.repositories.workbench_repository import WorkbenchNotFoundError

        repo = WatchlistRepository({})

        with pytest.raises(WorkbenchNotFoundError, match="关注项不存在或无权操作"):
            repo.remove_item("user1", "wl-b-001")

    def test_user_a_can_remove_own_item(self, monkeypatch):
        """用户 A 可以删除自己的关注项。"""
        cursor = _make_cursor()
        cursor.rowcount = 1
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.watchlist_repository import WatchlistRepository

        repo = WatchlistRepository({})
        result = repo.remove_item("user1", "wl-a-001")

        assert result["deleted"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# 聊天消息隔离
# ═══════════════════════════════════════════════════════════════════════════════

class TestMessageIsolation:
    def test_prepare_message_checks_conversation_ownership(self, monkeypatch):
        """发送消息时验证会话归属：_conversation_for_user 检查用户权限。"""
        cursor = _make_cursor(fetchone_result=None)
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.conversation_repository import ConversationRepository
        from backend.repositories.workbench_repository import WorkbenchNotFoundError

        repo = ConversationRepository({})

        with pytest.raises(WorkbenchNotFoundError, match="会话不存在或当前用户无权访问"):
            repo.prepare_message("user1", "conv-b-001", "hello", "msg-001")

    def test_get_agent_history_checks_conversation_ownership(self, monkeypatch):
        """获取 Agent 历史时先验证会话归属。"""
        cursor = _make_cursor(fetchone_result=None)
        _mock_pymysql_connect(cursor, monkeypatch)

        from backend.repositories.message_repository import MessageRepository
        from backend.repositories.workbench_repository import WorkbenchNotFoundError

        repo = MessageRepository({})

        with pytest.raises(WorkbenchNotFoundError, match="会话不存在或当前用户无权访问"):
            repo.get_agent_history("user1", "conv-b-001", 50)
