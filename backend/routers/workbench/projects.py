from typing import Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.config.config import API_PREFIX
from backend.repositories.conversation_repository import ConversationRepository
from backend.routers.workbench.helpers import raise_repository_error


router = APIRouter(prefix=f"{API_PREFIX}/workbench/projects", tags=["workbench-projects"])


def _clean_required(value: str) -> str:
    value = " ".join(value.split())
    if not value:
        raise ValueError("不能为空")
    return value


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _clean_required(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() or None if value else None


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: Optional[str]) -> Optional[str]:
        return _clean_required(value) if value is not None else None

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() or None if value else None

    @model_validator(mode="after")
    def require_change(self):
        if not self.model_fields_set:
            raise ValueError("至少提供一个要更新的字段")
        return self


@router.get("")
def list_projects(request: Request, limit: int = Query(default=20, ge=1, le=50), cursor: Optional[str] = None):
    repository: ConversationRepository = request.app.state.repository
    try:
        return {"data": repository.list_projects(request.state.username, limit, cursor)}
    except Exception as exc:
        raise_repository_error(exc)


@router.post("", status_code=201)
def create_project(request: Request, body: ProjectCreateRequest):
    repository: ConversationRepository = request.app.state.repository
    try:
        return {"data": repository.create_project(request.state.username, body.name, body.description)}
    except Exception as exc:
        raise_repository_error(exc)


@router.get("/{project_id}")
def get_project(request: Request, project_id: str):
    repository: ConversationRepository = request.app.state.repository
    try:
        return {"data": repository.get_project(request.state.username, project_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.patch("/{project_id}")
def update_project(request: Request, project_id: str, body: ProjectUpdateRequest):
    repository: ConversationRepository = request.app.state.repository
    try:
        return {"data": repository.update_project(request.state.username, project_id, body.model_dump(exclude_unset=True))}
    except Exception as exc:
        raise_repository_error(exc)


@router.get("/{project_id}/conversations")
def list_project_conversations(request: Request, project_id: str, limit: int = Query(default=20, ge=1, le=50), cursor: Optional[str] = None, archived: bool = False):
    repository: ConversationRepository = request.app.state.repository
    try:
        return {"data": repository.list_conversations(request.state.username, project_id, limit, cursor, archived)}
    except Exception as exc:
        raise_repository_error(exc)


@router.delete("/{project_id}")
def delete_project(request: Request, project_id: str):
    repository: ConversationRepository = request.app.state.repository
    try:
        return {"data": repository.soft_delete_project(request.state.username, project_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/{project_id}/restore")
def restore_project(request: Request, project_id: str):
    repository: ConversationRepository = request.app.state.repository
    try:
        return {"data": repository.restore_project(request.state.username, project_id)}
    except Exception as exc:
        raise_repository_error(exc)
