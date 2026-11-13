"""预测报告的确定性上下文。

方向口径、数据截止日期等元数据由代码写入，不交给 LLM 猜测。
该模块不依赖数据库或 LLM 客户端，便于独立测试。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

FORECAST_TARGET = {
    "名称": "中债国债到期收益率",
    "期限": "10Y",
    "方向口径": "上涨/下跌均指10Y国债收益率上行/下行，债券价格方向相反",
}


def _date_text(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    return str(value) if value is not None else ""


def attach_forecast_context(
    forecast_data: dict[str, Any],
    news_data: list[dict[str, Any]],
    yield_data: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    """向 LLM 结果附加预测标的及真实输入数据范围（原地补充并返回）。"""
    news_dates = [_date_text(item.get("pub_date")) for item in news_data]
    yield_dates = [
        _date_text(point.get("date"))
        for points in yield_data.values()
        for point in points
    ]
    news_dates = [value for value in news_dates if value]
    yield_dates = [value for value in yield_dates if value]

    # LLM 只能引用本次真实输入的新闻；过滤幻觉 ID、字符串 ID 与重复项。
    input_news_ids = {
        item.get("id")
        for item in news_data
        if isinstance(item.get("id"), int) and not isinstance(item.get("id"), bool)
    }
    drivers = forecast_data.get("核心驱动")
    if isinstance(drivers, list):
        for driver in drivers:
            if not isinstance(driver, dict):
                continue
            evidence_ids = driver.get("证据新闻ID")
            if not isinstance(evidence_ids, list):
                driver["证据新闻ID"] = []
                continue
            driver["证据新闻ID"] = list(dict.fromkeys(
                news_id for news_id in evidence_ids
                if isinstance(news_id, int)
                and not isinstance(news_id, bool)
                and news_id in input_news_ids
            ))

    forecast_data["预测标的"] = dict(FORECAST_TARGET)
    forecast_data["数据状态"] = {
        "包含新闻": bool(news_data),
        "包含收益率": bool(yield_dates),
        "新闻截至": max(news_dates) if news_dates else None,
        "收益率截至": max(yield_dates) if yield_dates else None,
    }
    return forecast_data
