"""新闻重要性打分纯函数单元测试（S3-2）。

守三件事：
1. 每个信号的归一化边界（无分析/无因子/小样本/饱和）符合设计；
2. 合成权重和为 1，静态分恒在 0-100；
3. 时间衰减为只读时施加的指数函数，半衰期与配置一致。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from backend.config.config import NEWS_IMPORTANCE_WEIGHTS, RECOMMEND_DECAY_LAMBDA
from backend.recommend.importance import (
    FactorStudy,
    ImportanceInput,
    ImportanceResult,
    apply_decay,
    category_weight,
    compute_static_score,
    direction_score,
    hit_prior,
    horizon_score,
    is_policy_news,
    model_agreement,
    nfactor_score,
    normalize_direction,
    richness_score,
    source_score,
    time_decay_weight,
)


class TestNormalizeDirection:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("positive", "positive"),
            ("bullish", "positive"),
            ("利多", "positive"),
            ("利好", "positive"),
            ("涨", "positive"),
            ("negative", "negative"),
            ("bearish", "negative"),
            ("利空", "negative"),
            ("跌", "negative"),
            ("neutral", "neutral"),
            ("中性", "neutral"),
        ],
    )
    def test_word_table(self, raw, expected):
        assert normalize_direction(raw) == expected

    def test_empty_and_unknown(self):
        assert normalize_direction(None) is None
        assert normalize_direction("") is None
        assert normalize_direction("未知方向") is None


class TestSignalFunctions:
    def test_direction_score(self):
        assert direction_score("positive") == 1.0
        assert direction_score("利空") == 1.0
        assert direction_score("neutral") == 0.4
        assert direction_score(None) == 0.2

    def test_model_agreement(self):
        assert model_agreement(["positive", "positive", "negative"]) == pytest.approx(2 / 3)
        assert model_agreement(["positive", "positive"]) == 1.0
        # 单模型无交叉验证，给中性分
        assert model_agreement(["positive"]) == 0.6
        # 无分析 / 全部无法识别
        assert model_agreement([]) == 0.3
        assert model_agreement(["未知", None]) == 0.3

    def test_horizon_score(self):
        assert horizon_score("中期(1-6月)") == 1.0
        assert horizon_score("长期(6月+)") == 0.8
        assert horizon_score("短期(1周-1月)") == 0.65
        assert horizon_score(None) == 0.5
        assert horizon_score("看不懂的期限") == 0.5

    def test_category_weight(self):
        assert category_weight("POLICY") == 1.0
        assert category_weight("macro") == 0.9
        assert category_weight("INDUSTRY") == 0.45
        assert category_weight(None) == 0.3
        assert category_weight("UNKNOWN") == 0.3

    def test_hit_prior_uses_edge_against_base_and_clips(self):
        # edge = 0.2 → 0.5 + 2*0.2 = 0.9 封顶
        strong = FactorStudy("F1", hit_rate=0.9, majority_base=0.5, sample_size=100)
        assert hit_prior(strong) == 0.9
        # edge = -0.3 → 0.5 - 0.6 = -0.1，触底 0.2
        weak = FactorStudy("F2", hit_rate=0.2, majority_base=0.5, sample_size=100)
        assert hit_prior(weak) == 0.2

    def test_hit_prior_shrinks_small_samples_toward_half(self):
        # 样本 10/20，shrink=0.5：先验 0.9 向 0.5 收缩一半 → 0.7
        small = FactorStudy("F3", hit_rate=0.9, majority_base=0.5, sample_size=10)
        assert hit_prior(small) == pytest.approx(0.7)

    def test_hit_prior_missing_study(self):
        assert hit_prior(FactorStudy("F4", None, None, 0)) == 0.5

    def test_nfactor_score_saturates_at_five(self):
        assert nfactor_score(0) == 0.0
        assert nfactor_score(2) == 0.4
        assert nfactor_score(5) == 1.0
        assert nfactor_score(9) == 1.0

    def test_richness_score(self):
        assert richness_score(has_image=False, has_table=False, heading_count=0) == 0.0
        # 仅含表：1.0 / 1.5
        assert richness_score(has_image=False, has_table=True, heading_count=0) == pytest.approx(2 / 3)
        # 全满：0.5 + 1.0 + 1.0 = 2.5，除以 1.5 后封顶 1.0
        assert richness_score(has_image=True, has_table=True, heading_count=9) == 1.0

    def test_is_policy_news(self):
        assert is_policy_news(title="普通行业新闻", factor_categories=["INDUSTRY"]) is False
        assert is_policy_news(title="普通标题", factor_categories=["POLICY"]) is True
        assert is_policy_news(title="央行开展逆回购操作", factor_categories=[]) is True
        assert is_policy_news(title="MLF 利率维持不变", factor_categories=[]) is True
        assert is_policy_news(title="mlf 利率维持不变", factor_categories=[]) is True

    def test_source_score(self):
        assert source_score("wallstreetcn") == 1.0
        assert source_score("yicai") == 1.0
        assert source_score(None) == 1.0


def _full_input() -> ImportanceInput:
    return ImportanceInput(
        news_id=1,
        title="央行降准释放长期流动性",
        source="wallstreetcn",
        best_direction="positive",
        all_directions=["positive", "positive", "negative"],
        horizon="中期(1-6月)",
        factor_categories=["POLICY", "INDUSTRY"],
        factor_studies=[
            FactorStudy("F_POLICY", hit_rate=0.7, majority_base=0.5, sample_size=100),
            FactorStudy("F_IND", None, None, 0),  # 无回测 → 0.5
        ],
        factor_count=2,
        has_image=True,
        has_table=True,
        heading_count=4,
    )


class TestComputeStaticScore:
    def test_weights_sum_to_one(self):
        assert sum(NEWS_IMPORTANCE_WEIGHTS.values()) == pytest.approx(1.0)

    def test_full_input_matches_hand_calculation(self):
        result = compute_static_score(_full_input())
        assert isinstance(result, ImportanceResult)
        assert result.top_category == "POLICY"
        assert result.factor_count == 2

        # 独立手算各信号（不引用实现内常量）
        expected_signals = {
            "s_direction": 1.0,
            "s_agreement": pytest.approx(2 / 3, rel=1e-3),
            "s_horizon": 1.0,
            "s_category": 1.0,                 # max(POLICY 1.0, INDUSTRY 0.45)
            "s_hit": pytest.approx(0.7),       # (0.9 edge 命中 + 0.5 兜底) / 2
            "s_nfactor": 0.4,
            "s_rich": 1.0,
            "s_policy": 1.0,
            "s_source": 1.0,
        }
        for key, value in expected_signals.items():
            assert result.signals[key] == value

        # 加权手算：.18 + .14*2/3 + .08 + .20 + .12*.7 + .10*.4 + .08 + .07 + .03
        expected_score = 100 * (
            0.18 + 0.14 * (2 / 3) + 0.08 + 0.20
            + 0.12 * 0.7 + 0.10 * 0.4 + 0.08 + 0.07 + 0.03
        )
        assert result.score == pytest.approx(round(expected_score, 4), rel=1e-4)
        assert 0 <= result.score <= 100

    def test_bare_news_uses_fallback_signals(self):
        # 无分析、无因子、无内容块的新闻也必须产出合法分数
        bare = ImportanceInput(news_id=2, title="一条简讯", source=None)
        result = compute_static_score(bare)
        assert result.signals["s_direction"] == 0.2
        assert result.signals["s_agreement"] == 0.3
        assert result.signals["s_category"] == 0.3
        assert result.signals["s_hit"] == 0.5
        assert result.signals["s_nfactor"] == 0.0
        assert result.signals["s_rich"] == 0.0
        assert result.signals["s_policy"] == 0.0
        assert result.top_category is None
        assert 0 < result.score < 100

    def test_all_signals_within_unit_interval(self):
        result = compute_static_score(_full_input())
        for key, value in result.signals.items():
            assert 0.0 <= value <= 1.0, key


class TestTimeDecay:
    def test_fresh_news_weight_one(self):
        now = datetime(2026, 11, 6, 12, 0, 0)
        pub = now - timedelta(minutes=5)
        assert time_decay_weight(pub, now) == pytest.approx(1.0, abs=1e-3)

    def test_half_life(self):
        now = datetime(2026, 11, 6, 12, 0, 0)
        half_life_days = 0.69314718 / RECOMMEND_DECAY_LAMBDA
        pub = now - timedelta(days=half_life_days)
        assert time_decay_weight(pub, now) == pytest.approx(0.5, abs=1e-3)

    def test_future_pub_time_clamped_to_one(self):
        now = datetime(2026, 11, 6, 12, 0, 0)
        assert time_decay_weight(now + timedelta(days=2), now) == 1.0

    def test_apply_decay_scales_score(self):
        now = datetime(2026, 11, 6, 12, 0, 0)
        half_life_days = 0.69314718 / RECOMMEND_DECAY_LAMBDA
        pub = now - timedelta(days=half_life_days)
        assert apply_decay(80.0, pub, now) == pytest.approx(40.0, abs=0.05)
