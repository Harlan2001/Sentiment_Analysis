"""会话列表卡片摘要组装（build_conversation_summary）纯函数单测。"""

from __future__ import annotations

from backend.repositories.ai_strategy_history_repository import (
    build_conversation_summary,
)


def _metrics(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"key": key, "label": key, "value": value} for key, value in pairs]


class TestBuildConversationSummary:
    def test_idle_when_no_message(self):
        summary = build_conversation_summary({"instrument": None}, None, None)
        assert summary["turn_status"] == "idle"
        assert summary["verdict"] is None
        assert summary["verdict_passed"] is False
        assert summary["failure_reason"] is None

    def test_pending_draft_exposes_context_instrument(self):
        message = {
            "status": "pending_confirmation",
            "validation_json": None,
            "public_error_message": None,
            "context_json": {
                "instrument": "中金所10年期国债期货",
                "instrument_code": "FCT_T_MAIN",
                "backtest_mode": "bar",
                "candle_interval": "1d",
            },
        }
        summary = build_conversation_summary({"instrument": None}, message, None)
        assert summary["turn_status"] == "pending_confirmation"
        assert summary["instrument"] == "中金所10年期国债期货"
        assert summary["instrument_code"] == "FCT_T_MAIN"
        assert summary["backtest_mode"] == "bar"
        assert summary["candle_interval"] == "1d"

    def test_conversation_instrument_column_wins(self):
        message = {"context_json": {"instrument": "旧标的"}}
        summary = build_conversation_summary(
            {"instrument": "中金所30年期国债期货"}, message, None
        )
        assert summary["instrument"] == "中金所30年期国债期货"

    def test_passed_version_uses_validation_trade_count_and_annual(self):
        message = {
            "status": "succeeded",
            "validation_json": {
                "verdict": "passed",
                "passed": True,
                "trade_count": 29,
                "reason": "",
            },
        }
        version = {
            "local_version_no": 3,
            "backtest_metrics_json": _metrics(
                ("total_orders", "29"), ("compounding_annual_return", "2.1%")
            ),
        }
        summary = build_conversation_summary(
            {"instrument": "10年国债"}, message, version
        )
        assert summary["verdict"] == "passed"
        assert summary["verdict_passed"] is True
        assert summary["trade_count"] == 29
        assert summary["annual_return"] == "2.1%"
        assert summary["failure_reason"] is None

    def test_ghost_order_no_trade_takes_first_clause(self):
        message = {
            "status": "succeeded",
            "validation_json": {
                "verdict": "no_trade",
                "passed": False,
                "trade_count": 29,
                "reason": "提交 29 单但没有真实成交盈亏（Avg Win/Avg Loss 均为 0%），订单可能全部废单/未撮合；订单数不等于成交",
            },
        }
        version = {
            "backtest_metrics_json": _metrics(
                ("total_orders", "29"), ("compounding_annual_return", "0.000%")
            )
        }
        summary = build_conversation_summary({"instrument": None}, message, version)
        assert summary["verdict"] == "no_trade"
        assert summary["failure_reason"] == "提交 29 单但没有真实成交盈亏"
        assert summary["trade_count"] == 29

    def test_failed_turn_falls_back_to_public_error(self):
        message = {
            "status": "failed",
            "validation_json": None,
            "public_error_message": "DreamStrategy 生成失败，请重试。",
            "context_json": {},
        }
        summary = build_conversation_summary({"instrument": None}, message, None)
        assert summary["verdict"] is None
        assert summary["failure_reason"] == "DreamStrategy 生成失败"

    def test_timed_out_turn_marked(self):
        message = {
            "status": "timed_out",
            "validation_json": None,
            "public_error_message": "DreamStrategy generation timed out; retry this conversation.",
            "context_json": {},
        }
        summary = build_conversation_summary({"instrument": None}, message, None)
        assert summary["turn_status"] == "timed_out"
        assert summary["failure_reason"]

    def test_trade_count_falls_back_to_metrics_total_orders(self):
        # 验收门上线前的历史消息没有 validation_json。
        message = {"status": "succeeded", "context_json": {}}
        version = {"backtest_metrics_json": _metrics(("total_orders", "17"))}
        summary = build_conversation_summary({"instrument": None}, message, version)
        assert summary["trade_count"] == 17
        assert summary["annual_return"] is None

    def test_corrupt_json_is_tolerated(self):
        message = {
            "status": "succeeded",
            "validation_json": "not-json",
            "context_json": "{broken",
        }
        summary = build_conversation_summary({"instrument": None}, message, None)
        assert summary["verdict"] is None
        assert summary["instrument"] is None
        assert summary["turn_status"] == "succeeded"
