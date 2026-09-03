"""Computer 工作台总览 — 聚合研报生成、策略开发、每日新闻总结任务。"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

from backend.config.config import API_PREFIX
from backend.repositories.ai_strategy_history_repository import AiStrategyHistoryRepository
from backend.repositories.news_summary_repository import DailyNewsSummaryRepository
from backend.repositories.report_generation_repository import ReportGenerationRepository

router = APIRouter(prefix=f"{API_PREFIX}/workbench/computer", tags=["workbench-computer"])

logger = logging.getLogger(__name__)

_PER_SOURCE_LIMIT = 20

# ── 状态映射 ──────────────────────────────────────────────────

_REPORT_STATUS_LABEL: dict[str, str] = {
    "queued": "排队中",
    "running": "生成中",
    "completed": "已完成",
    "failed": "生成失败",
}

_NEWS_STATUS_LABEL: dict[str, str] = {
    "pending": "等待生成",
    "running": "生成中",
    "succeeded": "已完成",
    "failed": "生成失败",
    "empty": "无新闻",
}


def _date_only(value: str | None) -> str | None:
    if not value:
        return None
    return value[:10]


def _normalize_report(task: dict[str, Any]) -> dict[str, Any]:
    status = str(task.get("status") or "queued")
    sources = task.get("source_snapshot_json") or []
    return {
        "task_id": f"report:{task['id']}",
        "task_type": "report_generation",
        "module": "研报分析",
        "title": str(task.get("title") or "未命名研报"),
        "description": " ".join(str(task.get("requirement") or "").split())[:140],
        "source": "研报分析",
        "result": f"{len(sources)} 份来源"
        if status == "completed"
        else f"{len(sources)} 份来源 · 待完成",
        "status": status,
        "status_label": _REPORT_STATUS_LABEL.get(status, status),
        "date": _date_only(task.get("date_start"))
        or _date_only(task.get("created_at")),
        "updated_at": str(task.get("updated_at") or task.get("created_at") or ""),
        "needs_action": status == "failed",
    }


def _normalize_news(task: dict[str, Any]) -> dict[str, Any]:
    status = str(task.get("status") or "pending")
    start = str(task.get("start_date") or "")
    end = str(task.get("end_date") or "")
    date_range = start if start == end else f"{start} 至 {end}"
    news_count = int(task.get("news_count") or 0)
    focus = str(task.get("focus") or "")
    desc_parts = [f"覆盖 {news_count} 条新闻"]
    if focus:
        desc_parts.append(f"关注：{focus}")
    return {
        "task_id": f"news:{task['id']}",
        "task_type": "daily_news",
        "module": "每日新闻总结",
        "title": f"{date_range} 每日新闻总结",
        "description": " · ".join(desc_parts)[:140],
        "source": "手动触发" if focus else "自动计划",
        "result": f"新闻总结_{start}_{end}.md"
        if status == "succeeded"
        else "生成中" if status == "running"
        else "-",
        "status": status,
        "status_label": _NEWS_STATUS_LABEL.get(status, status),
        "date": start or _date_only(task.get("created_at")),
        "updated_at": str(task.get("updated_at") or task.get("created_at") or ""),
        "needs_action": status == "failed",
    }


def _normalize_strategy(conv: dict[str, Any]) -> dict[str, Any]:
    has_version = int(conv.get("current_local_version_no") or 0) > 0
    status = "completed" if has_version else "pending_confirmation"
    return {
        "task_id": f"strategy:{conv['id']}",
        "task_type": "strategy",
        "module": "策略开发",
        "title": str(conv.get("title") or "新策略对话"),
        "description": "策略已生成并完成回测"
        if has_version
        else "提示词草稿等待用户确认",
        "source": "用户生成",
        "result": f"策略 v{conv.get('current_local_version_no')}"
        if has_version
        else "等待确认",
        "status": status,
        "status_label": "已完成" if has_version else "待确认",
        "date": _date_only(conv.get("last_message_at") or conv.get("created_at")),
        "updated_at": str(conv.get("updated_at") or conv.get("created_at") or ""),
        "needs_action": not has_version,
    }


def _owner(request: Request) -> str:
    username = getattr(request.state, "username", None)
    if not username:
        username = "admin"
    return str(username)


@router.get("/tasks")
def list_computer_tasks(request: Request):
    username = _owner(request)

    # ── 研报生成 ──
    report_tasks: list[dict[str, Any]] = []
    try:
        report_repo = ReportGenerationRepository.from_environment()
        report_tasks = report_repo.list_tasks(
            username, status=None, date_start=None, date_end=None, limit=_PER_SOURCE_LIMIT
        )
    except Exception as exc:
        # 聚合总览：单个子源失败不影响整页，但必须留痕
        logger.warning("computer: 研报生成任务拉取失败: %s", exc)

    # ── 新闻总结 ──
    news_tasks: list[dict[str, Any]] = []
    try:
        news_repo = DailyNewsSummaryRepository.from_environment()
        news_tasks = news_repo.list_tasks(username, _PER_SOURCE_LIMIT)
    except Exception as exc:
        logger.warning("computer: 新闻总结任务拉取失败: %s", exc)

    # ── 策略开发 ──
    strategy_convs: list[dict[str, Any]] = []
    try:
        strategy_repo = AiStrategyHistoryRepository.from_environment()
        strategy_convs = strategy_repo.list_conversations(username, _PER_SOURCE_LIMIT)
    except Exception as exc:
        logger.warning("computer: 策略会话拉取失败: %s", exc)

    items: list[dict[str, Any]] = []
    for task in report_tasks:
        items.append(_normalize_report(task))
    for task in news_tasks:
        items.append(_normalize_news(task))
    for conv in strategy_convs:
        items.append(_normalize_strategy(conv))

    items.sort(key=lambda item: item["updated_at"], reverse=True)

    totals = {
        "report_generation": len(report_tasks),
        "daily_news": len(news_tasks),
        "strategy": len(strategy_convs),
        "total": len(items),
    }

    return {"data": {"items": items, "totals": totals}}
