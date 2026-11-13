"""收益日历纯规则：收益率差分、新闻方向对齐与静态重要性排序。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Iterable, Optional

from backend.recommend.importance import normalize_direction

_DIRECTION_LABELS = {
    "positive": "利多",
    "negative": "利空",
    "neutral": "中性",
}


def _as_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def direction_label(value: Any) -> str:
    """沿用收益日历中文响应契约，未知方向按历史行为归入中性。"""
    return _DIRECTION_LABELS.get(normalize_direction(value), "中性")


def classify_market_alignment(diff_bp: Any, news_direction: Any) -> str:
    """比较收益率变动和 AI 新闻方向；只表示符号一致，不表示因果。

    收益率上行对应债券利空，下行对应债券利多。没有可计算的非零基准时，
    所有新闻均为 unavailable，避免把持平或缺数据解释成方向证据。
    """
    if diff_bp is None or float(diff_bp) == 0:
        return "unavailable"
    direction = normalize_direction(news_direction)
    if direction == "neutral":
        return "neutral"
    if direction not in {"positive", "negative"}:
        return "unavailable"
    supporting = "negative" if float(diff_bp) > 0 else "positive"
    return "supporting" if direction == supporting else "opposing"


def build_yield_change_map(
    *,
    rows: Iterable[tuple[Any, Any]],
    previous: Optional[tuple[Any, Any]],
    start: date,
    end: date,
    label: str,
) -> dict[str, dict[str, Any]]:
    """用实际相邻行情记录计算差分，而非假设前一自然日有数据。

    ``previous`` 是 start 前最近一条记录；rows 通常只含请求范围内的记录。
    缺前值的 diff_bp 为 None，只有真实相等的相邻值才返回 0/flat。
    """
    previous_row = previous
    result: dict[str, dict[str, Any]] = {}
    ordered_rows = sorted(rows, key=lambda row: _as_date(row[0]))
    for raw_day, raw_value in ordered_rows:
        day = _as_date(raw_day)
        value = float(raw_value)
        if start <= day <= end:
            if previous_row is None:
                diff_bp = None
                direction = "unavailable"
                previous_date = None
            else:
                previous_day, previous_raw_value = previous_row
                diff_bp = round((value - float(previous_raw_value)) * 100, 1)
                direction = "up" if diff_bp > 0 else "down" if diff_bp < 0 else "flat"
                previous_date = _as_date(previous_day).isoformat()
            result[day.isoformat()] = {
                "label": label,
                "value": value,
                "diff_bp": diff_bp,
                "direction": direction,
                "previous_date": previous_date,
            }
        previous_row = (day, raw_value)
    return result


def sort_news_by_importance(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """静态分优先，时间和 ID 打破并列；未评分新闻保留并沉底。"""
    def sort_key(item: dict[str, Any]) -> tuple:
        score = item.get("importance_score")
        return (
            score is not None,
            float(score) if score is not None else 0.0,
            str(item.get("pub_time") or ""),
            int(item.get("id") or 0),
        )

    return sorted(items, key=sort_key, reverse=True)
