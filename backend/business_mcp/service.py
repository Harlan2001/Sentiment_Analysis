"""Compose existing domain capabilities into independently useful business results.

The public MCP process still talks to FastAPI over HTTP.  This module lives behind
that HTTP boundary so the orchestration can also be reused by non-MCP callers.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any

from fastapi import HTTPException

from backend.agent.chat_service import agent_chat_stream
from backend.agent.references import cited_news_references
from backend.routers.forecast import get_forecast_report
from backend.routers.returns import returns_calendar


def get_news(*args, **kwargs):
    from backend.routers.news import get_news as implementation

    return implementation(*args, **kwargs)


def get_news_detail(*args, **kwargs):
    from backend.routers.news import get_news_detail as implementation

    return implementation(*args, **kwargs)


def get_news_yield_data(*args, **kwargs):
    from backend.routers.news import get_news_yield_data as implementation

    return implementation(*args, **kwargs)


def similar_news(*args, **kwargs):
    from backend.routers.news import similar_news as implementation

    return implementation(*args, **kwargs)


def _data(response: Any) -> Any:
    if isinstance(response, dict) and set(response) == {"data"}:
        return response["data"]
    return response


def _direction(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"positive", "bullish", "利多", "利好", "涨"}:
        return "利多"
    if normalized in {"negative", "bearish", "利空", "跌"}:
        return "利空"
    return "中性"


async def ask_sentiment(question: str) -> dict[str, Any]:
    """调用现有 Agent 生成完整回复，并将流式分片聚合为 Markdown。"""
    parts: list[str] = []
    collected_references: list[dict[str, Any]] = []
    messages = [{"role": "user", "content": question}]
    async for delta in agent_chat_stream(
        messages, "anonymous", reference_collector=collected_references
    ):
        parts.append(delta)

    markdown = "".join(parts).strip()
    if not markdown:
        raise RuntimeError("Sentiment 未生成有效回复")
    return {
        "markdown": markdown,
        "references": cited_news_references(markdown, collected_references),
    }


def _market_sentiment_payload(
    news: list[dict[str, Any]],
    *,
    start_date: str,
    end_date: str,
    keyword: str | None,
    source: str | None,
) -> dict[str, Any]:
    counts = Counter(_direction(item.get("direction")) for item in news)
    total = len(news)
    analyzed = sum(
        1 for item in news if str(item.get("reason") or "").strip() not in {"", "待分析"}
    )
    score = round((counts["利多"] - counts["利空"]) / total, 4) if total else 0.0
    if score > 0.1:
        dominant = "利多"
    elif score < -0.1:
        dominant = "利空"
    else:
        dominant = "中性"

    def representatives(direction: str) -> list[dict[str, Any]]:
        return [
            {
                "news_id": item.get("id"),
                "title": item.get("title"),
                "publish_time": item.get("publish_time") or item.get("pub_time"),
                "source": item.get("source"),
                "direction": _direction(item.get("direction")),
                "horizon": item.get("horizon"),
                "reason": item.get("reason"),
            }
            for item in news
            if _direction(item.get("direction")) == direction
        ][:5]

    return {
        "query": {
            "start_date": start_date,
            "end_date": end_date,
            "keyword": keyword,
            "source": source,
        },
        "summary": {
            "dominant_direction": dominant,
            "sentiment_score": score,
            "total_news": total,
            "bullish_count": counts["利多"],
            "bearish_count": counts["利空"],
            "neutral_count": counts["中性"],
            "analyzed_count": analyzed,
            "analysis_coverage": round(analyzed / total, 4) if total else 0.0,
        },
        "representative_bullish_news": representatives("利多"),
        "representative_bearish_news": representatives("利空"),
        "limitations": (
            []
            if total and analyzed == total
            else ["部分或全部新闻尚未完成 AI 分析，汇总结论可能不完整"]
        ),
    }


async def analyze_bond_sentiment(news_id: int, force_refresh: bool = False) -> dict[str, Any]:
    current = _data(get_news_detail(news_id, model=None, include_all_models=False))
    needs_analysis = str(current.get("reason") or "").strip() in {"", "待分析"}
    refreshed = force_refresh or needs_analysis
    if refreshed:
        from backend.analysis.analyzer import process_single_news_analysis

        result = await process_single_news_analysis(news_id)
        if not result.get("success"):
            raise RuntimeError(result.get("message") or "新闻舆情分析失败")
        current = _data(get_news_detail(news_id, model=None, include_all_models=False))
    return {
        "news_id": news_id,
        "title": current.get("title"),
        "publish_time": current.get("publish_time"),
        "source": current.get("source"),
        "source_url": current.get("source_url"),
        "content": current.get("content"),
        "direction": _direction(current.get("direction")),
        "horizon": current.get("horizon"),
        "reason": current.get("reason"),
        "factors": current.get("factors") or [],
        "model": current.get("model"),
        "refreshed": refreshed,
        "data_as_of": current.get("publish_time"),
    }


def analyze_bond_market_sentiment(
    start_date: str,
    end_date: str,
    *,
    keyword: str | None = None,
    source: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    news = _data(
        get_news(
            date=None,
            start_date=start_date,
            end_date=end_date,
            source=source,
            keyword=keyword,
            model=None,
            view="best",
            include_content=False,
            limit=limit,
            offset=0,
        )
    )
    return _market_sentiment_payload(
        news,
        start_date=start_date,
        end_date=end_date,
        keyword=keyword,
        source=source,
    )


def explain_bond_market_move(trade_date: str, maturity: str = "10Y") -> dict[str, Any]:
    calendar = _data(returns_calendar(start=trade_date, end=trade_date))
    yield_point = (calendar.get("yields_by_date") or {}).get(trade_date, {}).get(maturity)
    news = (calendar.get("news_by_date") or {}).get(trade_date, [])
    active_factors = []
    for item in calendar.get("days") or []:
        if item.get("date") == trade_date:
            active_factors = item.get("active_factors") or []
            break

    diff_bp = yield_point.get("diff_bp") if yield_point else None
    expected_news_direction = "利空" if diff_bp and diff_bp > 0 else "利多" if diff_bp and diff_bp < 0 else None
    supporting = [item for item in news if _direction(item.get("direction")) == expected_news_direction]
    contradicting = [
        item
        for item in news
        if expected_news_direction and _direction(item.get("direction")) not in {expected_news_direction, "中性"}
    ]
    confidence = 0.0
    if yield_point:
        confidence += 0.35
    if supporting:
        confidence += 0.35
    if active_factors:
        confidence += 0.2
    if contradicting:
        confidence -= min(0.15, len(contradicting) * 0.03)

    return {
        "trade_date": trade_date,
        "maturity": maturity,
        "market_change": yield_point,
        "primary_drivers": [
            {
                "news_id": item.get("id"),
                "title": item.get("title"),
                "direction": _direction(item.get("direction")),
                "reason": item.get("reason"),
                "factors": item.get("factors") or [],
            }
            for item in supporting[:5]
        ],
        "active_factors": active_factors,
        "contradicting_evidence": [
            {"news_id": item.get("id"), "title": item.get("title"), "reason": item.get("reason")}
            for item in contradicting[:5]
        ],
        "unexplained": not bool(yield_point and supporting),
        "confidence": round(max(0.0, min(confidence, 1.0)), 2),
        "method": "收益率变动方向与当日已分析新闻、活跃因子的规则归因",
        "limitations": ["归因反映可观测新闻与因子的一致性，不代表完整的因果识别"],
    }


def analyze_similar_event_impact(
    news_id: int,
    *,
    top_k: int = 5,
    maturity: str = "10年",
    window_before: int = 5,
    window_after: int = 5,
) -> dict[str, Any]:
    current = _data(get_news_detail(news_id, model=None, include_all_models=False))
    matches = _data(similar_news(news_id=news_id, top_k=top_k))
    events = []
    for match in matches:
        candidate_id = int(match["news_id"])
        detail = _data(get_news_detail(candidate_id, model=None, include_all_models=False))
        try:
            impact = _data(
                get_news_yield_data(
                    candidate_id,
                    period=maturity,
                    window_before=window_before,
                    window_after=window_after,
                )
            )
        except HTTPException:
            impact = {"data": [], "relative_changes": []}
        points = impact.get("data") or []
        change_bp = None
        if len(points) >= 2:
            change_bp = round((float(points[-1]["value"]) - float(points[0]["value"])) * 100, 2)
        events.append(
            {
                "news_id": candidate_id,
                "title": detail.get("title") or match.get("title"),
                "similarity_score": match.get("score"),
                "publish_time": detail.get("publish_time"),
                "direction": _direction(detail.get("direction")),
                "horizon": detail.get("horizon"),
                "reason": detail.get("reason"),
                "yield_change_bp": change_bp,
                "yield_window": points,
            }
        )
    observed = [event["yield_change_bp"] for event in events if event["yield_change_bp"] is not None]
    return {
        "current_event": {
            "news_id": news_id,
            "title": current.get("title"),
            "direction": _direction(current.get("direction")),
            "reason": current.get("reason"),
        },
        "maturity": maturity,
        "similar_events": events,
        "historical_summary": {
            "events_with_yield_data": len(observed),
            "average_yield_change_bp": round(sum(observed) / len(observed), 2) if observed else None,
            "up_count": sum(1 for value in observed if value > 0),
            "down_count": sum(1 for value in observed if value < 0),
        },
        "limitations": ["语义相似不等于市场环境相同，历史表现不能直接外推"],
    }


async def generate_bond_market_forecast(report_date: str, force_refresh: bool = False) -> dict[str, Any]:
    existing = _data(get_forecast_report(date=report_date, limit=10))
    if existing.get("count") and not force_refresh:
        return {"generated": False, "cache_hit": True, **existing}
    from backend.analysis.generate_report import generate_for_news_date

    generated = await asyncio.to_thread(generate_for_news_date, report_date)
    result = _data(get_forecast_report(date=report_date, limit=10))
    return {"generated": bool(generated), "cache_hit": False, **result}


def generate_news_digest(
    start_date: str,
    end_date: str,
    *,
    focus: str | None = None,
    source: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    sentiment = analyze_bond_market_sentiment(
        start_date,
        end_date,
        keyword=focus,
        source=source,
        limit=limit,
    )
    summary = sentiment["summary"]
    return {
        "query": sentiment["query"],
        "headline": (
            f"{start_date} 至 {end_date} 共纳入 {summary['total_news']} 条新闻，"
            f"债市舆情整体{summary['dominant_direction']}"
        ),
        "sentiment": summary,
        "key_bullish_news": sentiment["representative_bullish_news"],
        "key_bearish_news": sentiment["representative_bearish_news"],
        "follow_ups": [
            item["title"]
            for item in (
                sentiment["representative_bullish_news"]
                + sentiment["representative_bearish_news"]
            )[:5]
            if item.get("title")
        ],
        "limitations": sentiment["limitations"],
    }
