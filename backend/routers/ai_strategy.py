import logging

from fastapi import APIRouter, HTTPException, Query

from backend.common.api_response import ok
from backend.config.config import API_PREFIX
from backend.strategy.strategy_recommendation import (
    get_all_strategies,
    get_latest_recommendation,
    get_recommendation_history,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=f"{API_PREFIX}/ai-strategy-recommendation", tags=["ai-strategy"]
)


@router.get("/latest")
def latest_recommendation():
    try:
        return ok(get_latest_recommendation())
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("最新推荐读取失败")
        raise HTTPException(status_code=500, detail=f"最新推荐读取失败: {exc}") from exc


@router.get("/history")
def recommendation_history(limit: int = Query(50, ge=1, le=200)):
    try:
        return ok({"items": get_recommendation_history(limit)})
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("推荐历史读取失败")
        raise HTTPException(status_code=500, detail=f"推荐历史读取失败: {exc}") from exc


@router.get("/strategies")
def list_all_strategies():
    """统一获取所有策略列表（量化策略 + 交易策略），字段已标准化并带有中文标签"""
    try:
        return ok(get_all_strategies())
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("策略列表获取失败")
        raise HTTPException(status_code=500, detail=f"策略列表获取失败: {exc}") from exc