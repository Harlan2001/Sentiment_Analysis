"""策略推送 SSE 服务：快照查询 + 生命周期启停（由流水线触发推送）。"""

from __future__ import annotations

from fastapi import APIRouter
from openai import OpenAI

from backend.config.config import (
    API_PREFIX,
    create_openai_http_client,
    get_llm_api_key,
    get_llm_base_url,
)
from backend.strategy.strategy_push import get_strategy_push_service

llm_client = OpenAI(
    api_key=get_llm_api_key(),
    base_url=get_llm_base_url(),
    http_client=create_openai_http_client(),
)

strategy_push_service = get_strategy_push_service(llm_client)

router = APIRouter(prefix=f"{API_PREFIX}/strategy", tags=["strategy"])


@router.get("/snapshot")
async def get_strategy_snapshot():
    return await strategy_push_service.get_snapshot()


async def start_strategy_services() -> None:
    await strategy_push_service.start()


async def stop_strategy_services() -> None:
    await strategy_push_service.stop()