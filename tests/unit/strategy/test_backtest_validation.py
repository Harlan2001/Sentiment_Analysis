"""验收门（backtest_validation）单元测试。

平台口径下"0 成交也算回测通过"，实测 25 个历史模板里 21 个 0 成交却全部
passed；2026-10-30 会话 #60 又出现 ``Total Orders 29`` 但平均盈亏 0%、换手率
0% 的废单假阳性。所以这里的用例守五件事：
1. 四种结论要分开判，不能混成一种；
2. 只有"无成交/废单/模型可修正的代码问题"值得重试，平台级失败不重试；
3. 演示稿（只打印不下单）在回测之前就要被静态检查拦住；
4. 订单数 >0 不等于成交，STATISTICS 经济指标为 0 时判废单；
5. 标的白名单检查不能误伤"通过参数传入标的"的合法写法。
"""

from __future__ import annotations

from pathlib import Path

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

# 语法合法、含真实下单调用的最小策略骨架，避免每个用例重复。
ORDERING_CODE = '''
variety = "FCT_T_MAIN"

def on_bar(self, bar):
    if bar.close > bar.open:
        self.MarketOrder(variety, 1)
    else:
        self.MarketOrder(variety, -1)
'''

FIXTURES = Path(__file__).parent / "fixtures"


def _result(
    code: str = ORDERING_CODE,
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


def _step(verdict, name: str):
    return next(step for step in verdict.steps if step.step == name)


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
            _result(summary="成交笔数: 27"),
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

    def test_only_fixable_failures_are_retryable(self):
        no_trade = validate_strategy_result(_result(summary="成交笔数: 0"))
        failed = validate_strategy_result(_result(passed=False, exit_code=-1))
        error = validate_strategy_result(_result(summary="no trade line"))
        assert no_trade.retryable is True
        assert failed.retryable is False
        assert error.retryable is False


class TestStaticCodeReview:
    def test_demo_code_without_any_order_call_is_rejected(self):
        """21/25 历史模板的形态：逻辑齐全但动作只有 Debug，回测前就该拦住。"""
        code = """
def on_bar(self, bar):
    self.Debug(f"signal={bar.close}")
    self.Log("record only")
"""
        verdict = validate_strategy_result(_result(code=code, summary="成交笔数: 0"))
        assert verdict.verdict == VERDICT_NO_TRADE
        assert verdict.retryable is True
        assert not _step(verdict, "code_places_real_orders").ok

    def test_self_confessed_demo_code_is_rejected_with_evidence(self):
        code = '''
# 本策略仅打印交易信号，不进行真实下单
def on_bar(self, bar):
    self.Debug("signal")
'''
        verdict = validate_strategy_result(_result(code=code, summary="成交笔数: 0"))
        assert verdict.verdict == VERDICT_NO_TRADE
        assert "演示稿" in verdict.reason

    def test_syntax_error_is_retryable_backtest_error(self):
        """语法错误模型能修，给一次重生机会，但不当成无成交。"""
        verdict = validate_strategy_result(
            _result(code="def on_bar(self, bar:\n    pass", summary="成交笔数: 0")
        )
        assert verdict.verdict == VERDICT_BACKTEST_ERROR
        assert verdict.retryable is True


class TestTradeCountFallback:
    """对端只有部分分支打印中文结果块，必须能从 STATISTICS 回退取数。"""

    def test_falls_back_to_total_orders_without_zero_economics_metrics(self):
        # 只有 Total Orders/胜率，没有平均盈亏/换手率/净利润——证据不足，
        # 不能武断判废单，保持既有行为（会话 #60 的日志这些指标是齐全的）。
        log = "STATISTICS:: Total Orders 29" + "\n" + "STATISTICS:: Win Rate 64%"
        verdict = validate_strategy_result(
            _result(summary=log),
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


class TestGhostOrders:
    """S0 实证 P0：29 单全废（平均盈亏 0%、换手率 0%），不能判 passed。"""

    def test_s0_real_log_fixture_is_ghost_orders_not_passed(self):
        log = (FIXTURES / "s0_ghost_orders_statistics.txt").read_text(encoding="utf-8")
        verdict = validate_strategy_result(
            _result(summary=log),
            "FCT_T_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_NO_TRADE
        assert verdict.passed is False
        assert verdict.retryable is True
        assert verdict.trade_count == 29
        assert not _step(verdict, "fills_have_economic_value").ok
        assert "废单" in verdict.reason

    def test_zero_turnover_and_zero_profit_is_ghost_even_without_avg_metrics(self):
        """证据链 B：平均盈亏指标缺失时，换手率 0% + 净利润 0% 同样判废单。"""
        log = (
            "STATISTICS:: Total Orders 5\n"
            "STATISTICS:: Portfolio Turnover 0.00%\n"
            "STATISTICS:: Net Profit 0.000%\n"
        )
        verdict = validate_strategy_result(_result(summary=log))
        assert verdict.verdict == VERDICT_NO_TRADE
        assert verdict.trade_count == 5

    def test_genuine_fills_with_real_economics_pass(self):
        log = (
            "STATISTICS:: Total Orders 29\n"
            "STATISTICS:: Average Win 0.12%\n"
            "STATISTICS:: Average Loss -0.08%\n"
            "STATISTICS:: Win Rate 64%\n"
            "STATISTICS:: Loss Rate 36%\n"
            "STATISTICS:: Portfolio Turnover 12.50%\n"
            "STATISTICS:: Net Profit 3.41%\n"
        )
        verdict = validate_strategy_result(
            _result(summary=log),
            "FCT_T_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_PASSED
        assert _step(verdict, "fills_have_economic_value").ok

    def test_zero_avg_without_any_rate_is_not_evidence(self):
        """平均盈亏为 0 但连胜率都没有，可能是指标没打全，证据不足不判废。"""
        log = (
            "STATISTICS:: Total Orders 3\n"
            "STATISTICS:: Average Win 0.00%\n"
            "STATISTICS:: Average Loss 0.00%\n"
        )
        verdict = validate_strategy_result(
            _result(summary=log),
            "FCT_T_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_PASSED


class TestExpectedInstrument:
    def test_using_other_whitelisted_instrument_is_still_rejected(self):
        """白名单只保证不出圈；任务卡指定 FCT_T_MAIN 就不能交 FCT_TS_MAIN。"""
        code = '''
variety = "FCT_TS_MAIN"
def on_bar(self, bar):
    self.MarketOrder(variety, 1)
'''
        verdict = validate_strategy_result(
            _result(code=code, summary="成交笔数: 5"),
            "FCT_T_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_BACKTEST_ERROR
        assert verdict.retryable is True
        assert not _step(verdict, "expected_instrument_used").ok

    def test_numeric_alias_100040_counts_as_fct_t_main(self):
        code = '''
variety = "100040"
def on_bar(self, bar):
    self.MarketOrder(variety, 1)
'''
        verdict = validate_strategy_result(
            _result(code=code, summary="成交笔数: 5"),
            "FCT_T_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_PASSED
        assert _step(verdict, "expected_instrument_used").ok


class TestSymbolWhitelist:
    def test_disallowed_symbol_is_rejected(self):
        """黄金被剔除：债市口径的因子方向不能套到黄金上。"""
        code = '''
variety = "FCT_AU_MAIN"
def on_bar(self, bar):
    self.MarketOrder(variety, 1)
'''
        verdict = validate_strategy_result(
            _result(code=code, summary="成交笔数: 3"),
            "FCT_T_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_BACKTEST_ERROR
        assert verdict.symbol_whitelisted is False

    def test_symbol_passed_via_parameter_is_allowed(self):
        """标的不出现在代码文本里是合法写法，不能误判为违规。"""
        code = """
symbol = self.parameters['variety']
def on_bar(self, bar):
    self.MarketOrder(symbol, 1)
"""
        verdict = validate_strategy_result(
            _result(code=code, summary="成交笔数: 12"),
            "FCT_T_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_PASSED
        assert verdict.symbol_whitelisted is True

    def test_allowed_symbol_passes(self):
        code = '''
variety = "FCT_TL_MAIN"
def on_bar(self, bar):
    self.MarketOrder(variety, 1)
'''
        verdict = validate_strategy_result(
            _result(code=code, summary="成交笔数: 5"),
            "FCT_TL_MAIN",
            WHITELIST,
        )
        assert verdict.verdict == VERDICT_PASSED


class TestOrderTypeMismatch:
    def test_futures_with_xbond_order_type_is_rejected(self):
        """历史样本里出现过用现券下单类型下期货，属于逻辑错误。"""
        code = (
            'variety = "FCT_T_MAIN"\n'
            "flag = BusinessType.XBOND\n"
            "def on_bar(self, bar):\n"
            "    self.MarketOrder(variety, 1)\n"
        )
        verdict = validate_strategy_result(
            _result(code=code, summary="成交笔数: 5")
        )
        assert verdict.verdict == VERDICT_BACKTEST_ERROR
        assert verdict.retryable is True

    def test_bond_with_xbond_order_type_is_fine(self):
        code = (
            "flag = BusinessType.XBOND\n"
            "def on_bar(self, bar):\n"
            "    self.Buy(symbol, 100)\n"
        )
        verdict = validate_strategy_result(_result(code=code, summary="成交笔数: 5"))
        assert verdict.verdict == VERDICT_PASSED


class TestRetryFeedback:
    def test_feedback_states_the_hard_requirement(self):
        verdict = validate_strategy_result(_result(summary="成交笔数: 0"))
        feedback = build_retry_feedback(verdict, _result(summary="成交笔数: 0"))
        assert "必须真实调用下单接口" in feedback
        assert "禁止只打印信号日志" in feedback
        assert "成交笔数: 0" in feedback

    def test_feedback_warns_about_ghost_orders(self):
        log = (FIXTURES / "s0_ghost_orders_statistics.txt").read_text(encoding="utf-8")
        result = _result(summary=log)
        verdict = validate_strategy_result(result)
        feedback = build_retry_feedback(verdict, result)
        assert "换手率" in feedback
        assert "废单" in feedback

    def test_feedback_truncates_long_log(self):
        long_log = "x" * 5000
        verdict = validate_strategy_result(_result(summary=long_log))
        feedback = build_retry_feedback(
            verdict, _result(summary=long_log + "\n成交笔数: 0")
        )
        # 单条消息有 10000 token 上限，回测摘要不能整段塞进去。
        assert len(feedback) < 2000
