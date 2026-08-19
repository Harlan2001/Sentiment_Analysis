from backend.integrations.dream.service import (
    _backtest_is_complete,
    _clean_strategy_description,
    _merge_backtest_log,
    _parse_backtest_metrics,
    _summarize_backtest_log,
)
from backend.strategy.dream_strategy_prompt import (
    _default_trading_parameters,
    _resolve_instrument,
)


def test_backtest_is_not_failed_merely_because_the_boolean_defaults_to_false():
    assert not _backtest_is_complete(
        {"backtest_passed": False, "backtest_exit_code": -1, "backtest_log": ""}
    )
    assert not _backtest_is_complete(
        {"backtest_passed": False, "backtest_exit_code": 0, "backtest_log": ""}
    )
    assert _backtest_is_complete(
        {"backtest_passed": False, "backtest_exit_code": 1, "backtest_log": "compile error"}
    )


def test_backtest_log_merges_stream_and_persisted_template_output():
    streamed = "start\nSTATISTICS:: Net Profit 1%\n"
    persisted = "STATISTICS:: Net Profit 1%\ncomplete"

    assert _merge_backtest_log(streamed, persisted) == (
        "start\nSTATISTICS:: Net Profit 1%\ncomplete"
    )


def test_default_trading_parameters_are_visible_and_editable_in_the_prompt():
    parameters = _default_trading_parameters()

    assert "开仓规则" in parameters
    assert "平仓规则" in parameters
    assert "回测区间" in parameters


def test_backtest_parser_retains_unknown_platform_statistics_and_full_log():
    log = (
        "STATISTICS:: Total Orders 4\n"
        "STATISTICS:: OrderListHash abc123\n"
        "STATISTICS:: Platform Metric: 12.3\n"
    )

    metrics = _parse_backtest_metrics(log)
    assert [metric["label"] for metric in metrics] == [
        "Total Orders",
        "OrderListHash",
        "Platform Metric",
    ]
    assert metrics[1]["value"] == "abc123"
    assert _summarize_backtest_log(log) == log.strip()


def test_broad_strategy_request_uses_a_runnable_default_instrument():
    instrument = _resolve_instrument("随便生成一个策略")

    assert instrument.name == "10Y 国债期货 (FCT_T_MAIN)"


def test_strategy_summary_removes_fenced_code():
    description = "```python\ndef OnData(self):\n    pass\n```\n这是策略逻辑概要。"

    assert _clean_strategy_description(description) == "这是策略逻辑概要。"
