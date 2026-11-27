import asyncio
import json
import logging
from typing import Literal, Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.agent.chat_service import (
    AgentGenerationError,
    agent_chat_stream,
    reset_trace_queue,
    set_trace_queue,
)
from backend.config.config import API_PREFIX, CONVERSATION_HISTORY_LIMIT
from backend.repositories.chat_attachment_repository import (
    MAX_CHAT_ATTACHMENT_BYTES,
    ChatAttachmentRepository,
)
from backend.repositories.file_library_repository import FileLibraryRepository
from backend.repositories.message_repository import MessageRepository
from backend.repositories.skill_repository import SkillRepository
from backend.routers.workbench_helpers import (
    collapse_whitespace_required,
    raise_repository_error,
)
from backend.services.skill_attachment_parser import AttachmentParseError

logger = logging.getLogger(__name__)
router = APIRouter(prefix=f"{API_PREFIX}/workbench/conversations", tags=["workbench-conversations"])


class ConversationCreateRequest(BaseModel):
    project_id: Optional[str] = None
    title: Optional[str] = Field(default=None, max_length=120)
    source: Literal["home", "sidebar", "project"]

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: Optional[str]) -> Optional[str]:
        return collapse_whitespace_required(value) if value is not None else None

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
        return collapse_whitespace_required(value) if value is not None else None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个要更新的字段")
        return self


class MessageCreateRequest(BaseModel):
    content: str = ""
    client_message_id: str = Field(min_length=1, max_length=191)
    skill_ids: list[str] = Field(default_factory=list, max_length=3)
    attachment_ids: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def require_content_or_attachment(self):
        if not self.content and not self.attachment_ids:
            raise ValueError("消息内容或附件不能为空")
        return self

    @field_validator("client_message_id")
    @classmethod
    def validate_client_message_id(cls, value: str) -> str:
        return collapse_whitespace_required(value)

    @field_validator("skill_ids")
    @classmethod
    def validate_skill_ids(cls, value: list[str]) -> list[str]:
        cleaned = [collapse_whitespace_required(skill_id) for skill_id in value]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("Skill 不能重复选择")
        return cleaned

    @field_validator("attachment_ids")
    @classmethod
    def validate_attachment_ids(cls, value: list[str]) -> list[str]:
        cleaned = [collapse_whitespace_required(attachment_id) for attachment_id in value]
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("附件不能重复选择")
        return cleaned


class LibraryAttachmentRequest(BaseModel):
    source_key: Literal["skill_attachment", "research_report", "policy_document"]
    source_ref: str = Field(min_length=1, max_length=191)


class VisitorHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class VisitorChatRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    history: list[VisitorHistoryMessage] = Field(default_factory=list, max_length=10)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return collapse_whitespace_required(value)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/visitor-chat")
async def visitor_chat(body: VisitorChatRequest):
    """访客临时聊天：调用 Agent，但不创建或写入任何会话记录。"""
    messages = [message.model_dump() for message in body.history]
    messages.append({"role": "user", "content": body.content})

    async def event_stream():
        try:
            async for delta in agent_chat_stream(messages, "anonymous"):
                yield _sse("assistant.delta", {"delta": delta})
        except AgentGenerationError as exc:
            yield _sse("assistant.failed", {"error": {"code": exc.code, "message": str(exc)}})
        except Exception:
            logger.exception("访客 Agent 会话失败")
            yield _sse("assistant.failed", {"error": {"code": "VISITOR_CHAT_FAILED", "message": "会话生成失败"}})
        yield _sse("stream.done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


@router.post("/{conversation_id}/attachments", status_code=201)
async def upload_chat_attachment(request: Request, conversation_id: str, file: UploadFile = File(...)):
    content = await file.read(MAX_CHAT_ATTACHMENT_BYTES + 1)
    try:
        result = ChatAttachmentRepository.from_environment().create_attachment(
            request.state.username, conversation_id, file.filename or "", content
        )
        return {"data": result}
    except (ValueError, AttachmentParseError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/{conversation_id}/attachments/from-library", status_code=201)
def attach_library_file(request: Request, conversation_id: str, body: LibraryAttachmentRequest):
    try:
        filename, content = FileLibraryRepository.from_environment().read_for_chat(
            request.state.username, body.source_key, body.source_ref
        )
        result = ChatAttachmentRepository.from_environment().create_attachment(
            request.state.username, conversation_id, filename, content
        )
        return {"data": result}
    except (ValueError, AttachmentParseError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/{conversation_id}/messages")
async def create_message(request: Request, conversation_id: str, body: MessageCreateRequest):
    repository: MessageRepository = request.app.state.repository
    effective_content = body.content or "请分析附件内容"
    try:
        prepared = repository.get_message_retry(
            request.state.username,
            conversation_id,
            effective_content,
            body.client_message_id,
            body.attachment_ids,
        )
        selected_skills = []
        attachment_context = ""
        if prepared is None:
            skill_repository = SkillRepository.from_environment()
            selected_skills = skill_repository.list_chat_skills(request.state.username, body.skill_ids)
            attachment_context = skill_repository.get_attachment_context(request.state.username, selected_skills, effective_content)
            if body.attachment_ids:
                prepared = repository.prepare_message(
                    request.state.username, conversation_id, effective_content,
                    body.client_message_id, selected_skills, body.attachment_ids,
                )
            else:
                prepared = repository.prepare_message(
                    request.state.username, conversation_id, effective_content,
                    body.client_message_id, selected_skills,
                )
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
        thinking_parts: list[str] = []

        def _thinking_text() -> str | None:
            text = "".join(thinking_parts).strip()
            return text or None

        def _finish_kwargs() -> dict[str, str]:
            text = _thinking_text()
            return {"thinking": text} if text else {}

        try:
            history = repository.get_agent_history(request.state.username, conversation_id, CONVERSATION_HISTORY_LIMIT)
            chat_attachment_context = repository.get_chat_attachment_context(
                request.state.username, conversation_id, effective_content
            )
            if not isinstance(chat_attachment_context, str):
                chat_attachment_context = ""
            conversation = repository.get_conversation(request.state.username, conversation_id)
            project_context = None
            personal_context = None
            personal_memory_repository = getattr(request.app.state, "user_memory_repository", None)
            if conversation.get("project_id") and hasattr(repository, "get_project_memory_context"):
                project_context = repository.get_project_memory_context(
                    request.state.username,
                    conversation["project_id"],
                )
            elif personal_memory_repository is not None:
                candidate_context = personal_memory_repository.get_user_memory_context(request.state.username)
                personal_context = candidate_context if isinstance(candidate_context, str) else None
            trace_queue: asyncio.Queue[dict] = asyncio.Queue()
            token = set_trace_queue(trace_queue)

            async def _produce_stream() -> None:
                try:
                    async for delta in agent_chat_stream(
                        history,
                        request.state.username,
                        project_context,
                        selected_skills,
                        attachment_context,
                        personal_context,
                        chat_attachment_context=chat_attachment_context,
                    ):
                        trace_queue.put_nowait({"kind": "content", "delta": delta})
                except BaseException as exc:
                    trace_queue.put_nowait({"kind": "_error", "exc": exc})
                else:
                    trace_queue.put_nowait({"kind": "_done"})

            stream_task = asyncio.create_task(_produce_stream())
            try:
                while True:
                    item = await trace_queue.get()
                    kind = item.get("kind")
                    if kind == "content":
                        delta = str(item["delta"])
                        parts.append(delta)
                        yield _sse("assistant.delta", {"message_id": assistant_message["id"], "delta": delta})
                    elif kind in ("reasoning", "tool_start", "tool_done"):
                        if kind == "reasoning" and item.get("delta"):
                            thinking_parts.append(str(item["delta"]))
                        elif kind == "tool_start" and item.get("tool_name"):
                            thinking_parts.append(f"\n- 正在调用工具：`{item['tool_name']}`\n")
                        elif kind == "tool_done" and item.get("tool_name"):
                            duration_ms = item.get("duration_ms")
                            suffix = f" ({duration_ms}ms)" if duration_ms is not None else ""
                            thinking_parts.append(f"- 已完成：`{item['tool_name']}`{suffix}\n")
                        yield _sse("assistant.thinking", {"message_id": assistant_message["id"], **item})
                    elif kind == "_error":
                        raise item["exc"]
                    elif kind == "_done":
                        break
            finally:
                if not stream_task.done():
                    stream_task.cancel()
                reset_trace_queue(token)
            completed = repository.finish_assistant_message(assistant_message["id"], "".join(parts), "completed", **_finish_kwargs())
            yield _sse("assistant.completed", {"message": completed})
            if body.content and not conversation.get("project_id") and personal_memory_repository is not None:
                try:
                    memory_events = personal_memory_repository.process_user_memory_message(
                        request.state.username,
                        conversation_id,
                        user_message["id"],
                        body.content,
                    )
                    for memory_event in memory_events if isinstance(memory_events, list) else []:
                        yield _sse(memory_event["event"], memory_event["data"])
                except Exception:
                    logger.exception("个人记忆提取失败: %s", conversation_id)
        except asyncio.CancelledError:
            # 客户端断开时也保留已输出的内容，供刷新页面后恢复。
            repository.finish_assistant_message(assistant_message["id"], "".join(parts), "interrupted", "CLIENT_DISCONNECTED", **_finish_kwargs())
            raise
        except AgentGenerationError as exc:
            failed = repository.finish_assistant_message(assistant_message["id"], "".join(parts), "failed", exc.code, **_finish_kwargs())
            yield _sse("assistant.failed", {"message": failed, "error": {"code": exc.code, "message": str(exc)}})
        except Exception:
            logger.exception("工作台 Agent 会话失败: %s", conversation_id)
            failed = repository.finish_assistant_message(assistant_message["id"], "".join(parts), "failed", "WORKBENCH_STREAM_FAILED", **_finish_kwargs())
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
