"""Computer report-generation API."""

from __future__ import annotations

from datetime import date
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator, model_validator

from backend.common.pagination import limit_param
from backend.config.config import ANALYSIS_MODEL_REGISTRY, API_PREFIX
from backend.report.export_service import export_filename, generate_docx, generate_pdf
from backend.report.generation_service import start_report_generation
from backend.repositories.report_generation_repository import ReportGenerationRepository
from backend.routers.workbench_helpers import raise_repository_error, strip_to_required

router = APIRouter(prefix=f"{API_PREFIX}/report-generation", tags=["report-generation"])
ALLOWED_STATUSES = {"queued", "running", "completed", "failed"}


def _validate_model_short_name(model: str) -> str:
    if model not in ANALYSIS_MODEL_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的模型: {model}，可选: {', '.join(ANALYSIS_MODEL_REGISTRY)}",
        )
    return model


def _dedupe_positive_ids(value: list[int]) -> list[int]:
    if any(item <= 0 for item in value):
        raise ValueError("研报 ID 必须为正整数")
    return list(dict.fromkeys(value))


class ReportGenerationCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    requirement: str = Field(min_length=1, max_length=4000)
    report_ids: list[int] = Field(min_length=1, max_length=12)
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    model: str = Field(default="glm", max_length=50)

    @field_validator("title", "requirement")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return strip_to_required(value)

    @field_validator("report_ids")
    @classmethod
    def validate_report_ids(cls, value: list[int]) -> list[int]:
        return _dedupe_positive_ids(value)

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_start and self.date_end and self.date_start > self.date_end:
            raise ValueError("Start date cannot be after end date")
        return self


class ReportGenerationRegenerateRequest(BaseModel):
    """基于历史任务改需求/来源再生成：标题与日期默认沿用原任务。"""

    requirement: str = Field(min_length=1, max_length=4000)
    report_ids: Optional[list[int]] = Field(default=None, min_length=1, max_length=12)
    model: str = Field(default="glm", max_length=50)

    @field_validator("requirement")
    @classmethod
    def clean_requirement(cls, value: str) -> str:
        return strip_to_required(value)

    @field_validator("report_ids")
    @classmethod
    def validate_report_ids(cls, value: Optional[list[int]]) -> Optional[list[int]]:
        if value is None:
            return None
        return _dedupe_positive_ids(value)


def _repository() -> ReportGenerationRepository:
    return ReportGenerationRepository.from_environment()


def _coerce_date(value: Optional[str]) -> Optional[date]:
    """序列化后的日期是 ISO 字符串，再生成时转回 date 入参。"""
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _validate_date_range(date_start: Optional[date], date_end: Optional[date]) -> None:
    """路由参数日期区间校验：start > end 时抛 400。"""
    if date_start and date_end and date_start > date_end:
        raise HTTPException(status_code=400, detail="Start date cannot be after end date")


@router.get("/sources")
def list_report_sources(
    keyword: Optional[str] = Query(default=None, max_length=100),
    institution: Optional[str] = Query(default=None, max_length=100),
    industry: Optional[str] = Query(default=None, max_length=100),
    date_start: Optional[date] = None,
    date_end: Optional[date] = None,
    limit: int = limit_param(),
):
    _validate_date_range(date_start, date_end)
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
    limit: int = limit_param(),
):
    if status and status not in ALLOWED_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid task status")
    _validate_date_range(date_start, date_end)
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
    _validate_model_short_name(body.model)
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
        raise_repository_error(exc)
    start_report_generation(task["id"], model=body.model)
    return {"data": task}


@router.post("/tasks/{task_id}/regenerate", status_code=201)
def regenerate_report_generation_task(
    request: Request, task_id: str, body: ReportGenerationRegenerateRequest
):
    """基于历史任务再生成：沿用标题/日期/来源（来源可覆盖），版本号 +1。"""
    _validate_model_short_name(body.model)
    repository = _repository()
    old_task = repository.get_task(request.state.username, task_id)
    if not old_task:
        raise HTTPException(status_code=404, detail="Report generation task not found")

    report_ids = (
        body.report_ids
        if body.report_ids is not None
        else [int(item) for item in old_task["report_ids_json"]]
    )
    try:
        sources = repository.load_sources(report_ids)
        task = repository.create_task(
            owner_username=request.state.username,
            title=old_task["title"],
            requirement=body.requirement,
            date_start=_coerce_date(old_task.get("date_start")),
            date_end=_coerce_date(old_task.get("date_end")),
            sources=sources,
            version_no=int(old_task.get("version_no") or 1) + 1,
            parent_task_id=old_task["id"],
        )
    except Exception as exc:
        raise_repository_error(exc)
    start_report_generation(task["id"], model=body.model)
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
        raise_repository_error(exc)
    start_report_generation(task_id)
    return {"data": task}


@router.delete("/tasks/{task_id}")
def delete_report_generation_task(request: Request, task_id: str):
    try:
        return {"data": _repository().soft_delete_task(request.state.username, task_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/tasks/{task_id}/restore")
def restore_report_generation_task(request: Request, task_id: str):
    try:
        return {"data": _repository().restore_task(request.state.username, task_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.delete("/tasks/{task_id}/permanently")
def permanently_delete_report_generation_task(request: Request, task_id: str):
    try:
        return {"data": _repository().permanently_delete_task(request.state.username, task_id)}
    except Exception as exc:
        raise_repository_error(exc)


@router.get("/tasks/{task_id}/export")
def export_report_generation_task(
    request: Request,
    task_id: str,
    format: str = Query(..., pattern="^(pdf|docx)$"),
):
    task = _repository().get_task(request.state.username, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Report generation task not found")
    if task["status"] != "completed" or not task.get("result_markdown"):
        raise HTTPException(status_code=409, detail="Only completed reports can be exported")
    try:
        content = (
            generate_pdf(task["title"], task["result_markdown"], task["source_snapshot_json"])
            if format == "pdf"
            else generate_docx(task["title"], task["result_markdown"], task["source_snapshot_json"])
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    media_type = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    filename = export_filename(task["title"], format)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )
