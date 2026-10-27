"""美债收益率取数：美国财政部官方 CSV。

**合规性**：美国政府官方公开数据，无授权风险（已通过项目的数据源筛查）。

CSV 格式：Date 列（MM/DD/YYYY）+ 各期限列（"2 Yr"/"10 Yr"/"30 Yr"）。
本模块只取 2Y/10Y/30Y 三个关键期限，供中美利差使用。
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date
from typing import Any

import requests

from backend.config.config import get_requests_proxies

logger = logging.getLogger(__name__)

_ENDPOINT = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
    "?type=daily_treasury_yield_curve&field_tdr_date_value={year}&_format=csv"
)

# CSV 列名 → 期限码
_TERM_COLUMNS: dict[str, str] = {
    "2 Yr": "2Y",
    "10 Yr": "10Y",
    "30 Yr": "30Y",
}


class TreasurySourceError(RuntimeError):
    """取数失败（网络异常 / 格式变化）。"""


def _parse_date(raw: str) -> str | None:
    """MM/DD/YYYY → YYYY-MM-DD；解析失败返回 None。"""
    parts = (raw or "").strip().split("/")
    if len(parts) != 3:
        return None
    month, day, year = parts
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return None


def fetch_treasury_yields(year: int | None = None) -> list[dict[str, Any]]:
    """抓取指定年份的美债收益率（2Y/10Y/30Y）。

    某期限缺值（如早期年份无 30Y）只跳过该格，不影响其它期限。
    """
    target_year = year or date.today().year
    url = _ENDPOINT.format(year=target_year)

    try:
        response = requests.get(url, timeout=60, proxies=get_requests_proxies())
        response.raise_for_status()
    except Exception as exc:
        raise TreasurySourceError(f"美债数据获取失败: {exc}") from exc

    try:
        rows = list(csv.DictReader(io.StringIO(response.text)))
    except Exception as exc:
        raise TreasurySourceError(f"美债 CSV 解析失败: {exc}") from exc

    if not rows:
        raise TreasurySourceError("美债数据为空，请检查数据源可用性")

    records: list[dict[str, Any]] = []
    for row in rows:
        trade_date = _parse_date(row.get("Date", ""))
        if not trade_date:
            continue
        for column, term in _TERM_COLUMNS.items():
            raw = (row.get(column) or "").strip()
            if not raw:
                continue
            try:
                value = float(raw)
            except ValueError:
                continue
            records.append({"trade_date": trade_date, "term": term, "value": round(value, 4)})

    if not records:
        raise TreasurySourceError("美债数据未解析出有效记录")

    logger.info("美债取数完成: %d 条（%d 年）", len(records), target_year)
    return records