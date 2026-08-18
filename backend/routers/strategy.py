"""策略推送 SSE 服务：快照查询 + 生命周期启停（由流水线触发推送）。"""

from __future__ import annotations

import os

from fastapi import APIRouter
from openai import OpenAI

from backend.config.config import API_PREFIX, create_openai_http_client
from backend.strategy.strategy_push import get_strategy_push_service

kingstar_API_KEY = os.getenv("kingstar_API_KEY")
kingstar_BASE_URL = os.getenv("kingstar_BASE_URL")
kingstar_client = OpenAI(
    api_key=kingstar_API_KEY,
    base_url=kingstar_BASE_URL,
    http_client=create_openai_http_client(),
)

strategy_push_service = get_strategy_push_service(kingstar_client)

router = APIRouter(prefix=f"{API_PREFIX}/strategy", tags=["strategy"])


@router.get("/snapshot")
async def get_strategy_snapshot():
    return await strategy_push_service.get_snapshot()


async def start_strategy_services() -> None:
    await strategy_push_service.start()


async def stop_strategy_services() -> None:
    await strategy_push_service.stop()