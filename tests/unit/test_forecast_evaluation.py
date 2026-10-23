"""预测诊断单元测试：口径正确性（多数类基准、交易日对齐、防小样本误导）。

全部使用构造的假数据注入，不连数据库。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.evaluation import forecast_evaluation as fe


def _business_days(start: date, count: int) -> list[date]:
    """构造 count 个工作日（跳过周末），模拟交易日序列。"""
    days: list[date] = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


class _FakeCalendar(fe._TradingCalendar):
    """用构造的日期序列 + 指定收益率建日历，避免依赖数据库。"""

    def __init__(self, dates: list[date], values: list[float]):
        super().__init__(list(zip(dates, values)))


def _report(trade_date: date, *, up: bool, up_bp: float, down_bp: float, confidence: float = 0.7):
    """构造一份只含指定方向预测的报告 prediction 结构。"""
    return {
        "trade_date": trade_date,
        "model_name": "test",
        "prompt_version": "v-test",
        "prediction": {
            "预测结果": {
                "日": {
                    "上涨概率": 0.7 if up else 0.3,
                    "下跌概率": 0.3 if up else 0.7,
                    "上涨基点": up_bp,
                    "下跌基点": down_bp,
                    "置信度": confidence,
                }
            }
        },
    }


class TestTradingCalendar:
    def test_uses_trading_day_sequence_not_calendar_day(self):
        """T+N 必须按交易日序号推进：跨周末的 T+1 应是下一个交易日。"""
        days = _business_days(date(2026, 3, 2), 10)  # 周一开盘
        calendar = _FakeCalendar(days, [1.0 + i * 0.01 for i in range(10)])

        friday_index = calendar.index_of(days[4])
        assert friday_index == 4
        # 周一（days[5]）是周五的"下一个交易日"，即使相隔 3 个自然日
        assert calendar.value_at_offset(friday_index, 1) == pytest.approx(1.05)

    def test_non_trading_date_returns_none(self):
        """非交易日不应被对齐到邻近日期。"""
        days = _business_days(date(2026, 3, 2), 5)
        calendar = _FakeCalendar(days, [1.0] * 5)
        assert calendar.index_of(date(2026, 3, 1)) is None  # 周日


class TestMajorityBase:
    def test_base_is_majority_direction_not_half(self):
        """多数类基准 = 事后猜多数方向的命中率，不是 50%。"""
        # 4 条中 3 条上行：无脑猜"上行"命中 3/4
        records = [
            {"predicted_up": True, "actual_bp": 1.0, "hit": True, "abs_error_bp": 0.1},
            {"predicted_up": True, "actual_bp": 2.0, "hit": True, "abs_error_bp": 0.1},
            {"predicted_up": True, "actual_bp": 3.0, "hit": True, "abs_error_bp": 0.1},
            {"predicted_up": True, "actual_bp": -1.0, "hit": False, "abs_error_bp": 0.1},
        ]
        summary = fe._summarize(records)
        assert summary["majority_base"] == 0.75
        assert summary["hit_rate"] == 0.75

    def test_quality_risk_when_interval_below_base(self):
        """命中率置信区间整体低于基准 → 判定为 risk。"""
        records = [
            {"predicted_up": True, "actual_bp": 1.0, "hit": False, "abs_error_bp": 0.1}
        ] * 90 + [
            {"predicted_up": True, "actual_bp": 1.0, "hit": True, "abs_error_bp": 0.1}
        ] * 10
        summary = fe._summarize(records)
        assert summary["quality"] == "risk"

    def test_quality_effective_when_interval_above_base(self):
        """命中率显著高于基准 → 判定为 effective。"""
        # 构造实际方向五五开（基准 0.5），但预测命中 95%：
        # 上行 50 条全部命中 + 下行 50 条全部命中，再掺入 5 条反向错判
        records = (
            [
                {"predicted_up": True, "actual_bp": 1.0, "hit": True, "abs_error_bp": 0.1}
            ]
            * 50
            + [
                {"predicted_up": False, "actual_bp": -1.0, "hit": True, "abs_error_bp": 0.1}
            ]
            * 45
            + [
                {"predicted_up": True, "actual_bp": -1.0, "hit": False, "abs_error_bp": 0.1}
            ]
            * 5
        )
        summary = fe._summarize(records)
        # 上行 50 / 下行 50 → 基准 0.5；命中 95/100 → 显著高于基准
        assert summary["majority_base"] == 0.5
        assert summary["hit_rate"] == 0.95
        assert summary["quality"] == "effective"

    def test_empty_sample_is_neutral(self):
        """无样本时不臆断，返回 noise 且各统计量为 None。"""
        summary = fe._summarize([])
        assert summary["sample_size"] == 0
        assert summary["hit_rate"] is None
        assert summary["quality"] == "noise"


class TestEvaluation:
    def test_direction_takes_value_matching_actual_direction(self):
        """误差必须取与实际方向一致的基点：看涨用上涨基点，看跌用下跌基点。"""
        days = _business_days(date(2026, 3, 2), 4)
        # 收益率上行：从 1.00 到 1.05，实际 +5bp
        calendar = _FakeCalendar(days, [1.00, 1.05, 1.06, 1.07])
        reports = [_report(days[0], up=True, up_bp=4.0, down_bp=-9.0)]

        records = fe._evaluate_reports(reports, calendar)["日"]
        assert len(records) == 1
        assert records[0]["actual_bp"] == pytest.approx(5.0)
        # 预测看涨 → 应与 +4.0 比较，误差 1.0，而不是与 -9.0 比较
        assert records[0]["abs_error_bp"] == pytest.approx(1.0)

    def test_unevaluated_when_horizon_not_reached(self):
        """尚未到期的预测不参与评估（避免把未发生的当成错误）。"""
        days = _business_days(date(2026, 3, 2), 2)
        calendar = _FakeCalendar(days, [1.00, 1.01])
        reports = [_report(days[1], up=True, up_bp=4.0, down_bp=-9.0)]
        assert fe._evaluate_reports(reports, calendar)["日"] == []

    def test_hit_uses_actual_direction(self):
        """命中判定：预测看涨且收益率上行才算命中。"""
        days = _business_days(date(2026, 3, 2), 4)
        calendar = _FakeCalendar(days, [1.00, 1.05, 1.06, 1.07])  # 上行
        hit = fe._evaluate_reports(
            [_report(days[0], up=True, up_bp=1.0, down_bp=-1.0)], calendar
        )["日"]
        miss = fe._evaluate_reports(
            [_report(days[0], up=False, up_bp=1.0, down_bp=-1.0)], calendar
        )["日"]
        assert hit[0]["hit"] is True
        assert miss[0]["hit"] is False


class TestConfidenceBuckets:
    def test_small_bucket_marked_insufficient(self):
        """分档样本不足时必须标记，由前端隐藏，避免小样本误导。"""
        records = [
            {
                "confidence": 0.9,
                "predicted_up": True,
                "actual_bp": 1.0,
                "hit": True,
                "abs_error_bp": 0.1,
            }
        ]
        buckets = fe._confidence_buckets(records)
        high = next(b for b in buckets if b["label"] == "≥0.65")
        assert high["sample_size"] == 1
        assert high["sufficient"] is False

    def test_bucket_boundaries_are_half_open(self):
        """分档边界为左闭右开，0.65 归入 ≥0.65 档。"""
        records = [
            {
                "confidence": 0.65,
                "predicted_up": True,
                "actual_bp": 1.0,
                "hit": True,
                "abs_error_bp": 0.1,
            }
        ]
        buckets = fe._confidence_buckets(records)
        assert next(b for b in buckets if b["label"] == "≥0.65")["sample_size"] == 1
        assert next(b for b in buckets if b["label"] == "0.50-0.65")["sample_size"] == 0


class TestCalibration:
    def test_series_separates_predicted_and_actual_up_share(self):
        """校准度序列分离"预测看涨占比"与"实际上涨占比"，用于识别偏置。"""
        records = [
            {"trade_date": "2026-03-02", "predicted_up": True, "actual_bp": -1.0},
            {"trade_date": "2026-03-03", "predicted_up": True, "actual_bp": -2.0},
            {"trade_date": "2026-04-01", "predicted_up": False, "actual_bp": 1.0},
        ]
        series = fe._calibration_series(records)
        march = next(item for item in series if item["month"] == "2026-03")
        assert march["predicted_up_share"] == 1.0  # 全预测看涨
        assert march["actual_up_share"] == 0.0  # 实际全跌 → 明显偏置