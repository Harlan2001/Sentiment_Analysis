"""
策略与标的变动对比 — API 路由层。
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel

from backend.change.change_service import (
    CHANGE_TZ,
    compute_diff,
    compute_window_from_news,
    count_news_raw,
    generate_recommendations,
    latest_snapshot,
    list_snapshots,
    query_news_for_window,
    query_news_ids_analyzed,
    save_snapshot,
    snapshot_by_id,
    snapshot_by_version_time,
)

logger = logging.getLogger("change_router")

router = APIRouter(prefix="/api/change", tags=["change"])


# ============================================================
# Pydantic 请求模型
# ============================================================

class TriggerRequest(BaseModel):
    force: bool = False


class CompareRequest(BaseModel):
    old_snapshot_id: Optional[int] = None
    new_snapshot_id: Optional[int] = None
    old_version_time: Optional[str] = None
    new_version_time: Optional[str] = None


# ============================================================
# API 端点
# ============================================================

@router.post("/trigger")
async def trigger_snapshot(request: TriggerRequest = Body(default=TriggerRequest())):
    """
    触发一次快照生成。
    基于 news.pub_time（数据源时间，非服务器时间）确定24h滚动窗口，
    取 analysis.reason 作为LLM输入，生成标的+策略推荐，写入快照表。

    保护措施：
    - 若 news 表最新 pub_time 与当前服务器时间偏差 > 2h，标记待确认
    - 若窗口内未分析新闻占比 > 50%，标记待确认
    """
    # 基于 news.pub_time 计算窗口（而非服务器时间）
    version_time, window_start, window_end = compute_window_from_news()

    if version_time is None or window_start is None or window_end is None:
        raise HTTPException(status_code=503, detail="news 表为空，无法确定窗口范围。请先执行新闻爬取与分析。")

    # 查询窗口内已分析的新闻（有 reason 的）
    news_rows = query_news_for_window(window_start, window_end)

    # 统计窗口内新闻覆盖情况
    total_news_raw = count_news_raw(window_start, window_end)
    analyzed_count = len(news_rows)
    unanalyzed_count = max(0, total_news_raw - analyzed_count)
    analysis_coverage = (analyzed_count / total_news_raw * 100) if total_news_raw > 0 else 0

    logger.info(
        "窗口 [%s ~ %s]：总新闻=%d, 已分析=%d, 未分析=%d, 覆盖率=%.1f%%",
        window_start.strftime("%Y-%m-%d %H:%M"),
        window_end.strftime("%Y-%m-%d %H:%M"),
        total_news_raw, analyzed_count, unanalyzed_count, analysis_coverage,
    )

    if not news_rows and not request.force:
        return {
            "success": True,
            "message": (
                f"窗口内无已分析新闻（总{total_news_raw}条，已分析0条）。"
                f"请检查 analysis 表是否已写入。使用 force=true 可强制生成。"
            ),
            "skipped": True,
            "window": {
                "start": window_start.strftime("%Y-%m-%d %H:%M:%S"),
                "end": window_end.strftime("%Y-%m-%d %H:%M:%S"),
                "total_news_raw": total_news_raw,
                "analyzed_count": 0,
            },
        }

    # 计算相比上一版本的新闻变动
    current_news_ids = {r["news_id"] for r in news_rows}
    prev = latest_snapshot()
    news_added_count = 0
    news_removed_count = 0

    if prev:
        prev_window_start = datetime.strptime(prev["window_start"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CHANGE_TZ)
        prev_window_end = datetime.strptime(prev["window_end"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=CHANGE_TZ)
        prev_news_ids = query_news_ids_analyzed(prev_window_start, prev_window_end)
        news_added_count = len(current_news_ids - prev_news_ids)
        news_removed_count = len(prev_news_ids - current_news_ids)

    # 调用 LLM 生成推荐
    try:
        result = generate_recommendations(news_rows, window_start, window_end)
    except Exception as exc:
        logger.exception("LLM 推荐生成失败")
        raise HTTPException(status_code=500, detail=f"LLM 推荐生成失败: {exc}")

    stock_recommend = result.get("stock_recommend", [])
    strategy_recommend = result.get("strategy_recommend", [])
    summary_stats = result.get("summary_stats", {})
    summary_stats["market_overview"] = result.get("market_overview", "")

    # 注入分析覆盖信息到 summary_stats（前端可展示）
    summary_stats["news_total_raw"] = total_news_raw
    summary_stats["analyzed_count"] = analyzed_count
    summary_stats["unanalyzed_count"] = unanalyzed_count
    summary_stats["analysis_coverage_pct"] = round(analysis_coverage, 1)

    # --- 校验与保护 ---
    generate_status = 1
    warnings: List[str] = []

    # 1) 时间偏差检测：news 最新时间 vs 服务器当前时间
    server_now = datetime.now(CHANGE_TZ)
    time_gap_hours = abs((server_now - version_time).total_seconds()) / 3600
    if time_gap_hours > 2:
        generate_status = 2
        warnings.append(f"数据源最新时间与服务器时间偏差 {time_gap_hours:.1f}h，可能爬虫或分析管道延迟")

    # 2) 分析覆盖率不足
    if total_news_raw > 0 and analysis_coverage < 50:
        generate_status = 2
        warnings.append(f"窗口内仅 {analysis_coverage:.0f}% 新闻已完成分析（{analyzed_count}/{total_news_raw}），推荐可能不完整")

    # 3) 新闻量波动超过 50%
    if prev and prev.get("news_total", 0) > 0 and analyzed_count > 0:
        news_change_ratio = abs(analyzed_count - prev["news_total"]) / prev["news_total"]
        if news_change_ratio > 0.5:
            generate_status = 2
            warnings.append(f"新闻量波动 {news_change_ratio:.0%}，超过 50% 阈值")

    # 4) LLM 未生成任何推荐
    if len(stock_recommend) == 0 and len(strategy_recommend) == 0:
        generate_status = 2
        warnings.append("LLM 未生成任何标的或策略推荐")

    if warnings:
        summary_stats["warnings"] = warnings

    snapshot = {
        "version_time": version_time.strftime("%Y-%m-%d %H:%M:%S"),
        "window_start": window_start.strftime("%Y-%m-%d %H:%M:%S"),
        "window_end": window_end.strftime("%Y-%m-%d %H:%M:%S"),
        "news_total": analyzed_count,
        "news_added_count": news_added_count,
        "news_removed_count": news_removed_count,
        "stock_recommend": stock_recommend,
        "strategy_recommend": strategy_recommend,
        "summary_stats": summary_stats,
        "generate_status": generate_status,
    }

    try:
        new_id = save_snapshot(snapshot)
    except Exception as exc:
        logger.exception("快照写入失败")
        raise HTTPException(status_code=500, detail=f"快照写入失败: {exc}")

    snapshot["id"] = new_id
    return {
        "success": True,
        "snapshot": snapshot,
        "message": (
            "快照生成成功"
            if generate_status == 1
            else f"快照已生成（待确认），警告: {'; '.join(warnings)}"
        ),
    }


@router.get("/snapshots")
def get_snapshots(hours: int = Query(24, ge=1, le=168)):
    """返回指定小时数内的快照列表，用于时间轴渲染"""
    try:
        items = list_snapshots(hours)
        return {"success": True, "items": items, "count": len(items)}
    except Exception as exc:
        logger.exception("快照列表查询失败")
        raise HTTPException(status_code=500, detail=f"快照列表查询失败: {exc}")


@router.post("/compare")
def compare_snapshots(request: CompareRequest = Body(default=CompareRequest())):
    """对比两个版本的快照，返回标的&策略变动详情"""
    # 确定新旧快照
    old_snapshot = None
    new_snapshot = None

    if request.new_snapshot_id:
        new_snapshot = snapshot_by_id(request.new_snapshot_id)
    elif request.new_version_time:
        new_snapshot = snapshot_by_version_time(request.new_version_time)

    if request.old_snapshot_id:
        old_snapshot = snapshot_by_id(request.old_snapshot_id)
    elif request.old_version_time:
        old_snapshot = snapshot_by_version_time(request.old_version_time)

    # 默认：取最新两个版本
    if not new_snapshot:
        all_items = list_snapshots(48)
        if len(all_items) >= 1:
            new_snapshot = snapshot_by_id(all_items[0]["id"])
        if not old_snapshot and len(all_items) >= 2:
            old_snapshot = snapshot_by_id(all_items[1]["id"])

    if not new_snapshot:
        raise HTTPException(status_code=404, detail="未找到快照数据，请先调用 /api/change/trigger 生成")

    if not old_snapshot:
        raise HTTPException(
            status_code=400,
            detail="仅有一个版本的快照，无法对比。请至少生成两个版本后重试。",
        )

    try:
        diff = compute_diff(old_snapshot, new_snapshot)
        diff["old_snapshot_id"] = old_snapshot["id"]
        diff["new_snapshot_id"] = new_snapshot["id"]
        diff["old_summary"] = old_snapshot.get("summary_stats", {})
        diff["new_summary"] = new_snapshot.get("summary_stats", {})
        return {"success": True, **diff}
    except Exception as exc:
        logger.exception("快照对比失败")
        raise HTTPException(status_code=500, detail=f"快照对比失败: {exc}")
