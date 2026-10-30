"""AI 策略会话与两阶段生成流程的 HTTP 编排。"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.common.api_response import ok
from backend.common.pagination import limit_param
from backend.config.config import API_PREFIX, AUTH_ENABLED
from backend.integrations.dream.service import DreamGenerationError, generate_strategy
from backend.repositories.ai_strategy_history_repository import (
    AiStrategyHistoryRepository,
)
from backend.routers.workbench_helpers import raise_repository_error
from backend.strategy.dream_strategy_prompt import (
    DEFAULT_INSTRUMENT,
    EXCLUDED_INSTRUMENTS,
    WHITELISTED_INSTRUMENTS,
    apply_user_edited_requirement,
    build_dream_strategy_continuation_prompt,
    build_dream_strategy_first_prompt,
    build_dream_strategy_prompt,
    resolve_instrument,
)

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix=f"{API_PREFIX}/ai-strategy-generation", tags=["ai-strategy-generation"]
)

# Fire-and-forget handle to running generation tasks so they are not garbage-collected.
_background_generation_tasks: set[asyncio.Task] = set()

# 对端同一账号同一时间只允许跑一个生成任务（单飞约束）。进程内按 owner 占位：
# owner -> 正在运行的 conversation_id，用于 409 文案。进程重启后占位自然清空，
# DB 里遗留的 running 行由 sweep_stale_running 兜底。
_active_generation_owners: dict[str, int] = {}


class ConversationCreateRequest(BaseModel):
    title: str = Field(
        default="New strategy conversation", min_length=1, max_length=255
    )


class ConversationDraftRequest(BaseModel):
    requirement: str = Field(min_length=1, max_length=2000)
    lookback_days: int = Field(default=7, ge=1, le=30)
    model_name: Optional[str] = None
    # 标的必须来自白名单；不传时由后端从需求文本解析，仍不命中则用默认标的。
    instrument_code: Optional[str] = None
    backtest_mode: str = Field(default="bar", pattern="^(bar|tick|factor)$")
    candle_interval: str = Field(default="1d", max_length=16)


class PromptDraftConfirmRequest(BaseModel):
    edited_prompt: str = Field(min_length=1, max_length=30000)


def _history_owner(request: Request) -> str:
    """Resolve the history owner from server-authenticated request state only."""
    if AUTH_ENABLED:
        username = getattr(request.state, "username", None)
        if not username:
            raise HTTPException(
                status_code=401, detail="Sign in to access history conversations"
            )
        return str(username)
    return "admin"


def _history_repository() -> AiStrategyHistoryRepository:
    return AiStrategyHistoryRepository.from_environment()


def _serialize_news_references(context: dict[str, Any]) -> list[dict[str, Any]]:
    """Keep only the news fields consumed by history and the strategy page."""
    references: list[dict[str, Any]] = []
    for event in context.get("events", []):
        pub_time = event.get("pub_time")
        references.append(
            {
                "news_id": event.get("news_id"),
                "title": str(event.get("title") or ""),
                "pub_time": (
                    pub_time.isoformat()
                    if hasattr(pub_time, "isoformat")
                    else str(pub_time or "")
                ),
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
        "instrument_code": context.get("instrument_code"),
        "backtest_mode": context.get("backtest_mode"),
        "candle_interval": context.get("candle_interval"),
        "frequency": context.get("frequency"),
        "model_name": context.get("model_name"),
        "lookback_days": context.get("lookback_days"),
        "window_start": (
            context.get("window_start").isoformat()
            if context.get("window_start")
            else None
        ),
        "reference_time": (
            context.get("reference_time").isoformat()
            if context.get("reference_time")
            else None
        ),
        "generated_at": context.get("generated_at"),
        "prompt_version": context.get("prompt_version"),
        "market_scope": context.get("market_scope"),
        # 因子面板与 token 用量要能还原，缺了就无法解释"当时凭什么这么判"。
        "factor_panel": context.get("factor_panel"),
        "token_used": context.get("token_used"),
        "token_budget": context.get("token_budget"),
    }


@router.post("/conversations")
def create_conversation(request: Request, body: ConversationCreateRequest):
    owner_username = _history_owner(request)
    repository = _history_repository()
    return ok(repository.create_conversation(owner_username, body.title))


@router.get("/conversations")
def list_conversations(request: Request, limit: int = limit_param()):
    owner_username = _history_owner(request)
    repository = _history_repository()
    return ok({"items": repository.list_conversations(owner_username, limit)})


@router.get("/instruments")
def list_supported_instruments():
    """标的白名单元数据：前端下拉不再硬编码，以后端校验口径为准。"""
    return ok(
        {
            "default": DEFAULT_INSTRUMENT,
            "instruments": [
                {"code": code, "label": label}
                for code, label in WHITELISTED_INSTRUMENTS.items()
            ],
            "excluded": [
                {"code": code, "reason": reason}
                for code, reason in EXCLUDED_INSTRUMENTS.items()
            ],
        }
    )


@router.get("/conversations/{conversation_id}")
def get_conversation(request: Request, conversation_id: int):
    owner_username = _history_owner(request)
    repository = _history_repository()
    detail = repository.get_conversation_detail(owner_username, conversation_id)
    if not detail:
        raise HTTPException(status_code=404, detail="History conversation not found")
    return ok(detail)


@router.post("/conversations/{conversation_id}/draft")
async def create_prompt_draft(
    request: Request,
    conversation_id: int,
    body: ConversationDraftRequest,
):
    owner_username = _history_owner(request)
    # 白名单校验前置：必须在任何并发/会话状态检查之前把非法标的拒绝掉。
    # 否则合法标的也可能撞上"当前有任务在跑"，用户看到的错误原因与事实不符。
    try:
        resolve_instrument(body.requirement, body.instrument_code)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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
            body.instrument_code,
            body.backtest_mode,
            body.candle_interval,
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
            instrument_label=str(context.get("instrument") or "") or None,
        )
    except Exception as exc:
        raise_repository_error(exc)
    return ok(
        {
            "user_message_id": turn["user_message_id"],
            "assistant_message_id": turn["assistant_message_id"],
            "status": "pending_confirmation",
            "system_draft_prompt": context["prompt"],
            "context": snapshot,
        }
    )


def _validation_context_from_snapshot(
    snapshot: Any, prompt: str
) -> dict[str, Any]:
    """Build the whitelist context for the acceptance gate.

    The instrument comes from the draft snapshot so that later edits to the
    requirement text cannot silently widen what counts as an acceptable symbol.
    """
    instrument = ""
    if isinstance(snapshot, dict):
        instrument = str(snapshot.get("instrument_code") or "").strip()
    if not instrument:
        # 快照缺失时退化到从提示词的 [INSTRUMENT] 段读取。
        matched = re.search(
            r"\[INSTRUMENT\][\s\S]*?交易标的：([A-Za-z0-9_]+)", prompt or ""
        )
        if matched:
            instrument = matched.group(1)
    if not instrument:
        instrument = DEFAULT_INSTRUMENT
    return {
        "expected_instrument": instrument,
        "whitelist": frozenset(WHITELISTED_INSTRUMENTS),
    }


async def _run_generation(
    owner_username: str,
    conversation_id: int,
    assistant_message_id: int,
    final_sent_prompt: str,
    remote_session_id: str | None,
    on_session_created: Any,
    validation_context: dict[str, Any] | None = None,
) -> None:
    """Run a DreamStrategy generation in a worker thread and persist its outcome.

    The message row is already marked ``running`` by the confirm endpoint before this
    task starts; here we only execute the blocking remote call and flip the row to a
    terminal status via the repository.
    """
    try:
        result = await asyncio.to_thread(
            generate_strategy,
            final_sent_prompt,
            session_id=remote_session_id,
            on_session_created=on_session_created,
            validation_context=validation_context,
        )
        repository = _history_repository()
        repository.complete_generation(
            owner_username, conversation_id, assistant_message_id, result
        )
    except DreamGenerationError as exc:
        # 对端明确报错：立刻落库具体原因，不要等到超时把问题糊成"超时"。
        repository = _history_repository()
        repository.fail_generation(
            owner_username,
            conversation_id,
            assistant_message_id,
            exc.remote_message or str(exc),
        )
    except TimeoutError:
        repository = _history_repository()
        repository.fail_generation(
            owner_username,
            conversation_id,
            assistant_message_id,
            "DreamStrategy generation timed out; the remote result was not received.",
            timed_out=True,
        )
    except Exception as exc:
        logger.exception(
            "DreamStrategy generation failed for conversation %s", conversation_id
        )
        repository = _history_repository()
        repository.fail_generation(
            owner_username,
            conversation_id,
            assistant_message_id,
            str(exc).strip()
            or "DreamStrategy generation failed; retry with a new prompt draft.",
        )


@router.post("/conversations/{conversation_id}/drafts/{assistant_message_id}/confirm")
async def confirm_prompt_draft(
    request: Request,
    conversation_id: int,
    assistant_message_id: int,
    body: PromptDraftConfirmRequest,
):
    owner_username = _history_owner(request)
    repository = _history_repository()
    draft = repository.get_prompt_draft(
        owner_username, conversation_id, assistant_message_id
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Prompt draft not found")
    if draft.get("status") != "pending_confirmation":
        raise HTTPException(
            status_code=409,
            detail="This prompt draft has already been confirmed or replaced",
        )
    try:
        user_edited_prompt = apply_user_edited_requirement(
            str(draft.get("system_draft_prompt") or ""), body.edited_prompt
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    conversation = repository.get_conversation(
        owner_username, conversation_id, include_private=True
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="History conversation not found")
    remote_session_id = conversation.get("remote_session_id")
    final_sent_prompt = (
        build_dream_strategy_continuation_prompt(user_edited_prompt)
        if remote_session_id
        else build_dream_strategy_first_prompt(user_edited_prompt)
    )

    # 账号级单飞：从这里到 create_task 之间没有 await，check+claim 对事件循环原子。
    active_conversation_id = _active_generation_owners.get(owner_username)
    if active_conversation_id is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"该账号已有一个策略生成任务正在进行（会话 #{active_conversation_id}），"
                "平台同一时间只允许运行一个；请等当前任务结束后再发送。"
            ),
        )
    if not repository.confirm_prompt_draft(
        owner_username,
        conversation_id,
        assistant_message_id,
        user_edited_prompt,
        final_sent_prompt,
    ):
        raise HTTPException(
            status_code=409, detail="This prompt draft can no longer be confirmed"
        )
    _active_generation_owners[owner_username] = conversation_id

    def on_session_created(session_id: str) -> None:
        repository.save_remote_session(
            owner_username,
            conversation_id,
            str(
                conversation.get("remote_template_id")
                or os.getenv("DREAM_TEMPLATE_ID", "")
            ),
            session_id,
        )

    # 验收门要用的标的取自草稿快照——那里记录了本轮任务卡实际定下的品种，
    # 用户后续改需求文本也不该改变本次验收的白名单口径。
    validation_context = _validation_context_from_snapshot(
        draft.get("context_json"), user_edited_prompt
    )

    task = asyncio.create_task(
        _run_generation(
            owner_username,
            conversation_id,
            assistant_message_id,
            final_sent_prompt,
            remote_session_id,
            on_session_created if not remote_session_id else None,
            validation_context,
        )
    )

    def _release_owner(done_task: asyncio.Task) -> None:
        _background_generation_tasks.discard(done_task)
        # 只释放自己的占位，避免任务收尾交错时误删后来者的占位。
        if _active_generation_owners.get(owner_username) == conversation_id:
            _active_generation_owners.pop(owner_username, None)

    task.add_done_callback(_release_owner)
    _background_generation_tasks.add(task)

    return ok(
        {
            "conversation_id": conversation_id,
            "assistant_message_id": assistant_message_id,
            "status": "running",
        }
    )


@router.post("/conversations/{conversation_id}/drafts/{assistant_message_id}/abandon")
def abandon_prompt_draft(
    request: Request, conversation_id: int, assistant_message_id: int
):
    """放弃待确认草稿（纯本地操作；待确认阶段没有任何远端调用）。"""
    owner_username = _history_owner(request)
    repository = _history_repository()
    draft = repository.get_prompt_draft(
        owner_username, conversation_id, assistant_message_id
    )
    if not draft:
        raise HTTPException(status_code=404, detail="Prompt draft not found")
    if draft.get("status") != "pending_confirmation":
        raise HTTPException(
            status_code=409,
            detail="This prompt draft has already been confirmed, replaced, or abandoned",
        )
    if not repository.abandon_prompt_draft(
        owner_username, conversation_id, assistant_message_id
    ):
        raise HTTPException(
            status_code=409, detail="This prompt draft can no longer be abandoned"
        )
    return ok({"status": "cancelled"})


@router.patch("/conversations/{conversation_id}/archive")
def archive_conversation(request: Request, conversation_id: int):
    owner_username = _history_owner(request)
    repository = _history_repository()
    try:
        archived = repository.archive_conversation(owner_username, conversation_id)
    except Exception as exc:
        raise_repository_error(exc)
    if not archived:
        raise HTTPException(status_code=404, detail="History conversation not found")
    return ok(None)


@router.delete("/conversations/{conversation_id}")
def delete_conversation(request: Request, conversation_id: int):
    owner_username = _history_owner(request)
    try:
        return ok(
            _history_repository().soft_delete_conversation(
                owner_username, conversation_id
            )
        )
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/conversations/{conversation_id}/restore")
def restore_conversation(request: Request, conversation_id: int):
    owner_username = _history_owner(request)
    try:
        return ok(
            _history_repository().restore_conversation(owner_username, conversation_id)
        )
    except Exception as exc:
        raise_repository_error(exc)


@router.delete("/conversations/{conversation_id}/permanently")
def permanently_delete_conversation(request: Request, conversation_id: int):
    owner_username = _history_owner(request)
    try:
        return ok(
            _history_repository().permanently_delete_conversation(
                owner_username, conversation_id
            )
        )
    except Exception as exc:
        raise_repository_error(exc)
