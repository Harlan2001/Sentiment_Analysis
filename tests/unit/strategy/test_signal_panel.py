"""因子信号面板（signal_panel）单元测试。

守三件事（需求文档 FR-1）：
1. 只有"样本量达标且跑赢多数类基准"的因子能进面板；
2. 窗口按 7 天 → 30 天回退，不硬凑数量；
3. 面板文本受 token 预算约束。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.strategy import signal_panel as sp


class _FakeCursor:
    """按 SQL 特征返回预置数据的游标，避免单测依赖真实数据库。"""

    def __init__(self, qualified_rows, event_rows):
        self._qualified_rows = qualified_rows
        self._event_rows = event_rows
        self._result = []

    def execute(self, sql: str, params=()):
        normalized = " ".join(sql.split())
        if "FROM factor_event_study" in normalized:
            self._result = self._qualified_rows
        elif "FROM news_factor nf" in normalized and "GROUP BY" not in normalized:
            start_time, end_time = params[-2], params[-1]
            self._result = [
                row
                for row in self._event_rows
                if start_time < row["pub_time"] <= end_time
            ]
        else:
            self._result = []

    def fetchall(self):
        return self._result

    def fetchone(self):
        return self._result[0] if self._result else None


def _qualified(code: str, factor_id: int, hit: float = 0.62, base: float = 0.55):
    """与 ``_qualifying_factors`` 的返回结构保持一致（键名必须是 factor_id）。"""
    return {
        "factor_code": code,
        "sample_size": 100,
        "hit_rate": hit,
        "majority_base": base,
        "factor_id": factor_id,
        "name": f"因子{code}",
        "category": "MACRO",
        "factor_type": "conceptual",
    }


def _event(factor_id: int, direction: str, offset_days: int, now: datetime):
    return {
        "factor_id": factor_id,
        "direction": direction,
        "pub_time": now - timedelta(days=offset_days),
    }


class TestQualifyingFilter:
    def test_sql_requires_beating_majority_base(self):
        """筛选条件必须由 SQL 表达，避免把跑输基准的因子取出来再过滤掉。"""
        captured: dict[str, str] = {}

        class _Cur(_FakeCursor):
            def execute(self, sql, params=()):
                captured["sql"] = " ".join(sql.split())
                super().execute(sql, params)

        sp._qualifying_factors(_Cur([], []), 5, 20)
        assert "s.sample_size >= %s" in captured["sql"]
        assert "s.hit_rate > s.majority_base" in captured["sql"]

    def test_dirty_factor_codes_excluded(self):
        """文档明确指出 NEW_FACTOR / NEW_FACTOR_1 是模型违规占位 code。"""
        captured: dict[str, str] = {}

        class _Cur(_FakeCursor):
            def execute(self, sql, params=()):
                captured["sql"] = " ".join(sql.split())
                super().execute(sql, params)

        sp._qualifying_factors(_Cur([], []), 5, 20)
        assert "NOT IN" in captured["sql"]


class TestDirectionalScore:
    def test_all_positive_scores_one(self):
        now = datetime(2026, 10, 28)
        events = [("positive", now - timedelta(days=1))]
        score, _ = sp._directional_score(events, now, 0.1)
        assert score == pytest.approx(1.0)

    def test_balanced_events_are_neutral(self):
        now = datetime(2026, 10, 28)
        events = [
            ("positive", now - timedelta(days=1)),
            ("negative", now - timedelta(days=1)),
        ]
        score, _ = sp._directional_score(events, now, 0.1)
        assert sp._score_to_direction(score) == "neutral"

    def test_recent_events_outweigh_older_ones(self):
        now = datetime(2026, 10, 28)
        events = [
            ("negative", now - timedelta(days=20)),
            ("positive", now - timedelta(days=1)),
        ]
        score, _ = sp._directional_score(events, now, 0.1)
        assert score > 0

    def test_empty_events_score_zero(self):
        score, confidence = sp._directional_score([], datetime.now(), 0.1)
        assert score == 0.0
        assert confidence == 0.0


class TestWindowFallback:
    def test_prefers_seven_day_window_when_enough_candidates(self):
        now = datetime(2026, 10, 28)
        qualified = {f"F{i}": _qualified(f"F{i}", i) for i in range(1, 5)}
        events = [_event(i, "positive", 1, now) for i in range(1, 5)]
        items, window = sp._build_items_with_fallback(
            _FakeCursor(list(qualified.values()), events),
            qualified,
            now,
            "glm",
            8,
            0.1,
            5,
        )
        assert window == 7
        assert len(items) == 4

    def test_falls_back_to_thirty_days_when_sparse(self):
        now = datetime(2026, 10, 28)
        qualified = {f"F{i}": _qualified(f"F{i}", i) for i in range(1, 5)}
        # 只有 2 个因子在 7 天内有事件，低于阈值 3，应回退到 30 天。
        events = [
            _event(1, "positive", 2, now),
            _event(2, "positive", 3, now),
            _event(3, "positive", 20, now),
            _event(4, "positive", 25, now),
        ]
        items, window = sp._build_items_with_fallback(
            _FakeCursor(list(qualified.values()), events),
            qualified,
            now,
            "glm",
            8,
            0.1,
            5,
        )
        assert window == 30
        assert len(items) == 4

    def test_no_events_returns_empty_panel_not_filler(self):
        """没有事件就返回空面板，不能编造因子凑数。"""
        now = datetime(2026, 10, 28)
        qualified = {"F1": _qualified("F1", 1)}
        items, _ = sp._build_items_with_fallback(
            _FakeCursor(list(qualified.values()), []),
            qualified,
            now,
            "glm",
            8,
            0.1,
            5,
        )
        assert items == []


class TestPanelAssembly:
    def test_neutral_factors_are_dropped(self):
        """方向不明确就不是信号，放进去只会让模型为难。"""
        now = datetime(2026, 10, 28)
        qualified = {"F1": _qualified("F1", 1)}
        events = [
            _event(1, "positive", 1, now),
            _event(1, "negative", 1, now),
        ]
        items = sp._assemble_items(
            qualified,
            {1: [(event["direction"], event["pub_time"]) for event in events]},
            now,
            0.1,
            5,
        )
        assert items == []

    def test_ranking_uses_strength_times_hit_rate(self):
        now = datetime(2026, 10, 28)
        # 1.0 × 0.50 = 0.50 < 0.8 × 0.90 = 0.72
        strong_low_hit = sp.FactorSignal(
            code="A", name="A", category="", factor_type="",
            direction="positive", signal_score=1.0, confidence=1.0,
            event_count=1, positive_count=1, negative_count=0,
            hit_rate=0.50, majority_base=0.49, sample_size=30,
            holding_days=5, latest_event_time=now,
        )
        weaker_high_hit = sp.FactorSignal(
            code="B", name="B", category="", factor_type="",
            direction="positive", signal_score=0.8, confidence=1.0,
            event_count=1, positive_count=1, negative_count=0,
            hit_rate=0.90, majority_base=0.49, sample_size=30,
            holding_days=5, latest_event_time=now,
        )
        ranked = sp._rank_and_trim([strong_low_hit, weaker_high_hit], 8)
        # 命中率高的那个综合得分更高，应排在前面。
        assert ranked[0].code == "B"

    def test_panel_size_is_capped(self):
        now = datetime(2026, 10, 28)
        items = [
            sp.FactorSignal(
                code=f"F{i}", name=f"因子{i}", category="", factor_type="",
                direction="positive", signal_score=0.5, confidence=1.0,
                event_count=1, positive_count=1, negative_count=0,
                hit_rate=0.6, majority_base=0.5, sample_size=50,
                holding_days=5, latest_event_time=now,
            )
            for i in range(20)
        ]
        assert len(sp._rank_and_trim(items, 8)) == 8


class TestFormatting:
    def test_empty_panel_says_evidence_insufficient(self):
        text = sp.format_signal_panel({"items": []})
        assert "无通过历史检验的因子" in text

    def test_formatted_panel_mentions_caliber(self):
        panel = {
            "items": [
                {
                    "code": "RISK_APPETITE",
                    "name": "风险偏好",
                    "direction": "positive",
                    "direction_label": "多",
                    "signal_score": 0.72,
                    "hit_rate": 0.618,
                    "majority_base": 0.606,
                    "sample_size": 170,
                    "event_count": 3,
                    "latest_event_time": "2026-10-27T14:12:00",
                }
            ],
            "window_days": 7,
            "model_name": "glm",
        }
        text = sp.format_signal_panel(panel)
        assert "全模型混合口径" in text
        assert "RISK_APPETITE" in text
        assert "不单独触发交易" in text

    def test_panel_text_fits_token_budget(self):
        """面板要能塞进情报包（≤4000 汉字），8 个因子也不能超。"""
        panel = {
            "items": [
                {
                    "code": f"FACTOR_CODE_{i}",
                    "name": f"因子中文名{i}",
                    "direction": "positive",
                    "direction_label": "多",
                    "signal_score": 0.72,
                    "hit_rate": 0.618,
                    "majority_base": 0.606,
                    "sample_size": 170,
                    "event_count": 3,
                    "latest_event_time": "2026-10-27T14:12:00",
                }
                for i in range(8)
            ],
            "window_days": 7,
            "model_name": "glm",
        }
        assert len(sp.format_signal_panel(panel)) < 2000