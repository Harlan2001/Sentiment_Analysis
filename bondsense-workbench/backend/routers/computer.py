"""Computer 工作台路由 — 策略会话、研报和新闻总结代理。"""

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator
from typing import Optional

from backend.config.config import API_PREFIX
from backend.integrations.legacy_api import LegacyApiError


router = APIRouter(prefix=f"{API_PREFIX}/computer", tags=["workbench-computer"])


# ── 请求模型 ──────────────────────────────────────────────

class StrategyCreateRequest(BaseModel):
    title: str = Field(default="新策略对话", min_length=1, max_length=255)


class StrategyDraftRequest(BaseModel):
    requirement: str = Field(min_length=1, max_length=2000)
    lookback_days: int = Field(default=7, ge=1, le=30)

    @field_validator("requirement")
    @classmethod
    def validate_requirement(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("不能为空")
        return value


class StrategyConfirmRequest(BaseModel):
    edited_prompt: str = Field(min_length=1, max_length=30000)


# ── 端点 ──────────────────────────────────────────────────

@router.get("/strategy-conversations")
async def list_strategy_conversations(request: Request, limit: int = Query(default=50, ge=1, le=100)):
    try:
        items = await request.app.state.legacy_api.list_strategy_conversations(
            request.headers.get("Authorization"), limit,
        )
    except LegacyApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return {"data": {"items": items}}


@router.post("/strategy-conversations", status_code=201)
async def create_strategy_conversation(request: Request, body: StrategyCreateRequest):
    try:
        result = await request.app.state.legacy_api.create_strategy_conversation(
            body.title, request.headers.get("Authorization"),
        )
    except LegacyApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return {"data": result}


@router.get("/strategy-conversations/{conversation_id}")
async def get_strategy_conversation(request: Request, conversation_id: int):
    try:
        result = await request.app.state.legacy_api.get_strategy_conversation(
            conversation_id, request.headers.get("Authorization"),
        )
    except LegacyApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return {"data": result}


@router.post("/strategy-conversations/{conversation_id}/draft")
async def create_strategy_draft(request: Request, conversation_id: int, body: StrategyDraftRequest):
    try:
        result = await request.app.state.legacy_api.create_strategy_draft(
            conversation_id, body.requirement, body.lookback_days,
            request.headers.get("Authorization"),
        )
    except LegacyApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return {"data": result}


@router.post("/strategy-conversations/{conversation_id}/drafts/{assistant_message_id}/confirm")
async def confirm_strategy_draft(request: Request, conversation_id: int, assistant_message_id: int, body: StrategyConfirmRequest):
    try:
        result = await request.app.state.legacy_api.confirm_strategy_draft(
            conversation_id, assistant_message_id, body.edited_prompt,
            request.headers.get("Authorization"),
        )
    except LegacyApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return {"data": result}


@router.patch("/strategy-conversations/{conversation_id}/archive")
async def archive_strategy_conversation(request: Request, conversation_id: int):
    try:
        await request.app.state.legacy_api.archive_strategy_conversation(
            conversation_id, request.headers.get("Authorization"),
        )
    except LegacyApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    return {"data": {"archived": True}}
