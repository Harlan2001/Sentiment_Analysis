"""策略推送 SSE 服务：快照查询 + 生命周期启停（由流水线触发推送）。"""

from __future__ import annotations

from fastapi import APIRouter

from backend.common.api_response import ok
from backend.common.llm_call import get_llm_client
from backend.config.config import API_PREFIX
from backend.strategy.strategy_push import get_strategy_push_service

llm_client = get_llm_client()
if llm_client is None:
    raise RuntimeError("LLM 客户端未初始化（缺少 LLM_API_KEY / LLM_BASE_URL）")

strategy_push_service = get_strategy_push_service(llm_client)

router = APIRouter(prefix=f"{API_PREFIX}/strategy", tags=["strategy"])


@router.get("/snapshot")
async def get_strategy_snapshot():
    return ok(await strategy_push_service.get_snapshot())


async def start_strategy_services() -> None:
    await strategy_push_service.start()


async def stop_strategy_services() -> None:
    await strategy_push_service.stop()