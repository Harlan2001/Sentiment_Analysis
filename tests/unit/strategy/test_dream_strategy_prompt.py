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
    _default_trading_parameters,
    _format_events,
    _format_yields,
    _resolve_market_scope,
    _sentiment_guidance,
    apply_user_edited_requirement,
    build_dream_strategy_continuation_prompt,
    build_dream_strategy_first_prompt,
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
        assert "均衡或不足" in conclusion


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