"""验收门（backtest_validation）单元测试。

这个模块守的是需求文档 FR-5：平台口径下"0 成交也算回测通过"，而实测 25 个
历史模板里 21 个 0 成交却全部 passed。所以这里的用例重点守三件事：
1. 三种失败要分开判，不能混成一种；
2. 只有"无成交"值得重试；
3. 标的白名单检查不能误伤"通过参数传入标的"的合法写法。
"""

from __future__ import annotations

import pytest

from backend.strategy.backtest_validation import (
    VERDICT_BACKTEST_ERROR,
    VERDICT_BACKTEST_FAILED,
    VERDICT_NO_TRADE,
    VERDICT_PASSED,
    build_retry_feedback,
    validate_strategy_result,
)

WHITELIST = {
    "FCT_T_MAIN",
    "100040",
    "FCT_TS_MAIN",
    "FCT_TL_MAIN",
    "IBK_G10Y_ACTV",
    "IBK_CDB10_ACTV",
}


def _result(
    code: str = "x = 1",
    passed: bool | None = True,
    exit_code: int | None = 0,
    summary: str = "",
) -> dict:
    return {
        "strategy": {"code": code},
        "backtest_passed": passed,
        "backtest_exit_code": exit_code,
        "backtest_summary": summary,
    }


class TestVerdicts:
    def test_zero_trades_is_rejected_not_passed(self):
        """核心用例：平台说通过，但 0 成交必须被我们判为不合格。"""
        verdict = validate_strategy_result(
            _result(summary="===== 回测结果 =====\n成交笔数: 0\n总收益率: 0%"),
            "FCT_T_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_NO_TRADE
        assert verdict.passed is False
        assert verdict.trade_count == 0

    def test_real_trades_pass(self):
        verdict = validate_strategy_result(
            _result(code='variety = "FCT_T_MAIN"', summary="成交笔数: 27"),
            "FCT_T_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_PASSED
        assert verdict.trade_count == 27

    def test_failed_backtest_is_terminal_and_not_retried(self):
        verdict = validate_strategy_result(_result(passed=False, exit_code=-1))
        assert verdict.verdict == VERDICT_BACKTEST_FAILED
        assert verdict.retryable is False

    def test_missing_trade_line_is_error_not_zero_trade(self):
        """成交笔数行只在成功分支打印，解析不到说明日志不完整，不能当 0 成交。"""
        verdict = validate_strategy_result(
            _result(summary="STATISTICS:: Sharpe Ratio 1.0")
        )
        assert verdict.verdict == VERDICT_BACKTEST_ERROR
        assert verdict.retryable is False

    def test_only_no_trade_is_retryable(self):
        no_trade = validate_strategy_result(_result(summary="成交笔数: 0"))
        failed = validate_strategy_result(_result(passed=False, exit_code=-1))
        error = validate_strategy_result(_result(summary="no trade line"))
        assert no_trade.retryable is True
        assert failed.retryable is False
        assert error.retryable is False


class TestTradeCountFallback:
    """对端只有部分分支打印中文结果块，必须能从 STATISTICS 回退取数。"""

    def test_falls_back_to_total_orders(self):
        # 实测 version 26：passed=1、Total Orders=29，但日志无「成交笔数」
        log = "STATISTICS:: Total Orders 29" + "\n" + "STATISTICS:: Win Rate 64%"
        verdict = validate_strategy_result(
            _result(code='variety = "FCT_T_MAIN"', summary=log),
            "FCT_T_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_PASSED
        assert verdict.trade_count == 29
        assert verdict.raw_trade_line == "STATISTICS:: Total Orders 29"

    def test_total_orders_zero_is_still_rejected(self):
        log = "STATISTICS:: Total Orders 0"
        verdict = validate_strategy_result(_result(summary=log), "FCT_T_MAIN", WHITELIST)
        assert verdict.verdict == VERDICT_NO_TRADE
        assert verdict.trade_count == 0

    def test_chinese_block_wins_over_statistics(self):
        log = "成交笔数: 27" + "\n" + "STATISTICS:: Total Orders 29"
        verdict = validate_strategy_result(_result(summary=log))
        # 中文结果块是对端的正式口径，优先采信
        assert verdict.trade_count == 27


class TestSymbolWhitelist:
    def test_disallowed_symbol_is_rejected(self):
        """黄金被剔除：债市口径的因子方向不能套到黄金上。"""
        verdict = validate_strategy_result(
            _result(code='variety = "FCT_AU_MAIN"', summary="成交笔数: 3"),
            "FCT_T_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_BACKTEST_ERROR
        assert verdict.symbol_whitelisted is False

    def test_symbol_passed_via_parameter_is_allowed(self):
        """标的不出现在代码文本里是合法写法，不能误判为违规。"""
        verdict = validate_strategy_result(
            _result(code="symbol = self.parameters['variety']", summary="成交笔数: 12"),
            "FCT_T_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_PASSED
        assert verdict.symbol_whitelisted is True

    def test_allowed_symbol_passes(self):
        verdict = validate_strategy_result(
            _result(code='variety = "FCT_TL_MAIN"', summary="成交笔数: 5"),
            "FCT_TL_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_PASSED


class TestOrderTypeMismatch:
    def test_futures_with_xbond_order_type_is_rejected(self):
        """历史样本里出现过用现券下单类型下期货，属于逻辑错误。"""
        verdict = validate_strategy_result(
            _result(
                code='variety = "FCT_T_MAIN"\nBusinessType.XBOND',
                summary="成交笔数: 5",
            )
        )
        assert verdict.verdict == VERDICT_BACKTEST_ERROR

    def test_bond_with_xbond_order_type_is_fine(self):
        verdict = validate_strategy_result(
            _result(code="BusinessType.XBOND", summary="成交笔数: 5")
        )
        assert verdict.verdict == VERDICT_PASSED


class TestRetryFeedback:
    def test_feedback_states_the_hard_requirement(self):
        verdict = validate_strategy_result(_result(summary="成交笔数: 0"))
        feedback = build_retry_feedback(verdict, _result(summary="成交笔数: 0"))
        assert "必须真实调用下单接口" in feedback
        assert "禁止只打印信号日志" in feedback
        assert "成交笔数: 0" in feedback

    def test_feedback_truncates_long_log(self):
        long_log = "x" * 5000
        verdict = validate_strategy_result(_result(summary=long_log))
        feedback = build_retry_feedback(
            verdict, _result(summary=long_log + "\n成交笔数: 0")
        )
        # 单条消息有 10000 token 上限，回测摘要不能整段塞进去。
        assert len(feedback) < 2000