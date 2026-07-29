"""构建按交易标的筛选、可复现的 Sentiment 提示词上下文。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from backend.common.database import get_db_connection
from backend.config.config import get_default_analysis_model_name


DEFAULT_LOOKBACK_DAYS = 7
MAX_LOOKBACK_DAYS = 30
YIELD_PERIODS = ("1Y", "5Y", "10Y", "30Y")
SHORT_HORIZON = "短期"
BEIJING_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class MarketContextScope:
    """Defines the news universe and interpretation boundary for a strategy instrument."""

    label: str
    news_keywords: tuple[str, ...] = ()
    directional_trade_guidance: bool = True
    include_yield_curve: bool = True


DEFAULT_MARKET_SCOPE = MarketContextScope(label="债券市场")


def _direction_counts(rows: list[tuple[str, int]]) -> dict[str, int]:
    counts = {"positive": 0, "negative": 0, "neutral": 0}
    for direction, count in rows:
        normalized = (direction or "neutral").lower()
        counts[normalized if normalized in counts else "neutral"] += count
    return counts


def _direction_label(direction: str, scope: MarketContextScope) -> str:
    normalized = (direction or "neutral").lower()
    if not scope.directional_trade_guidance:
        return {"positive": "正向情绪标注", "negative": "负向情绪标注"}.get(normalized, "中性")
    return {"positive": f"利多{scope.label}", "negative": f"利空{scope.label}", "neutral": "中性"}.get(normalized, "中性")


def _reference_usage(direction: str, scope: MarketContextScope, in_sentiment_window: bool) -> str:
    """Explain whether a saved reference is directional evidence or background only."""
    window_label = "当前统计窗口" if in_sentiment_window else f"{MAX_LOOKBACK_DAYS}日补充背景"
    normalized = (direction or "neutral").lower()
    if not scope.directional_trade_guidance:
        return f"{window_label}的{scope.label}背景；不直接作为标的多空依据"
    if normalized in {"positive", "negative"} and in_sentiment_window:
        return "用于方向确认与风险过滤；不单独触发交易"
    return f"{window_label}的市场背景与风险提示；不单独触发交易"

def _compact_text(value: Any, limit: int = 56) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else f"{text[:limit]}…"


def _factor_names(factors: list[dict[str, Any]]) -> str:
    return "、".join(item["name"] for item in factors) if factors else "暂无高置信号"


def _build_synthesis(news_counts: dict[str, int], scope: MarketContextScope) -> str:
    if not scope.directional_trade_guidance:
        return (
            f"已按{scope.label}过滤新闻。现有分析模型的方向标签以债券语境为主，"
            "只能作为风险背景和信号过滤，不得直接解读为标的多空交易方向。"
        )
    directional_total = news_counts["positive"] + news_counts["negative"]
    if directional_total == 0:
        return "当前范围没有方向明确的新闻；不以新闻形成交易方向，等待价格和技术信号确认。"
    if news_counts["positive"] > news_counts["negative"]:
        return f"利多{scope.label}信号占优；仅在价格确认后考虑使用与趋势一致的仓位。"
    if news_counts["negative"] > news_counts["positive"]:
        return f"利空{scope.label}信号占优；仅在价格确认后收缩仓位或提高开仓阈值。"
    return "正负向信号均衡；保持中性仓位，不用新闻单独触发交易。"


def _scope_filter(scope: MarketContextScope) -> tuple[str, tuple[str, ...]]:
    if not scope.news_keywords:
        return "", ()
    predicates: list[str] = []
    params: list[str] = []
    for keyword in scope.news_keywords:
        # Title-only matching avoids treating an incidental mention in a long article as a relevant market event.
        predicates.append("COALESCE(n.title, '') LIKE %s")
        params.append(f"%{keyword}%")
    return f" AND ({' OR '.join(predicates)})", tuple(params)


def _build_prompt(
    reference_time: datetime,
    window_start: datetime,
    lookback_days: int,
    model_name: str,
    news_counts: dict[str, int],
    horizon_counts: dict[str, int],
    events: list[dict[str, Any]],
    positive_factors: list[dict[str, Any]],
    negative_factors: list[dict[str, Any]],
    yield_curve: list[dict[str, Any]],
    scope: MarketContextScope,
) -> str:
    event_text = "\n".join(
        f"- {item['pub_time']:%m-%d %H:%M} | {item['title']} | "
        f"{_direction_label(item['direction'], scope)}/{item['horizon']} | {item['reason']}"
        for item in events
    ) or "- 当前统计窗口及30日补充范围内暂无与标的匹配的新闻。"
    yield_text = "；".join(
        f"{item['period']} {item['value']:.2f}%（5日{item['change_5d_bp']:+.0f}bp）"
        for item in yield_curve
    ) if scope.include_yield_curve else "本标的不使用债券收益率曲线；价格和技术数据由策略运行时读取。"
    return (
        "【Sentiment -> 策略 AI 市场情报】\n"
        f"标的情报范围：{scope.label}；产生时点：{reference_time:%Y-%m-%d %H:%M}；"
        f"数据窗口：{window_start:%m-%d %H:%M}至{reference_time:%m-%d %H:%M}（{lookback_days}日）；分析模型：{model_name}。\n"
        "【一、提取来源】仅使用与当前标的匹配的 news、analysis 和 factor/news_factor 数据。\n"
        f"【二、新闻提取结果】方向明确{news_counts['positive'] + news_counts['negative']}条；"
        f"正向{news_counts['positive']}、负向{news_counts['negative']}；短期{horizon_counts.get(SHORT_HORIZON, 0)}条。\n"
        f"代表性新闻引用（优先当前统计窗口，不足时补充30日标题匹配背景）：\n{event_text}\n"
        f"【三、因子整合】正向因子：{_factor_names(positive_factors)}。"
        f"负向因子：{_factor_names(negative_factors)}。\n"
        f"【四、市场验证】{yield_text}。\n"
        f"【五、给策略 AI 的使用方式】{_build_synthesis(news_counts, scope)}"
        "新闻不代替价格、流动性和回测验证，不得单独作为交易触发。"
    )


def build_sentiment_strategy_context(
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    model_name: Optional[str] = None,
    scope: MarketContextScope = DEFAULT_MARKET_SCOPE,
) -> dict[str, Any]:
    """Build a read-only, instrument-scoped intelligence brief for strategy generation."""
    if not 1 <= lookback_days <= MAX_LOOKBACK_DAYS:
        raise ValueError(f"lookback_days must be between 1 and {MAX_LOOKBACK_DAYS}")

    selected_model = model_name or get_default_analysis_model_name()
    scope_sql, scope_params = _scope_filter(scope)
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT MAX(n.pub_time) FROM news n WHERE 1=1{scope_sql}", scope_params)
        reference_time = cur.fetchone()[0]
        if reference_time is None:
            # Keep the requested instrument scope empty instead of failing the
            # draft when there are no title-matched news items in this window.
            cur.execute("SELECT MAX(pub_time) FROM news")
            reference_time = cur.fetchone()[0]
            if reference_time is None:
                raise RuntimeError("No news is available to build a strategy context")
        window_start = reference_time - timedelta(days=lookback_days)

        cur.execute(
            f"""SELECT COALESCE(a.direction, 'neutral'), COUNT(*)
               FROM news n JOIN analysis a ON a.news_id=n.id
               WHERE a.model=%s AND n.pub_time>%s AND n.pub_time<=%s
                 AND LOWER(COALESCE(a.direction, 'neutral')) IN ('positive', 'negative'){scope_sql}
               GROUP BY COALESCE(a.direction, 'neutral')""",
            (selected_model, window_start, reference_time, *scope_params),
        )
        news_counts = _direction_counts(cur.fetchall())
        cur.execute(
            f"""SELECT COALESCE(a.horizon, '未标注'), COUNT(*)
               FROM news n JOIN analysis a ON a.news_id=n.id
               WHERE a.model=%s AND n.pub_time>%s AND n.pub_time<=%s
                 AND LOWER(COALESCE(a.direction, 'neutral')) IN ('positive', 'negative'){scope_sql}
               GROUP BY COALESCE(a.horizon, '未标注')""",
            (selected_model, window_start, reference_time, *scope_params),
        )
        horizon_counts = {horizon: count for horizon, count in cur.fetchall()}
        # Saved references may include neutral or not-yet-analysed title matches. Directional
        # counts remain strict, so background news never becomes a trading signal by accident.
        reference_window_start = reference_time - timedelta(days=MAX_LOOKBACK_DAYS)
        cur.execute(
            f"""SELECT n.id, n.title, n.pub_time, a.direction, a.horizon, a.reason,
                      CASE WHEN n.pub_time > %s THEN 1 ELSE 0 END AS in_sentiment_window
               FROM news n LEFT JOIN analysis a ON a.news_id=n.id AND a.model=%s
               WHERE n.pub_time>%s AND n.pub_time<=%s{scope_sql}
               ORDER BY in_sentiment_window DESC, n.pub_time DESC LIMIT 3""",
            (window_start, selected_model, reference_window_start, reference_time, *scope_params),
        )
        events = []
        for news_id, title, pub_time, direction, horizon, reason, in_sentiment_window in cur.fetchall():
            normalized_direction = (direction or "neutral").lower()
            if normalized_direction not in {"positive", "negative", "neutral"}:
                normalized_direction = "neutral"
            is_current_window = bool(in_sentiment_window)
            events.append(
                {
                    "news_id": news_id,
                    "title": title,
                    "pub_time": pub_time,
                    "direction": normalized_direction,
                    "direction_label": _direction_label(normalized_direction, scope),
                    "horizon": horizon or "未标注",
                    "reason": _compact_text(reason) or "该新闻尚无当前模型的方向分析，仅作为可追溯市场背景。",
                    "usage": _reference_usage(normalized_direction, scope, is_current_window),
                }
            )
        cur.execute(
            # Keep factor and news-analysis labels on the same model to avoid mixing model-specific directions.
            f"""SELECT f.code, f.name, f.category, f.factor_type, COUNT(*) AS event_count,
                      SUM(CASE LOWER(nf.direction) WHEN 'positive' THEN 1 WHEN 'negative' THEN -1 ELSE 0 END) AS net_direction,
                      MAX(nf.pub_time) AS latest_event_time
               FROM news_factor nf
               JOIN news n ON n.id=nf.news_id
               JOIN factor f ON f.id=nf.factor_id
               JOIN analysis a ON a.news_id=nf.news_id AND a.model=nf.model
               WHERE nf.model=%s AND n.pub_time>%s AND n.pub_time<=%s
                 AND LOWER(COALESCE(a.direction, 'neutral')) IN ('positive', 'negative')
                 AND LOWER(COALESCE(nf.direction, 'neutral')) IN ('positive', 'negative'){scope_sql}
               GROUP BY f.id, f.code, f.name, f.category, f.factor_type
               HAVING net_direction<>0
               ORDER BY ABS(net_direction) DESC, event_count DESC, latest_event_time DESC""",
            (selected_model, window_start, reference_time, *scope_params),
        )
        positive_factors: list[dict[str, Any]] = []
        negative_factors: list[dict[str, Any]] = []
        for code, name, category, factor_type, event_count, net_direction, latest_event_time in cur.fetchall():
            item = {
                "code": code,
                "name": name or code,
                "category": category,
                "factor_type": factor_type,
                "event_count": event_count,
                "net_direction": int(net_direction),
                "latest_event_time": latest_event_time,
            }
            target = positive_factors if net_direction > 0 else negative_factors
            if len(target) < 3:
                target.append(item)

        grouped_yields: dict[str, list[tuple[Any, float]]] = defaultdict(list)
        if scope.include_yield_curve:
            cur.execute("SELECT MAX(date) FROM yield_data WHERE date<=%s", (reference_time.date(),))
            latest_yield_date = cur.fetchone()[0]
            if latest_yield_date is not None:
                placeholders = ",".join(["%s"] * len(YIELD_PERIODS))
                cur.execute(
                    f"""SELECT period, date, value FROM yield_data
                        WHERE period IN ({placeholders}) AND date<=%s AND date>=%s
                        ORDER BY period, date""",
                    (*YIELD_PERIODS, latest_yield_date, latest_yield_date - timedelta(days=14)),
                )
                for period, value_date, value in cur.fetchall():
                    grouped_yields[period].append((value_date, float(value)))

    yield_curve: list[dict[str, Any]] = []
    for period in YIELD_PERIODS:
        rows = grouped_yields.get(period, [])
        if not rows:
            continue
        value_date, value = rows[-1]
        baseline = rows[-6][1] if len(rows) >= 6 else rows[0][1]
        yield_curve.append({"period": period, "date": value_date, "value": value, "change_5d_bp": round((value - baseline) * 100, 1)})

    prompt = _build_prompt(
        reference_time,
        window_start,
        lookback_days,
        selected_model,
        news_counts,
        horizon_counts,
        events,
        positive_factors,
        negative_factors,
        yield_curve,
        scope,
    )
    return {
        "generated_at": datetime.now(BEIJING_TZ).isoformat(timespec="seconds"),
        "reference_time": reference_time,
        "window_start": window_start,
        "lookback_days": lookback_days,
        "model_name": selected_model,
        "market_scope": {
            "label": scope.label,
            "keywords": list(scope.news_keywords),
            "directional_trade_guidance": scope.directional_trade_guidance,
        },
        "source_summary": {
            "news": ["id", "title", "pub_time"],
            "analysis": ["direction", "horizon", "reason"],
            "factors": ["code", "name", "category", "net_direction"],
            "yield_curve": ["period", "date", "value"],
        },
        "events": events,
        "prompt": prompt,
        "quant_message": {"role": "user", "content": prompt},
        "news_sentiment": {"counts": news_counts, "horizons": horizon_counts},
        "factors": {
            "positive": positive_factors,
            "negative": negative_factors,
            "bond_bullish": positive_factors,
            "bond_bearish": negative_factors,
        },
        "yield_curve": yield_curve,
    }
