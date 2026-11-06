"""新闻重要性打分纯函数层（S3-2）。

不碰数据库：信号采集在 repository / scoring 层完成，本模块只做方向归一化、
信号归一化与加权合成，保证公式可单测、可复算、可解释。所有权重与词表来自
``backend.config.config``，调参不改代码。

两层结构：
- 静态重要性分 ``compute_static_score`` → 0-100，预计算落 news_importance_score；
- 时间衰减 ``apply_decay`` → 读时施加，final = I * EXP(-lambda * age_days)。
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from backend.config.config import (
    FACTOR_CATEGORY_WEIGHTS,
    NEWS_IMPORTANCE_WEIGHTS,
    NEWS_SOURCE_WEIGHTS,
    POLICY_TITLE_KEYWORDS,
    RECOMMEND_DECAY_LAMBDA,
    RECOMMEND_MIN_STUDY_SAMPLES,
)

# 方向归一化词表单点维护：Python 侧 normalize_direction 与 SQL 侧 IN-list
# （routers/discover.py 的 direction 筛选）都从这里取，杜绝两份词表漂移。
DIRECTION_WORDS: dict[str, tuple[str, ...]] = {
    "positive": ("bullish", "positive", "up", "涨", "利多", "利好"),
    "negative": ("bearish", "negative", "down", "跌", "利空"),
    "neutral": ("neutral", "中性"),
}
_POSITIVE_WORDS = set(DIRECTION_WORDS["positive"])
_NEGATIVE_WORDS = set(DIRECTION_WORDS["negative"])
_NEUTRAL_WORDS = set(DIRECTION_WORDS["neutral"])

# 期限打分：中期事件最贴合仓位决策，短期时效性已由时间衰减体现
_HORIZON_SCORES = (("中期", 1.0), ("长期", 0.8), ("短期", 0.65))
_HORIZON_MISSING = 0.5

# 无因子/无分析时的兜底信号分
_NO_FACTOR_CATEGORY = 0.3
_NO_ANALYSIS_DIRECTION = 0.2
_NO_ANALYSIS_AGREEMENT = 0.3
_NEUTRAL_DIRECTION = 0.4
_SINGLE_MODEL_AGREEMENT = 0.6
_NO_STUDY_HIT = 0.5


def normalize_direction(value) -> Optional[str]:
    """把中英文混存的方向词归一化为 positive / negative / neutral，无法识别返回 None。"""
    if not value:
        return None
    word = str(value).strip().lower()
    if word in _POSITIVE_WORDS:
        return "positive"
    if word in _NEGATIVE_WORDS:
        return "negative"
    if word in _NEUTRAL_WORDS:
        return "neutral"
    return None


def direction_score(best_direction) -> float:
    """s_direction：利多利空对利率交易同等可操作，中性弱化，无分析最低。"""
    normalized = normalize_direction(best_direction)
    if normalized in ("positive", "negative"):
        return 1.0
    if normalized == "neutral":
        return _NEUTRAL_DIRECTION
    return _NO_ANALYSIS_DIRECTION


def model_agreement(all_directions: list) -> float:
    """s_agreement：多模型归一化方向投票，max(票数)/模型数；单模型给中性分。"""
    normed = [d for d in (normalize_direction(x) for x in all_directions) if d]
    if not normed:
        return _NO_ANALYSIS_AGREEMENT
    if len(normed) == 1:
        return _SINGLE_MODEL_AGREEMENT
    counts = Counter(normed)
    return max(counts.values()) / len(normed)


def horizon_score(horizon) -> float:
    """s_horizon：库内存「短期(1周-1月)」类带括号文案，按包含关系匹配。"""
    if not horizon:
        return _HORIZON_MISSING
    text = str(horizon)
    for keyword, score in _HORIZON_SCORES:
        if keyword in text:
            return score
    return _HORIZON_MISSING


def category_weight(category) -> float:
    """单个因子类别的先验权重，未知类别按无因子兜底处理。"""
    return FACTOR_CATEGORY_WEIGHTS.get(str(category or "").upper(), _NO_FACTOR_CATEGORY)


@dataclass
class FactorStudy:
    """factor_event_study 中一个因子的回测先验（period_label='all'）。"""

    factor_code: str
    hit_rate: Optional[float]
    majority_base: Optional[float]
    sample_size: int


def hit_prior(study: FactorStudy) -> float:
    """s_hit 单因子先验：用相对多数类基准的 edge 而非裸 hit_rate，避免奖励类别失衡。

    p = clip(0.5 + 2*(hit_rate - majority_base), 0.2, 0.9)；
    样本不足门槛时按 sample/门槛 向 0.5 收缩；无回测行给 0.5。
    """
    if study.hit_rate is None or study.majority_base is None:
        return _NO_STUDY_HIT
    prior = 0.5 + 2.0 * (float(study.hit_rate) - float(study.majority_base))
    prior = max(0.2, min(0.9, prior))
    sample = max(int(study.sample_size or 0), 0)
    if sample < RECOMMEND_MIN_STUDY_SAMPLES:
        shrink = sample / float(RECOMMEND_MIN_STUDY_SAMPLES)
        prior = 0.5 + (prior - 0.5) * shrink
    return prior


def nfactor_score(factor_count: int) -> float:
    """s_nfactor：关联因子数 5 个饱和，防关键词堆砌膨胀。"""
    return min(max(int(factor_count), 0) / 5.0, 1.0)


def richness_score(*, has_image: bool, has_table: bool, heading_count: int) -> float:
    """s_rich：含表格（数据型文章）权重最高，图次之，标题块封顶计分。"""
    points = (
        0.5 * (1.0 if has_image else 0.0)
        + 1.0 * (1.0 if has_table else 0.0)
        + 0.25 * min(max(int(heading_count), 0), 4)
    )
    return min(points / 1.5, 1.0)


def is_policy_news(*, title: str, factor_categories: list) -> bool:
    """s_policy：关联 POLICY 因子即政策新闻；否则用标题关键词兜底。"""
    if any(str(c).upper() == "POLICY" for c in (factor_categories or [])):
        return True
    text = title or ""
    text_upper = text.upper()
    return any(
        keyword in (text_upper if keyword.isascii() else text)
        for keyword in POLICY_TITLE_KEYWORDS
    )


def source_score(source) -> float:
    """s_source：v1 两源同分，未知来源默认 1.0，保留配置位待行为数据拉开。"""
    return NEWS_SOURCE_WEIGHTS.get(str(source or ""), 1.0)


@dataclass
class ImportanceInput:
    """单条新闻的打分原料（由 repository 批量采集后组装）。"""

    news_id: int
    title: str
    source: Optional[str] = None
    best_direction: Optional[str] = None  # analysis 最佳模型行的原始方向词
    all_directions: list = field(default_factory=list)  # 全部模型行的原始方向词
    horizon: Optional[str] = None
    factor_categories: list = field(default_factory=list)   # DISTINCT 类别
    factor_studies: list = field(default_factory=list)      # list[FactorStudy]
    factor_count: int = 0
    has_image: bool = False
    has_table: bool = False
    heading_count: int = 0


@dataclass
class ImportanceResult:
    """打分输出：静态分 + 9 个信号子分 + 解释性元数据。"""

    news_id: int
    score: float
    signals: dict
    factor_count: int
    top_category: Optional[str]


def compute_static_score(data: ImportanceInput) -> ImportanceResult:
    """按 NEWS_IMPORTANCE_WEIGHTS 合成 0-100 静态重要性分。"""
    categories = [str(c).upper() for c in (data.factor_categories or [])]

    s_direction = direction_score(data.best_direction)
    s_agreement = model_agreement(data.all_directions)
    s_horizon = horizon_score(data.horizon)

    if categories:
        s_category = max(category_weight(c) for c in categories)
        top_category = max(categories, key=category_weight)
    else:
        s_category = _NO_FACTOR_CATEGORY
        top_category = None

    if data.factor_studies:
        s_hit = sum(hit_prior(study) for study in data.factor_studies) / len(data.factor_studies)
    else:
        s_hit = _NO_STUDY_HIT

    s_nfactor = nfactor_score(data.factor_count)
    s_rich = richness_score(
        has_image=data.has_image,
        has_table=data.has_table,
        heading_count=data.heading_count,
    )
    s_policy = 1.0 if is_policy_news(
        title=data.title, factor_categories=categories
    ) else 0.0
    s_source = source_score(data.source)

    weights = NEWS_IMPORTANCE_WEIGHTS
    score = 100.0 * (
        weights["direction"] * s_direction
        + weights["agreement"] * s_agreement
        + weights["horizon"] * s_horizon
        + weights["category"] * s_category
        + weights["hit"] * s_hit
        + weights["nfactor"] * s_nfactor
        + weights["rich"] * s_rich
        + weights["policy"] * s_policy
        + weights["source"] * s_source
    )

    signals = {
        "s_direction": round(s_direction, 4),
        "s_agreement": round(s_agreement, 4),
        "s_horizon": round(s_horizon, 4),
        "s_category": round(s_category, 4),
        "s_hit": round(s_hit, 4),
        "s_nfactor": round(s_nfactor, 4),
        "s_rich": round(s_rich, 4),
        "s_policy": s_policy,
        "s_source": round(s_source, 4),
    }
    return ImportanceResult(
        news_id=data.news_id,
        score=round(score, 4),
        signals=signals,
        factor_count=data.factor_count,
        top_category=top_category,
    )


def time_decay_weight(
    pub_time: datetime,
    now: Optional[datetime] = None,
    decay_lambda: float = RECOMMEND_DECAY_LAMBDA,
) -> float:
    """指数时间衰减权重 exp(-lambda * age_days)，未来时间按 0 天处理。"""
    now = now or datetime.now()
    age_days = max((now - pub_time).total_seconds() / 86400.0, 0.0)
    return math.exp(-decay_lambda * age_days)


# 与 time_decay_weight 数学等价的 SQL 表达式，供推荐流/排行榜在库侧施加读时衰减。
# 占位参数传 -RECOMMEND_DECAY_LAMBDA；GREATEST 把未来发布时间钳到 0 天。
# 引用别名：打分表须以 s 别名接入，新闻表须以 n 别名接入。
FINAL_SCORE_EXPR = (
    "s.importance_score * EXP(%s * GREATEST("
    "TIMESTAMPDIFF(MINUTE, n.pub_time, NOW()) / 1440.0, 0))"
)


def apply_decay(
    importance_score: float,
    pub_time: datetime,
    now: Optional[datetime] = None,
    decay_lambda: float = RECOMMEND_DECAY_LAMBDA,
) -> float:
    """静态分叠加时间衰减后的最终分（0-100）。"""
    final = float(importance_score) * time_decay_weight(pub_time, now, decay_lambda)
    return round(final, 4)
