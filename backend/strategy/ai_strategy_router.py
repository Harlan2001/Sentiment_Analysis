import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from backend.strategy.ai_strategy_recommendation import (
    get_all_strategies,
    get_latest_recommendation,
    get_or_create_recommendation,
    get_recommendation_history,
)

logger = logging.getLogger("ai_strategy_router")

router = APIRouter(prefix="/api/ai-strategy-recommendation", tags=["ai-strategy"])


class RecommendationRequest(BaseModel):
    analysis_date: Optional[date] = None
    force_refresh: bool = False
    model_name: Optional[str] = None


@router.post("/analyze")
async def analyze_recommendation(
    request: RecommendationRequest = Body(default=RecommendationRequest()),
):
    try:
        return await get_or_create_recommendation(
            target_date=request.analysis_date,
            force_refresh=request.force_refresh,
            model_name=request.model_name,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("AI推荐生成失败")
        raise HTTPException(status_code=500, detail=f"AI推荐生成失败: {exc}") from exc


@router.get("/latest")
def latest_recommendation():
    try:
        data = get_latest_recommendation()
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("最新推荐读取失败")
        raise HTTPException(status_code=500, detail=f"最新推荐读取失败: {exc}") from exc


@router.get("/history")
def recommendation_history(limit: int = Query(50, ge=1, le=200)):
    try:
        return {"success": True, "items": get_recommendation_history(limit)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("推荐历史读取失败")
        raise HTTPException(status_code=500, detail=f"推荐历史读取失败: {exc}") from exc


@router.get("/strategies")
def list_all_strategies():
    """统一获取所有策略列表（量化策略 + 交易策略），字段已标准化并带有中文标签"""
    try:
        data = get_all_strategies()
        return {"success": True, **data}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("策略列表获取失败")
        raise HTTPException(status_code=500, detail=f"策略列表获取失败: {exc}") from exc
