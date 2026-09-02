"""
看板数据模块 — 服务健康、基础统计、各子模块数据组装、缓存、用户画像
"""

from __future__ import annotations

import json
import threading
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from backend.common.database import execute_query, execute_update, get_db_connection
from backend.config.config import (
    BEHAVIOR_LOG_RETENTION_DAYS,
    CACHE_TTL_SEC,
    DIR_MAP,
    FACTOR_CATEGORY_MAP,
    NEWS_SOURCE_LABELS,
    PERIOD_LIST,
    PERIOD_REVERSE_MAP,
)
from backend.dashboard.helpers import (
    assemble_trend,
    fmt_dt,
    fmt_dt2,
    normalize_route,
    pad_page_routes,
    page_title,
    pct,
    safe_one,
    to_iso,
)
from backend.repositories.forecast_report_repository import ForecastReportRepository

cache_lock = threading.Lock()


def _dept_scope(
    department: str, company: str, base_alias: str = "l"
) -> tuple:
    """构建「部门+公司」作用域：JOIN users + 条件 + 参数，供各统计函数复用。

    base_alias 为当前查询的主表别名（默认 l=llm_usage_log）；
    主表已是 users u 时传 "u"，此时跳过 join（由各 SQL 自行声明）。
    返回 (join, conds, params)；无部门时返回 ("", [], [])。
    """
    conds: List[str] = []
    params: List[Any] = []
    join = ""
    if department:
        if base_alias != "u":
            join = f"JOIN users u ON u.id={base_alias}.user_id"
        conds.append("u.department = %s")
        params.append(department)
        if company:
            conds.append("u.company = %s")
            params.append(company)
    return join, conds, params


def _coverage_pct(counted: int, total: int, pending: int) -> float:
    """覆盖率百分比：分母为 0 返回 0；存在待处理项且已超 99.9 时封顶 99.99。"""
    if total <= 0:
        return 0
    raw = counted / total * 100
    if pending > 0 and raw >= 99.9:
        return 99.99
    return round(raw, 2)


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
    row = execute_query(
        """
        SELECT (SELECT COUNT(*) FROM news),(SELECT COUNT(DISTINCT news_id) FROM analysis),
               (SELECT COUNT(*) FROM news n WHERE NOT EXISTS(SELECT 1 FROM analysis a WHERE a.news_id=n.id)),
               (SELECT COUNT(*) FROM factor),(SELECT COUNT(*) FROM news WHERE indexed=1),
               (SELECT COUNT(*) FROM news WHERE indexed=0 AND content IS NOT NULL AND content!=''),
               (SELECT COUNT(DISTINCT date) FROM yield_data),(SELECT COUNT(*) FROM forecast_report),
               (SELECT COUNT(*) FROM analysis WHERE direction IS NOT NULL AND direction!=''
                 AND horizon IS NOT NULL AND horizon!='' AND reason IS NOT NULL AND reason!=''),
               (SELECT COUNT(*) FROM analysis),
               (SELECT COUNT(*) FROM research_report),
               (SELECT COUNT(*) FROM research_report WHERE status='analyzed'),
               (SELECT COUNT(*) FROM research_report WHERE ai_market_view='bullish'),
               (SELECT COUNT(*) FROM research_report WHERE ai_market_view='bearish'),
               (SELECT COUNT(*) FROM research_report WHERE ai_market_view='neutral')
    """,
        one=True,
    )
    if not row:
        return {}
    return dict(
        zip(
            [
                "news_total",
                "analyzed",
                "pending",
                "factor_total",
                "indexed",
                "vec_pending",
                "yield_days",
                "report_total",
                "valid_analysis",
                "analysis_total",
                "research_total",
                "research_analyzed",
                "research_bullish",
                "research_bearish",
                "research_neutral",
            ],
            row,
        )
    )


# ============================================================
# 模块 A-F（接收 base+svc 复用）
# ============================================================
def build_news_module(total: int) -> Dict[str, Any]:
    """新闻模块：总量、7天趋势、来源分布、各来源最新采集时间"""
    t = execute_query(
        "SELECT DATE(pub_time)d,source,COUNT(*)c FROM news "
        "WHERE pub_time>=DATE_SUB(NOW(),INTERVAL 7 DAY) GROUP BY d,source ORDER BY d"
    )
    # 一次查询同时获取来源分布 + 最新采集时间
    s = execute_query(
        "SELECT source,COUNT(*)c,MAX(pub_time) FROM news GROUP BY source ORDER BY c DESC"
    )
    lt = []
    for source, cnt, max_pub in s:
        name = NEWS_SOURCE_LABELS.get(source, source)
        v = max_pub
        st = "ok"
        if v is None:
            st = "red"
        elif (datetime.now() - v).total_seconds() / 3600 > 24:
            st = "yellow"
        lt.append(
            {"source": source, "name": name, "latest_time": fmt_dt2(v), "status": st}
        )

    return {
        "total": total,
        "trend_7d": assemble_trend(t, NEWS_SOURCE_LABELS),
        "source_distribution": [
            {
                "source": x,
                "name": NEWS_SOURCE_LABELS.get(x, x),
                "count": c,
                "percentage": pct(c, total),
            }
            for x, c, _ in s
        ],
        "latest_per_source": lt,
    }


def build_analysis_module(
    analyzed: int, pending: int, news_total: int, base: Dict[str, int]
) -> Dict[str, Any]:
    """AI分析模块：覆盖率、模型分布、涨跌趋势、时效性"""
    m = execute_query(
        "SELECT model,COUNT(*)c FROM analysis GROUP BY model ORDER BY c DESC"
    )
    d = execute_query("""
        SELECT DATE(n.pub_time)d,COALESCE(a.direction,'中性')dir,COUNT(*)c
        FROM analysis a JOIN news n ON n.id=a.news_id
        WHERE n.pub_time>=DATE_SUB(NOW(),INTERVAL 7 DAY) GROUP BY d,dir ORDER BY d
    """)
    r = execute_query(
        """
        SELECT (SELECT MAX(n.pub_time) FROM news n JOIN analysis a ON a.news_id=n.id)la,
        (SELECT MAX(pub_time) FROM news)lp
    """,
        one=True,
    )
    lag = (
        round((r[1] - r[0]).total_seconds() / 3600, 1) if r and r[0] and r[1] else None
    )

    coverage_pct = _coverage_pct(analyzed, news_total, pending)

    return {
        "analyzed": analyzed,
        "pending": pending,
        "coverage_pct": coverage_pct,
        "model_distribution": [
            {
                "model": x or "unknown",
                "count": c,
                "percentage": pct(c, max(analyzed, 1)),
            }
            for x, c in m
        ],
        "direction_7d": assemble_trend(
            [(dt, DIR_MAP.get(dr, dr), cnt) for dt, dr, cnt in d]
        ),
        "valid_analysis_pct": pct(base["valid_analysis"], base["analysis_total"]),
        "timeliness_diff_hours": lag,
    }


def build_factor_module(total: int) -> Dict[str, Any]:
    """因子模块：分类、类型分布、7天新增、新闻关联覆盖率"""
    r = execute_query(
        "SELECT category,factor_type,COUNT(*)c FROM factor GROUP BY category,factor_type"
    )
    cat: Dict[str, int] = {}
    typ: Dict[str, int] = {}
    for cat_n, typ_n, cnt in r:
        cat[cat_n] = cat.get(cat_n, 0) + cnt
        typ[typ_n or "unknown"] = typ.get(typ_n or "unknown", 0) + cnt

    n7 = safe_one(
        "SELECT COUNT(*) FROM factor_discovery_history WHERE created_at>=DATE_SUB(NOW(),INTERVAL 7 DAY)"
    )
    tr = execute_query(
        "SELECT DATE(created_at)d,COUNT(*)c FROM factor_discovery_history "
        "WHERE created_at>=DATE_SUB(NOW(),INTERVAL 7 DAY) GROUP BY d ORDER BY d"
    )
    tr_map = {fmt_dt(d): c for d, c in tr}
    today = date.today()
    tr = [
        (
            today - timedelta(days=i),
            tr_map.get((today - timedelta(days=i)).isoformat(), 0),
        )
        for i in range(6, -1, -1)
    ]

    row = execute_query(
        """
        SELECT (SELECT COUNT(DISTINCT nf.news_id) FROM news_factor nf JOIN analysis a ON nf.news_id=a.news_id),
        (SELECT COUNT(DISTINCT news_id) FROM analysis)
    """,
        one=True,
    )
    assoc = pct(row[0], row[1]) if row and row[1] > 0 else 0
    r2 = execute_query("SELECT MAX(created_at) FROM news_factor", one=True)
    lm = (
        round((datetime.now() - r2[0]).total_seconds() / 60, 1)
        if r2 and r2[0]
        else None
    )

    return {
        "total": total,
        "category_distribution": [
            {"category": k, "display_name": FACTOR_CATEGORY_MAP.get(k, k), "count": v}
            for k, v in sorted(cat.items(), key=lambda x: -x[1])
        ],
        "type_distribution": [{"factor_type": k, "count": v} for k, v in typ.items()],
        "new_factors_7d": n7,
        "new_factors_trend_7d": [{"date": fmt_dt(d), "count": c} for d, c in tr],
        "association_coverage_pct": assoc,
        "update_timeliness_diff_minutes": lm,
    }


def build_vector_module(indexed: int, pending: int) -> Dict[str, Any]:
    """向量模块：已入库/待入库/覆盖率"""
    t = indexed + pending
    coverage_pct = _coverage_pct(indexed, t, pending)
    return {
        "indexed_count": indexed,
        "pending_count": pending,
        "coverage_pct": coverage_pct,
    }


def build_yield_module() -> Dict[str, Any]:
    """债券收益率模块：数据时间区间、各期限完整度、各期限近7天走势"""
    r = execute_query(
        "SELECT MIN(date),MAX(date),COUNT(DISTINCT date) FROM yield_data", one=True
    )
    p = execute_query(
        "SELECT period,COUNT(*)c FROM yield_data GROUP BY period ORDER BY period"
    )
    sp = []
    for dbp in PERIOD_LIST:
        v = execute_query(
            "SELECT date,value FROM yield_data WHERE period=%s ORDER BY date DESC LIMIT 7",
            (dbp,),
        )
        ld = v[0][0] if v else None
        lv = float(v[0][1]) if v else None
        sp.append(
            {
                "period": dbp,
                "display_name": PERIOD_REVERSE_MAP.get(dbp, dbp),
                "latest_date": fmt_dt(ld),
                "latest_value": lv,
                "sparkline": [float(x) for _, x in reversed(v)],
            }
        )
    return {
        "date_min": fmt_dt(r[0]) if r and r[0] else None,
        "date_max": fmt_dt(r[1]) if r and r[1] else None,
        "coverage_days": r[2] if r else 0,
        "period_completeness": [
            {"period": x, "display_name": PERIOD_REVERSE_MAP.get(x, x), "count": c}
            for x, c in p
        ],
        "latest_yields": sp,
    }


def build_forecast_module(report_total: int) -> Dict[str, Any]:
    """预测模块：报告总数、最新日期、30天覆盖情况"""
    latest_date = ForecastReportRepository().get_latest_trade_date()
    cal = execute_query(
        "SELECT DISTINCT trade_date FROM forecast_report "
        "WHERE trade_date>=DATE_SUB(CURDATE(),INTERVAL 30 DAY) ORDER BY trade_date"
    )
    covered = {fmt_dt(x[0]) for x in cal}
    today = date.today()
    dates = [today - timedelta(days=29 - i) for i in range(30)]
    return {
        "total_reports": report_total,
        "latest_date": fmt_dt(latest_date) if latest_date else None,
        "coverage_30d": [
            {"date": d.isoformat(), "has_report": d.isoformat() in covered}
            for d in dates
        ],
    }


def build_research_module(base: Dict[str, int]) -> Dict[str, Any]:
    """研报模块：总数、分析数、观点分布"""
    return {
        "total": base.get("research_total", 0),
        "analyzed": base.get("research_analyzed", 0),
        "bullish": base.get("research_bullish", 0),
        "bearish": base.get("research_bearish", 0),
        "neutral": base.get("research_neutral", 0),
    }


# ============================================================
# 缓存（加锁防穿透）
# ============================================================
_cache_table_ready = False
_cache_table_lock = threading.Lock()

_CACHE_TABLE_DDL = """CREATE TABLE IF NOT EXISTS `dashboard_metric_cache` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `calc_time` datetime NOT NULL,
  `cache_type` varchar(50) NOT NULL DEFAULT 'core',
  `metrics_json` longtext,
  `service_status` longtext,
  PRIMARY KEY (`id`),
  KEY `idx_cache_hit` (`cache_type`, `calc_time` DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""


def _ensure_cache_table() -> None:
    global _cache_table_ready
    if _cache_table_ready:
        return
    with _cache_table_lock:
        if _cache_table_ready:
            return
        try:
            execute_update(_CACHE_TABLE_DDL)
        except Exception:
            pass
        _cache_table_ready = True


def read_cache(cache_type: str = "core") -> Optional[Dict[str, Any]]:
    """读取缓存：查询 CACHE_TTL_SEC 秒内生成的指标快照"""
    _ensure_cache_table()
    row = execute_query(
        "SELECT metrics_json FROM dashboard_metric_cache "
        "WHERE cache_type=%s AND calc_time>=DATE_SUB(NOW(),INTERVAL %s SECOND) ORDER BY calc_time DESC LIMIT 1",
        (cache_type, CACHE_TTL_SEC),
        one=True,
    )
    if row and row[0]:
        return json.loads(row[0]) if isinstance(row[0], str) else row[0]
    return None


def write_cache(data: Dict[str, Any], cache_type: str = "core") -> None:
    """写入缓存：将指标 JSON 存入缓存表"""
    _ensure_cache_table()
    execute_update(
        "INSERT INTO dashboard_metric_cache (calc_time, cache_type, metrics_json, service_status) VALUES (NOW(),%s,%s,'{}')",
        (cache_type, json.dumps(data, default=str)),
    )


def cleanup_cache() -> None:
    """缓存清理：删除1天前的旧缓存"""
    execute_update(
        "DELETE FROM dashboard_metric_cache WHERE calc_time<DATE_SUB(NOW(),INTERVAL 1 DAY)"
    )


# ============================================================
# 行为日志清理（保留180天）
# ============================================================
def cleanup_old_behavior_logs(retention_days: Optional[int] = None) -> int:
    """清理超过保留期的行为日志，返回删除条数"""
    if retention_days is None:
        retention_days = BEHAVIOR_LOG_RETENTION_DAYS

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

    total_sessions = safe_one(
        "SELECT COUNT(*) FROM user_session WHERE user_id=%s", user_id
    )
    total_page_views = safe_one(
        "SELECT COUNT(*) FROM user_page_view WHERE user_id=%s", user_id
    )
    total_active_sec = int(
        safe_one(
            "SELECT COALESCE(SUM(duration_sec),0) FROM user_page_view WHERE user_id=%s AND duration_sec>0",
            user_id,
        )
    )
    fv_row = execute_query(
        "SELECT MIN(DATE(enter_time)) FROM user_page_view WHERE user_id=%s",
        (user_id,),
        one=True,
    )
    first_visit = fmt_dt(fv_row[0]) if fv_row and fv_row[0] else None
    lv_row = execute_query(
        "SELECT MAX(enter_time) FROM user_page_view WHERE user_id=%s",
        (user_id,),
        one=True,
    )
    last_visit = lv_row[0] if lv_row else None
    active_days_30d = safe_one(
        "SELECT COUNT(DISTINCT DATE(enter_time)) FROM user_page_view WHERE user_id=%s AND enter_time>=%s",
        user_id,
        d30,
    )
    avg_session_sec = int(
        safe_one(
            "SELECT COALESCE(AVG(duration_sec),0) FROM user_session WHERE user_id=%s AND duration_sec>0",
            user_id,
        )
    )
    pv_30d = safe_one(
        "SELECT COUNT(*) FROM user_page_view WHERE user_id=%s AND enter_time>=%s",
        user_id,
        d30,
    )
    avg_daily_pages = round(active_days_30d and pv_30d / active_days_30d or 0, 2)

    # 页面偏好
    page_rows = execute_query(
        "SELECT page_route,COUNT(*)c FROM user_page_view "
        "WHERE user_id=%s AND enter_time>=%s GROUP BY page_route ORDER BY c DESC",
        (user_id, d30),
    )
    total_pv = sum(r[1] for r in page_rows) if page_rows else 0
    page_affinity = {
        r[0]: round(r[1] / total_pv, 3) if total_pv > 0 else 0 for r in page_rows
    }
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
        user_id,
        d30,
    )
    advanced_pages = ["/agents", "/select-strategy"]
    adv_count = safe_one(
        "SELECT COUNT(*) FROM user_page_view WHERE user_id=%s AND page_route IN (%s,%s)",
        user_id,
        advanced_pages[0],
        advanced_pages[1],
    )
    advanced_feature_used = adv_count > 0

    # 行为特征
    active_sec_30d = int(
        safe_one(
            "SELECT COALESCE(SUM(duration_sec),0) FROM user_page_view"
            " WHERE user_id=%s AND duration_sec>0 AND enter_time>=%s",
            user_id,
            d30,
        )
    )
    is_power_user = active_days_30d > 20 and (
        active_sec_30d / (max(active_days_30d, 1) * 60) > 30
    )
    last_active_row = execute_query(
        "SELECT MAX(DATE(enter_time)) FROM user_page_view WHERE user_id=%s",
        (user_id,),
        one=True,
    )
    last_active_date = last_active_row[0] if last_active_row else None
    if last_active_date:
        if hasattr(last_active_date, "date"):
            days_since = (now.date() - last_active_date.date()).days
        elif isinstance(last_active_date, date):
            days_since = (now.date() - last_active_date).days
        else:
            days_since = 0
        churn_risk = round(min(days_since / 30.0, 1.0), 2)
    else:
        churn_risk = 1.0

    # UPSERT
    execute_update(
        """INSERT INTO user_behavior_profile
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
        (
            user_id,
            username,
            total_sessions,
            total_page_views,
            total_active_sec,
            first_visit,
            last_visit,
            active_days_30d,
            avg_session_sec,
            avg_daily_pages,
            json.dumps(page_affinity, ensure_ascii=False),
            peak_hour,
            json.dumps(hour_dist, ensure_ascii=False),
            distinct_pages,
            advanced_feature_used,
            is_power_user,
            is_report_focused,
            is_strategy_focused,
            churn_risk,
        ),
    )
    return {"user_id": user_id, "username": username, "computed": True}


def profile_row_to_dict(row: tuple) -> Dict[str, Any]:
    """将 user_behavior_profile 查询行转为字典"""
    return {
        "id": row[0],
        "user_id": row[1],
        "username": row[2],
        "total_sessions": row[3],
        "total_page_views": row[4],
        "total_active_sec": row[5],
        "first_visit": fmt_dt(row[6]) if row[6] else None,
        "last_visit": to_iso(row[7]),
        "active_days_30d": row[8],
        "avg_session_sec": row[9],
        "avg_daily_pages_30d": float(row[10]) if row[10] else 0,
        "page_affinity": (
            json.loads(row[11])
            if isinstance(row[11], str)
            else row[11] if row[11] else {}
        ),
        "peak_hour": row[12],
        "hour_distribution": (
            json.loads(row[13])
            if isinstance(row[13], str)
            else row[13] if row[13] else {}
        ),
        "distinct_pages_30d": row[14],
        "advanced_feature_used": bool(row[15]),
        "is_power_user": bool(row[16]),
        "is_report_focused": bool(row[17]),
        "is_strategy_focused": bool(row[18]),
        "churn_risk_score": float(row[19]) if row[19] else 0,
        "computed_at": to_iso(row[20]),
        "profile_version": row[21],
        "updated_at": to_iso(row[22]),
    }


# user_behavior_profile 查询列（画像接口三处复用，避免重复拼写）
_PROFILE_SELECT = """SELECT id,user_id,username,total_sessions,total_page_views,total_active_sec,
first_visit,last_visit,active_days_30d,avg_session_sec,avg_daily_pages_30d,
page_affinity_json,peak_hour,hour_distribution_json,
distinct_pages_30d,advanced_feature_used,
is_power_user,is_report_focused,is_strategy_focused,churn_risk_score,
computed_at,profile_version,updated_at FROM user_behavior_profile"""


def fetch_user_profile(user_id: int) -> Optional[tuple]:
    """按 user_id 查询单条用户行为画像；不存在返回 None"""
    return execute_query(f"{_PROFILE_SELECT} WHERE user_id=%s", (user_id,), one=True)


def fetch_profiles(sort_by: str = "last_visit", order: str = "DESC") -> List[tuple]:
    """查询全部用户行为画像（动态排序；sort_by 需经调用方白名单校验）"""
    return execute_query(f"{_PROFILE_SELECT} ORDER BY {sort_by} {order}")


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


# ============================================================
# Token 使用统计
# ============================================================


def get_token_overview(
    manager_department: str = "", manager_company: str = ""
) -> Dict[str, Any]:
    """Token 消耗全局汇总（今日/本月/总计，按 call_source 维度）；manager 参数非空时仅本部门+本公司"""
    dept_join, dept_c, cond_params = _dept_scope(
        manager_department, manager_company, base_alias="l"
    )
    dept_cond = (" AND " + " AND ".join(dept_c)) if dept_c else ""

    today_total = safe_one(
        f"SELECT COALESCE(SUM(l.total_tokens),0) FROM llm_usage_log l {dept_join} WHERE DATE(l.created_at)=CURDATE() AND l.success=1 {dept_cond}",
        *cond_params,
    )
    month_total = safe_one(
        f"SELECT COALESCE(SUM(l.total_tokens),0) FROM llm_usage_log l {dept_join} WHERE YEAR(l.created_at)=YEAR(CURDATE()) AND MONTH(l.created_at)=MONTH(CURDATE()) AND l.success=1 {dept_cond}",
        *cond_params,
    )
    all_total = safe_one(
        f"SELECT COALESCE(SUM(l.total_tokens),0) FROM llm_usage_log l {dept_join} WHERE l.success=1 {dept_cond}",
        *cond_params,
    )
    today_calls = safe_one(
        f"SELECT COUNT(*) FROM llm_usage_log l {dept_join} WHERE DATE(l.created_at)=CURDATE() {dept_cond}",
        *cond_params,
    )
    today_users = safe_one(
        f"SELECT COUNT(DISTINCT l.user_id) FROM llm_usage_log l {dept_join} WHERE DATE(l.created_at)=CURDATE() AND l.user_id>0 AND l.success=1 {dept_cond}",
        *cond_params,
    )
    today_failed = safe_one(
        f"SELECT COUNT(*) FROM llm_usage_log l {dept_join} WHERE DATE(l.created_at)=CURDATE() AND l.success=0 {dept_cond}",
        *cond_params,
    )

    by_source_rows = execute_query(
        f"""SELECT l.call_source, COALESCE(SUM(l.total_tokens),0) AS t, COUNT(*) AS c
        FROM llm_usage_log l {dept_join} WHERE DATE(l.created_at)=CURDATE() AND l.success=1 {dept_cond}
        GROUP BY l.call_source ORDER BY t DESC""",
        *cond_params,
    )
    by_source = [
        {"source": r[0], "tokens": int(r[1]), "calls": r[2]} for r in by_source_rows
    ]

    return {
        "today_tokens": today_total,
        "month_tokens": month_total,
        "all_tokens": all_total,
        "today_calls": today_calls,
        "today_users": today_users,
        "today_failed": today_failed,
        "by_source": by_source,
    }


def get_token_trend(
    days: int = 7, manager_department: str = "", manager_company: str = ""
) -> List[Dict[str, Any]]:
    """Token 消耗趋势（按天 + 按模型堆叠）；manager 参数非空时仅本部门+本公司"""
    dept_join, dept_c, dept_params = _dept_scope(
        manager_department, manager_company, base_alias="l"
    )
    dept_cond = (" AND " + " AND ".join(dept_c)) if dept_c else ""
    cond_params: List[Any] = [days, *dept_params]

    rows = execute_query(
        f"""SELECT DATE(l.created_at)d, l.model_name, COALESCE(SUM(l.total_tokens),0)t
        FROM llm_usage_log l {dept_join} WHERE l.success=1 AND l.created_at>=DATE_SUB(CURDATE(),INTERVAL %s DAY) {dept_cond}
        GROUP BY d, l.model_name ORDER BY d""",
        tuple(cond_params),
    )
    # 组装为 [{date, 各 model: tokens, total: N}, ...]（模型名动态取自数据）
    return assemble_trend(rows, total=True)


def get_token_by_model(
    days: int = 7, manager_department: str = "", manager_company: str = ""
) -> List[Dict[str, Any]]:
    """各模型用量分布；manager 参数非空时仅本部门+本公司"""
    dept_join, dept_c, dept_params = _dept_scope(
        manager_department, manager_company, base_alias="l"
    )
    dept_cond = (" AND " + " AND ".join(dept_c)) if dept_c else ""
    cond_params: List[Any] = [days, *dept_params]

    rows = execute_query(
        f"""SELECT l.model_name, COALESCE(SUM(l.total_tokens),0)t, COUNT(*)c
        FROM llm_usage_log l {dept_join} WHERE l.success=1 AND l.created_at>=DATE_SUB(CURDATE(),INTERVAL %s DAY) {dept_cond}
        GROUP BY l.model_name ORDER BY t DESC""",
        tuple(cond_params),
    )
    total = sum(int(r[1]) for r in rows) or 1
    return [
        {
            "model": r[0] or "unknown",
            "tokens": int(r[1]),
            "calls": r[2],
            "percentage": round(int(r[1]) / total * 100, 1),
        }
        for r in rows
    ]


def get_user_token_list(
    sort_by: str = "month_tokens",
    order: str = "desc",
    limit: int = 50,
    offset: int = 0,
    search: str = "",
    manager_department: str = "",
    manager_company: str = "",
) -> Dict[str, Any]:
    """全员 Token 消耗列表（分页、排序、搜索）；manager 参数不为空时仅该部门+公司"""
    allowed_sort = {
        "month_tokens",
        "today_tokens",
        "total_tokens",
        "total_calls",
        "active_days",
        "last_active",
    }
    if sort_by not in allowed_sort:
        sort_by = "month_tokens"
    order_dir = "DESC" if order.lower() == "desc" else "ASC"

    conds = []
    search_params: List[Any] = []
    if search:
        conds.append("u.username LIKE %s")
        search_params.append(f"%{search}%")
    _, dept_c, dept_params = _dept_scope(
        manager_department, manager_company, base_alias="u"
    )
    search_params.extend(dept_params)
    search_cond = (" AND " + " AND ".join(conds + dept_c)) if (conds or dept_c) else ""

    # 子查询：聚合每个用户的 Token 数据
    count_sql = f"""SELECT COUNT(DISTINCT u.id) FROM users u
        WHERE u.is_active=1 {search_cond}"""
    total = safe_one(count_sql, *search_params)

    query = f"""SELECT u.id, u.username, u.display_name, COALESCE(u.role,'user') AS role,
        u.department, u.employee_no, u.is_admin, COALESCE(u.company,'') AS company,
        COALESCE(t.today_tokens,0) AS today_tokens,
        COALESCE(t.month_tokens,0) AS month_tokens,
        COALESCE(t.total_tokens,0) AS total_tokens,
        COALESCE(t.total_calls,0) AS total_calls,
        COALESCE(t.active_days,0) AS active_days_30d,
        t.last_active
    FROM users u
    LEFT JOIN (
        SELECT user_id,
            COALESCE(SUM(CASE WHEN DATE(created_at)=CURDATE() THEN total_tokens ELSE 0 END),0) AS today_tokens,
            COALESCE(SUM(CASE WHEN YEAR(created_at)=YEAR(CURDATE()) AND MONTH(created_at)=MONTH(CURDATE()) THEN total_tokens ELSE 0 END),0) AS month_tokens,
            COALESCE(SUM(total_tokens),0) AS total_tokens,
            COUNT(*) AS total_calls,
            COUNT(DISTINCT CASE WHEN created_at>=DATE_SUB(CURDATE(),INTERVAL 30 DAY) THEN DATE(created_at) END) AS active_days,
            MAX(created_at) AS last_active
        FROM llm_usage_log WHERE success=1 AND user_id>0
        GROUP BY user_id
    ) t ON t.user_id=u.id
    WHERE u.is_active=1 {search_cond}
    ORDER BY {sort_by} {order_dir}
    LIMIT %s OFFSET %s"""

    params = tuple(search_params) + (limit, offset)
    rows = execute_query(query, params)

    items = []
    for r in rows:
        items.append(
            {
                "user_id": r[0],
                "username": r[1],
                "display_name": r[2] or r[1],
                "role": r[3],
                "department": r[4],
                "employee_no": r[5],
                "is_admin": bool(r[6]),
                "company": r[7] or None,
                "today_tokens": int(r[8]),
                "month_tokens": int(r[9]),
                "total_tokens": int(r[10]),
                "total_calls": r[11],
                "active_days_30d": r[12],
                "last_active": to_iso(r[13]),
            }
        )

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "total_pages": (total + limit - 1) // limit if total > 0 else 0,
    }


def get_leader_overview(
    manager_department: str = "", manager_company: str = ""
) -> Dict[str, Any]:
    """领导看板全局汇总（总用户数/今日活跃/今日Token/本月Token/用户分层）；manager 参数非空时仅本部门+本公司"""
    _, dept_c, cond_params = _dept_scope(
        manager_department, manager_company, base_alias="u"
    )
    dept_cond = (" AND " + " AND ".join(dept_c)) if dept_c else ""

    total_users = safe_one(
        f"SELECT COUNT(*) FROM users u WHERE u.is_active=1 AND u.id>0 {dept_cond}",
        *cond_params,
    )
    active_today = safe_one(
        f"""SELECT COUNT(DISTINCT v.user_id) FROM user_page_view v
        JOIN users u ON u.id=v.user_id
        WHERE DATE(v.enter_time)=CURDATE() {dept_cond}""",
        *cond_params,
    )
    today_tokens = safe_one(
        f"""SELECT COALESCE(SUM(l.total_tokens),0) FROM llm_usage_log l
        JOIN users u ON u.id=l.user_id
        WHERE DATE(l.created_at)=CURDATE() AND l.success=1 AND l.user_id>0 {dept_cond}""",
        *cond_params,
    )
    month_tokens = safe_one(
        f"""SELECT COALESCE(SUM(l.total_tokens),0) FROM llm_usage_log l
        JOIN users u ON u.id=l.user_id
        WHERE YEAR(l.created_at)=YEAR(CURDATE()) AND MONTH(l.created_at)=MONTH(CURDATE())
        AND l.success=1 AND l.user_id>0 {dept_cond}""",
        *cond_params,
    )

    # 用户分层：复用 user_behavior_profile 的 is_power_user 和 churn_risk_score
    power_users = safe_one(
        f"""SELECT COUNT(*) FROM user_behavior_profile p
        JOIN users u ON u.id=p.user_id
        WHERE p.is_power_user=1 {dept_cond}""",
        *cond_params,
    )
    churn_users = safe_one(
        f"""SELECT COUNT(*) FROM user_behavior_profile p
        JOIN users u ON u.id=p.user_id
        WHERE p.churn_risk_score>0.5 {dept_cond}""",
        *cond_params,
    )

    # 活跃用户（30天内有活跃）
    active_30d = safe_one(
        f"""SELECT COUNT(DISTINCT v.user_id) FROM user_page_view v
        JOIN users u ON u.id=v.user_id
        WHERE v.enter_time>=DATE_SUB(CURDATE(),INTERVAL 30 DAY) {dept_cond}""",
        *cond_params,
    )

    return {
        "total_users": total_users,
        "active_today": active_today,
        "active_30d": active_30d,
        "today_tokens": today_tokens,
        "month_tokens": month_tokens,
        "power_users": power_users,
        "churn_risk_users": churn_users,
    }


def build_behavior_stats(
    department: str = "", company: str = "", days: int = 7
) -> Dict[str, Any]:
    """行为统计大盘（admin 全局与部门/经理视角复用同一套聚合）。

    department 为空 → 全库（原 /dashboard/behavior-stats）；
    非空 → 限定本部门+本公司（原 /dashboard/usage/behavior）。
    页面路由统一经 normalize_route 归一化后聚合，取代 SQL 内 CASE 规范化。
    """
    _, dept_c, dept_p = _dept_scope(department, company, base_alias="u")
    dept_cond = (" AND " + " AND ".join(dept_c)) if dept_c else ""

    def djoin(alias: str) -> str:
        """按部门过滤时，为各基础表补充 users join"""
        return f"JOIN users u ON u.id={alias}.user_id" if department else ""

    # 活跃用户 / 会话 / 平均停留
    active_today = safe_one(
        f"""SELECT COUNT(DISTINCT v.user_id) FROM user_page_view v {djoin('v')}
        WHERE DATE(v.enter_time)=CURDATE() {dept_cond}""",
        *dept_p,
    )
    sessions_today = safe_one(
        f"""SELECT COUNT(*) FROM user_session s {djoin('s')}
        WHERE DATE(s.login_time)=CURDATE() {dept_cond}""",
        *dept_p,
    )
    avg_duration = int(
        safe_one(
            f"""SELECT COALESCE(AVG(s.duration_sec),0) FROM user_session s {djoin('s')}
            WHERE s.login_time>=DATE_SUB(NOW(),INTERVAL %s DAY) AND s.duration_sec>0 {dept_cond}""",
            days,
            *dept_p,
        )
    )

    # 最热页面（归一化后展示）
    top_row = execute_query(
        f"""SELECT v.page_route FROM user_page_view v {djoin('v')}
        WHERE v.enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY) {dept_cond}
        GROUP BY v.page_route ORDER BY COUNT(*) DESC LIMIT 1""",
        (days, *dept_p),
        one=True,
    )
    top_page = normalize_route(top_row[0]) if top_row and top_row[0] else None

    # 重度用户 + 流失风险
    power_users = safe_one(
        f"""SELECT COUNT(*) FROM user_behavior_profile p {djoin('p')}
        WHERE p.is_power_user=1 {dept_cond}""",
        *dept_p,
    )
    churn_users = safe_one(
        f"""SELECT COUNT(*) FROM user_behavior_profile p {djoin('p')}
        WHERE p.churn_risk_score>0.5 {dept_cond}""",
        *dept_p,
    )

    # 7日活跃趋势
    trend_rows = execute_query(
        f"""SELECT DATE(s.login_time)d, COUNT(DISTINCT s.user_id) dau, COUNT(*) sessions
        FROM user_session s {djoin('s')}
        WHERE s.login_time>=DATE_SUB(CURDATE(),INTERVAL %s DAY) {dept_cond}
        GROUP BY d ORDER BY d""",
        (days, *dept_p),
    )
    activity_trend = [
        {"date": fmt_dt(r[0]), "dau": r[1], "sessions": r[2]} for r in trend_rows
    ]

    # 时段热力
    heatmap_rows = execute_query(
        f"""SELECT HOUR(v.enter_time)h, DAYOFWEEK(v.enter_time) dow, COUNT(*) c
        FROM user_page_view v {djoin('v')}
        WHERE v.enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY) {dept_cond}
        GROUP BY h,dow ORDER BY dow,h""",
        (days, *dept_p),
    )
    heatmap = [{"hour": r[0], "day_of_week": r[1], "count": r[2]} for r in heatmap_rows]

    # 页面访问分布：SQL 按原始路由聚合，Python 归一化后求和
    dist_rows = execute_query(
        f"""SELECT v.page_route, COUNT(*) c FROM user_page_view v {djoin('v')}
        WHERE v.enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY) {dept_cond}
        GROUP BY v.page_route""",
        (days, *dept_p),
    )
    cnt_acc: Dict[str, int] = {}
    for route, cnt in dist_rows:
        norm = normalize_route(route)
        cnt_acc[norm] = cnt_acc.get(norm, 0) + cnt
    page_dist = pad_page_routes(
        [
            {"page_route": r, "page_title": page_title(r), "count": c}
            for r, c in sorted(cnt_acc.items(), key=lambda x: -x[1])
        ]
    )

    # 页面停留时长：按原始路由 AVG + COUNT，Python 归一化后做加权平均
    avg_rows = execute_query(
        f"""SELECT v.page_route, AVG(v.duration_sec), COUNT(*) c FROM user_page_view v {djoin('v')}
        WHERE v.enter_time>=DATE_SUB(NOW(),INTERVAL %s DAY) AND v.duration_sec>0 {dept_cond}
        GROUP BY v.page_route""",
        (days, *dept_p),
    )
    wavg: Dict[str, List[float]] = {}
    for route, avg_sec, cnt in avg_rows:
        norm = normalize_route(route)
        acc = wavg.setdefault(norm, [0.0, 0.0])
        acc[0] += float(avg_sec) * cnt
        acc[1] += cnt
    page_avg = [
        {"page_route": r, "avg_sec": round(acc[0] / acc[1], 0) if acc[1] else 0}
        for r, acc in wavg.items()
    ]
    page_avg.sort(key=lambda x: -x["avg_sec"])
    page_avg = pad_page_routes(page_avg, count_key="avg_sec")

    result = {
        "active_users_today": active_today,
        "sessions_today": sessions_today,
        "avg_duration_7d": avg_duration,
        "top_page": top_page,
        "power_users": power_users,
        "churn_risk_users": churn_users,
        "activity_trend": activity_trend,
        "hourly_heatmap": heatmap,
        "page_distribution": page_dist,
        "page_avg_duration": page_avg,
    }
    if department:
        dept_size = safe_one(
            "SELECT COUNT(*) FROM users WHERE is_active=1 AND department=%s AND id>0"
            + (" AND company=%s" if company else ""),
            department,
            *([company] if company else []),
        )
        result["department"] = department
        result["dept_size"] = dept_size
    return result
