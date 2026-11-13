from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from backend.recommend.importance import parse_score_signals
from backend.returns.rules import (
    build_yield_change_map,
    classify_market_alignment,
    direction_label,
    sort_news_by_importance,
)


class TestYieldChanges:
    def test_monday_uses_previous_valid_trading_day_and_real_flat_is_zero(self):
        result = build_yield_change_map(
            rows=[
                (date(2026, 11, 6), Decimal("1.800")),
                (date(2026, 11, 9), Decimal("1.820")),
                (date(2026, 11, 10), Decimal("1.820")),
            ],
            previous=None,
            start=date(2026, 11, 9),
            end=date(2026, 11, 10),
            label="10年",
        )

        assert result["2026-11-09"] == {
            "label": "10年",
            "value": 1.82,
            "diff_bp": 2.0,
            "direction": "up",
            "previous_date": "2026-11-06",
        }
        assert result["2026-11-10"]["diff_bp"] == 0
        assert result["2026-11-10"]["direction"] == "flat"
        assert result["2026-11-10"]["previous_date"] == "2026-11-09"

    def test_range_start_uses_latest_observation_before_start(self):
        result = build_yield_change_map(
            rows=[(date(2026, 10, 9), Decimal("1.750"))],
            previous=(date(2026, 9, 30), Decimal("1.700")),
            start=date(2026, 10, 9),
            end=date(2026, 10, 9),
            label="10年",
        )

        assert result["2026-10-09"]["diff_bp"] == 5.0
        assert result["2026-10-09"]["previous_date"] == "2026-09-30"

    def test_missing_previous_is_unavailable_not_fake_zero(self):
        result = build_yield_change_map(
            rows=[(date(2026, 11, 9), Decimal("1.800"))],
            previous=None,
            start=date(2026, 11, 9),
            end=date(2026, 11, 9),
            label="10年",
        )

        assert result["2026-11-09"]["diff_bp"] is None
        assert result["2026-11-09"]["direction"] == "unavailable"
        assert result["2026-11-09"]["previous_date"] is None

    def test_days_without_market_rows_are_not_fabricated(self):
        result = build_yield_change_map(
            rows=[(date(2026, 11, 6), Decimal("1.800"))],
            previous=None,
            start=date(2026, 11, 6),
            end=date(2026, 11, 8),
            label="10年",
        )

        assert list(result) == ["2026-11-06"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" Positive ", "利多"),
        ("BULLISH", "利多"),
        ("利好", "利多"),
        (" negative ", "利空"),
        ("down", "利空"),
        ("neutral", "中性"),
        ("unexpected", "中性"),
        (None, "中性"),
    ],
)
def test_direction_label_uses_shared_normalization(raw, expected):
    assert direction_label(raw) == expected


@pytest.mark.parametrize(
    ("diff_bp", "news_direction", "expected"),
    [
        (2.0, "positive", "opposing"),
        (2.0, "negative", "supporting"),
        (-2.0, "positive", "supporting"),
        (-2.0, "negative", "opposing"),
        (2.0, "neutral", "neutral"),
        (2.0, "unknown", "unavailable"),
        (0.0, "positive", "unavailable"),
        (None, "negative", "unavailable"),
        (None, "neutral", "unavailable"),
    ],
)
def test_market_alignment_matrix(diff_bp, news_direction, expected):
    assert classify_market_alignment(diff_bp, news_direction) == expected


def test_news_sort_uses_static_score_then_time_and_id_and_keeps_unscored():
    items = [
        {"id": 1, "pub_time": "2026-11-09 09:00:00", "importance_score": None},
        {"id": 2, "pub_time": "2026-11-09 08:00:00", "importance_score": Decimal("80")},
        {"id": 3, "pub_time": "2026-11-09 09:00:00", "importance_score": Decimal("80")},
        {"id": 4, "pub_time": "2026-11-08 09:00:00", "importance_score": Decimal("90")},
        {"id": 5, "pub_time": "2026-11-10 09:00:00", "importance_score": Decimal("0")},
    ]

    ordered = sort_news_by_importance(items)

    assert [item["id"] for item in ordered] == [4, 3, 2, 5, 1]
    assert ordered[0]["importance_score"] == 90  # static score; no NOW()-based decay
    assert len(ordered) == len(items)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"s_hit": 0.5}, {"s_hit": 0.5}),
        ('{"s_hit": 0.5}', {"s_hit": 0.5}),
        ("not-json", None),
        ("[1, 2]", None),
        (None, None),
    ],
)
def test_parse_score_signals_is_fault_tolerant(raw, expected):
    assert parse_score_signals(raw) == expected
