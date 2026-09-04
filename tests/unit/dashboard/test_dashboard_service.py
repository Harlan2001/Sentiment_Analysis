"""dashboard/dashboard_service：覆盖率/时段标签/画像行映射的纯函数单测（不触 DB）。"""

from datetime import datetime

import pytest

from backend.dashboard.dashboard_service import (
    _coverage_pct,
    peak_slot_label,
    profile_row_to_dict,
)


class TestCoveragePct:
    def test_zero_total(self):
        assert _coverage_pct(0, 0, 0) == 0

    def test_normal_percentage_rounded(self):
        assert _coverage_pct(2, 3, 0) == 66.67

    def test_pending_caps_near_full(self):
        assert _coverage_pct(999, 1000, 1) == 99.99

    def test_pending_below_threshold_stays_normal(self):
        assert _coverage_pct(900, 1000, 0) == 90.0


class TestPeakSlotLabel:
    def test_none(self):
        assert peak_slot_label(None) == "未知"

    @pytest.mark.parametrize(
        "hour,label",
        [
            (6, "上午"), (11, "上午"),
            (12, "午间"), (13, "午间"),
            (14, "下午"), (17, "下午"),
            (18, "晚间"), (21, "晚间"),
            (0, "深夜"), (5, "深夜"), (22, "深夜"), (23, "深夜"),
        ],
    )
    def test_hour_buckets(self, hour, label):
        assert peak_slot_label(hour) == label


class TestProfileRowToDict:
    @staticmethod
    def _row():
        return (
            1, 10, "user1",          # id, user_id, username
            5, 100, 3600,            # sessions, page_views, active_sec
            datetime(2026, 8, 1), datetime(2026, 9, 1, 10, 30),  # first/last visit
            3, 120, 4.2,             # active_days, avg_session, avg_daily_pages
            '{"a": 1}', 9, '{"1":2}',
            8, 1, 1, 0, 1,           # distinct_pages, flags(is_power, report, strategy)
            0.2,                     # churn_risk_score
            datetime(2026, 9, 1, 10, 30), "v2", datetime(2026, 9, 1, 10, 30),
        )

    def test_scalar_mapping(self):
        d = profile_row_to_dict(self._row())
        assert d["user_id"] == 10
        assert d["username"] == "user1"
        assert d["total_sessions"] == 5
        assert d["distinct_pages_30d"] == 8

    def test_datetime_fields(self):
        d = profile_row_to_dict(self._row())
        # fmt_dt 默认只到日期; to_iso 输出 ISO 时间
        assert d["first_visit"] == "2026-08-01"
        assert d["last_visit"] == "2026-09-01T10:30:00"

    def test_json_fields_parsed(self):
        d = profile_row_to_dict(self._row())
        assert d["page_affinity"] == {"a": 1}
        assert d["hour_distribution"] == {"1": 2}

    def test_numeric_and_bool_conversions(self):
        d = profile_row_to_dict(self._row())
        assert d["churn_risk_score"] == 0.2
        assert d["avg_daily_pages_30d"] == 4.2
        assert d["is_power_user"] is True
        assert d["is_report_focused"] is False
        assert d["is_strategy_focused"] is True

    def test_none_columns_tolerated(self):
        row = self._row()
        # first_visit / last_visit / json 字段为空
        row = tuple(None if i in (6, 11, 13) else v for i, v in enumerate(row))
        d = profile_row_to_dict(row)
        assert d["first_visit"] is None
        assert d["page_affinity"] == {}
        assert d["hour_distribution"] == {}