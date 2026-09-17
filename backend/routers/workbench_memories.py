"""账号级个人记忆 API。"""

from typing import Literal, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.config.config import API_PREFIX
from backend.repositories.user_memory_repository import UserMemoryRepository
from backend.routers.workbench_helpers import (
    collapse_whitespace_required,
    raise_repository_error,
    strip_to_required,
)

router = APIRouter(prefix=f"{API_PREFIX}/workbench/memories", tags=["workbench-memories"])
settings_router = APIRouter(prefix=f"{API_PREFIX}/workbench/memory-settings", tags=["workbench-memories"])

MemoryCategory = Literal[
    "response_preference",
    "user_background",
    "long_term_interest",
    "personal_constraint",
]
MemoryStatus = Literal["pending", "active", "disabled"]


class MemoryCreateRequest(BaseModel):
    category: MemoryCategory = "response_preference"
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=2000)
    is_pinned: bool = False

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return collapse_whitespace_required(value)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return strip_to_required(value)


class MemoryUpdateRequest(BaseModel):
    category: Optional[MemoryCategory] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    content: Optional[str] = Field(default=None, min_length=1, max_length=2000)
    status: Optional[MemoryStatus] = None
    is_pinned: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: Optional[str]) -> Optional[str]:
        return collapse_whitespace_required(value) if value is not None else None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: Optional[str]) -> Optional[str]:
        return strip_to_required(value) if value is not None else None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个要更新的字段")
        return self


class MemorySettingsUpdateRequest(BaseModel):
    memory_enabled: Optional[bool] = None
    auto_extract_enabled: Optional[bool] = None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个要更新的字段")
        return self


@router.get("")
def list_memories(
    request: Request,
    status: Optional[MemoryStatus] = None,
    category: Optional[MemoryCategory] = None,
    query: Optional[str] = Query(default=None, max_length=100),
    limit: int = Query(default=100, ge=1, le=100),
):
    repository: UserMemoryRepository = request.app.state.user_memory_repository
    try:
        return {"data": repository.list_user_memories(request.state.username, status, category, query, limit)}
    except Exception as exc:
        raise_repository_error(exc)


@router.post("", status_code=201)
def create_memory(request: Request, body: MemoryCreateRequest):
    repository: UserMemoryRepository = request.app.state.user_memory_repository
    try:
        return {
            "data": repository.create_user_memory(
                request.state.username,
                body.category,
                body.title,
                body.content,
                is_pinned=body.is_pinned,
            )
        }
    except Exception as exc:
        raise_repository_error(exc)


@router.patch("/{memory_id}")
def update_memory(request: Request, memory_id: str, body: MemoryUpdateRequest):
    repository: UserMemoryRepository = request.app.state.user_memory_repository
    try:
        return {
            "data": repository.update_user_memory(
                request.state.username,
                memory_id,
                body.model_dump(exclude_unset=True),
            )
        }
    except Exception as exc:
        raise_repository_error(exc)


@router.delete("/{memory_id}")
def delete_memory(request: Request, memory_id: str):
    repository: UserMemoryRepository = request.app.state.user_memory_repository
    try:
        return {"data": repository.delete_user_memory(request.state.username, memory_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.delete("")
def clear_memories(request: Request):
    repository: UserMemoryRepository = request.app.state.user_memory_repository
    try:
        return {"data": repository.clear_user_memories(request.state.username)}
    except Exception as exc:
        raise_repository_error(exc)


@settings_router.get("")
def get_memory_settings(request: Request):
    repository: UserMemoryRepository = request.app.state.user_memory_repository
    try:
        return {"data": repository.get_user_memory_settings(request.state.username)}
    except Exception as exc:
        raise_repository_error(exc)


@settings_router.patch("")
def update_memory_settings(request: Request, body: MemorySettingsUpdateRequest):
    repository: UserMemoryRepository = request.app.state.user_memory_repository
    try:
        return {
            "data": repository.update_user_memory_settings(
                request.state.username,
                body.model_dump(exclude_unset=True),
            )
        }
    except Exception as exc:
        raise_repository_error(exc)
