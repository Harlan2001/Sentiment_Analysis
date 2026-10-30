"""strategy_code_review（生成代码静态检查）单元测试。

守的是高置信度拦截的边界：演示稿/只打印不下单必须判废，但任务卡里的禁令
原句、POC 之类的中性词不能误伤真实下单的策略。
"""

from __future__ import annotations

from backend.strategy.strategy_code_review import review_generated_code


class TestAcceptsRealStrategies:
    def test_market_order_call_passes(self):
        code = """
def OnData(self, data):
    if self.golden_cross:
        self.MarketOrder(self.variety, 1)
"""
        result = review_generated_code(code)
        assert result.ok
        assert result.syntactically_valid

    def test_lowercase_order_helper_passes(self):
        # 模块级小写下单助手也在白名单内，不能只认 self.MarketOrder。
        result = review_generated_code('order("FCT_T_MAIN", 1, "buy")')
        assert result.ok

    def test_negated_prohibition_is_not_a_confession(self):
        # 任务卡/注释里写"禁止只打印信号日志"是在提要求，不是自陈。
        code = """
# 硬性要求：禁止只打印信号日志，必须走完整下单链路
def OnData(self, data):
    self.MarketOrder("FCT_T_MAIN", 1)
"""
        result = review_generated_code(code)
        assert result.ok, result.reason

    def test_poc_word_alone_is_not_a_confession(self):
        code = """
# 舆情门控（POC 静态快照，非历史回放）
def OnData(self, data):
    self.MarketOrder("FCT_T_MAIN", 1)
"""
        result = review_generated_code(code)
        assert result.ok, result.reason


class TestRejectsDemoCode:
    def test_debug_only_code_fails(self):
        code = """
def OnData(self, data):
    self.Debug(f"signal={data.Close}")
    self.Log("nothing happens")
"""
        result = review_generated_code(code)
        assert not result.ok
        assert result.syntactically_valid
        assert "下单接口" in result.reason

    def test_self_confessed_demo_in_comment_fails(self):
        code = """
# 本策略仅打印交易信号，不进行真实下单
def OnData(self, data):
    self.Debug("signal")
"""
        result = review_generated_code(code)
        assert not result.ok
        assert "演示稿" in result.reason
        assert "仅打印交易信号" in result.evidence

    def test_self_confessed_demo_in_string_fails(self):
        code = """
NOTICE = "交易指令以信号日志形式呈现，不触发真实下单"
def OnData(self, data):
    self.Debug(NOTICE)
"""
        result = review_generated_code(code)
        assert not result.ok
        assert result.evidence

    def test_empty_code_fails(self):
        result = review_generated_code("")
        assert not result.ok
        assert result.syntactically_valid

    def test_syntax_error_is_flagged_unparseable(self):
        result = review_generated_code("def OnData(self, data:\n    pass")
        assert not result.ok
        assert not result.syntactically_valid
        assert "语法错误" in result.reason

    def test_negation_marker_rescues_partial_confession(self):
        # 同一句里既有"仅打印"字样又有"不得"，是禁令而非自陈；
        # 但代码没有任何下单调用，仍应因"无下单调用"判废。
        code = """
# 不得仅打印信号日志
def OnData(self, data):
    self.Debug("signal")
"""
        result = review_generated_code(code)
        assert not result.ok
        assert "演示稿" not in result.reason
