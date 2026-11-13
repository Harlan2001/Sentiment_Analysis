from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from backend.routers import returns


class ScriptedCursor:
    def __init__(self, fixture: dict):
        self.fixture = fixture
        self.result = []
        self.calls = []

    def execute(self, sql, params=()):
        normalized = " ".join(sql.split())
        self.calls.append((normalized, tuple(params)))
        if normalized.startswith("SELECT DATE(n.pub_time) as d, a.direction"):
            self.result = self.fixture.get("direction_counts", [])
        elif normalized.startswith("SELECT DATE(n.pub_time) as d, f.id"):
            self.result = self.fixture.get("active_factors", [])
        elif "FROM yield_data" in normalized and "date < %s" in normalized:
            previous = self.fixture.get("previous_yields", {}).get(params[0])
            self.result = [previous] if previous else []
        elif "FROM yield_data" in normalized:
            self.result = self.fixture.get("yield_rows", {}).get(params[0], [])
        elif normalized.startswith("SELECT n.id, n.title, n.pub_time"):
            self.result = self.fixture.get("news_rows", [])
        elif normalized.startswith("SELECT nf.news_id, f.id, f.name, nf.direction"):
            self.result = self.fixture.get("news_factors", [])
        elif "FROM macro_indicator_data" in normalized:
            self.result = []
        else:
            raise AssertionError(f"Unexpected SQL: {normalized}; params={params}")

    def fetchall(self):
        return self.result

    def fetchone(self):
        return self.result[0] if self.result else None


class FakeScoreRepository:
    def __init__(self, scores):
        self.scores = scores
        self.requested_ids = None

    def get_by_news_ids(self, news_ids):
        self.requested_ids = list(news_ids)
        return {news_id: self.scores[news_id] for news_id in news_ids if news_id in self.scores}


@pytest.fixture
def route_fixture(monkeypatch):
    def install(*, scores=None, **fixture):
        cursor = ScriptedCursor(fixture)
        connection = MagicMock()
        connection.cursor.return_value = cursor

        @contextmanager
        def fake_connection():
            yield connection

        repository = FakeScoreRepository(scores or {})
        monkeypatch.setattr(returns, "get_db_connection", fake_connection)
        monkeypatch.setattr(
            returns.NewsImportanceRepository,
            "from_environment",
            classmethod(lambda cls: repository),
        )
        return cursor, repository

    return install


def _news_row(news_id, direction, pub_time):
    return (
        news_id,
        f"新闻{news_id}",
        pub_time,
        "wallstreetcn",
        direction,
        f"理由{news_id}",
        "中期",
    )


def test_calendar_enriches_static_scores_aligns_and_sorts_without_dropping_news(route_fixture):
    cursor, repository = route_fixture(
        direction_counts=[
            (date(2026, 11, 9), " Positive ", 1),
            (date(2026, 11, 9), "negative", 1),
            (date(2026, 11, 9), "neutral", 1),
        ],
        previous_yields={"10Y": (date(2026, 11, 6), Decimal("1.800"))},
        yield_rows={"10Y": [(date(2026, 11, 9), Decimal("1.820"))]},
        active_factors=[(date(2026, 11, 9), 8, "货币政策", "POLICY", 2)],
        news_rows=[
            _news_row(1, " Positive ", datetime(2026, 11, 9, 9, 0)),
            _news_row(2, "negative", datetime(2026, 11, 9, 8, 0)),
            _news_row(3, "neutral", datetime(2026, 11, 9, 10, 0)),
        ],
        news_factors=[
            (1, 8, "货币政策", "positive", "glm"),
            (1, 8, "货币政策", "negative", "kimi"),
            (1, 9, "资金面", "positive", "glm"),
        ],
        scores={
            1: {
                "importance_score": Decimal("70"),
                "signals_json": "broken-json",
                "top_category": "POLICY",
                "score_version": "v1",
            },
            2: {
                "importance_score": Decimal("90"),
                "signals_json": '{"s_hit": 0.7}',
                "top_category": "MACRO",
                "score_version": "v1",
            },
        },
    )

    payload = returns.returns_calendar(start="2026-11-09", end="2026-11-09")["data"]

    yield_10y = payload["yields_by_date"]["2026-11-09"]["10Y"]
    assert yield_10y["diff_bp"] == 2.0
    assert yield_10y["previous_date"] == "2026-11-06"
    assert payload["days"][0]["bullish_count"] == 1
    assert payload["days"][0]["active_factors"][0]["news_count"] == 2

    items = payload["news_by_date"]["2026-11-09"]
    assert [item["id"] for item in items] == [2, 1, 3]
    assert items[0]["importance_score"] == 90.0
    assert items[0]["score_signals"] == {"s_hit": 0.7}
    assert items[0]["market_alignment"] == "supporting"
    assert items[1]["market_alignment"] == "opposing"
    assert items[1]["score_signals"] is None
    assert [factor["id"] for factor in items[1]["factors"]] == [8, 9]
    assert items[2]["importance_score"] is None
    assert items[2]["market_alignment"] == "neutral"
    assert repository.requested_ids == [1, 2, 3]

    all_sql = "\n".join(sql for sql, _ in cursor.calls)
    assert "COUNT(DISTINCT nf.news_id)" in all_sql
    assert "n.pub_time >= %s AND n.pub_time < %s" in all_sql
    assert "FINAL_SCORE_EXPR" not in all_sql


def test_missing_previous_and_scores_have_explicit_nullable_contract(route_fixture):
    route_fixture(
        yield_rows={"10Y": [(date(2026, 11, 9), Decimal("1.800"))]},
        news_rows=[_news_row(1, "positive", datetime(2026, 11, 9, 9, 0))],
        scores={},
    )

    payload = returns.returns_calendar(start="2026-11-09", end="2026-11-09")["data"]

    point = payload["yields_by_date"]["2026-11-09"]["10Y"]
    assert point["diff_bp"] is None
    assert point["direction"] == "unavailable"
    assert point["previous_date"] is None
    item = payload["news_by_date"]["2026-11-09"][0]
    assert item["importance_score"] is None
    assert item["score_signals"] is None
    assert item["market_alignment"] == "unavailable"


def test_flat_market_does_not_claim_supporting_news(route_fixture):
    route_fixture(
        previous_yields={"10Y": (date(2026, 11, 6), Decimal("1.800"))},
        yield_rows={"10Y": [(date(2026, 11, 9), Decimal("1.800"))]},
        news_rows=[_news_row(1, "positive", datetime(2026, 11, 9, 9, 0))],
    )

    payload = returns.returns_calendar(start="2026-11-09", end="2026-11-09")["data"]

    assert payload["yields_by_date"]["2026-11-09"]["10Y"]["diff_bp"] == 0
    assert payload["news_by_date"]["2026-11-09"][0]["market_alignment"] == "unavailable"


def test_empty_news_skips_factor_and_score_enrichment(route_fixture):
    cursor, repository = route_fixture()

    payload = returns.returns_calendar(start="2026-11-09", end="2026-11-09")["data"]

    assert payload["news_by_date"] == {}
    assert repository.requested_ids is None
    assert not any(sql.startswith("SELECT nf.news_id, f.id") for sql, _ in cursor.calls)


@pytest.mark.parametrize(
    ("start", "end"),
    [("2026/11/09", "2026-11-09"), ("2026-11-10", "2026-11-09")],
)
def test_invalid_date_range_returns_400(start, end):
    with pytest.raises(HTTPException) as exc_info:
        returns.returns_calendar(start=start, end=end)
    assert exc_info.value.status_code == 400
