"""宏观信号纯逻辑单测（presence / directional + 时间衰减）。

只测不碰数据库的纯函数：方向→分数映射、分数→信号阈值、presence/directional 计算。
DB 集成（get_macro_signal 的真实查询）留给下周的集成测试。
"""

import math
from datetime import datetime, timedelta

from backend.macrosignal.macro_signal import (
    DIRECTIONAL_THRESHOLD,
    NewsFactorRow,
    _compute_directional,
    _compute_presence,
    _direction_to_score,
    _score_to_signal,
)

START = datetime(2026, 8, 1)
END = datetime(2026, 8, 28)

# news_factor 查询行结构：factor_code, news_id, direction, pub_time
def _row(code, news_id, direction, pub_time):
    return NewsFactorRow(code, news_id, direction, pub_time)


# ---- 方向 → 分数映射 ----

def test_direction_to_score_maps_known_directions():
    assert _direction_to_score("positive") == 1.0
    assert _direction_to_score("neutral") == 0.0
    assert _direction_to_score("negative") == -1.0


def test_direction_to_score_is_case_insensitive_and_lenient():
    assert _direction_to_score("Positive") == 1.0
    assert _direction_to_score("") == 0.0
    assert _direction_to_score(None) == 0.0
    assert _direction_to_score("unknown") == 0.0


# ---- 分数 → 信号阈值（±0.3 边界） ----

def test_score_to_signal_threshold_boundaries():
    assert _score_to_signal(DIRECTIONAL_THRESHOLD) == 1  # >= +0.3 → 1
    assert _score_to_signal(DIRECTIONAL_THRESHOLD - 0.001) == 0
    assert _score_to_signal(0.0) == 0
    assert _score_to_signal(-DIRECTIONAL_THRESHOLD + 0.001) == 0
    assert _score_to_signal(-DIRECTIONAL_THRESHOLD) == -1  # <= -0.3 → -1


# ---- presence ----

def test_presence_counts_matching_news_and_marks_hit_ids():
    rows = [
        _row("GDP", 1, "positive", END),
        _row("GDP", 2, "negative", END),
    ]
    result = _compute_presence(rows, "GDP", START, END)
    assert result["signal_value"] == 1
    assert result["news_count"] == 2
    assert result["hit_news_ids"] == [1, 2]
    assert result["time_range"] == {"start": START.isoformat(), "end": END.isoformat()}


def test_presence_for_factor_without_news_returns_zero():
    result = _compute_presence([], "GDP", START, END)
    assert result["signal_value"] == 0
    assert result["news_count"] == 0
    assert result["hit_news_ids"] == []


# ---- directional（时间衰减） ----

def test_directional_empty_returns_zero_signal():
    result = _compute_directional([], "GDP", START, END, decay_lambda=0.1)
    assert result["signal_value"] == 0
    assert result["confidence"] == 0.0
    assert result["news_count"] == 0
    assert result["hit_news_ids"] == []


def test_directional_single_news_at_end_time_full_confidence():
    rows = [_row("GDP", 1, "positive", END)]
    result = _compute_directional(rows, "GDP", START, END, decay_lambda=0.1)
    # delta_days = 0 → 权重 = e^0 = 1 → raw_score = 1.0 → 信号 1, 置信度 1.0
    assert result["signal_value"] == 1
    assert result["confidence"] == 1.0


def test_directional_older_news_is_half_weight_at_ln2_decay():
    # decay_lambda = ln2 → 每过去 1 天权重恰好减半
    pub = END - timedelta(days=1)
    rows = [_row("GDP", 1, "positive", pub)]
    result = _compute_directional(rows, "GDP", START, END, decay_lambda=math.log(2))
    assert result["confidence"] == 0.5
    assert result["signal_value"] == 1  # 单条正向 → raw_score 恒为 1


def test_directional_mixed_directions_weighted_by_recency():
    recent = _row("GDP", 1, "positive", END)  # w = 1.0
    older = _row("GDP", 2, "negative", END - timedelta(days=1))  # w = 0.5
    rows = [older, recent]  # 乱序不应影响计算结果
    result = _compute_directional(rows, "GDP", START, END, decay_lambda=math.log(2))
    # weighted_sum = 1.0 + (-1.0)*0.5 = 0.5; weight_total = 1.5
    # raw_score = 0.5/1.5 = 0.333 > 0.3 → 信号 1; confidence = 1.5/2 = 0.75
    assert result["signal_value"] == 1
    assert result["confidence"] == 0.75
    assert result["hit_news_ids"] == [2, 1]


def test_directional_negative_dominance_when_only_negative_news():
    rows = [_row("GDP", 1, "negative", END)]
    result = _compute_directional(rows, "GDP", START, END, decay_lambda=0.1)
    assert result["signal_value"] == -1