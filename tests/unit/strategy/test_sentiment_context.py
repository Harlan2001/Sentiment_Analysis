"""strategy/sentiment_context：市场情报 prompt 构建的纯函数单测（不触 DB）。

覆盖: 方向计数/方向标签/引用用法/文本截断/因子与收益率曲线格式化/
情绪主导判断/综合话术/scope 过滤条件/完整 prompt 组装。
"""

from datetime import datetime

from backend.strategy.sentiment_context import (
    DEFAULT_MARKET_SCOPE,
    MarketContextScope,
    _build_prompt,
    _build_synthesis,
    _compact_text,
    _direction_counts,
    _direction_label,
    _reference_usage,
    _scope_filter,
    format_factor_names,
    format_yield_curve,
    sentiment_dominance,
)


class TestDirectionCounts:
    def test_counts_with_normalization(self):
        rows = [("positive", 3), ("NEGATIVE", 2), ("neutral", 1), (None, 4)]
        assert _direction_counts(rows) == {"positive": 3, "negative": 2, "neutral": 5}

    def test_unknown_direction_goes_neutral(self):
        assert _direction_counts([("weird", 7)]) == {
            "positive": 0,
            "negative": 0,
            "neutral": 7,
        }


class TestDirectionLabel:
    def test_directional_scope(self):
        assert _direction_label("positive", DEFAULT_MARKET_SCOPE) == "利多债券市场"
        assert _direction_label("negative", DEFAULT_MARKET_SCOPE) == "利空债券市场"
        assert _direction_label("neutral", DEFAULT_MARKET_SCOPE) == "中性"

    def test_non_directional_scope(self):
        scope = MarketContextScope(
            label="半导体ETF", directional_trade_guidance=False
        )
        assert _direction_label("positive", scope) == "正向情绪标注"
        assert _direction_label("negative", scope) == "负向情绪标注"
        assert _direction_label(None, scope) == "中性"

    def test_scope_label_used_in_directional(self):
        scope = MarketContextScope(label="半导体")
        assert _direction_label("positive", scope) == "利多半导体"


class TestReferenceUsage:
    def test_directional_in_window(self):
        assert (
            _reference_usage("positive", DEFAULT_MARKET_SCOPE, in_sentiment_window=True)
            == "用于方向确认与风险过滤；不单独触发交易"
        )

    def test_directional_outside_window(self):
        assert "补充背景" in _reference_usage(
            "positive", DEFAULT_MARKET_SCOPE, in_sentiment_window=False
        )

    def test_non_directional_background_only(self):
        scope = MarketContextScope(
            label="半导体", directional_trade_guidance=False
        )
        out = _reference_usage("positive", scope, in_sentiment_window=True)
        assert "背景" in out and "不直接作为标的多空依据" in out


class TestCompactText:
    def test_collapses_whitespace(self):
        assert _compact_text(" a  b\n c ") == "a b c"

    def test_truncates_with_ellipsis(self):
        assert _compact_text("x" * 100, limit=10) == "x" * 10 + "…"

    def test_short_text_unchanged(self):
        assert _compact_text(None) == ""


class TestFormatFactorNames:
    def test_formats_names(self):
        assert format_factor_names([{"name": "利率"}, {"name": "流动性"}]) == "利率、流动性"

    def test_empty_factors(self):
        assert format_factor_names([]) == "暂无高置信号"


class TestFormatYieldCurve:
    def test_formats_period_value_change(self):
        curve = [{"period": "1Y", "value": 1.5, "change_5d_bp": -2}]
        assert format_yield_curve(curve) == "1Y 1.50%（5日-2bp）"


class TestSentimentDominance:
    def test_background_only(self):
        scope = MarketContextScope(label="x", directional_trade_guidance=False)
        assert sentiment_dominance({}, scope) == "background_only"

    def test_no_data(self):
        counts = {"positive": 0, "negative": 0, "neutral": 3}
        assert sentiment_dominance(counts, DEFAULT_MARKET_SCOPE) == "no_data"

    def test_positive(self):
        assert sentiment_dominance({"positive": 5, "negative": 2}, DEFAULT_MARKET_SCOPE) == "positive"

    def test_negative(self):
        assert sentiment_dominance({"positive": 1, "negative": 4}, DEFAULT_MARKET_SCOPE) == "negative"

    def test_balanced(self):
        assert sentiment_dominance({"positive": 3, "negative": 3}, DEFAULT_MARKET_SCOPE) == "balanced"


class TestBuildSynthesis:
    def test_positive_branch(self):
        out = _build_synthesis({"positive": 4, "negative": 1, "neutral": 0}, DEFAULT_MARKET_SCOPE)
        assert "利多债券市场信号占优" in out

    def test_background_branch(self):
        scope = MarketContextScope(label="股", directional_trade_guidance=False)
        out = _build_synthesis({}, scope)
        assert "风险背景和信号过滤" in out

    def test_news_bear_but_factors_bull_is_flagged_conflict(self):
        """S0 实证 P1：7 个因子全多，新闻却利空占优——必须显式标注冲突。"""
        bull_factors = [{"name": f"f{i}"} for i in range(7)]
        out = _build_synthesis(
            {"positive": 1, "negative": 4, "neutral": 0},
            DEFAULT_MARKET_SCOPE,
            positive_factors=bull_factors,
            negative_factors=[],
        )
        assert "情报口径冲突" in out
        assert "正向因子7个" in out
        assert "单边做空" in out

    def test_news_bull_but_factors_bear_is_flagged_conflict(self):
        bear_factors = [{"name": f"f{i}"} for i in range(3)]
        out = _build_synthesis(
            {"positive": 4, "negative": 1, "neutral": 0},
            DEFAULT_MARKET_SCOPE,
            positive_factors=[],
            negative_factors=bear_factors,
        )
        assert "情报口径冲突" in out
        assert "负向因子3个" in out
        assert "单边做多" in out

    def test_aligned_directions_are_not_conflict(self):
        out = _build_synthesis(
            {"positive": 4, "negative": 1, "neutral": 0},
            DEFAULT_MARKET_SCOPE,
            positive_factors=[{"name": "f1"}, {"name": "f2"}],
            negative_factors=[],
        )
        assert "冲突" not in out
        assert "同向偏多" in out

    def test_no_news_with_bull_factors_uses_factor_gate(self):
        out = _build_synthesis(
            {"positive": 0, "negative": 0, "neutral": 0},
            DEFAULT_MARKET_SCOPE,
            positive_factors=[{"name": "f1"}],
            negative_factors=[],
        )
        assert "没有方向明确的新闻" in out
        assert "因子面板整体偏多" in out

    def test_balanced_news_with_bull_factors_is_not_conflict(self):
        out = _build_synthesis(
            {"positive": 2, "negative": 2, "neutral": 0},
            DEFAULT_MARKET_SCOPE,
            positive_factors=[{"name": "f1"}, {"name": "f2"}],
            negative_factors=[],
        )
        assert "冲突" not in out
        assert "因子面板作同向门控" in out


class TestScopeFilter:
    def test_no_keywords_empty(self):
        assert _scope_filter(DEFAULT_MARKET_SCOPE) == ("", ())

    def test_with_keywords_builds_predicates(self):
        scope = MarketContextScope(label="半导体", news_keywords=("芯片", "晶圆"))
        tail, params = _scope_filter(scope)
        assert tail.count("LIKE %s") == 2
        assert params == ("%芯片%", "%晶圆%")


class TestBuildPrompt:
    def _default_args(self, scope=DEFAULT_MARKET_SCOPE):
        return dict(
            reference_time=datetime(2026, 9, 1, 10, 0),
            window_start=datetime(2026, 8, 25, 10, 0),
            lookback_days=7,
            model_name="glm",
            news_counts={"positive": 2, "negative": 1, "neutral": 0},
            horizon_counts={"短期": 1},
            events=[
                {
                    "pub_time": datetime(2026, 8, 31, 9, 0),
                    "title": "央行预告降准",
                    "direction": "positive",
                    "horizon": "短期",
                    "reason": "释放流动性",
                }
            ],
            positive_factors=[{"name": "资金面"}],
            negative_factors=[],
            yield_curve=[{"period": "10Y", "value": 2.1, "change_5d_bp": 3}],
            scope=scope,
        )

    def _contains_all(self, text, parts):
        return [part for part in parts if part not in text]

    def test_prompt_contains_key_sections(self):
        prompt = _build_prompt(**self._default_args())
        missing = self._contains_all(
            prompt,
            ["标的情报范围：债券市场", "央行预告降准", "利多债券市场/短期", "正向2、负向1"],
        )
        assert not missing, f"prompt 缺少片段: {missing}"

    def test_yield_curve_included_when_enabled(self):
        prompt = _build_prompt(**self._default_args())
        assert "10Y 2.10%（5日+3bp）" in prompt

    def test_yield_curve_omitted_when_disabled(self):
        scope = MarketContextScope(label="半导体", include_yield_curve=False)
        prompt = _build_prompt(**self._default_args(scope=scope))
        assert "不使用债券收益率曲线" in prompt
        assert "10Y 2.10%" not in prompt

    def test_no_events_fallback_message(self):
        args = self._default_args()
        args["events"] = []
        prompt = _build_prompt(**args)
        assert "暂无与标的匹配的新闻" in prompt