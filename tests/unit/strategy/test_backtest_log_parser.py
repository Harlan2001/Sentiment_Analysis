"""backtest_log_parser 单测（B2 / S2-4）。

异常样本直接回放 S0 真实日志 fixture（会话 #60：29 单废单、Sharpe -42182），
另构造健康样本对照；逐笔成交不在日志里，解析器只负责 STATISTICS。
"""

from __future__ import annotations

from pathlib import Path

from backend.strategy.backtest_log_parser import (
    TIER_CORE,
    TIER_OTHER,
    TIER_QUALITY,
    TIER_RISK,
    detect_metric_anomalies,
    parse_backtest_metrics,
    parse_metric_number,
    parse_statistics,
)

FIXTURE = (
    Path(__file__).parent / "fixtures" / "s0_ghost_orders_statistics.txt"
).read_text(encoding="utf-8")


class TestParseMetricNumber:
    def test_percent_money_and_plain_numbers(self):
        assert parse_metric_number("2.1%") == 2.1
        assert parse_metric_number("-42182.563") == -42182.563
        assert parse_metric_number("$1,000,000.24") == 1000000.24
        assert parse_metric_number("0") == 0.0

    def test_non_numeric_is_none(self):
        assert parse_metric_number("FCT_T_MAIN.MockMinuteBar 2S") is None
        assert parse_metric_number("83a25f94e4116584f") is None
        assert parse_metric_number("") is None


class TestParseStatistics:
    def test_ghost_fixture_metrics_are_complete_and_tiered(self):
        metrics = parse_statistics(FIXTURE)
        # 28 行 STATISTICS，TRACE/DATA USAGE 不算指标。
        assert len(metrics) == 28
        by_label = {m["label"]: m for m in metrics}

        assert by_label["Total Orders"]["value"] == "29"
        assert by_label["Total Orders"]["numeric"] == 29.0
        assert by_label["Sharpe Ratio"]["numeric"] == -42182.563

        assert by_label["Total Orders"]["tier"] == TIER_CORE
        assert by_label["Compounding Annual Return"]["tier"] == TIER_CORE
        assert by_label["Drawdown"]["tier"] == TIER_CORE
        assert by_label["Win Rate"]["tier"] == TIER_CORE
        assert by_label["Net Profit"]["tier"] == TIER_CORE

        assert by_label["Profit-Loss Ratio"]["tier"] == TIER_QUALITY
        assert by_label["Expectancy"]["tier"] == TIER_QUALITY
        assert by_label["Total Fees"]["tier"] == TIER_QUALITY

        assert by_label["Sharpe Ratio"]["tier"] == TIER_RISK
        assert by_label["Annual Standard Deviation"]["tier"] == TIER_RISK

        # 工程字段默认折叠。
        assert by_label["OrderListHash"]["tier"] == TIER_OTHER
        assert by_label["Lowest Capacity Asset"]["tier"] == TIER_OTHER

    def test_non_statistics_lines_are_ignored(self):
        log = (
            "20261030 TRACE:: Engine.Run()\n"
            "STATISTICS:: Total Orders 3\n"
            "DATA USAGE:: Total data requests 2\n"
        )
        metrics = parse_statistics(log)
        assert [m["label"] for m in metrics] == ["Total Orders"]

    def test_unknown_statistic_is_retained_not_dropped(self):
        # 未知指标走「标签: 值」/双空格切分；无分隔符时整条保留为标签，
        # 不臆造数值（与原 service 行为一致）。
        metrics = parse_statistics("STATISTICS:: Some Future Metric: 12.5\n")
        assert metrics[0]["label"] == "Some Future Metric"
        assert metrics[0]["value"] == "12.5"
        assert metrics[0]["tier"] == TIER_OTHER

        metrics = parse_statistics("STATISTICS:: Mystery Metric\n")
        assert metrics[0]["label"] == "Mystery Metric"
        assert metrics[0]["value"] == ""

    def test_empty_log(self):
        assert parse_statistics("") == []
        assert parse_backtest_metrics("") == {"metrics": [], "anomalies": []}


class TestAnomalies:
    def test_ghost_fixture_flags_ratio_explosion(self):
        result = parse_backtest_metrics(FIXTURE)
        by_key = {m["key"]: m for m in result["metrics"]}
        flagged = {a["key"] for a in result["anomalies"]}

        # |Sharpe|=42182、|Sortino|=39432，远超 10；波动率为 0 是根因。
        assert flagged == {"sharpe_ratio", "sortino_ratio"}
        assert "除式爆炸" in by_key["sharpe_ratio"]["anomaly"]
        for key in flagged:
            assert by_key[key]["anomaly"]

    def test_healthy_ratios_are_not_flagged(self):
        log = (
            "STATISTICS:: Total Orders 29\n"
            "STATISTICS:: Annual Standard Deviation 0.084\n"
            "STATISTICS:: Sharpe Ratio 1.32\n"
            "STATISTICS:: Sortino Ratio 1.87\n"
        )
        anomalies = detect_metric_anomalies(parse_statistics(log))
        assert anomalies == []

    def test_zero_volatility_without_orders_is_not_risk_anomaly(self):
        # 无成交是验收门 no_trade 的职责，风险层不重复告警。
        log = (
            "STATISTICS:: Total Orders 0\n"
            "STATISTICS:: Annual Standard Deviation 0\n"
            "STATISTICS:: Sharpe Ratio 0\n"
        )
        anomalies = detect_metric_anomalies(parse_statistics(log))
        assert anomalies == []

    def test_borderline_values(self):
        assert detect_metric_anomalies(parse_statistics(
            "STATISTICS:: Sharpe Ratio 10.0\n"
        )) == []
        flagged = detect_metric_anomalies(parse_statistics(
            "STATISTICS:: Sharpe Ratio -10.1\n"
        ))
        assert [a["key"] for a in flagged] == ["sharpe_ratio"]
