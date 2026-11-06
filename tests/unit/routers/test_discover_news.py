"""discover/news 与 recommend-rankings 路由单测（S3-3）。

不连真实数据库：脚本化假游标按 SQL 特征分派，主查询 SQL/参数被捕获用于断言
排序模式、方向归一化筛选与窗口条件；排行榜端点只测 TTL 缓存行为。
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from backend.routers import discover

# ── 假连接/假游标 ─────────────────────────────────────────────────────


class ScriptedCursor:
    """主查询返回预置行，COUNT 返回行数，其余 enrichment 查询返回空。"""

    def __init__(self, main_rows: list[tuple], capture: dict):
        self._main_rows = main_rows
        self._capture = capture
        self._result: list = []

    def execute(self, sql: str, params=()):
        normalized = " ".join(sql.split())
        if "COUNT(*)" in normalized:
            self._result = [(len(self._main_rows),)]
            return
        # 注意：主查询在方向筛选时带 best_analysis_join 子查询（内含 FROM analysis a2），
        # 故 enrichment 查询必须用各自 SELECT 列特征识别，不能只匹配表名。
        if "image_url FROM news_content_blocks" in normalized \
                or normalized.startswith("SELECT news_id, direction, reason") \
                or normalized.startswith("SELECT nf.news_id, f.id, f.name"):
            self._result = []
            return
        # 分页主查询：捕获 SQL 与参数
        self._capture["sql"] = normalized
        self._capture["params"] = list(params)
        self._result = self._main_rows

    def fetchall(self):
        return self._result

    def fetchone(self):
        return self._result[0] if self._result else None


@pytest.fixture
def patch_connection(monkeypatch):
    capture: dict = {}

    def install(main_rows: list[tuple]):
        cursor = ScriptedCursor(main_rows, capture)
        fake_conn = MagicMock()
        fake_conn.cursor.return_value = cursor

        @contextmanager
        def _fake_get_db_connection():
            yield fake_conn

        monkeypatch.setattr(discover, "get_db_connection", _fake_get_db_connection)
        return capture

    return install


def _news_row(**tail):
    """10 列分页行：前 6 列固定，后 4 列为打分字段。"""
    return (
        tail.pop("id", 1),
        tail.pop("title", "测试新闻标题"),
        tail.pop("pub_time", datetime(2026, 11, 6, 9, 30)),
        tail.pop("source", "wallstreetcn"),
        tail.pop("url", "http://example.local/1"),
        tail.pop("gid", "g-1"),
        tail.get("importance"),
        tail.get("final"),
        tail.get("signals"),
        tail.get("top_category"),
    )


def _call(**overrides):
    params = {
        "page": 1, "page_size": 20, "direction": None, "source": None,
        "sort": "latest", "days": None,
    }
    params.update(overrides)
    return discover.discover_news(**params)["data"]


# ── latest 模式（默认，行为保持兼容）──────────────────────────────────


class TestLatestMode:
    def test_default_query_keeps_time_order_and_null_scores(self, patch_connection):
        capture = patch_connection([_news_row(id=1), _news_row(id=2)])
        payload = _call()

        sql = capture["sql"]
        assert "news_importance_score" not in sql
        assert "ORDER BY n.pub_time DESC" in sql
        assert payload["total"] == 2
        item = payload["items"][0]
        assert item["source_name"] == "数据源1"
        assert item["importance_score"] is None
        assert item["final_score"] is None
        assert item["score_signals"] is None
        assert item["top_category"] is None

    def test_days_param_adds_window_clause(self, patch_connection):
        capture = patch_connection([_news_row()])
        _call(days=3)
        assert "DATE_SUB(NOW(), INTERVAL %s DAY)" in capture["sql"]
        assert 3 in capture["params"]

    def test_invalid_sort_falls_back_to_latest(self, patch_connection):
        capture = patch_connection([_news_row()])
        _call(sort="weird")
        assert "news_importance_score" not in capture["sql"]


# ── recommend 模式 ────────────────────────────────────────────────────


class TestRecommendMode:
    def test_score_join_decay_order_and_fields(self, patch_connection):
        capture = patch_connection([
            _news_row(
                id=1, importance=Decimal("80.0000"), final=Decimal("70.5000"),
                signals='{"s_direction": 1.0}', top_category="POLICY",
            ),
            _news_row(id=2),  # 未打分新闻：LEFT JOIN 全 NULL，仍在列表内
        ])
        payload = _call(sort="recommend")

        sql = capture["sql"]
        assert "LEFT JOIN news_importance_score s" in sql
        assert "s.score_version = %s" in sql
        assert "EXP(" in sql and "TIMESTAMPDIFF(MINUTE, n.pub_time, NOW())" in sql
        assert "ORDER BY final_score DESC, n.pub_time DESC, n.id DESC" in sql
        # 衰减参数（负 lambda）→ version → 分页参数顺序
        assert capture["params"][0] == pytest.approx(-0.08)
        assert capture["params"][1] == "v1"

        scored, unscored = payload["items"]
        assert scored["importance_score"] == 80.0
        assert scored["final_score"] == 70.5
        assert scored["score_signals"] == {"s_direction": 1.0}
        assert scored["top_category"] == "POLICY"
        assert unscored["final_score"] is None
        assert payload["total"] == 2

    def test_default_window_seven_days_and_clamped_to_thirty(self, patch_connection):
        capture = patch_connection([_news_row()])
        _call(sort="recommend")
        assert 7 in capture["params"]  # 缺省窗口

        capture = patch_connection([_news_row()])
        _call(sort="recommend", days=90)
        assert 30 in capture["params"]  # 硬上限
        assert 90 not in capture["params"]

    def test_malformed_signals_json_degrades_to_none(self, patch_connection):
        patch_connection([_news_row(id=1, signals="not-json", final=Decimal("1.0"))])
        item = _call(sort="recommend")["items"][0]
        assert item["score_signals"] is None
        assert item["final_score"] == 1.0


# ── 方向筛选：SQL 内归一化 ─────────────────────────────────────────────


class TestDirectionFilter:
    def test_positive_uses_normalized_in_list(self, patch_connection):
        capture = patch_connection([_news_row()])
        _call(direction="positive")
        sql = capture["sql"]
        assert "LOWER(a.direction) IN" in sql
        # 词表来自 recommend.importance 单点维护，中文词必须进 IN-list
        for word in ("positive", "bullish", "利多", "利好"):
            assert word in capture["params"]

    def test_negative_words(self, patch_connection):
        capture = patch_connection([_news_row()])
        _call(direction="negative")
        for word in ("negative", "bearish", "利空"):
            assert word in capture["params"]

    def test_unknown_direction_ignored(self, patch_connection):
        capture = patch_connection([_news_row()])
        _call(direction="nonsense")
        assert "LOWER(a.direction) IN" not in capture["sql"]


# ── 排行榜端点 TTL 缓存 ────────────────────────────────────────────────


class TestRecommendRankingsCache:
    @pytest.fixture(autouse=True)
    def _clear_cache(self):
        discover._rankings_cache.clear()
        yield
        discover._rankings_cache.clear()

    def test_second_call_within_ttl_serves_cache(self, monkeypatch):
        builder = MagicMock(return_value={"days": 7, "top_news": []})
        monkeypatch.setattr(discover, "build_rankings", builder)

        first = discover.recommend_rankings(days=7)["data"]
        second = discover.recommend_rankings(days=7)["data"]

        assert first == second
        builder.assert_called_once_with(7)

    def test_different_days_have_independent_cache_entries(self, monkeypatch):
        builder = MagicMock(side_effect=lambda d: {"days": d})
        monkeypatch.setattr(discover, "build_rankings", builder)

        discover.recommend_rankings(days=7)
        discover.recommend_rankings(days=30)
        discover.recommend_rankings(days=7)  # 命中缓存

        assert builder.call_count == 2
        builder.assert_any_call(7)
        builder.assert_any_call(30)
