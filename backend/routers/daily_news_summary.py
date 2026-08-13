"""每日新闻总结任务 HTTP 编排。"""

from __future__ import annotations

import asyncio
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, model_validator

from backend.config.config import API_PREFIX, NEWS_SOURCES
from backend.news_summary.repository import DailyNewsSummaryRepository
from backend.news_summary.service import generate_daily_news_summary

router = APIRouter(
    prefix=f"{API_PREFIX}/daily-news-summaries", tags=["daily-news-summaries"]
)
_background_tasks: set[asyncio.Task] = set()


class DailyNewsSummaryCreateRequest(BaseModel):
    start_date: date
    end_date: date
    sources: list[str] = Field(default_factory=list, max_length=20)
    focus: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def validate_range(self) -> "DailyNewsSummaryCreateRequest":
        if self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        if (self.end_date - self.start_date).days > 30:
            raise ValueError("单次最多总结 31 天新闻")
        invalid_sources = sorted(set(self.sources) - set(NEWS_SOURCES))
        if invalid_sources:
            raise ValueError(f"未知新闻来源: {', '.join(invalid_sources)}")
        self.sources = list(dict.fromkeys(self.sources))
        self.focus = " ".join(self.focus.split())
        return self


def _owner(request: Request) -> str:
    username = getattr(request.state, "username", None)
    if not username:
        raise HTTPException(status_code=401, detail="请先登录后再使用新闻总结")
    return str(username)


def _repository() -> DailyNewsSummaryRepository:
    return DailyNewsSummaryRepository.from_environment()


def _start_generation(owner_username: str, task_id: int) -> None:
    task = asyncio.create_task(
        generate_daily_news_summary(_repository(), owner_username, task_id)
    )
    task.add_done_callback(_background_tasks.discard)
    _background_tasks.add(task)


@router.get("")
def list_summaries(request: Request, limit: int = Query(default=50, ge=1, le=100)):
    items = _repository().list_tasks(_owner(request), limit)
    return {"success": True, "data": {"items": items}}


@router.get("/{task_id}")
def get_summary(request: Request, task_id: int):
    task = _repository().get_task(_owner(request), task_id)
    if not task:
        raise HTTPException(status_code=404, detail="新闻总结任务不存在")
    return {"success": True, "data": task}


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_summary(request: Request, body: DailyNewsSummaryCreateRequest):
    owner_username = _owner(request)
    task = await asyncio.to_thread(
        _repository().create_task,
        owner_username,
        body.start_date,
        body.end_date,
        body.sources,
        body.focus,
    )
    _start_generation(owner_username, int(task["id"]))
    return {"success": True, "data": task}


@router.post("/{task_id}/retry", status_code=status.HTTP_202_ACCEPTED)
async def retry_summary(request: Request, task_id: int):
    owner_username = _owner(request)
    repository = _repository()
    previous = await asyncio.to_thread(repository.get_task, owner_username, task_id)
    if not previous:
        raise HTTPException(status_code=404, detail="新闻总结任务不存在")
    if previous["status"] not in {"failed", "empty"}:
        raise HTTPException(status_code=409, detail="仅失败或无新闻的任务可以重试")
    task = await asyncio.to_thread(
        repository.create_task,
        owner_username,
        date.fromisoformat(previous["start_date"]),
        date.fromisoformat(previous["end_date"]),
        previous.get("sources_json") or [],
        str(previous.get("focus") or ""),
        task_id,
    )
    _start_generation(owner_username, int(task["id"]))
    return {"success": True, "data": task}
