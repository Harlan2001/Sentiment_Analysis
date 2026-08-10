from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, Body, HTTPException
from openai import OpenAI
from pydantic import BaseModel

from backend.config.config import API_PREFIX, create_openai_http_client
from backend.strategy.portfolio_strategy import get_portfolio_strategy_service
from backend.strategy.strategy_push import get_strategy_push_service

kingstar_API_KEY = os.getenv("kingstar_API_KEY")
kingstar_BASE_URL = os.getenv("kingstar_BASE_URL")
kingstar_client = OpenAI(
    api_key=kingstar_API_KEY,
    base_url=kingstar_BASE_URL,
    http_client=create_openai_http_client(),
)

strategy_push_service = get_strategy_push_service(kingstar_client)
portfolio_strategy_service = get_portfolio_strategy_service(kingstar_client)

router = APIRouter(prefix=f"{API_PREFIX}/strategy", tags=["strategy"])


class StrategyTriggerRequest(BaseModel):
    run_now: bool = True


class PortfolioStrategyRequest(BaseModel):
    force_refresh: bool = False


@router.get("/snapshot")
async def get_strategy_snapshot():
    return await strategy_push_service.get_snapshot()


@router.post("/trigger")
async def trigger_strategy_snapshot(
    _: StrategyTriggerRequest = Body(default=StrategyTriggerRequest()),
):
    snapshot = await strategy_push_service.trigger_now()
    return {"success": True, "snapshot": snapshot}


@router.get("/sse")
async def strategy_sse():
    queue = await strategy_push_service.subscribe()

    async def event_stream():
        try:
            yield "retry: 5000\n\n"
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=20)
                    yield f"event: strategy_full_snapshot\ndata: {payload}\n\n"
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: {}\n\n"
        finally:
            await strategy_push_service.unsubscribe(queue)

    from fastapi.responses import StreamingResponse

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/portfolio-analysis")
async def portfolio_strategy_analysis(
    request: PortfolioStrategyRequest = Body(default=PortfolioStrategyRequest()),
):
    try:
        result = await portfolio_strategy_service.analyze(
            force_refresh=request.force_refresh
        )
        return {"success": True, "data": result["data"], "meta": result["meta"]}
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"组合策略分析失败: {str(exc)}"
        ) from exc


async def start_strategy_services() -> None:
    await strategy_push_service.start()


async def stop_strategy_services() -> None:
    await strategy_push_service.stop()
