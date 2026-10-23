"""国债期货持仓 API。

数据源：中金所成交持仓排名（公开 CSV，每日快照）。
仅覆盖 T / TF / TS / TL 四个国债期货品种。
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.common.api_response import ok
from backend.config.config import API_PREFIX
from backend.repositories.futures_position_repository import FuturesPositionRepository
from backend.tools.futures_source import (
    VARIETIES,
    VARIETY_LABELS,
    FuturesSourceError,
    fetch_positions,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"{API_PREFIX}/futures", tags=["futures"])


def _repository() -> FuturesPositionRepository:
    return FuturesPositionRepository.from_environment()


@router.get("/overview")
def get_overview():
    """最新交易日的品种列表与四品种多空比对比。"""
    repository = _repository()
    latest = repository.latest_trade_date()
    if not latest:
        return ok(
            {
                "trade_date": None,
                "varieties": [
                    {"variety": v, "label": VARIETY_LABELS[v]} for v in VARIETIES
                ],
                "contracts": [],
                "comparison": [],
            }
        )
    return ok(
        {
            "trade_date": str(latest),
            "varieties": [{"variety": v, "label": VARIETY_LABELS[v]} for v in VARIETIES],
            "contracts": repository.list_contracts(latest),
            "comparison": repository.get_variety_comparison(latest),
        }
    )


@router.get("/ranking")
def get_ranking(
    contract: str = Query(..., description="合约代码，如 T2612"),
    trade_date: str | None = Query(None, description="交易日 YYYY-MM-DD，缺省取最新"),
):
    """指定合约的持仓排名（前 20 会员）+ 多空合计与多空比。"""
    repository = _repository()
    target = trade_date or repository.latest_trade_date()
    if not target:
        raise HTTPException(status_code=404, detail="暂无国债期货持仓数据")
    result = repository.get_ranking(target, contract)
    if not result["rows"]:
        raise HTTPException(status_code=404, detail=f"未找到合约持仓: {contract}")
    return ok(result)


@router.get("/trend")
def get_trend(
    variety: str = Query("T", description="品种 T/TF/TS/TL"),
    limit: int = Query(60, ge=5, le=250),
):
    """某品种的多空比走势（近 limit 个交易日）。"""
    if variety not in VARIETIES:
        raise HTTPException(status_code=400, detail=f"未知品种: {variety}")
    series = _repository().get_ratio_trend(variety, limit)
    return ok({"variety": variety, "label": VARIETY_LABELS[variety], "series": series})


@router.post("/sync")
def sync_positions(
    trade_date: str | None = Query(None, description="交易日 YYYY-MM-DD，缺省为今天"),
):
    """抓取指定交易日（缺省今天）四个国债期货品种的持仓排名并入库（幂等）。"""
    target = date.today()
    if trade_date:
        try:
            target = date.fromisoformat(trade_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD") from None

    try:
        records = fetch_positions(target)
    except FuturesSourceError as exc:
        logger.error("国债期货持仓同步失败: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    stats = _repository().upsert_many(records)
    return ok(
        {
            "trade_date": str(target),
            "fetched": len(records),
            "inserted": stats["inserted"],
            "updated": stats["updated"],
        }
    )