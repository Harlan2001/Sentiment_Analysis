"""Computer report-generation API."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.config.config import API_PREFIX
from backend.repositories.report_generation_repository import (
    ReportGenerationConflictError,
    ReportGenerationNotFoundError,
    ReportGenerationRepository,
)
from backend.services.report_generation_service import start_report_generation

router = APIRouter(prefix=f"{API_PREFIX}/report-generation", tags=["report-generation"])
ALLOWED_STATUSES = {"queued", "running", "completed", "failed"}


class ReportGenerationCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    requirement: str = Field(min_length=1, max_length=4000)
    report_ids: list[int] = Field(min_length=1, max_length=12)
    date_start: Optional[date] = None
    date_end: Optional[date] = None

    @field_validator("title", "requirement")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("不能为空")
        return value

    @field_validator("report_ids")
    @classmethod
    def validate_report_ids(cls, value: list[int]) -> list[int]:
        if any(item <= 0 for item in value):
            raise ValueError("研报 ID 必须为正整数")
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_start and self.date_end and self.date_start > self.date_end:
            raise ValueError("Start date cannot be after end date")
        return self


def _repository() -> ReportGenerationRepository:
    return ReportGenerationRepository.from_environment()


def _raise_repository_error(exc: Exception) -> None:
    if isinstance(exc, ReportGenerationNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ReportGenerationConflictError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    raise exc


@router.get("/sources")
def list_report_sources(
    keyword: Optional[str] = Query(default=None, max_length=100),
    institution: Optional[str] = Query(default=None, max_length=100),
    industry: Optional[str] = Query(default=None, max_length=100),
    date_start: Optional[date] = None,
    date_end: Optional[date] = None,
    limit: int = Query(default=50, ge=1, le=100),
):
    if date_start and date_end and date_start > date_end:
        raise HTTPException(status_code=400, detail="Start date cannot be after end date")
    data = _repository().list_sources(
        keyword=keyword.strip() if keyword else None,
        institution=institution,
        industry=industry,
        date_start=date_start,
        date_end=date_end,
        limit=limit,
    )
    return {"data": data}


@router.get("/tasks")
def list_report_generation_tasks(
    request: Request,
    status: Optional[str] = None,
    date_start: Optional[date] = None,
    date_end: Optional[date] = None,
    limit: int = Query(default=50, ge=1, le=100),
):
    if status and status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid task status")
    if date_start and date_end and date_start > date_end:
        raise HTTPException(status_code=400, detail="Start date cannot be after end date")
    items = _repository().list_tasks(
        request.state.username,
        status=status,
        date_start=date_start,
        date_end=date_end,
        limit=limit,
    )
    return {"data": {"items": items}}


@router.post("/tasks", status_code=201)
def create_report_generation_task(
    request: Request, body: ReportGenerationCreateRequest
):
    repository = _repository()
    try:
        sources = repository.load_sources(body.report_ids)
        task = repository.create_task(
            owner_username=request.state.username,
            title=body.title,
            requirement=body.requirement,
            date_start=body.date_start,
            date_end=body.date_end,
            sources=sources,
        )
    except Exception as exc:
        _raise_repository_error(exc)
    start_report_generation(task["id"])
    return {"data": task}


@router.get("/tasks/{task_id}")
def get_report_generation_task(request: Request, task_id: str):
    task = _repository().get_task(request.state.username, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Report generation task not found")
    return {"data": task}


@router.post("/tasks/{task_id}/retry")
def retry_report_generation_task(request: Request, task_id: str):
    try:
        task = _repository().retry_task(request.state.username, task_id)
    except Exception as exc:
        _raise_repository_error(exc)
    start_report_generation(task_id)
    return {"data": task}


@router.delete("/tasks/{task_id}")
def delete_report_generation_task(request: Request, task_id: str):
    try:
        return {"data": _repository().soft_delete_task(request.state.username, task_id)}
    except Exception as exc:
        _raise_repository_error(exc)


@router.post("/tasks/{task_id}/restore")
def restore_report_generation_task(request: Request, task_id: str):
    try:
        return {"data": _repository().restore_task(request.state.username, task_id)}
    except Exception as exc:
        _raise_repository_error(exc)


@router.delete("/tasks/{task_id}/permanently")
def permanently_delete_report_generation_task(request: Request, task_id: str):
    try:
        return {"data": _repository().permanently_delete_task(request.state.username, task_id)}
    except Exception as exc:
        _raise_repository_error(exc)
