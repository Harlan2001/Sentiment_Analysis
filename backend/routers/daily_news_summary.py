"""每日新闻总结任务 HTTP 编排。"""

from __future__ import annotations

import asyncio
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, model_validator

from backend.config.config import API_PREFIX, NEWS_SOURCES
from backend.news_summary.repository import (
    DailyNewsSummaryNotFoundError,
    DailyNewsSummaryRepository,
)
from backend.news_summary.service import generate_daily_news_summary

router = APIRouter(
    prefix=f"{API_PREFIX}/daily-news-summaries", tags=["daily-news-summaries"]
)
_background_tasks: set[asyncio.Task] = set()
POLICY_DEMO_SUMMARY_ID = 0


def _policy_demo_summary(owner_username: str) -> dict:
    """返回政策驱动演示对话所指向的固定新闻总结，不写入用户任务数据。"""
    return {
        "id": POLICY_DEMO_SUMMARY_ID,
        "owner_username": owner_username,
        "start_date": "2026-07-20",
        "end_date": "2026-07-26",
        "sources_json": ["财联社", "中国证券报"],
        "focus": "政策驱动：逆回购投放、LPR持稳与利率债久期判断",
        "status": "succeeded",
        "news_count": 2,
        "source_stats_json": {"财联社": 1, "中国证券报": 1},
        "summary": """# 政策驱动｜新闻总结

## 核心结论

本轮政策组合呈现“**数量工具发力、价格工具观望**”的特征。2.1万亿元逆回购提前投放，直接缓解跨月资金压力，对短端利率债构成利多；LPR连续14个月持稳，意味着长端暂未获得新的降息驱动。

## 新闻影响链路

- **逆回购投放** → 银行间流动性充裕 → 短端资金成本回落 → 短久期与杠杆套息相对受益。
- **LPR持稳** → 政策利率预期稳定 → 长端降息预期受限 → 长久期维持观察。

## 关注重点

后续需结合财政支出累计值及同比增速，验证流动性支持是否继续向逆周期调节传导；若资金面收紧或供给放量，应及时收缩久期与杠杆暴露。""",
        "references_json": [
            {
                "news_id": 14483,
                "title": "2.1万亿隔夜逆回购护航跨月，央行“给量不给价”释放清晰信号",
                "publish_time": "2026-07-26T00:00:00",
                "source": "财联社",
                "direction": "positive",
                "horizon": "short",
            },
            {
                "news_id": 14395,
                "title": "LPR连续14个月持稳，下半年逆周期调节如何落地？",
                "publish_time": "2026-07-20T00:00:00",
                "source": "中国证券报",
                "direction": "neutral",
                "horizon": "medium",
            },
        ],
        "error_message": None,
        "retry_of_id": None,
        "started_at": "2026-07-26T09:30:00",
        "completed_at": "2026-07-26T09:31:00",
        "created_at": "2026-07-26T09:30:00",
        "updated_at": "2026-07-26T09:31:00",
    }


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
    owner_username = _owner(request)
    if task_id == POLICY_DEMO_SUMMARY_ID:
        return {"success": True, "data": _policy_demo_summary(owner_username)}
    task = _repository().get_task(owner_username, task_id)
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


@router.delete("/{task_id}")
def delete_summary(request: Request, task_id: int):
    try:
        return {"success": True, "data": _repository().soft_delete_task(_owner(request), task_id)}
    except DailyNewsSummaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{task_id}/restore")
def restore_summary(request: Request, task_id: int):
    try:
        return {"success": True, "data": _repository().restore_task(_owner(request), task_id)}
    except DailyNewsSummaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{task_id}/permanently")
def permanently_delete_summary(request: Request, task_id: int):
    try:
        return {"success": True, "data": _repository().permanently_delete_task(_owner(request), task_id)}
    except DailyNewsSummaryNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
