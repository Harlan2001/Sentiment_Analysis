"""统一工作台任务读接口与人工重试；策略历史只读。"""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request

from backend.common.api_response import ok
from backend.common.pagination import page_param, page_size_param
from backend.config.config import API_PREFIX
from backend.repositories.ai_task_repository import AITaskRepository
from backend.routers.workbench_helpers import raise_repository_error
from backend.task_execution.dispatcher import wake_dispatcher
from backend.task_execution.queue import AITaskQueue

router = APIRouter(prefix=f"{API_PREFIX}/workbench/computer", tags=["workbench-computer"])

TaskType = Literal[
    "research_report", "policy_document", "report_generation", "daily_news", "strategy"
]
TaskStatus = Literal[
    "queued", "running", "succeeded", "failed", "empty", "pending", "pending_confirmation"
]


def _owner(request: Request) -> str:
    return str(getattr(request.state, "username", None) or "admin")


@router.get("/tasks")
def list_computer_tasks(
    request: Request,
    task_type: TaskType | None = Query(None),
    status: TaskStatus | None = Query(None),
    selected_date: date | None = Query(None, alias="date"),
    page: int = page_param(),
    page_size: int = page_size_param(default=20, max_size=100),
):
    try:
        result = AITaskRepository.from_environment().list_tasks(
            _owner(request),
            task_type=task_type,
            status=status,
            selected_date=selected_date,
            page=page,
            page_size=page_size,
        )
        return ok(result)
    except Exception as exc:
        raise_repository_error(exc)


@router.get("/tasks/{task_type}/{domain_id}")
def get_computer_task(request: Request, task_type: TaskType, domain_id: str):
    try:
        result = AITaskRepository.from_environment().get_execution_detail(
            _owner(request), task_type, domain_id
        )
        return ok(result)
    except Exception as exc:
        raise_repository_error(exc)


@router.post("/tasks/{task_type}/{domain_id}/retry", status_code=202)
def retry_computer_task(request: Request, task_type: TaskType, domain_id: str):
    if task_type == "strategy":
        raise HTTPException(status_code=409, detail="策略历史仅保留只读跳转")
    owner = _owner(request)
    try:
        AITaskQueue.from_environment().retry(task_type, domain_id, owner)
        wake_dispatcher()
        task = AITaskRepository.from_environment().get_task(owner, task_type, domain_id)
        return ok(task)
    except Exception as exc:
        raise_repository_error(exc)
