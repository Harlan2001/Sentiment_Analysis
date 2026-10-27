"""中美利差 API。

数据源：美国财政部官方 CSV（合规）；中债 10Y 来自库内 yield_data。
利差 = 中债 10Y − 美债 10Y，**只在双方都有数据的日期计算，不插值**。
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.common.api_response import ok
from backend.config.config import API_PREFIX
from backend.repositories.treasury_yield_repository import (
    DEFAULT_TERM,
    TreasuryYieldRepository,
)
from backend.tools.treasury_source import TreasurySourceError, fetch_treasury_yields

logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"{API_PREFIX}/treasury", tags=["treasury"])


def _repository() -> TreasuryYieldRepository:
    return TreasuryYieldRepository.from_environment()


def _percentile(values: list[float], current: float) -> float | None:
    """当前值在历史序列中的分位（0-100）。"""
    if not values:
        return None
    return round(sum(1 for value in values if value <= current) / len(values) * 100, 1)


@router.get("/overview")
def get_overview(term: str = Query(DEFAULT_TERM, description="期限码：2Y/10Y/30Y")):
    """中美利差概览：当前值、历史分位、区间、序列。"""
    repository = _repository()
    series = repository.get_spread_series(term, limit=250)
    if not series:
        return ok(
            {
                "term": term,
                "latest": None,
                "available_terms": repository.get_available_terms(),
                "series": [],
                "curve": [],
            }
        )

    spreads = [item["spread_bp"] for item in series]
    latest = series[-1]
    return ok(
        {
            "term": term,
            "latest": latest,
            "percentile": _percentile(spreads, latest["spread_bp"]),
            "min_bp": min(spreads),
            "max_bp": max(spreads),
            "avg_bp": round(sum(spreads) / len(spreads), 2),
            "sample_size": len(series),
            "available_terms": repository.get_available_terms(),
            "series": series,
            "curve": repository.get_curve(),
        }
    )


@router.post("/sync")
def sync_treasury(year: int | None = Query(None, description="年份，缺省取今年")):
    """抓取美国财政部美债收益率并入库（幂等）。"""
    try:
        records = fetch_treasury_yields(year)
    except TreasurySourceError as exc:
        logger.error("美债同步失败: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    stats = _repository().upsert_many(records)
    return ok({"year": year or date.today().year, "fetched": len(records), **stats})