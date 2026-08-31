import asyncio
import json
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.agent.chat_service import AgentGenerationError, agent_chat_stream
from backend.agent.demo_reply import (
    AI_EXPANSION_DEMO_REPLY,
    AI_EXPANSION_DEMO_TRIGGER,
    DEMO_REPLY,
    DEMO_REPLY_TRIGGER,
)
from backend.config.config import API_PREFIX, CONVERSATION_HISTORY_LIMIT
from backend.repositories.message_repository import MessageRepository
from backend.repositories.skill_repository import SkillRepository
from backend.routers.workbench_helpers import raise_repository_error

logger = logging.getLogger(__name__)
router = APIRouter(prefix=f"{API_PREFIX}/workbench/conversations", tags=["workbench-conversations"])


def _clean_required(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("不能为空")
    return value


class ConversationCreateRequest(BaseModel):
    project_id: Optional[str] = None
    title: Optional[str] = Field(default=None, max_length=120)
    source: Literal["home", "sidebar", "project"]

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: Optional[str]) -> Optional[str]:
        return _clean_required(value) if value is not None else None

    @model_validator(mode="after")
    def validate_project_source(self):
        if self.source == "project" and not self.project_id:
            raise ValueError("项目会话必须提供 project_id")
        if self.source != "project" and self.project_id is not None:
            raise ValueError("普通会话不能提供 project_id")
        return self


class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    archived: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: Optional[str]) -> Optional[str]:
        return _clean_required(value) if value is not None else None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个要更新的字段")
        return self


class MessageCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    client_message_id: str = Field(min_length=1, max_length=191)
    skill_ids: list[str] = Field(default_factory=list, max_length=5)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("client_message_id")
    @classmethod
    def validate_client_message_id(cls, value: str) -> str:
        return _clean_required(value)

    @field_validator("skill_ids")
    @classmethod
    def validate_skill_ids(cls, value: list[str]) -> list[str]:
        cleaned = [_clean_required(skill_id) for skill_id in value]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Skill 不能重复选择")
        return cleaned


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("")
def list_conversations(request: Request, scope: Literal["recent"] = "recent", limit: int = Query(default=20, ge=1, le=50), cursor: Optional[str] = None, archived: bool = False):
    repository: MessageRepository = request.app.state.repository
    try:
        return {"data": repository.list_conversations(request.state.username, None, limit, cursor, archived)}
    except Exception as exc:
        raise_repository_error(exc)


@router.post("", status_code=201)
def create_conversation(request: Request, body: ConversationCreateRequest):
    repository: MessageRepository = request.app.state.repository
    try:
        return {"data": repository.create_conversation(request.state.username, body.project_id, body.title, body.source)}
    except Exception as exc:
        raise_repository_error(exc)


@router.get("/{conversation_id}")
def get_conversation(request: Request, conversation_id: str, message_limit: int = Query(default=50, ge=1, le=100)):
    repository: MessageRepository = request.app.state.repository
    try:
        return {"data": repository.get_conversation_detail(request.state.username, conversation_id, message_limit)}
    except Exception as exc:
        raise_repository_error(exc)


@router.patch("/{conversation_id}")
def update_conversation(request: Request, conversation_id: str, body: ConversationUpdateRequest):
    repository: MessageRepository = request.app.state.repository
    try:
        return {"data": repository.update_conversation(request.state.username, conversation_id, body.model_dump(exclude_unset=True))}
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/{conversation_id}/messages")
async def create_message(request: Request, conversation_id: str, body: MessageCreateRequest):
    repository: MessageRepository = request.app.state.repository
    try:
        selected_skills = SkillRepository.from_environment().list_chat_skills(request.state.username, body.skill_ids)
        prepared = repository.prepare_message(request.state.username, conversation_id, body.content, body.client_message_id, selected_skills)
    except Exception as exc:
        raise_repository_error(exc)

    async def event_stream():
        user_message = prepared["user_message"]
        assistant_message = prepared["assistant_message"]
        yield _sse("message.accepted", {"message": user_message})
        if not prepared["created"]:
            if assistant_message["status"] == "completed":
                yield _sse("assistant.completed", {"message": assistant_message})
            elif assistant_message["status"] in {"failed", "interrupted"}:
                yield _sse("assistant.failed", {"message": assistant_message, "error": {"code": assistant_message.get("error_code") or "PREVIOUS_ATTEMPT_FAILED", "message": "此前生成未完成"}})
            else:
                yield _sse("assistant.started", {"message_id": assistant_message["id"], "status": assistant_message["status"]})
            yield _sse("stream.done", {"conversation_id": conversation_id})
            return

        yield _sse("assistant.started", {"message_id": assistant_message["id"]})
        parts: list[str] = []
        try:
            if AI_EXPANSION_DEMO_TRIGGER in body.content:
                demo_reply = AI_EXPANSION_DEMO_REPLY
                await asyncio.sleep(1.0)
                for i in range(0, len(demo_reply), 4):
                    chunk = demo_reply[i : i + 4]
                    parts.append(chunk)
                    yield _sse("assistant.delta", {"message_id": assistant_message["id"], "delta": chunk})
                    await asyncio.sleep(0.022)
            elif DEMO_REPLY_TRIGGER in body.content:
                # 演示：流式输出写死回复，不调用模型，仍正常持久化进历史
                demo_reply = DEMO_REPLY
                await asyncio.sleep(1.0)  # 先弹 1 秒省略号（前端 pending 态），更像在思考
                for i in range(0, len(demo_reply), 4):
                    chunk = demo_reply[i : i + 4]
                    parts.append(chunk)
                    yield _sse("assistant.delta", {"message_id": assistant_message["id"], "delta": chunk})
                    await asyncio.sleep(0.022)
            else:
                history = repository.get_agent_history(request.state.username, conversation_id, CONVERSATION_HISTORY_LIMIT)
                conversation = repository.get_conversation(request.state.username, conversation_id)
                project_context = None
                if conversation.get("project_id") and hasattr(repository, "get_project_memory_context"):
                    project_context = repository.get_project_memory_context(
                        request.state.username,
                        conversation["project_id"],
                    )
                async for delta in agent_chat_stream(history, request.state.username, project_context, selected_skills):
                    parts.append(delta)
                    yield _sse("assistant.delta", {"message_id": assistant_message["id"], "delta": delta})
            completed = repository.finish_assistant_message(assistant_message["id"], "".join(parts), "completed")
            yield _sse("assistant.completed", {"message": completed})
        except asyncio.CancelledError:
            # 客户端断开时也保留已输出的内容，供刷新页面后恢复。
            repository.finish_assistant_message(assistant_message["id"], "".join(parts), "interrupted", "CLIENT_DISCONNECTED")
            raise
        except AgentGenerationError as exc:
            failed = repository.finish_assistant_message(assistant_message["id"], "".join(parts), "failed", exc.code)
            yield _sse("assistant.failed", {"message": failed, "error": {"code": exc.code, "message": str(exc)}})
        except Exception:
            logger.exception("工作台 Agent 会话失败: %s", conversation_id)
            failed = repository.finish_assistant_message(assistant_message["id"], "".join(parts), "failed", "WORKBENCH_STREAM_FAILED")
            yield _sse("assistant.failed", {"message": failed, "error": {"code": "WORKBENCH_STREAM_FAILED", "message": "会话生成失败"}})
        yield _sse("stream.done", {"conversation_id": conversation_id})

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


@router.delete("/{conversation_id}")
def delete_conversation(request: Request, conversation_id: str):
    repository: MessageRepository = request.app.state.repository
    try:
        return {"data": repository.soft_delete_conversation(request.state.username, conversation_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/{conversation_id}/restore")
def restore_conversation(request: Request, conversation_id: str):
    repository: MessageRepository = request.app.state.repository
    try:
        return {"data": repository.restore_conversation(request.state.username, conversation_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.delete("/{conversation_id}/permanently")
def permanently_delete_conversation(request: Request, conversation_id: str):
    repository: MessageRepository = request.app.state.repository
    try:
        return {"data": repository.permanently_delete_conversation(request.state.username, conversation_id)}
    except Exception as exc:
        raise_repository_error(exc)
