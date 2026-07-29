"""AI 策略会话与两阶段生成流程的 HTTP 编排。"""

from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.config.config import AUTH_ENABLED
from backend.integrations.dream.service import generate_strategy
from backend.strategy.ai_strategy_history import (
    AiStrategyHistoryRepository,
    ArchivedConversationError,
    GenerationInProgressError,
    HistoryStoreConfigurationError,
)
from backend.strategy.dream_strategy_prompt import (
    apply_user_edited_requirement,
    build_dream_strategy_continuation_prompt,
    build_dream_strategy_prompt,
)


router = APIRouter(prefix="/api/ai-strategy-generation", tags=["ai-strategy-generation"])


class ConversationCreateRequest(BaseModel):
    title: str = Field(default="New strategy conversation", min_length=1, max_length=255)


class ConversationDraftRequest(BaseModel):
    requirement: str = Field(min_length=1, max_length=2000)
    lookback_days: int = Field(default=7, ge=1, le=30)
    model_name: Optional[str] = None


class PromptDraftConfirmRequest(BaseModel):
    edited_prompt: str = Field(min_length=1, max_length=30000)



def _history_owner(request: Request) -> str:
    """Resolve the history owner from server-authenticated request state only."""
    if AUTH_ENABLED:
        username = getattr(request.state, "username", None)
        if not username:
            raise HTTPException(status_code=401, detail="Sign in to access history conversations")
        return str(username)
    demo_owner = os.getenv("AI_STRATEGY_HISTORY_DEMO_OWNER", "").strip()
    if demo_owner:
        return demo_owner
    raise HTTPException(
        status_code=503,
        detail="History requires authentication or AI_STRATEGY_HISTORY_DEMO_OWNER in demo mode",
    )


def _history_repository() -> AiStrategyHistoryRepository:
    try:
        return AiStrategyHistoryRepository.from_environment()
    except HistoryStoreConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _history_generation_payload(
    conversation_id: int,
    assistant_message_id: int,
    result: dict[str, Any],
    final_sent_prompt: str,
    version: dict[str, Any] | None,
    references: list[dict[str, Any]],
) -> dict[str, Any]:
    strategy = result.get("strategy")
    return {
        "success": True,
        "data": {
            "conversation_id": conversation_id,
            "assistant_message_id": assistant_message_id,
            "version": version,
            "chat_message": result.get("summary", ""),
            "logic_overview": strategy["description"] if strategy else "",
            "generated_prompt": final_sent_prompt,
            "strategy": strategy,
            "generation_status": result.get("generation_status"),
            "backtest": {
                "passed": result.get("backtest_passed"),
                "exit_code": result.get("backtest_exit_code"),
                "summary": result.get("backtest_summary", ""),
                "metrics": result.get("backtest_metrics", []),
            },
            "references": {"news": references},
            "elapsed_seconds": result.get("elapsed_seconds", 0),
        },
    }


def _serialize_news_references(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep only the news fields consumed by history and the strategy page."""
    references: list[dict[str, Any]] = []
    for event in context.get("events", []):
        pub_time = event.get("pub_time")
        references.append(
            {
                "news_id": event.get("news_id"),
                "title": str(event.get("title") or ""),
                "pub_time": pub_time.isoformat() if hasattr(pub_time, "isoformat") else str(pub_time or ""),
                "direction": str(event.get("direction") or "neutral"),
                "direction_label": str(event.get("direction_label") or ""),
                "horizon": str(event.get("horizon") or ""),
                "reason": str(event.get("reason") or ""),
                "usage": str(event.get("usage") or ""),
            }
        )
    return references


def _draft_context_snapshot(context: dict[str, Any]) -> dict[str, Any]:
    """Persist the full reproducibility metadata for one prompt draft."""
    return {
        "references": _serialize_news_references(context),
        "instrument": context.get("instrument"),
        "frequency": context.get("frequency"),
        "model_name": context.get("model_name"),
        "lookback_days": context.get("lookback_days"),
        "window_start": context.get("window_start").isoformat() if context.get("window_start") else None,
        "reference_time": context.get("reference_time").isoformat() if context.get("reference_time") else None,
        "generated_at": context.get("generated_at"),
        "prompt_version": context.get("prompt_version"),
        "market_scope": context.get("market_scope"),
    }


@router.post("/conversations")
def create_conversation(request: Request, body: ConversationCreateRequest):
    owner_username = _history_owner(request)
    repository = _history_repository()
    return {"success": True, "data": repository.create_conversation(owner_username, body.title)}


@router.get("/conversations")
def list_conversations(request: Request, limit: int = Query(default=50, ge=1, le=100)):
    owner_username = _history_owner(request)
    repository = _history_repository()
    return {"success": True, "data": {"items": repository.list_conversations(owner_username, limit)}}


@router.get("/conversations/{conversation_id}")
def get_conversation(request: Request, conversation_id: int):
    owner_username = _history_owner(request)
    repository = _history_repository()
    detail = repository.get_conversation_detail(owner_username, conversation_id)
    if not detail:
        raise HTTPException(status_code=404, detail="History conversation not found")
    return {"success": True, "data": detail}


@router.post("/conversations/{conversation_id}/draft")
async def create_prompt_draft(
    request: Request,
    conversation_id: int,
    body: ConversationDraftRequest,
):
    owner_username = _history_owner(request)
    repository = _history_repository()
    if not repository.get_conversation(owner_username, conversation_id):
        raise HTTPException(status_code=404, detail="History conversation not found")
    normalized_requirement = " ".join(body.requirement.split())
    try:
        context = await asyncio.to_thread(
            build_dream_strategy_prompt,
            normalized_requirement,
            body.lookback_days,
            body.model_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    snapshot = _draft_context_snapshot(context)
    try:
        turn = repository.create_prompt_draft(
            owner_username,
            conversation_id,
            normalized_requirement,
            context["prompt"],
            snapshot,
        )
    except GenerationInProgressError as exc:
        raise HTTPException(status_code=409, detail="Confirm or wait for the current strategy turn first") from exc
    except ArchivedConversationError as exc:
        raise HTTPException(status_code=409, detail="Archived conversations cannot be continued") from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="History conversation not found") from exc
    return {
        "success": True,
        "data": {
            "user_message_id": turn["user_message_id"],
            "assistant_message_id": turn["assistant_message_id"],
            "status": "pending_confirmation",
            "system_draft_prompt": context["prompt"],
            "context": snapshot,
        },
    }


@router.post("/conversations/{conversation_id}/drafts/{assistant_message_id}/confirm")
async def confirm_prompt_draft(
    request: Request,
    conversation_id: int,
    assistant_message_id: int,
    body: PromptDraftConfirmRequest,
):
    owner_username = _history_owner(request)
    repository = _history_repository()
    draft = repository.get_prompt_draft(owner_username, conversation_id, assistant_message_id)
    if not draft:
        raise HTTPException(status_code=404, detail="Prompt draft not found")
    if draft.get("status") != "pending_confirmation":
        raise HTTPException(status_code=409, detail="This prompt draft has already been confirmed or replaced")
    try:
        user_edited_prompt = apply_user_edited_requirement(str(draft.get("system_draft_prompt") or ""), body.edited_prompt)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    conversation = repository.get_conversation(owner_username, conversation_id, include_private=True)
    if not conversation:
        raise HTTPException(status_code=404, detail="History conversation not found")
    remote_session_id = conversation.get("remote_session_id")
    final_sent_prompt = build_dream_strategy_continuation_prompt(user_edited_prompt) if remote_session_id else user_edited_prompt
    if not repository.confirm_prompt_draft(owner_username, conversation_id, assistant_message_id, user_edited_prompt, final_sent_prompt):
        raise HTTPException(status_code=409, detail="This prompt draft can no longer be confirmed")

    def on_session_created(session_id: str) -> None:
        repository.save_remote_session(
            owner_username,
            conversation_id,
            str(conversation.get("remote_template_id") or os.getenv("DREAM_TEMPLATE_ID", "")),
            session_id,
        )

    snapshot = draft.get("context_json") or {}
    references = snapshot.get("references") or []
    try:
        result = await asyncio.to_thread(
            generate_strategy,
            final_sent_prompt,
            session_id=str(remote_session_id) if remote_session_id else None,
            on_session_created=on_session_created if not remote_session_id else None,
        )
        version = repository.complete_generation(owner_username, conversation_id, assistant_message_id, result)
        return _history_generation_payload(
            conversation_id,
            assistant_message_id,
            result,
            final_sent_prompt,
            version,
            references,
        )
    except TimeoutError as exc:
        repository.fail_generation(
            owner_username,
            conversation_id,
            assistant_message_id,
            "DreamStrategy generation timed out; the remote result was not received.",
            timed_out=True,
        )
        raise HTTPException(status_code=504, detail="DreamStrategy generation timed out") from exc
    except Exception as exc:
        repository.fail_generation(
            owner_username,
            conversation_id,
            assistant_message_id,
            "DreamStrategy generation failed; retry with a new prompt draft.",
        )
        raise HTTPException(status_code=502, detail="DreamStrategy generation failed") from exc


@router.patch("/conversations/{conversation_id}/archive")
def archive_conversation(request: Request, conversation_id: int):
    owner_username = _history_owner(request)
    repository = _history_repository()
    try:
        archived = repository.archive_conversation(owner_username, conversation_id)
    except GenerationInProgressError as exc:
        raise HTTPException(status_code=409, detail="Wait for the running generation before archiving") from exc
    if not archived:
        raise HTTPException(status_code=404, detail="History conversation not found")
    return {"success": True}
