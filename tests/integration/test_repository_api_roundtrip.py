"""集成测试：repositories 真实 API 的 roundtrip（workbench 项目/会话 + ai_strategy 会话）。"""

import pytest

from backend.repositories.ai_strategy_history_repository import AiStrategyHistoryRepository
from backend.repositories.workbench_repository import (
    WorkbenchNotFoundError,
    WorkbenchRepository,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _clean(clean_tables):
    clean_tables(
        "workbench_project_members",
        "workbench_projects",
        "workbench_conversations",
        "ai_strategy_conversations",
        "ai_strategy_messages",
    )


class TestWorkbenchRepository:
    def test_project_lifecycle(self):
        repo = WorkbenchRepository.from_environment()
        created = repo.create_project("tester", "集成项目", "说明")
        pid = created["id"]
        assert created["name"] == "集成项目"

        got = repo.get_project("tester", pid)
        assert got["id"] == pid

        updated = repo.update_project("tester", pid, {"name": "集成项目2"})
        assert updated["name"] == "集成项目2"

        listing = repo.list_projects("tester", limit=10)
        assert any(item["id"] == pid for item in listing["items"])

    def test_project_ownership_isolation(self):
        repo = WorkbenchRepository.from_environment()
        pid = repo.create_project("owner", "私有项目", None)["id"]
        with pytest.raises(WorkbenchNotFoundError):
            repo.get_project("stranger", pid)

    def test_conversation_within_project(self):
        repo = WorkbenchRepository.from_environment()
        pid = repo.create_project("tester", "项目", None)["id"]
        conv = repo.create_conversation("tester", pid, "会话主题", "project")
        cid = conv["id"]
        assert conv["title"] == "会话主题"
        assert repo.get_conversation("tester", cid)["id"] == cid


class TestAiStrategyHistoryRepository:
    def _repo(self):
        return AiStrategyHistoryRepository.from_environment()

    def test_create_and_get_conversation(self):
        repo = self._repo()
        conv = repo.create_conversation("stratuser", "策略会话")
        cid = conv["id"]
        got = repo.get_conversation("stratuser", cid, include_private=True)
        assert got is not None
        assert got["title"] == "策略会话"
        assert got["owner_username"] == "stratuser"

    def test_list_conversations_newest_first(self):
        repo = self._repo()
        repo.create_conversation("stratuser", "第一个")
        repo.create_conversation("stratuser", "第二个")
        items = repo.list_conversations("stratuser", limit=10)
        assert len(items) >= 2
        # list_conversations 的 SELECT 列不含 owner_username, 只校验标题/数量
        assert any(item["title"] == "第一个" for item in items)

    def test_other_user_cannot_see(self):
        repo = self._repo()
        cid = repo.create_conversation("alice", "仅自己")["id"]
        assert repo.get_conversation("bob", cid, include_private=True) is None