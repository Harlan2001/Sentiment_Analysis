"""组合策略分析路由（POST /sapi/strategy/portfolio-analysis）。

按目标新闻日情绪生成债券组合配置约束建议；文档见 docs/组合策略API.md。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.common.api_response import ok
from backend.config.config import API_PREFIX
from backend.strategy.portfolio_analysis import (
    PortfolioAnalysisError,
    analyze_portfolio_strategy,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix=f"{API_PREFIX}/strategy", tags=["strategy"])


class PortfolioAnalysisRequest(BaseModel):
    force_refresh: bool = False


@router.post("/portfolio-analysis")
async def portfolio_analysis(body: PortfolioAnalysisRequest):
    """生成当日组合策略配置约束建议（命中缓存直接返回，force_refresh 强制重算）。"""
    try:
        result = await analyze_portfolio_strategy(force_refresh=body.force_refresh)
    except PortfolioAnalysisError as exc:
        logger.warning("组合策略分析失败: %s", exc)
        raise HTTPException(status_code=500, detail=f"组合策略分析失败: {exc}")
    return ok(result)