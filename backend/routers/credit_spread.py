"""信用利差 API。

数据源：中债中短期票据曲线（与国债曲线同一接口，参数不同）。
利差 = 信用债收益率 − 同期限国债收益率，在查询时计算。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from backend.common.api_response import ok
from backend.config.config import API_PREFIX
from backend.repositories.credit_curve_repository import (
    COMMON_TERMS,
    DEFAULT_TERM,
    CreditCurveRepository,
)
from backend.tools.credit_curve_source import CreditCurveError, fetch_credit_curve

logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"{API_PREFIX}/credit-spread", tags=["credit-spread"])


def _repository() -> CreditCurveRepository:
    return CreditCurveRepository.from_environment()


def _percentile(values: list[float], current: float) -> float | None:
    """当前值在历史序列中的分位（0-100）。"""
    if not values:
        return None
    below = sum(1 for value in values if value <= current)
    return round(below / len(values) * 100, 1)


@router.get("/overview")
def get_overview(term: str = Query(DEFAULT_TERM, description="期限码，如 10Y")):
    """某期限的信用利差概览：当前值、历史分位、区间。"""
    repository = _repository()
    series = repository.get_spread_series(term, limit=250)
    if not series:
        return ok(
            {
                "term": term,
                "latest": None,
                "available_terms": repository.get_available_terms(),
                "series": [],
                "term_structure": [],
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
            "term_structure": repository.get_term_structure(),
        }
    )


@router.get("/terms")
def get_terms():
    """可用的期限列表。"""
    return ok({"terms": _repository().get_available_terms(), "all_terms": list(COMMON_TERMS)})


@router.post("/sync")
def sync_credit_curve(days: int = Query(365, ge=30, le=365)):
    """从下载并导入中债信用债曲线（幂等）。"""
    try:
        records = fetch_credit_curve(days)
    except CreditCurveError as exc:
        logger.error("信用债曲线同步失败: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not records:
        raise HTTPException(status_code=502, detail="未解析到信用债曲线数据")

    stats = _repository().upsert_many(records)
    return ok(
        {
            "fetched": len(records),
            "inserted": stats["inserted"],
            "updated": stats["updated"],
        }
    )