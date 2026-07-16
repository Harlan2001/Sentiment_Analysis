"""
开发者可视化看板 API — 路由层
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from backend.common.database import execute_query, execute_update, get_db_connection
from backend.config.config import (
    API_PREFIX,
    SESSION_COOLING_SEC,
    BEHAVIOR_LOG_DEFAULT_DAYS,
)
from backend.tools.dashboard import (
    admin_check,
    fmt_dt,
    fmt_dt2,
    page_title,
    safe_one,
)
from backend.dashboard.dashboard_service import (
    check_service_health,
    get_base_stats,
    build_news_module,
    build_analysis_module,
    build_factor_module,
    build_vector_module,
    build_yield_module,
    build_forecast_module,
    read_cache,
    write_cache,
    cleanup_cache,
    cleanup_old_behavior_logs,
    compute_user_profile,
    profile_row_to_dict,
    peak_slot_label,
)

router = APIRouter(prefix=f"{API_PREFIX}/dashboard", tags=["dashboard"])


# ============================================================
# 核心看板指标接口
# ============================================================
@router.get("/core")
def get_dashboard_core():
    """
    前端大盘首页核心数据接口（GET请求）
    逻辑：先读缓存→无缓存加锁再读一次缓存→无缓存全量计算→写入缓存→返回数据
    """
    import threading
    from backend.dashboard.dashboard_service import cache_lock

    cached = read_cache()
    if cached:
        return {"generated_at": datetime.now().isoformat(), "from_cache": True, **cached}

    with cache_lock:
        cached = read_cache()
        if cached:
            return {"generated_at": datetime.now().isoformat(), "from_cache": True, **cached}

        svc = check_service_health()
        base = get_base_stats()
        if not base:
            return {"error": "数据库无数据"}

        data = {
            "generated_at": datetime.now().isoformat(), "from_cache": False,
            "service_status": svc,
            "top_cards": {
                "news_total": base["news_total"], "analyzed": base["analyzed"],
                "pending": base["pending"], "factor_total": base["factor_total"],
                "yield_days": base["yield_days"],
            },
            "news": build_news_module(base["news_total"], base),
            "analysis": build_analysis_module(base["analyzed"], base["pending"], base["news_total"], base),
            "factor": build_factor_module(base["factor_total"], base),
            "vector": build_vector_module(base["indexed"], base["vec_pending"]),
            "yield": build_yield_module(),
            "forecast": build_forecast_module(base["report_total"]),
        }
        write_cache(data)
        cleanup_cache()
        return data


# ============================================================
# 历史指标快照查询接口
# ============================================================
@router.get("/history")
def get_dashboard_history(days: int = Query(7, ge=1, le=90)):
    """查询历史手动保存的看板快照"""
    rs = execute_query(
        "SELECT id,snapshot_time,metrics_json FROM dashboard_snapshot "
        "WHERE snapshot_time>=DATE_SUB(NOW(),INTERVAL %s DAY) ORDER BY snapshot_time DESC",
        (days,),
    )
    return [
        {
            "id": r[0],
            "snapshot_time": fmt_dt2(r[1]),
            "metrics": json.loads(r[2]) if isinstance(r[2], str) else r[2],
        }
        for r in rs
    ]


# ============================================================
# 手动保存当前大盘快照接口
# ============================================================
@router.post("/snapshot")
def create_dashboard_snapshot():
    """POST接口，手动触发保存当前大盘指标到快照表"""
    core = get_dashboard_core()
    execute_update(
        "INSERT INTO dashboard_snapshot (snapshot_time,metrics_json) VALUES (NOW(),%s)",
        (json.dumps(core, default=str, ensure_ascii=False),),
    )
    return {"success": True}


# ============================================================
# 用户行为事件
# ============================================================
class PageVisitEvent(BaseModel):
    page_route: str
    page_title: Optional[str] = None
    enter_time: str
    leave_time: Optional[str] = None
    duration_sec: Optional[int] = None
    exit_type: Optional[str] = None
    action_type: Optional[str] = "page_enter"
    action_target: Optional[str] = None
    action_detail: Optional[Any] = None
    client_ts: Optional[str] = None


class BehaviorBatchRequest(BaseModel):
    events: List[PageVisitEvent]


@router.post("/behavior/batch")
def post_behavior_batch(body: BehaviorBatchRequest, request: Request):
    """前端批量上报页面访问行为日志接口"""
    un = getattr(request.state, 'username', None)
    if not un or un == 'anonymous':
        return {"received": 0, "note": "anonymous skipped"}
    r = execute_query("SELECT id FROM users WHERE username=%s", (un,), one=True)
    if not r:
        return {"received": 0, "note": f"user '{un}' not found"}
    uid = r[0]
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,login_time FROM user_session WHERE user_id=%s AND logout_time IS NULL ORDER BY login_time DESC LIMIT 1",
                (uid,),
            )
            act = cur.fetchone()
            reuse = False
            if act:
                sid, _ = act
                cur.execute("SELECT MAX(leave_time) FROM user_page_view WHERE session_id=%s", (sid,))
                last = cur.fetchone()[0]
                if last and (datetime.now() - last).total_seconds() <= SESSION_COOLING_SEC:
                    reuse = True
            if reuse:
                sid = act[0]
            else:
                cur.execute(
                    "UPDATE user_session SET logout_time=NOW(),duration_sec=TIMESTAMPDIFF(SECOND,login_time,NOW()) WHERE user_id=%s AND logout_time IS NULL",
                    (uid,),
                )
                cur.execute(
                    "INSERT INTO user_session (user_id,username,login_time) VALUES (%s,%s,NOW())",
                    (uid, un),
                )
                sid = cur.lastrowid
            for evt in body.events:
                cur.execute(
                    """INSERT INTO user_page_view
                    (session_id,user_id,username,page_route,page_title,enter_time,leave_time,duration_sec,exit_type,
                     action_type,action_target,action_detail,client_ts)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        sid, uid, un, evt.page_route,
                        evt.page_title or page_title(evt.page_route),
                        evt.enter_time, evt.leave_time, evt.duration_sec, evt.exit_type,
                        evt.action_type or "page_enter", evt.action_target,
                        json.dumps(evt.action_detail, ensure_ascii=False) if evt.action_detail else None,
                        evt.client_ts or evt.enter_time,
                    ),
                )
        conn.commit()
    return {"received": len(body.events)}


# ============================================================
# 清理长时间无操作的闲置会话接口（管理员）
# ============================================================
@router.post("/cleanup-sessions")
def cleanup_stale_sessions(minutes: int = Query(30)):
    """批量标记超时会话为已登出"""
    n = execute_update(
        """UPDATE user_session s
        LEFT JOIN (SELECT session_id,MAX(leave_time)last FROM user_page_view GROUP BY session_id) p ON p.session_id=s.id
        SET s.logout_time=NOW(),s.duration_sec=TIMESTAMPDIFF(SECOND,s.login_time,NOW())
        WHERE s.logout_time IS NULL AND p.last IS NOT NULL
        AND p.last<DATE_SUB(NOW(),INTERVAL %s MINUTE)""",
        (minutes,),
    )
    return {"cleaned": n, "threshold_minutes": minutes}


# ============================================================
# 清理过期行为日志（保留180天）
# ============================================================
@router.post("/cleanup-behavior-logs")
def trigger_cleanup_behavior_logs(days: int = Query(180, ge=30, le=365), _a=Depends(admin_check)):
    """手动触发清理超过保留期的行为日志"""
    deleted = cleanup_old_behavior_logs(days)
    return {"deleted": deleted, "retention_days": days}


# ============================================================
# 用户行为统计大盘接口（仅管理员访问）
# ============================================================
@router.get("/behavior-stats")
def get_behavior_stats(days: int = Query(7, ge=1, le=90), _a=Depends(admin_check)):
    """行为统计：活跃用户、会话数、页面访问排行、平均停留时长 + 7日趋势 + 时段热力图"""
    # 活跃趋势
    trend_rows = execute_query("""
        SELECT DATE(login_time)d,COUNT(DISTINCT user_id)dau,COUNT(*)sessions
        FROM user_session WHERE login_time>=DATE_SUB(CURDATE(),INTERVAL %s DAY)
        GROUP BY d ORDER BY d""", (days,))
    activity_trend = [{"date": fmt_dt(r[0]), "dau": r[1], "sessions": r[2]} for r in trend_rows]

    # 时段热力分布
    heatmap_rows = execute_query("""
        SELECT HOUR(enter_time)h,DAYOFWEEK(enter_time)dow,COUNT(*)c
        FROM user_page_view WHERE enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY)
        GROUP BY h,dow ORDER BY dow,h""", (days,))
    heatmap = [{"hour": r[0], "day_of_week": r[1], "count": r[2]} for r in heatmap_rows]

    # 重度用户 + 流失风险
    power_users = safe_one("SELECT COUNT(*) FROM user_behavior_profile WHERE is_power_user=1")
    churn_users = safe_one("SELECT COUNT(*) FROM user_behavior_profile WHERE churn_risk_score>0.5")

    return {
        "active_users_today": safe_one(
            "SELECT COUNT(DISTINCT user_id) FROM user_page_view WHERE DATE(enter_time)=CURDATE()"
        ),
        "sessions_today": safe_one(
            "SELECT COUNT(*) FROM user_session WHERE DATE(login_time)=CURDATE()"
        ),
        "avg_duration_7d": int(safe_one(
            "SELECT COALESCE(AVG(duration_sec),0) FROM user_session "
            "WHERE login_time>=DATE_SUB(NOW(),INTERVAL %s DAY) AND duration_sec>0", days
        )),
        "top_page": (lambda r: r[0] if r else None)(
            execute_query(
                "SELECT page_route FROM user_page_view WHERE enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY) "
                "GROUP BY page_route ORDER BY COUNT(*) DESC LIMIT 1", (days,), one=True
            )
        ),
        "power_users": power_users,
        "churn_risk_users": churn_users,
        "activity_trend": activity_trend,
        "hourly_heatmap": heatmap,
        "page_distribution": [
            {"page_route": r[0], "page_title": r[1] or page_title(r[0]), "count": r[2]}
            for r in execute_query("""
                SELECT CASE WHEN page_route IN ('/','/news') THEN '/news' ELSE page_route END AS route,
                CASE WHEN page_route IN ('/','/news') THEN '新闻' ELSE page_title END AS title,
                COUNT(*)c FROM user_page_view WHERE enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY)
                GROUP BY route, title ORDER BY c DESC""", (days,))
        ],
        "page_avg_duration": [
            {"page_route": r[0], "avg_sec": round(float(r[1]), 0) if r[1] else 0}
            for r in execute_query("""
                SELECT CASE WHEN page_route IN ('/','/news') THEN '/news' ELSE page_route END AS route,
                AVG(duration_sec) FROM user_page_view WHERE enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY)
                AND duration_sec>0 GROUP BY route ORDER BY 2 DESC""", (days,))
        ],
    }


# ============================================================
# 行为日志分页查询接口（管理员，默认只查最近10天）
# ============================================================
@router.get("/behavior-logs")
def get_behavior_logs(
    user_id: Optional[str] = Query(None),
    page_route: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    start: Optional[str] = Query(None),
    end: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _a=Depends(admin_check),
):
    """分页查询用户行为明细日志，默认只显示最近10天"""
    cond, params = ["1=1"], []
    for k, v in [("user_id", user_id), ("page_route", page_route), ("action_type", action_type)]:
        if v:
            cond.append(f"{k}=%s")
            params.append(v)

    # 默认只查询最近 N 天
    if not start:
        cond.append("enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY)")
        params.append(BEHAVIOR_LOG_DEFAULT_DAYS)
    else:
        cond.append("enter_time>=%s")
        params.append(start)

    if end:
        cond.append("enter_time<=%s")
        params.append(end)

    w = " AND ".join(cond)
    total = safe_one(f"SELECT COUNT(*) FROM user_page_view WHERE {w}", *params)
    rows = execute_query(
        f"""SELECT id,session_id,user_id,username,page_route,page_title,
        enter_time,leave_time,duration_sec,exit_type,action_type,action_target,action_detail
        FROM user_page_view WHERE {w} ORDER BY enter_time DESC LIMIT %s OFFSET %s""",
        tuple(params) + (limit, offset),
    )
    return {
        "items": [
            {
                "id": r[0], "session_id": r[1], "user_id": r[2], "username": r[3],
                "page_route": r[4],
                "page_title": r[5] or page_title(r[4]) if r[4] else "",
                "enter_time": r[6].isoformat() if hasattr(r[6], 'isoformat') else str(r[6]),
                "leave_time": r[7].isoformat() if r[7] and hasattr(r[7], 'isoformat') else (str(r[7]) if r[7] else None),
                "duration_sec": r[8], "exit_type": r[9],
                "action_type": r[10] or "page_enter",
                "action_target": r[11] or "",
                "action_detail": json.loads(r[12]) if isinstance(r[12], str) else r[12] if r[12] else None,
            }
            for r in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
        "total_pages": (total + limit - 1) // limit if total > 0 else 0,
    }


# ============================================================
# 用户画像接口（管理员）
# ============================================================
@router.get("/behavior/profiles")
def get_behavior_profiles(
    sort_by: str = Query("last_visit"),
    order: str = Query("desc"),
    _a=Depends(admin_check),
):
    """获取所有用户行为画像列表"""
    allowed = {"last_visit", "active_days_30d", "total_active_sec", "total_page_views", "churn_risk_score"}
    if sort_by not in allowed:
        sort_by = "last_visit"
    order_dir = "DESC" if order.lower() == "desc" else "ASC"
    rows = execute_query(
        f"""SELECT id,user_id,username,total_sessions,total_page_views,total_active_sec,
        first_visit,last_visit,active_days_30d,avg_session_sec,avg_daily_pages_30d,
        page_affinity_json,peak_hour,hour_distribution_json,
        distinct_pages_30d,advanced_feature_used,
        is_power_user,is_report_focused,is_strategy_focused,churn_risk_score,
        computed_at,profile_version,updated_at
        FROM user_behavior_profile ORDER BY {sort_by} {order_dir}"""
    )
    return {"profiles": [profile_row_to_dict(r) for r in rows], "count": len(rows)}


@router.get("/behavior/profile/{user_id}")
def get_behavior_profile(user_id: int, _a=Depends(admin_check)):
    """获取单个用户画像（含雷达图数据），不存在时自动计算"""
    r = execute_query("""SELECT id,user_id,username,total_sessions,total_page_views,total_active_sec,
        first_visit,last_visit,active_days_30d,avg_session_sec,avg_daily_pages_30d,
        page_affinity_json,peak_hour,hour_distribution_json,
        distinct_pages_30d,advanced_feature_used,
        is_power_user,is_report_focused,is_strategy_focused,churn_risk_score,
        computed_at,profile_version,updated_at
        FROM user_behavior_profile WHERE user_id=%s""", (user_id,), one=True)
    if not r:
        ur = execute_query("SELECT id,username FROM users WHERE id=%s", (user_id,), one=True)
        if not ur:
            raise HTTPException(404, f"用户 {user_id} 不存在")
        compute_user_profile(ur[0], ur[1])
        r = execute_query("""SELECT id,user_id,username,total_sessions,total_page_views,total_active_sec,
            first_visit,last_visit,active_days_30d,avg_session_sec,avg_daily_pages_30d,
            page_affinity_json,peak_hour,hour_distribution_json,
            distinct_pages_30d,advanced_feature_used,
            is_power_user,is_report_focused,is_strategy_focused,churn_risk_score,
            computed_at,profile_version,updated_at
            FROM user_behavior_profile WHERE user_id=%s""", (user_id,), one=True)
        if not r:
            raise HTTPException(500, "画像计算失败")

    profile = profile_row_to_dict(r)

    # 雷达图数据
    max_active_days, max_daily_pages, max_avg_sec, max_distinct = 30, 50, 3600, 15
    radar = [
        {"dimension": "活跃天数", "score": min(100, round(profile["active_days_30d"] / max_active_days * 100)),
         "value": profile["active_days_30d"], "unit": "天"},
        {"dimension": "日均访问页数", "score": min(100, round(float(profile["avg_daily_pages_30d"]) / max_daily_pages * 100)),
         "value": profile["avg_daily_pages_30d"], "unit": "页/天"},
        {"dimension": "平均停留时长", "score": min(100, round((profile["avg_session_sec"] or 0) / max_avg_sec * 100)),
         "value": profile["avg_session_sec"] or 0, "unit": "秒"},
        {"dimension": "功能覆盖面", "score": min(100, round(profile["distinct_pages_30d"] / max_distinct * 100)),
         "value": profile["distinct_pages_30d"], "unit": "种页面"},
        {"dimension": "深度使用度", "score": 100 if profile["advanced_feature_used"] else 20,
         "value": 1 if profile["advanced_feature_used"] else 0, "unit": "是否使用高级功能"},
        {"dimension": "活跃频次", "score": min(100, round(profile["active_days_30d"] / max_active_days * 100)),
         "value": profile["active_days_30d"], "unit": "天/30天"},
    ]

    # 偏好详情
    page_affinity = profile.get("page_affinity", {}) or {}
    top_pages = sorted(page_affinity.items(), key=lambda x: -x[1])[:5]
    hour_dist = profile.get("hour_distribution", {}) or {}

    profile["radar"] = radar
    profile["preferences"] = {
        "top_pages": [{"route": r, "title": page_title(r), "affinity": round(v, 3)} for r, v in top_pages],
        "peak_slot": peak_slot_label(profile.get("peak_hour")),
        "peak_hour": profile.get("peak_hour"),
        "hour_distribution": hour_dist,
        "report_focused": profile.get("is_report_focused"),
        "strategy_focused": profile.get("is_strategy_focused"),
        "power_user": profile.get("is_power_user"),
        "churn_risk": profile.get("churn_risk_score"),
    }
    return profile


@router.get("/behavior/compare")
def get_behavior_compare(user_ids: str = Query(...), _a=Depends(admin_check)):
    """对比2-3个用户画像"""
    ids = [int(x.strip()) for x in user_ids.split(",") if x.strip()]
    if len(ids) < 2 or len(ids) > 3:
        raise HTTPException(400, "需要2-3个用户ID")
    profiles = []
    for uid in ids:
        try:
            p = get_behavior_profile(uid)
            profiles.append(p)
        except HTTPException:
            pass
    if len(profiles) < 2:
        raise HTTPException(404, "至少需要2个有效用户")

    dims = ["active_days_30d", "avg_daily_pages_30d", "avg_session_sec", "distinct_pages_30d",
            "total_page_views", "total_active_sec"]
    dim_labels = {
        "active_days_30d": "活跃天数(30日)", "avg_daily_pages_30d": "日均访问页数",
        "avg_session_sec": "平均停留(秒)", "distinct_pages_30d": "功能覆盖面",
        "total_page_views": "累计页面访问", "total_active_sec": "累计活跃时长(秒)",
    }
    comparison = []
    for dim in dims:
        entry = {"dimension": dim, "label": dim_labels.get(dim, dim), "values": []}
        for p in profiles:
            entry["values"].append({"user_id": p["user_id"], "username": p["username"], "value": p.get(dim, 0)})
        comparison.append(entry)
    return {"profiles": profiles, "comparison": comparison}


@router.post("/behavior/compute-profile/{user_id}")
def trigger_profile_compute(user_id: int, _a=Depends(admin_check)):
    """手动触发单个用户画像计算"""
    ur = execute_query("SELECT id,username FROM users WHERE id=%s", (user_id,), one=True)
    if not ur:
        raise HTTPException(404, f"用户 {user_id} 不存在")
    return compute_user_profile(ur[0], ur[1])


@router.post("/behavior/compute-all-profiles")
def trigger_all_profiles_compute(_a=Depends(admin_check)):
    """批量计算全部用户画像"""
    users = execute_query("SELECT id,username FROM users")
    done = 0
    for uid, un in users:
        try:
            compute_user_profile(uid, un)
            done += 1
        except Exception:
            pass
    return {"total_users": len(users), "computed": done}
