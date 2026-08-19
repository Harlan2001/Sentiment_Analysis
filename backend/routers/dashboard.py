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
    BEHAVIOR_LOG_DEFAULT_DAYS,
    SESSION_COOLING_SEC,
)
from backend.dashboard.dashboard_service import (
    build_analysis_module,
    build_factor_module,
    build_forecast_module,
    build_news_module,
    build_research_module,
    build_vector_module,
    build_yield_module,
    check_service_health,
    cleanup_cache,
    cleanup_old_behavior_logs,
    compute_user_profile,
    get_base_stats,
    get_department_behavior_stats,
    get_leader_overview,
    get_token_by_model,
    get_token_overview,
    get_token_trend,
    get_user_token_list,
    peak_slot_label,
    profile_row_to_dict,
    read_cache,
    write_cache,
)
from backend.tools.dashboard import (
    admin_check,
    fmt_dt,
    fmt_dt2,
    manager_check,
    pad_page_routes,
    page_title,
    safe_one,
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
    from backend.dashboard.dashboard_service import cache_lock

    cached = read_cache()
    if cached:
        return {**cached, "from_cache": True}

    with cache_lock:
        cached = read_cache()
        if cached:
            return {**cached, "from_cache": True}

        svc = check_service_health()
        base = get_base_stats()
        if not base:
            return {"error": "数据库无数据"}

        data = {
            "generated_at": datetime.now().isoformat(),
            "from_cache": False,
            "service_status": svc,
            "top_cards": {
                "news_total": base["news_total"],
                "analyzed": base["analyzed"],
                "pending": base["pending"],
                "factor_total": base["factor_total"],
                "yield_days": base["yield_days"],
            },
            "news": build_news_module(base["news_total"], base),
            "analysis": build_analysis_module(
                base["analyzed"], base["pending"], base["news_total"], base
            ),
            "factor": build_factor_module(base["factor_total"], base),
            "vector": build_vector_module(base["indexed"], base["vec_pending"]),
            "yield": build_yield_module(),
            "forecast": build_forecast_module(base["report_total"]),
            "research": build_research_module(base),
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
    un = getattr(request.state, "username", None)
    if not un or un == "anonymous":
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
                cur.execute(
                    "SELECT MAX(leave_time) FROM user_page_view WHERE session_id=%s",
                    (sid,),
                )
                last = cur.fetchone()[0]
                if (
                    last
                    and (datetime.now() - last).total_seconds() <= SESSION_COOLING_SEC
                ):
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
                        sid,
                        uid,
                        un,
                        evt.page_route,
                        evt.page_title or page_title(evt.page_route),
                        evt.enter_time,
                        evt.leave_time,
                        evt.duration_sec,
                        evt.exit_type,
                        evt.action_type or "page_enter",
                        evt.action_target,
                        (
                            json.dumps(evt.action_detail, ensure_ascii=False)
                            if evt.action_detail
                            else "{}"
                        ),
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
def trigger_cleanup_behavior_logs(
    days: int = Query(180, ge=30, le=365), _a=Depends(admin_check)
):
    """手动触发清理超过保留期的行为日志"""
    deleted = cleanup_old_behavior_logs(days)
    return {"deleted": deleted, "retention_days": days}


# ============================================================
# 用户行为统计大盘接口（仅管理员访问）
# ============================================================
@router.get("/behavior-stats")
def get_behavior_stats(days: int = Query(7, ge=1, le=90), _a=Depends(admin_check)):
    """行为统计：活跃用户、会话数、页面访问排行、平均停留时长 + 7日趋势 + 时段热力图"""
    from backend.dashboard.dashboard_service import read_cache, write_cache

    cache_key = f"behavior_{days}"
    cached = read_cache(cache_key)
    if cached:
        return cached
    # 活跃趋势
    trend_rows = execute_query(
        """
        SELECT DATE(login_time)d,COUNT(DISTINCT user_id)dau,COUNT(*)sessions
        FROM user_session WHERE login_time>=DATE_SUB(CURDATE(),INTERVAL %s DAY)
        GROUP BY d ORDER BY d""",
        (days,),
    )
    activity_trend = [
        {"date": fmt_dt(r[0]), "dau": r[1], "sessions": r[2]} for r in trend_rows
    ]

    # 时段热力分布
    heatmap_rows = execute_query(
        """
        SELECT HOUR(enter_time)h,DAYOFWEEK(enter_time)dow,COUNT(*)c
        FROM user_page_view WHERE enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY)
        GROUP BY h,dow ORDER BY dow,h""",
        (days,),
    )
    heatmap = [{"hour": r[0], "day_of_week": r[1], "count": r[2]} for r in heatmap_rows]

    # 重度用户 + 流失风险
    power_users = safe_one(
        "SELECT COUNT(*) FROM user_behavior_profile WHERE is_power_user=1"
    )
    churn_users = safe_one(
        "SELECT COUNT(*) FROM user_behavior_profile WHERE churn_risk_score>0.5"
    )

    result = {
        "active_users_today": safe_one(
            "SELECT COUNT(DISTINCT user_id) FROM user_page_view WHERE DATE(enter_time)=CURDATE()"
        ),
        "sessions_today": safe_one(
            "SELECT COUNT(*) FROM user_session WHERE DATE(login_time)=CURDATE()"
        ),
        "avg_duration_7d": int(
            safe_one(
                "SELECT COALESCE(AVG(duration_sec),0) FROM user_session "
                "WHERE login_time>=DATE_SUB(NOW(),INTERVAL %s DAY) AND duration_sec>0",
                days,
            )
        ),
        "top_page": (lambda r: r[0] if r else None)(
            execute_query(
                "SELECT page_route FROM user_page_view WHERE enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY) "
                "GROUP BY page_route ORDER BY COUNT(*) DESC LIMIT 1",
                (days,),
                one=True,
            )
        ),
        "power_users": power_users,
        "churn_risk_users": churn_users,
        "activity_trend": activity_trend,
        "hourly_heatmap": heatmap,
        "page_distribution": pad_page_routes(
            [
                {"page_route": r[0], "page_title": page_title(r[0]), "count": r[1]}
                for r in execute_query(
                    """
                SELECT CASE WHEN page_route IN ('/','/news') THEN '/news'
                WHEN page_route LIKE '/research/%%' THEN '/research'
                WHEN page_route LIKE '/ai-strategy-generation%%' THEN '/ai-strategy-generation'
                ELSE page_route END AS route,
                COUNT(*)c FROM user_page_view WHERE enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY)
                GROUP BY route ORDER BY c DESC""",
                    (days,),
                )
            ]
        ),
        "page_avg_duration": pad_page_routes(
            [
                {"page_route": r[0], "avg_sec": round(float(r[1]), 0) if r[1] else 0}
                for r in execute_query(
                    """
                SELECT CASE WHEN page_route IN ('/','/news') THEN '/news'
                WHEN page_route LIKE '/research/%%' THEN '/research'
                WHEN page_route LIKE '/ai-strategy-generation%%' THEN '/ai-strategy-generation'
                ELSE page_route END AS route,
                AVG(duration_sec) FROM user_page_view WHERE enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY)
                AND duration_sec>0 GROUP BY route ORDER BY 2 DESC""",
                    (days,),
                )
            ],
            count_key="avg_sec",
        ),
    }
    result["_ts"] = datetime.now().isoformat()
    write_cache(result, cache_key)
    return result


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
    for k, v in [
        ("user_id", user_id),
        ("page_route", page_route),
        ("action_type", action_type),
    ]:
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
                "id": r[0],
                "session_id": r[1],
                "user_id": r[2],
                "username": r[3],
                "page_route": r[4],
                "page_title": page_title(r[4]) if r[4] else "",
                "enter_time": (
                    r[6].isoformat() if hasattr(r[6], "isoformat") else str(r[6])
                ),
                "leave_time": (
                    r[7].isoformat()
                    if r[7] and hasattr(r[7], "isoformat")
                    else (str(r[7]) if r[7] else None)
                ),
                "duration_sec": r[8],
                "exit_type": r[9],
                "action_type": r[10] or "page_enter",
                "action_target": r[11] or "",
                "action_detail": (
                    json.loads(r[12])
                    if isinstance(r[12], str)
                    else r[12] if r[12] else None
                ),
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
@router.get("/users/active")
def get_active_users(_a=Depends(admin_check)):
    """获取所有活跃用户列表（用于画像选择器等下拉框）"""
    rows = execute_query(
        """SELECT id, username, display_name, department, role, COALESCE(company,'') as company
        FROM users WHERE is_active=1 ORDER BY id"""
    )
    return {
        "users": [
            {
                "id": r[0],
                "username": r[1],
                "display_name": r[2] or r[1],
                "department": r[3],
                "role": r[4],
                "company": r[5] or None,
            }
            for r in rows
        ]
    }


@router.get("/behavior/profiles")
def get_behavior_profiles(
    sort_by: str = Query("last_visit"),
    order: str = Query("desc"),
    _a=Depends(admin_check),
):
    """获取所有用户行为画像列表"""
    allowed = {
        "last_visit",
        "active_days_30d",
        "total_active_sec",
        "total_page_views",
        "churn_risk_score",
    }
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
    r = execute_query(
        """SELECT id,user_id,username,total_sessions,total_page_views,total_active_sec,
        first_visit,last_visit,active_days_30d,avg_session_sec,avg_daily_pages_30d,
        page_affinity_json,peak_hour,hour_distribution_json,
        distinct_pages_30d,advanced_feature_used,
        is_power_user,is_report_focused,is_strategy_focused,churn_risk_score,
        computed_at,profile_version,updated_at
        FROM user_behavior_profile WHERE user_id=%s""",
        (user_id,),
        one=True,
    )
    if not r:
        ur = execute_query(
            "SELECT id,username FROM users WHERE id=%s", (user_id,), one=True
        )
        if not ur:
            raise HTTPException(404, f"用户 {user_id} 不存在")
        compute_user_profile(ur[0], ur[1])
        r = execute_query(
            """SELECT id,user_id,username,total_sessions,total_page_views,total_active_sec,
            first_visit,last_visit,active_days_30d,avg_session_sec,avg_daily_pages_30d,
            page_affinity_json,peak_hour,hour_distribution_json,
            distinct_pages_30d,advanced_feature_used,
            is_power_user,is_report_focused,is_strategy_focused,churn_risk_score,
            computed_at,profile_version,updated_at
            FROM user_behavior_profile WHERE user_id=%s""",
            (user_id,),
            one=True,
        )
        if not r:
            raise HTTPException(500, "画像计算失败")

    profile = profile_row_to_dict(r)

    # 雷达图数据
    max_active_days, max_daily_pages, max_avg_sec, max_distinct = 30, 50, 3600, 15
    radar = [
        {
            "dimension": "活跃天数",
            "score": min(
                100, round(profile["active_days_30d"] / max_active_days * 100)
            ),
            "value": profile["active_days_30d"],
            "unit": "天",
        },
        {
            "dimension": "日均访问页数",
            "score": min(
                100,
                round(float(profile["avg_daily_pages_30d"]) / max_daily_pages * 100),
            ),
            "value": profile["avg_daily_pages_30d"],
            "unit": "页/天",
        },
        {
            "dimension": "平均停留时长",
            "score": min(
                100, round((profile["avg_session_sec"] or 0) / max_avg_sec * 100)
            ),
            "value": profile["avg_session_sec"] or 0,
            "unit": "秒",
        },
        {
            "dimension": "功能覆盖面",
            "score": min(
                100, round(profile["distinct_pages_30d"] / max_distinct * 100)
            ),
            "value": profile["distinct_pages_30d"],
            "unit": "种页面",
        },
        {
            "dimension": "深度使用度",
            "score": 100 if profile["advanced_feature_used"] else 20,
            "value": 1 if profile["advanced_feature_used"] else 0,
            "unit": "是否使用高级功能",
        },
        {
            "dimension": "活跃频次",
            "score": min(
                100, round(profile["active_days_30d"] / max_active_days * 100)
            ),
            "value": profile["active_days_30d"],
            "unit": "天/30天",
        },
    ]

    # 偏好详情
    page_affinity = profile.get("page_affinity", {}) or {}
    top_pages = sorted(page_affinity.items(), key=lambda x: -x[1])[:5]
    hour_dist = profile.get("hour_distribution", {}) or {}

    profile["radar"] = radar
    profile["preferences"] = {
        "top_pages": [
            {"route": r, "title": page_title(r), "affinity": round(v, 3)}
            for r, v in top_pages
        ],
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

    dims = [
        "active_days_30d",
        "avg_daily_pages_30d",
        "avg_session_sec",
        "distinct_pages_30d",
        "total_page_views",
        "total_active_sec",
    ]
    dim_labels = {
        "active_days_30d": "活跃天数(30日)",
        "avg_daily_pages_30d": "日均访问页数",
        "avg_session_sec": "平均停留(秒)",
        "distinct_pages_30d": "功能覆盖面",
        "total_page_views": "累计页面访问",
        "total_active_sec": "累计活跃时长(秒)",
    }
    comparison = []
    for dim in dims:
        entry = {"dimension": dim, "label": dim_labels.get(dim, dim), "values": []}
        for p in profiles:
            entry["values"].append(
                {
                    "user_id": p["user_id"],
                    "username": p["username"],
                    "value": p.get(dim, 0),
                }
            )
        comparison.append(entry)
    return {"profiles": profiles, "comparison": comparison}


@router.post("/behavior/compute-profile/{user_id}")
def trigger_profile_compute(user_id: int, _a=Depends(admin_check)):
    """手动触发单个用户画像计算"""
    ur = execute_query(
        "SELECT id,username FROM users WHERE id=%s", (user_id,), one=True
    )
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


# ============================================================
# Token 使用统计接口（Task 1: 系统监控 | Task 2: 用户管理）
# ============================================================


@router.get("/token/overview")
def token_overview(dep=Depends(manager_check)):
    """Token 消耗全局汇总（今日/本月/总计 + 按来源分组）；经理仅看本部门+本公司"""
    from backend.dashboard.dashboard_service import read_cache, write_cache

    cache_key = f"token_{dep['department']}_{dep['company']}"
    cached = read_cache(cache_key)
    if cached:
        return cached
    data = get_token_overview(
        manager_department=dep["department"], manager_company=dep["company"]
    )
    data["_ts"] = datetime.now().isoformat()
    write_cache(data, cache_key)
    return data


@router.get("/token/trend")
def token_trend(days: int = Query(7, ge=1, le=90), dep=Depends(manager_check)):
    """Token 消耗趋势（按天 + 按模型堆叠）；经理仅看本部门+本公司"""
    return {
        "trend": get_token_trend(
            days, manager_department=dep["department"], manager_company=dep["company"]
        )
    }


@router.get("/token/by-model")
def token_by_model(days: int = Query(7, ge=1, le=90), dep=Depends(manager_check)):
    """各模型 Token 用量分布；经理仅看本部门+本公司"""
    return {
        "models": get_token_by_model(
            days, manager_department=dep["department"], manager_company=dep["company"]
        )
    }


@router.get("/token/users")
def token_users(
    sort_by: str = Query("month_tokens"),
    order: str = Query("desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    search: str = Query(""),
    dep=Depends(manager_check),
):
    """全员 Token 消耗列表（分页、排序、搜索）— 管理员/经理可见；经理仅看本部门+本公司"""
    return get_user_token_list(
        sort_by=sort_by,
        order=order,
        limit=limit,
        offset=offset,
        search=search,
        manager_department=dep["department"],
        manager_company=dep["company"],
    )


@router.get("/usage/overview")
def leader_overview(dep=Depends(manager_check)):
    """部门概览全局汇总 — 管理员/经理可见；经理仅看本部门+本公司"""
    return get_leader_overview(
        manager_department=dep["department"], manager_company=dep["company"]
    )


@router.get("/usage/behavior")
def dept_behavior(days: int = Query(7, ge=1, le=90), dep=Depends(manager_check)):
    """部门行为统计 — 经理可见；包含活跃趋势、时段热力、页面分布、停留排行"""
    if not dep["department"]:
        raise HTTPException(400, "管理员请使用 /dashboard/behavior-stats 接口")
    return get_department_behavior_stats(
        department=dep["department"], company=dep["company"], days=days
    )


# ============================================================
# 个人使用看板接口（Task 4: 所有登录用户可见）
# ============================================================


@router.get("/my-usage/overview")
def my_usage_overview(request: Request):
    """当前用户 Token 消耗汇总（今日/本月/总计）"""
    username = getattr(request.state, "username", None)
    if not username or username == "anonymous":
        return {
            "today_tokens": 0,
            "month_tokens": 0,
            "total_tokens": 0,
            "total_calls": 0,
        }

    from backend.dashboard.dashboard_service import safe_one

    today = safe_one(
        "SELECT COALESCE(SUM(total_tokens),0) FROM llm_usage_log WHERE username=%s AND DATE(created_at)=CURDATE() AND success=1",
        username,
    )
    month = safe_one(
        "SELECT COALESCE(SUM(total_tokens),0) FROM llm_usage_log WHERE username=%s AND YEAR(created_at)=YEAR(CURDATE()) AND MONTH(created_at)=MONTH(CURDATE()) AND success=1",
        username,
    )
    total = safe_one(
        "SELECT COALESCE(SUM(total_tokens),0) FROM llm_usage_log WHERE username=%s AND success=1",
        username,
    )
    calls = safe_one(
        "SELECT COUNT(*) FROM llm_usage_log WHERE username=%s AND success=1",
        username,
    )
    today_calls = safe_one(
        "SELECT COUNT(*) FROM llm_usage_log WHERE username=%s AND DATE(created_at)=CURDATE()",
        username,
    )
    return {
        "today_tokens": today,
        "month_tokens": month,
        "total_tokens": total,
        "total_calls": calls,
        "today_calls": today_calls,
    }


@router.get("/my-usage/trend")
def my_usage_trend(request: Request, days: int = Query(7, ge=1, le=90)):
    """当前用户 Token 消耗趋势（按天）"""
    username = getattr(request.state, "username", None)
    if not username or username == "anonymous":
        return {"trend": []}

    rows = execute_query(
        """SELECT DATE(created_at)d, model_name, COALESCE(SUM(total_tokens),0)t
        FROM llm_usage_log WHERE username=%s AND success=1
        AND created_at>=DATE_SUB(CURDATE(),INTERVAL %s DAY)
        GROUP BY d, model_name ORDER BY d""",
        (username, days),
    )
    bucket: dict = {}
    for d, model, t in rows:
        ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
        bucket.setdefault(ds, {})[model or "unknown"] = int(t)
    result = []
    for ds in sorted(bucket):
        entry = {"date": ds, **bucket[ds]}
        entry["total"] = sum(bucket[ds].values())
        result.append(entry)
    return {"trend": result}


@router.get("/my-usage/behavior")
def my_usage_behavior(request: Request):
    """当前用户行为统计（功能使用分布 + 时段分布）"""
    username = getattr(request.state, "username", None)
    if not username or username == "anonymous":
        return {"page_distribution": [], "hour_distribution": {}}

    # 功能使用分布（近30天页面访问）
    page_rows = execute_query(
        """SELECT page_route, COUNT(*)c FROM user_page_view
        WHERE username=%s AND enter_time>=DATE_SUB(NOW(),INTERVAL 30 DAY)
        GROUP BY page_route ORDER BY c DESC""",
        (username,),
    )
    total_pv = sum(r[1] for r in page_rows) or 1
    page_dist = [
        {
            "route": r[0],
            "title": page_title(r[0]),
            "count": r[1],
            "percentage": round(r[1] / total_pv * 100, 1),
        }
        for r in page_rows[:10]
    ]

    # 时段分布（近30天）
    hour_rows = execute_query(
        """SELECT HOUR(enter_time)h, COUNT(*)c FROM user_page_view
        WHERE username=%s AND enter_time>=DATE_SUB(NOW(),INTERVAL 30 DAY)
        GROUP BY h ORDER BY h""",
        (username,),
    )
    hour_dist = {str(r[0]): r[1] for r in hour_rows}

    # 模型使用偏好（近30天，仅 chat 来源）
    model_rows = execute_query(
        """SELECT model_name, COALESCE(SUM(total_tokens),0)t FROM llm_usage_log
        WHERE username=%s AND success=1 AND call_source='chat'
        AND created_at>=DATE_SUB(NOW(),INTERVAL 30 DAY)
        GROUP BY model_name ORDER BY t DESC""",
        (username,),
    )
    model_total = sum(r[1] for r in model_rows) or 1
    model_prefs = [
        {
            "model": r[0] or "unknown",
            "tokens": int(r[1]),
            "percentage": round(int(r[1]) / model_total * 100, 1),
        }
        for r in model_rows
    ]

    return {
        "page_distribution": page_dist,
        "hour_distribution": hour_dist,
        "model_preferences": model_prefs,
    }
