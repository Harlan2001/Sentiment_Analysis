"""
看板数据模块 — 服务健康、基础统计、各子模块数据组装、缓存、用户画像
"""
from __future__ import annotations

import json
import time
import threading
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from backend.common.database import execute_query, execute_update
from backend.config.config import (
    DIR_MAP,
    NEWS_SOURCES,
    PERIOD_LIST,
    PERIOD_MAP,
    CACHE_TTL_SEC,
    BEHAVIOR_LOG_RETENTION_DAYS,
)
from backend.tools.dashboard import fmt_dt, fmt_dt2, pct, safe_one

cache_lock = threading.Lock()


# ============================================================
# 服务健康
# ============================================================
def check_service_health() -> Dict[str, Any]:
    """检测 MySQL 连通性和延迟"""
    try:
        t0 = time.time()
        execute_query("SELECT 1", one=True)
        mysql = {"ok": True, "latency_ms": round((time.time() - t0) * 1000, 1)}
    except Exception as e:
        mysql = {"ok": False, "error": str(e)}
    return {"mysql": mysql}


# ============================================================
# 基础统计（一次查询收集所有 COUNT）
# ============================================================
def get_base_stats() -> Dict[str, int]:
    """一次 SQL 查询收集所有基础 COUNT 指标"""
    row = execute_query("""
        SELECT (SELECT COUNT(*) FROM news),(SELECT COUNT(DISTINCT news_id) FROM analysis),
               (SELECT COUNT(*) FROM news n WHERE NOT EXISTS(SELECT 1 FROM analysis a WHERE a.news_id=n.id)),
               (SELECT COUNT(*) FROM factor),(SELECT COUNT(*) FROM news WHERE indexed=1),
               (SELECT COUNT(*) FROM news WHERE indexed=0 AND content IS NOT NULL AND content!=''),
               (SELECT COUNT(DISTINCT date) FROM yield_data),(SELECT COUNT(*) FROM forecast_report),
               (SELECT COUNT(*) FROM analysis WHERE direction IS NOT NULL AND direction!=''
                 AND horizon IS NOT NULL AND horizon!='' AND reason IS NOT NULL AND reason!=''),
               (SELECT COUNT(*) FROM analysis)
    """, one=True)
    if not row:
        return {}
    return dict(zip([
        "news_total", "analyzed", "pending", "factor_total", "indexed", "vec_pending",
        "yield_days", "report_total", "valid_analysis", "analysis_total",
    ], row))


# ============================================================
# 模块 A-F（接收 base+svc 复用）
# ============================================================
def build_news_module(total: int, _b: Dict[str, int]) -> Dict[str, Any]:
    """新闻模块：总量、7天趋势、来源分布、各来源最新采集时间"""
    t = execute_query(
        "SELECT DATE(pub_time)d,source,COUNT(*)c FROM news "
        "WHERE pub_time>=DATE_SUB(NOW(),INTERVAL 7 DAY) GROUP BY d,source ORDER BY d"
    )
    s = execute_query("SELECT source,COUNT(*)c FROM news GROUP BY source ORDER BY c DESC")
    lt = []
    for k, n in NEWS_SOURCES.items():
        r = execute_query("SELECT MAX(pub_time) FROM news WHERE source=%s", (k,), one=True)
        v = r[0] if r and r[0] else None
        st = "ok"
        if v is None:
            st = "red"
        elif (datetime.now() - v).total_seconds() / 3600 > 24:
            st = "yellow"
        lt.append({"source": k, "name": n, "latest_time": fmt_dt2(v), "status": st})

    from backend.tools.dashboard import assemble_trend
    return {
        "total": total,
        "trend_7d": assemble_trend(t, NEWS_SOURCES),
        "source_distribution": [
            {"source": x, "name": NEWS_SOURCES.get(x, x), "count": c, "percentage": pct(c, total)}
            for x, c in s
        ],
        "latest_per_source": lt,
    }


def build_analysis_module(analyzed: int, pending: int, news_total: int, _b: Dict[str, int]) -> Dict[str, Any]:
    """AI分析模块：覆盖率、模型分布、涨跌趋势、时效性"""
    m = execute_query("SELECT model,COUNT(*)c FROM analysis GROUP BY model ORDER BY c DESC")
    d = execute_query("""
        SELECT DATE(n.pub_time)d,COALESCE(a.direction,'中性')dir,COUNT(*)c
        FROM analysis a JOIN news n ON n.id=a.news_id
        WHERE n.pub_time>=DATE_SUB(NOW(),INTERVAL 7 DAY) GROUP BY d,dir ORDER BY d
    """)
    r = execute_query("""
        SELECT (SELECT MAX(n.pub_time) FROM news n JOIN analysis a ON a.news_id=n.id)la,
        (SELECT MAX(pub_time) FROM news)lp
    """, one=True)
    lag = round((r[1] - r[0]).total_seconds() / 3600, 1) if r and r[0] and r[1] else None

    if news_total > 0:
        raw_rate = analyzed / news_total * 100
        if pending > 0 and raw_rate >= 99.9:
            coverage_pct = 99.99
        else:
            coverage_pct = round(raw_rate, 2)
    else:
        coverage_pct = 0

    from backend.tools.dashboard import assemble_trend
    return {
        "analyzed": analyzed,
        "pending": pending,
        "coverage_pct": coverage_pct,
        "model_distribution": [
            {"model": x or "unknown", "count": c, "percentage": pct(c, max(analyzed, 1))}
            for x, c in m
        ],
        "direction_7d": assemble_trend([(dt, DIR_MAP.get(dr, dr), cnt) for dt, dr, cnt in d]),
        "valid_analysis_pct": pct(_b["valid_analysis"], _b["analysis_total"]),
        "timeliness_diff_hours": lag,
    }


def build_factor_module(total: int, _b: Dict[str, int]) -> Dict[str, Any]:
    """因子模块：分类、类型分布、7天新增、新闻关联覆盖率"""
    r = execute_query("SELECT category,factor_type,COUNT(*)c FROM factor GROUP BY category,factor_type")
    cat: Dict[str, int] = {}
    typ: Dict[str, int] = {}
    for cat_n, typ_n, cnt in r:
        cat[cat_n] = cat.get(cat_n, 0) + cnt
        typ[typ_n or "unknown"] = typ.get(typ_n or "unknown", 0) + cnt

    n7 = safe_one("SELECT COUNT(*) FROM factor_discovery_history WHERE created_at>=DATE_SUB(NOW(),INTERVAL 7 DAY)")
    tr = execute_query(
        "SELECT DATE(created_at)d,COUNT(*)c FROM factor_discovery_history "
        "WHERE created_at>=DATE_SUB(NOW(),INTERVAL 7 DAY) GROUP BY d ORDER BY d"
    )
    tr_map = {fmt_dt(d): c for d, c in tr}
    today = date.today()
    tr = [(today - timedelta(days=i), tr_map.get((today - timedelta(days=i)).isoformat(), 0)) for i in range(6, -1, -1)]

    row = execute_query("""
        SELECT (SELECT COUNT(DISTINCT nf.news_id) FROM news_factor nf JOIN analysis a ON nf.news_id=a.news_id),
        (SELECT COUNT(DISTINCT news_id) FROM analysis)
    """, one=True)
    assoc = pct(row[0], row[1]) if row and row[1] > 0 else 0
    r2 = execute_query("SELECT MAX(created_at) FROM news_factor", one=True)
    lm = round((datetime.now() - r2[0]).total_seconds() / 60, 1) if r2 and r2[0] else None

    return {
        "total": total,
        "category_distribution": [{"category": k, "count": v} for k, v in sorted(cat.items(), key=lambda x: -x[1])],
        "type_distribution": [{"factor_type": k, "count": v} for k, v in typ.items()],
        "new_factors_7d": n7,
        "new_factors_trend_7d": [{"date": fmt_dt(d), "count": c} for d, c in tr],
        "association_coverage_pct": assoc,
        "update_timeliness_diff_minutes": lm,
    }


def build_vector_module(indexed: int, pending: int) -> Dict[str, Any]:
    """向量模块：已入库/待入库/覆盖率"""
    t = indexed + pending
    if t > 0:
        raw_rate = indexed / t * 100
        if pending > 0 and raw_rate >= 99.9:
            coverage_pct = 99.99
        else:
            coverage_pct = round(raw_rate, 2)
    else:
        coverage_pct = 0
    return {"indexed_count": indexed, "pending_count": pending, "coverage_pct": coverage_pct}


def build_yield_module() -> Dict[str, Any]:
    """债券收益率模块：数据时间区间、各期限完整度、各期限近7天走势"""
    r = execute_query("SELECT MIN(date),MAX(date),COUNT(DISTINCT date) FROM yield_data", one=True)
    p = execute_query("SELECT period,COUNT(*)c FROM yield_data GROUP BY period ORDER BY period")
    sp = []
    for dbp in PERIOD_LIST:
        v = execute_query(
            "SELECT date,value FROM yield_data WHERE period=%s ORDER BY date DESC LIMIT 7", (dbp,)
        )
        ld = v[-1][0] if v else None
        lv = float(v[-1][1]) if v else None
        sp.append({
            "period": dbp,
            "display_name": PERIOD_MAP.get(dbp, dbp),
            "latest_date": fmt_dt(ld),
            "latest_value": lv,
            "sparkline": [float(x) for _, x in reversed(v)],
        })
    return {
        "date_min": fmt_dt(r[0]) if r and r[0] else None,
        "date_max": fmt_dt(r[1]) if r and r[1] else None,
        "coverage_days": r[2] if r else 0,
        "period_completeness": [
            {"period": x, "display_name": PERIOD_MAP.get(x, x), "count": c} for x, c in p
        ],
        "latest_yields": sp,
    }


def build_forecast_module(report_total: int) -> Dict[str, Any]:
    """预测模块：报告总数、最新日期、30天覆盖情况"""
    r = execute_query("SELECT MAX(trade_date) FROM forecast_report", one=True)
    cal = execute_query(
        "SELECT DISTINCT trade_date FROM forecast_report "
        "WHERE trade_date>=DATE_SUB(CURDATE(),INTERVAL 30 DAY) ORDER BY trade_date"
    )
    covered = {fmt_dt(x[0]) for x in cal}
    today = date.today()
    return {
        "total_reports": report_total,
        "latest_date": fmt_dt(r[0]) if r and r[0] else None,
        "coverage_30d": [
            {
                "date": (today - timedelta(days=29 - i)).isoformat(),
                "has_report": (today - timedelta(days=29 - i)).isoformat() in covered,
            }
            for i in range(30)
        ],
    }


# ============================================================
# 缓存（加锁防穿透）
# ============================================================
def read_cache() -> Optional[Dict[str, Any]]:
    """读取缓存：查询 CACHE_TTL_SEC 秒内生成的指标快照"""
    row = execute_query(
        "SELECT core_metrics FROM dashboard_metric_cache "
        "WHERE calc_time>=DATE_SUB(NOW(),INTERVAL %s SECOND) ORDER BY calc_time DESC LIMIT 1",
        (CACHE_TTL_SEC,), one=True,
    )
    if row and row[0]:
        return json.loads(row[0]) if isinstance(row[0], str) else row[0]
    return None


def write_cache(data: Dict[str, Any]) -> None:
    """写入缓存：将全量指标 JSON 存入缓存表"""
    execute_update(
        "INSERT INTO dashboard_metric_cache (calc_time,core_metrics,service_status) VALUES (NOW(),%s,'{}')",
        (json.dumps(data, default=str),),
    )


def cleanup_cache() -> None:
    """缓存清理：删除1天前的旧缓存"""
    execute_update("DELETE FROM dashboard_metric_cache WHERE calc_time<DATE_SUB(NOW(),INTERVAL 1 DAY)")


# ============================================================
# 行为日志清理（保留180天）
# ============================================================
def cleanup_old_behavior_logs(retention_days: Optional[int] = None) -> int:
    """清理超过保留期的行为日志，返回删除条数"""
    if retention_days is None:
        retention_days = BEHAVIOR_LOG_RETENTION_DAYS
    from backend.common.database import get_db_connection
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_page_view WHERE enter_time < DATE_SUB(NOW(), INTERVAL %s DAY)",
                (retention_days,),
            )
            deleted = cur.rowcount
        conn.commit()
    return deleted


# ============================================================
# 用户画像
# ============================================================
def compute_user_profile(user_id: int, username: str) -> Dict[str, Any]:
    """计算单个用户画像并 UPSERT 到 user_behavior_profile"""
    now = datetime.now()
    d30 = now - timedelta(days=30)

    total_sessions = safe_one("SELECT COUNT(*) FROM user_session WHERE user_id=%s", user_id)
    total_page_views = safe_one("SELECT COUNT(*) FROM user_page_view WHERE user_id=%s", user_id)
    total_active_sec = int(safe_one(
        "SELECT COALESCE(SUM(duration_sec),0) FROM user_page_view WHERE user_id=%s AND duration_sec>0", user_id
    ))
    fv_row = execute_query("SELECT MIN(DATE(enter_time)) FROM user_page_view WHERE user_id=%s", (user_id,), one=True)
    first_visit = fmt_dt(fv_row[0]) if fv_row and fv_row[0] else None
    lv_row = execute_query("SELECT MAX(enter_time) FROM user_page_view WHERE user_id=%s", (user_id,), one=True)
    last_visit = lv_row[0] if lv_row else None
    active_days_30d = safe_one(
        "SELECT COUNT(DISTINCT DATE(enter_time)) FROM user_page_view WHERE user_id=%s AND enter_time>=%s",
        user_id, d30,
    )
    avg_session_sec = int(safe_one(
        "SELECT COALESCE(AVG(duration_sec),0) FROM user_session WHERE user_id=%s AND duration_sec>0", user_id
    ))
    avg_daily_pages = round(active_days_30d and total_page_views / active_days_30d or 0, 2)

    # 页面偏好
    page_rows = execute_query(
        "SELECT page_route,COUNT(*)c FROM user_page_view "
        "WHERE user_id=%s AND enter_time>=%s GROUP BY page_route ORDER BY c DESC",
        (user_id, d30),
    )
    total_pv = sum(r[1] for r in page_rows) if page_rows else 0
    page_affinity = {r[0]: round(r[1] / total_pv, 3) if total_pv > 0 else 0 for r in page_rows}
    pred_pct = page_affinity.get("/prediction", 0)
    strat_pct = page_affinity.get("/strategies", 0) + page_affinity.get("/change", 0)
    is_report_focused = pred_pct > 0.5
    is_strategy_focused = strat_pct > 0.5

    # 时段偏好
    hour_rows = execute_query(
        "SELECT HOUR(enter_time)h,COUNT(*)c FROM user_page_view "
        "WHERE user_id=%s AND enter_time>=%s GROUP BY h ORDER BY c DESC",
        (user_id, d30),
    )
    hour_dist = {str(r[0]): r[1] for r in hour_rows}
    peak_hour = hour_rows[0][0] if hour_rows else None

    # 功能覆盖
    distinct_pages = safe_one(
        "SELECT COUNT(DISTINCT page_route) FROM user_page_view WHERE user_id=%s AND enter_time>=%s",
        user_id, d30,
    )
    advanced_pages = ["/agents", "/select-strategy"]
    adv_count = safe_one(
        "SELECT COUNT(*) FROM user_page_view WHERE user_id=%s AND page_route IN (%s,%s)",
        user_id, advanced_pages[0], advanced_pages[1],
    )
    advanced_feature_used = adv_count > 0

    # 行为特征
    is_power_user = active_days_30d > 20 and (total_active_sec / (max(active_days_30d, 1) * 60) > 30)
    last_active_row = execute_query(
        "SELECT MAX(DATE(enter_time)) FROM user_page_view WHERE user_id=%s", (user_id,), one=True,
    )
    last_active_date = last_active_row[0] if last_active_row else None
    if last_active_date:
        if hasattr(last_active_date, 'date'):
            days_since = (now.date() - last_active_date.date()).days
        elif isinstance(last_active_date, date):
            days_since = (now.date() - last_active_date).days
        else:
            days_since = 0
        churn_risk = round(min(days_since / 30.0, 1.0), 2)
    else:
        churn_risk = 1.0

    # UPSERT
    execute_update("""INSERT INTO user_behavior_profile
        (user_id,username,total_sessions,total_page_views,total_active_sec,
         first_visit,last_visit,active_days_30d,avg_session_sec,avg_daily_pages_30d,
         page_affinity_json,peak_hour,hour_distribution_json,
         distinct_pages_30d,advanced_feature_used,
         is_power_user,is_report_focused,is_strategy_focused,churn_risk_score,
         computed_at,profile_version)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),'v1.0')
        ON DUPLICATE KEY UPDATE
         username=VALUES(username),total_sessions=VALUES(total_sessions),
         total_page_views=VALUES(total_page_views),total_active_sec=VALUES(total_active_sec),
         first_visit=VALUES(first_visit),last_visit=VALUES(last_visit),
         active_days_30d=VALUES(active_days_30d),avg_session_sec=VALUES(avg_session_sec),
         avg_daily_pages_30d=VALUES(avg_daily_pages_30d),
         page_affinity_json=VALUES(page_affinity_json),peak_hour=VALUES(peak_hour),
         hour_distribution_json=VALUES(hour_distribution_json),
         distinct_pages_30d=VALUES(distinct_pages_30d),
         advanced_feature_used=VALUES(advanced_feature_used),
         is_power_user=VALUES(is_power_user),is_report_focused=VALUES(is_report_focused),
         is_strategy_focused=VALUES(is_strategy_focused),
         churn_risk_score=VALUES(churn_risk_score),computed_at=NOW()""",
        (user_id, username, total_sessions, total_page_views, total_active_sec,
         first_visit, last_visit, active_days_30d, avg_session_sec, avg_daily_pages,
         json.dumps(page_affinity, ensure_ascii=False), peak_hour,
         json.dumps(hour_dist, ensure_ascii=False),
         distinct_pages, advanced_feature_used,
         is_power_user, is_report_focused, is_strategy_focused, churn_risk))
    return {"user_id": user_id, "username": username, "computed": True}


def profile_row_to_dict(row: tuple) -> Dict[str, Any]:
    """将 user_behavior_profile 查询行转为字典"""
    return {
        "id": row[0], "user_id": row[1], "username": row[2],
        "total_sessions": row[3], "total_page_views": row[4], "total_active_sec": row[5],
        "first_visit": fmt_dt(row[6]) if row[6] else None,
        "last_visit": row[7].isoformat() if row[7] and hasattr(row[7], 'isoformat') else str(row[7]) if row[7] else None,
        "active_days_30d": row[8], "avg_session_sec": row[9],
        "avg_daily_pages_30d": float(row[10]) if row[10] else 0,
        "page_affinity": json.loads(row[11]) if isinstance(row[11], str) else row[11] if row[11] else {},
        "peak_hour": row[12],
        "hour_distribution": json.loads(row[13]) if isinstance(row[13], str) else row[13] if row[13] else {},
        "distinct_pages_30d": row[14], "advanced_feature_used": bool(row[15]),
        "is_power_user": bool(row[16]), "is_report_focused": bool(row[17]), "is_strategy_focused": bool(row[18]),
        "churn_risk_score": float(row[19]) if row[19] else 0,
        "computed_at": row[20].isoformat() if row[20] and hasattr(row[20], 'isoformat') else (str(row[20]) if row[20] else None),
        "profile_version": row[21],
        "updated_at": row[22].isoformat() if row[22] and hasattr(row[22], 'isoformat') else None,
    }


def peak_slot_label(h: Optional[int]) -> str:
    """将小时数转为时段标签"""
    if h is None:
        return "未知"
    h = int(h)
    if 6 <= h < 12:
        return "上午"
    if 12 <= h < 14:
        return "午间"
    if 14 <= h < 18:
        return "下午"
    if 18 <= h < 22:
        return "晚间"
    return "深夜"
