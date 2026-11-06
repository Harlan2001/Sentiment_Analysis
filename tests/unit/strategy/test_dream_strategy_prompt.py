"""strategy/dream_strategy_prompt：Dream 策略 prompt 构建纯函数单测（不触 DB/外部服务）。

覆盖: 默认交易参数/市场范围解析(含否定排除)/事件与收益率格式化/情绪指引/
首轮与续轮执行规则/prompt 受保护区编辑校验。
"""

from datetime import datetime

import pytest

from backend.strategy.dream_strategy_prompt import (
    BOND_SCOPE,
    EDITABLE_SECTION_END,
    EDITABLE_SECTION_START,
    GOLD_SCOPE,
    PROMPT_TOKEN_BUDGET,
    _default_trading_parameters,
    _format_events,
    _format_yields,
    _resolve_market_scope,
    _sentiment_guidance,
    apply_user_edited_requirement,
    build_dream_strategy_continuation_prompt,
    build_dream_strategy_first_prompt,
    estimate_message_tokens,
    resolve_instrument,
)


class TestDefaultTradingParameters:
    def test_contains_rule_lines(self):
        out = _default_trading_parameters()
        assert "- 开仓规则：" in out
        assert "- 止损：" in out
        assert "- 回测区间：" in out
        assert out.count("\n") >= 5


class TestResolveMarketScope:
    def test_bond_when_no_gold_keyword(self):
        assert _resolve_market_scope("帮我做一个国债策略") == BOND_SCOPE

    def test_gold_when_gold_mentioned(self):
        assert _resolve_market_scope("黄金策略") == GOLD_SCOPE
        assert _resolve_market_scope("做空现货金") == GOLD_SCOPE

    def test_negation_excludes_gold(self):
        # 否定标记（除/不要/剔除等）出现在黄金关键词之前才算排除
        assert _resolve_market_scope("除了黄金以外的债券策略") == BOND_SCOPE
        assert _resolve_market_scope("不要黄金，做国债") == BOND_SCOPE

    def test_non_matching_negation_still_gold(self):
        # "不想要" 不在否定标记表内, 仍按提及黄金处理（函数设计语义）
        assert _resolve_market_scope("我不想要黄金，做国债") == GOLD_SCOPE

    def test_whitespace_insensitive(self):
        assert _resolve_market_scope("黄    金") == GOLD_SCOPE


class TestFormatEvents:
    def test_empty_events_default_text(self):
        assert "暂无" in _format_events([])

    def test_formats_event_line(self):
        events = [
            {
                "pub_time": datetime(2026, 9, 1, 9, 0),
                "title": "央行预告降准",
                "direction": "positive",
                "horizon": "短期",
                "reason": "释放流动性",
            }
        ]
        assert "- 09-01 09:00 | 央行预告降准 | positive/短期 | 释放流动性" in _format_events(events)


class TestFormatYields:
    def test_disabled_scope_message(self):
        assert "不使用债券收益率曲线" in _format_yields([], GOLD_SCOPE)

    def test_empty_curve(self):
        assert _format_yields([], BOND_SCOPE) == "暂无可用收益率数据"

    def test_formats_curve(self):
        curve = [{"period": "10Y", "value": 2.1, "change_5d_bp": 3}]
        assert "10Y 2.10%（5日+3bp）" in _format_yields(curve, BOND_SCOPE)


class TestSentimentGuidance:
    def test_background_only_scope(self):
        conclusion, action = _sentiment_guidance({}, GOLD_SCOPE)
        assert "不直接等同于黄金市场多空" in conclusion

    def test_positive(self):
        counts = {"positive": 4, "negative": 1, "neutral": 0}
        conclusion, action = _sentiment_guidance(counts, BOND_SCOPE)
        assert "利多债券市场信号占优" in conclusion

    def test_negative(self):
        counts = {"positive": 1, "negative": 3, "neutral": 0}
        conclusion, action = _sentiment_guidance(counts, BOND_SCOPE)
        assert "利空债券市场信号占优" in conclusion

    def test_balanced(self):
        counts = {"positive": 2, "negative": 2, "neutral": 0}
        conclusion, _ = _sentiment_guidance(counts, BOND_SCOPE)
        assert "信号均衡" in conclusion

    def test_news_negative_but_panel_bull_is_flagged_conflict(self):
        """S0 实证：新闻利空占优、因子面板 7 个全多时必须显式标注冲突。"""
        counts = {"positive": 1, "negative": 3, "neutral": 0}
        panel = [{"direction": "positive"}] * 7
        conclusion, action = _sentiment_guidance(counts, BOND_SCOPE, panel)
        assert "信号冲突" in conclusion
        assert "因子面板偏多" in conclusion
        assert "利空" in conclusion
        assert "单边做空" in action

    def test_news_positive_but_panel_bear_is_flagged_conflict(self):
        counts = {"positive": 4, "negative": 1, "neutral": 0}
        panel = [{"direction": "negative"}] * 3
        conclusion, action = _sentiment_guidance(counts, BOND_SCOPE, panel)
        assert "信号冲突" in conclusion
        assert "因子面板偏空" in conclusion
        assert "单边做多" in action

    def test_no_news_but_panel_has_direction_uses_panel(self):
        counts = {"positive": 0, "negative": 0, "neutral": 0}
        panel = [{"direction": "positive"}] * 5 + [{"direction": "negative"}] * 2
        conclusion, action = _sentiment_guidance(counts, BOND_SCOPE, panel)
        assert "因子面板偏多" in conclusion
        assert "同向门控" in action

    def test_aligned_news_and_panel_keeps_plain_conclusion(self):
        counts = {"positive": 4, "negative": 1, "neutral": 0}
        panel = [{"direction": "positive"}] * 3
        conclusion, _ = _sentiment_guidance(counts, BOND_SCOPE, panel)
        assert "信号冲突" not in conclusion
        assert "利多债券市场信号占优" in conclusion


class TestResolveInstrument:
    def test_explicit_whitelisted_code_passes(self):
        code, label = resolve_instrument("随便", "FCT_TS_MAIN")
        assert code == "FCT_TS_MAIN"
        assert "2年期" in label

    def test_numeric_alias_100040_passes(self):
        code, _label = resolve_instrument("随便", "100040")
        assert code == "100040"

    def test_excluded_gold_raises_with_reason(self):
        with pytest.raises(ValueError, match="本期不支持"):
            resolve_instrument("黄金策略", "FCT_AU_MAIN")

    def test_unknown_code_lists_alternatives(self):
        with pytest.raises(ValueError, match="FCT_T_MAIN"):
            resolve_instrument("随便", "NOT_A_CODE")

    def test_text_detection_finds_whitelisted_code(self):
        code, _label = resolve_instrument("帮我用 FCT_TL_MAIN 做一个趋势策略")
        assert code == "FCT_TL_MAIN"

    def test_default_when_nothing_matches(self):
        code, _label = resolve_instrument("随便生成一个策略")
        assert code == "FCT_T_MAIN"


class TestTokenBudget:
    def test_empty_is_zero(self):
        assert estimate_message_tokens("") == 0

    def test_ascii_one_token_per_four_chars(self):
        assert estimate_message_tokens("abcd") == 1
        assert estimate_message_tokens("a" * 400) == 100

    def test_chinese_roughly_one_and_half_tokens_per_char(self):
        # 与对端 EstimateTokenCount 同算法：一个三字节汉字记 6/4 = 1.5 token。
        assert estimate_message_tokens("国" * 2) == 3
        assert estimate_message_tokens("国" * 100) == 150

    def test_budget_holds_margin_below_remote_limit(self):
        # 对端硬上限 10,000 token；我方 6,000 必须保留明显余量给系统提示与输出。
        assert PROMPT_TOKEN_BUDGET <= 6000


class TestBuildFirstPrompt:
    def test_empty_raises(self):
        with pytest.raises(ValueError):
            build_dream_strategy_first_prompt("   ")

    def test_includes_common_rules(self):
        out = build_dream_strategy_first_prompt("【市场情报】...")
        assert "[EXECUTION RULES]" in out
        assert "backtest" in out

    def test_excludes_continuation_only_rules(self):
        out = build_dream_strategy_first_prompt("【市场情报】...")
        assert "Continue the existing DreamStrategy session" not in out


class TestBuildContinuationPrompt:
    def test_empty_raises(self):
        with pytest.raises(ValueError):
            build_dream_strategy_continuation_prompt("\n")

    def test_includes_continuation_rules(self):
        out = build_dream_strategy_continuation_prompt("【市场情报】...")
        assert "Continue the existing DreamStrategy session" in out


def _draft_with_requirement(requirement: str) -> str:
    return (
        f"{EDITABLE_SECTION_START}\n[TRADING_PARAMETERS]\n- 开仓规则：5日均线上穿\n"
        f"[/TRADING_PARAMETERS]\n[STRATEGY_REQUIREMENT]\n{requirement}\n"
        f"[/STRATEGY_REQUIREMENT]\n{EDITABLE_SECTION_END}\n"
        "【市场情报】受保护上下文不参与编辑"
    )


def _blank_edit_draft(content: str) -> str:
    """可编辑块(整段) = content 的草稿, 其余(受保护前缀/后缀)固定。"""
    return (
        f"{EDITABLE_SECTION_START}\n{content}\n{EDITABLE_SECTION_END}\n"
        "受保护后缀"
    )


class TestApplyUserEditedRequirement:
    def test_accepts_edit_inside_section(self):
        draft = _draft_with_requirement("原需求")
        edited = _draft_with_requirement("新需求")
        out = apply_user_edited_requirement(draft, edited)
        assert "新需求" in out
        assert "原需求" not in out
        assert "受保护上下文不参与编辑" in out

    def test_missing_section_raises(self):
        with pytest.raises(ValueError, match="editable requirement section"):
            apply_user_edited_requirement("无标记的提示词", "无标记的提示词")

    def test_protected_prefix_change_rejected(self):
        draft = _draft_with_requirement("需求")
        edited = "被篡改的前缀" + _draft_with_requirement("需求")
        with pytest.raises(ValueError, match="protected"):
            apply_user_edited_requirement(draft, edited)

    def test_empty_requirement_rejected(self):
        draft = _blank_edit_draft("原需求")
        edited = _blank_edit_draft("   \n  ")
        with pytest.raises(ValueError, match="must not be empty"):
            apply_user_edited_requirement(draft, edited)

    def test_oversized_requirement_rejected(self):
        draft = _draft_with_requirement("短需求")
        edited = _draft_with_requirement("字" * 2001)
        with pytest.raises(ValueError, match="2000"):
            apply_user_edited_requirement(draft, edited)