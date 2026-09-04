"""集成测试：新闻 → AI 分析 → analysis/news_factor 落库的真实业务流程。

前提(CI): MySQL 测试库已由 scripts/migrate_test_db.py 按生产 schema_full.sql 重建。
LLM 用 monkeypatch 注入(不触真实 Kingstar); factor 预置为已存在, 走真实关联落库路径。


"""

import json
from types import SimpleNamespace

import pytest

from backend.analysis import analyzer
from backend.analysis.analyzer import process_single_news_analysis
from backend.common.database import execute_query
from tests.integration.helpers import insert_factor, insert_news


def _openai_response(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=None,
    )


VALID_JSON = json.dumps(
    {
        "direction": "positive",
        "horizon": "短期",
        "reason": "降息预期支撑债市",
        "factors": [
            {"code": "RATE", "name": "利率", "category": "MACRO", "direction": "positive"}
        ],
    }
)


class TestAnalysisFlow:
    @pytest.fixture(autouse=True)
    def _fake_llm(self, monkeypatch):
        async def _fake(**kwargs):
            return _openai_response(VALID_JSON)

        monkeypatch.setattr(analyzer, "async_chat_completion", _fake)

    @pytest.fixture(autouse=True)
    def _no_real_discovery(self, monkeypatch):
        """AnalysisResultProcessor 构造会获取 discovery_manager —— 打桩,
        但不影响已预置因子的既有因子路径(不调用 process_new_factor)。"""

        class _FakeManager:
            def process_new_factor(self, **kwargs):
                return {"action": "skipped"}

        monkeypatch.setattr(
            "backend.analysis.result_processor.get_factor_discovery_manager",
            lambda: _FakeManager(),
        )

    @pytest.fixture(autouse=True)
    def _clean(self, clean_tables):
        clean_tables("news_factor", "analysis", "factor", "news")

    async def test_persists_analysis_and_factor_relation(self, mysql_conn):
        factor_id = insert_factor(mysql_conn, "RATE", "利率")
        news_id = insert_news(mysql_conn, title="央行宣布降息")

        result = await process_single_news_analysis(news_id)

        assert result["success"] is True, result.get("message")
        # analysis 表落库
        rows = execute_query(
            "SELECT direction, horizon, reason FROM analysis WHERE news_id=%s",
            (news_id,),
        )
        assert rows, "analysis 未落库"
        assert rows[0][0] == "positive"
        assert "降息" in rows[0][2]
        # news_factor 关联落库
        nf = execute_query(
            "SELECT factor_id, direction FROM news_factor WHERE news_id=%s",
            (news_id,),
        )
        assert nf and nf[0][0] == factor_id

    async def test_bad_llm_json_returns_failure_and_rolls_back(self, monkeypatch, mysql_conn):
        async def _bad(**kwargs):
            return _openai_response("抱歉，无法从新闻中提取结构化因子。")

        monkeypatch.setattr(analyzer, "async_chat_completion", _bad)
        news_id = insert_news(mysql_conn, title="无法分析的新闻")

        result = await process_single_news_analysis(news_id)

        assert result["success"] is False
        # 失败时不应该有 analysis 落库（事务回滚）
        count = execute_query(
            "SELECT COUNT(*) FROM analysis WHERE news_id=%s", (news_id,)
        )
        assert count[0][0] == 0

    async def test_llm_exception_returns_failure(self, monkeypatch, mysql_conn):
        async def _boom(**kwargs):
            raise RuntimeError("upstream 500")

        monkeypatch.setattr(analyzer, "async_chat_completion", _boom)
        news_id = insert_news(mysql_conn)
        result = await process_single_news_analysis(news_id)
        assert result["success"] is False
pytestmark = pytest.mark.integration
