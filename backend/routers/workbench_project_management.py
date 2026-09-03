from typing import Literal, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.config.config import API_PREFIX
from backend.repositories.project_management_repository import ProjectManagementRepository
from backend.routers.workbench_helpers import (
    collapse_whitespace_required,
    raise_repository_error,
    strip_to_required,
)

router = APIRouter(prefix=f"{API_PREFIX}/workbench/projects", tags=["workbench-project-management"])

MemoryCategory = Literal["background", "goal", "constraint", "preference", "conclusion", "other"]
MemberRole = Literal["editor", "viewer"]


class ProjectMemoryCreateRequest(BaseModel):
    category: MemoryCategory = "other"
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=10000)
    is_active: bool = True

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return collapse_whitespace_required(value)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return strip_to_required(value)


class ProjectMemoryUpdateRequest(BaseModel):
    category: Optional[MemoryCategory] = None
    title: Optional[str] = Field(default=None, min_length=1, max_length=120)
    content: Optional[str] = Field(default=None, min_length=1, max_length=10000)
    is_active: Optional[bool] = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: Optional[str]) -> Optional[str]:
        return collapse_whitespace_required(value) if value is not None else None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return strip_to_required(value)

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个要更新的字段")
        nullable_fields = ("category", "title", "content", "is_active")
        if any(
            field in self.model_fields_set and getattr(self, field) is None
            for field in nullable_fields
        ):
            raise ValueError("更新字段不能为 null")
        return self


class ProjectMemberUpsertRequest(BaseModel):
    role: MemberRole


@router.get("/{project_id}/memories")
def list_project_memories(request: Request, project_id: str, include_inactive: bool = True):
    repository: ProjectManagementRepository = request.app.state.repository
    try:
        return {"data": repository.list_project_memories(request.state.username, project_id, include_inactive)}
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/{project_id}/memories", status_code=201)
def create_project_memory(request: Request, project_id: str, body: ProjectMemoryCreateRequest):
    repository: ProjectManagementRepository = request.app.state.repository
    try:
        return {"data": repository.create_project_memory(request.state.username, project_id, body.category, body.title, body.content, body.is_active)}
    except Exception as exc:
        raise_repository_error(exc)


@router.get("/{project_id}/memories/{memory_id}")
def get_project_memory(request: Request, project_id: str, memory_id: str):
    repository: ProjectManagementRepository = request.app.state.repository
    try:
        return {"data": repository.get_project_memory(request.state.username, project_id, memory_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.patch("/{project_id}/memories/{memory_id}")
def update_project_memory(request: Request, project_id: str, memory_id: str, body: ProjectMemoryUpdateRequest):
    repository: ProjectManagementRepository = request.app.state.repository
    try:
        return {"data": repository.update_project_memory(request.state.username, project_id, memory_id, body.model_dump(exclude_unset=True))}
    except Exception as exc:
        raise_repository_error(exc)


@router.delete("/{project_id}/memories/{memory_id}")
def delete_project_memory(request: Request, project_id: str, memory_id: str):
    repository: ProjectManagementRepository = request.app.state.repository
    try:
        return {"data": repository.delete_project_memory(request.state.username, project_id, memory_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.get("/{project_id}/members")
def list_project_members(request: Request, project_id: str):
    repository: ProjectManagementRepository = request.app.state.repository
    try:
        return {"data": repository.list_project_members(request.state.username, project_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.put("/{project_id}/members/{member_username}")
def upsert_project_member(request: Request, project_id: str, member_username: str, body: ProjectMemberUpsertRequest):
    repository: ProjectManagementRepository = request.app.state.repository
    try:
        return {"data": repository.upsert_project_member(request.state.username, project_id, collapse_whitespace_required(member_username), body.role)}
    except Exception as exc:
        raise_repository_error(exc)


@router.delete("/{project_id}/members/{member_username}")
def remove_project_member(request: Request, project_id: str, member_username: str):
    repository: ProjectManagementRepository = request.app.state.repository
    try:
        return {"data": repository.remove_project_member(request.state.username, project_id, member_username)}
    except Exception as exc:
        raise_repository_error(exc)
