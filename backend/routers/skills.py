from typing import Literal, Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, field_validator

from backend.config.config import API_PREFIX
from backend.repositories.skill_repository import SkillRepository
from backend.routers.workbench_helpers import raise_repository_error, strip_to_required

router = APIRouter(prefix=f"{API_PREFIX}/skills", tags=["skills"])


class SkillPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    instructions: str = Field(min_length=1, max_length=12000)
    input_schema: list[dict] = Field(default_factory=list, max_length=20)
    output_format: Literal["markdown", "text"] = "markdown"
    status: Literal["draft", "published"] = "draft"

    @field_validator("name", "description", "instructions")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return strip_to_required(value, "Cannot be empty")


def _repository() -> SkillRepository:
    return SkillRepository.from_environment()


@router.get("")
def list_skills(request: Request, query: str = "", scope: Literal["all", "mine", "system"] = "all", status: Optional[Literal["draft", "published", "archived"]] = None):
    try:
        return {"data": {"items": _repository().list_skills(request.state.username, query.strip(), scope, status)}}
    except Exception as exc:
        raise_repository_error(exc)


@router.post("", status_code=201)
def create_skill(request: Request, body: SkillPayload):
    try:
        return {"data": _repository().create_skill(request.state.username, body.model_dump())}
    except Exception as exc:
        raise_repository_error(exc)


@router.get("/{skill_id}")
def get_skill(request: Request, skill_id: str):
    try:
        return {"data": _repository().get_skill(request.state.username, skill_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.put("/{skill_id}")
def update_skill(request: Request, skill_id: str, body: SkillPayload):
    try:
        return {"data": _repository().update_skill(request.state.username, skill_id, body.model_dump())}
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/{skill_id}/archive")
def archive_skill(request: Request, skill_id: str):
    try:
        return {"data": _repository().archive_skill(request.state.username, skill_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/{skill_id}/activate")
def activate_skill(request: Request, skill_id: str):
    try:
        return {"data": _repository().activate_skill(request.state.username, skill_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.delete("/{skill_id}")
def delete_skill(request: Request, skill_id: str):
    try:
        return {"data": _repository().delete_skill(request.state.username, skill_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/{skill_id}/attachments", status_code=201)
async def upload_attachment(request: Request, skill_id: str, file: UploadFile = File(...)):
    allowed = {".pdf", ".docx", ".xlsx", ".csv", ".txt", ".md", ".py", ".js", ".sql", ".sh"}
    filename = (file.filename or "attachment").strip()
    if not any(filename.lower().endswith(suffix) for suffix in allowed):
        raise HTTPException(status_code=400, detail="Unsupported attachment type")
    content = await file.read()
    if not content or len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Attachment must be between 1 byte and 10 MB")
    try:
        return {"data": _repository().create_attachment(request.state.username, skill_id, filename, file.content_type, content)}
    except Exception as exc:
        raise_repository_error(exc)


@router.delete("/{skill_id}/attachments/{attachment_id}")
def delete_attachment(request: Request, skill_id: str, attachment_id: str):
    try:
        return {"data": _repository().delete_attachment(request.state.username, skill_id, attachment_id)}
    except Exception as exc:
        raise_repository_error(exc)
