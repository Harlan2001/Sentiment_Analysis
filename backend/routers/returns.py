"""
收益日历 API — 按周聚合方向性新闻、收益率变动、活跃因子、宏观数据
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, Query

from backend.common.database import get_db_connection
from backend.common.db_operations import DBOperations
from backend.config.config import ANALYSIS_MODEL_PRIORITY, API_PREFIX, mask_news_source

logger = logging.getLogger(__name__)
router = APIRouter(prefix=API_PREFIX, tags=["returns"])

# 模型优先级 CASE 片段（glm > kimi > deepseek > qwen > default，历史 doubao 走 ELSE）
MODEL_PRIORITY_CASE = DBOperations.priority_case_sql()
# 按新闻选最高优先级模型的 analysis 的关联子句
_BEST_ANALYSIS_JOIN = (
    "JOIN analysis a ON n.id = a.news_id"
    " AND a.model = (SELECT a2.model FROM analysis a2"
    " WHERE a2.news_id = n.id ORDER BY CASE a2.model"
    f" {MODEL_PRIORITY_CASE} ELSE 999 END LIMIT 1)"
)
# 因子关联的模型优先级 CASE（与分析模型优先级一致；历史 doubao 视为最高优先级）
_FACTOR_MODEL_CASE = (
    "CASE nf.model"
    + "".join(f" WHEN '{m}' THEN {i}" for i, m in enumerate(ANALYSIS_MODEL_PRIORITY))
    + " WHEN 'doubao' THEN 0 ELSE 999 END"
)

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


@router.get("/returns/calendar")
def returns_calendar(
    start: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """
    收益日历聚合接口（一次返回整周数据，前端本地切换日期，避免重复请求）：
    - 每日利多/利空新闻计数
    - 每日收益率变动（各期限 bp 变化）
    - 每日活跃因子 top5
    - 每日方向性新闻列表
    - 各月宏观数据
    """
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "日期格式错误，请使用 YYYY-MM-DD"}
    if start_dt > end_dt:
        return {"error": "start 不能晚于 end"}

    periods = ["3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "30Y"]
    period_labels = {
        "3M": "3月", "6M": "6月", "1Y": "1年", "2Y": "2年", "3Y": "3年",
        "5Y": "5年", "7Y": "7年", "10Y": "10年", "30Y": "30年",
    }

    # 本周日期列表（含前一天用于计算每日收益率变动）
    week_days: List[date] = []
    current = start_dt
    while current <= end_dt:
        week_days.append(current)
        current += timedelta(days=1)

    with get_db_connection() as conn:
        cur = conn.cursor()

        # ── 1. 每日新闻方向统计 ──
        cur.execute(
            f"""SELECT DATE(n.pub_time) as d, a.direction, COUNT(*)
               FROM news n
               {_BEST_ANALYSIS_JOIN}
               WHERE DATE(n.pub_time) BETWEEN %s AND %s
               GROUP BY DATE(n.pub_time), a.direction""",
            (start, end),
        )
        day_dir: Dict[str, Dict[str, int]] = defaultdict(lambda: {"利多": 0, "利空": 0, "中性": 0})
        for d, direction, cnt in cur.fetchall():
            ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
            direction_str = str(direction) if direction else "中性"
            if direction_str in ("positive", "bullish", "利多", "利好", "涨"):
                day_dir[ds]["利多"] += cnt
            elif direction_str in ("negative", "bearish", "利空", "跌"):
                day_dir[ds]["利空"] += cnt
            else:
                day_dir[ds]["中性"] += cnt

        # ── 2. 每日收益率变动（整周，按期限一次查询 + Python 计算逐日 diff）──
        yields_by_date: Dict[str, Dict[str, Dict]] = defaultdict(dict)
        prev_start = start_dt - timedelta(days=1)
        for p in periods:
            cur.execute(
                """SELECT date, value FROM yield_data
                   WHERE period = %s AND date >= %s AND date <= %s
                   ORDER BY date ASC""",
                (p, prev_start, end_dt),
            )
            val_map: Dict[str, float] = {}
            for d, v in cur.fetchall():
                ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
                val_map[ds] = float(v)
            for day in week_days:
                ds = day.strftime("%Y-%m-%d")
                prev_ds = (day - timedelta(days=1)).strftime("%Y-%m-%d")
                if ds in val_map:
                    prev_val = val_map.get(prev_ds)
                    diff_bp = round((val_map[ds] - prev_val) * 100, 1) if prev_val is not None else 0
                    direction = "up" if diff_bp > 0 else ("down" if diff_bp < 0 else "flat")
                    yields_by_date[ds][p] = {
                        "label": period_labels.get(p, p),
                        "value": val_map[ds],
                        "diff_bp": diff_bp,
                        "direction": direction,
                    }

        # ── 3. 每日活跃因子 top5（按新闻数）──
        cur.execute(
            """SELECT DATE(n.pub_time) as d, f.id, f.name, f.category, COUNT(*) as cnt
               FROM news_factor nf
               JOIN factor f ON nf.factor_id = f.id
               JOIN news n ON nf.news_id = n.id
               WHERE DATE(n.pub_time) BETWEEN %s AND %s
               GROUP BY DATE(n.pub_time), f.id, f.name, f.category
               ORDER BY d, cnt DESC""",
            (start, end),
        )
        day_factors: Dict[str, List[Dict]] = defaultdict(list)
        for d, fid, fname, fcat, cnt in cur.fetchall():
            ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
            if len(day_factors[ds]) < 5:
                day_factors[ds].append({
                    "id": fid, "name": fname or "", "category": fcat or "",
                    "news_count": cnt,
                })

        # ── 4. 整周方向性新闻列表（一次查询 + 批量取因子）──
        cur.execute(
            f"""SELECT n.id, n.title, n.pub_time, n.source, a.direction, a.reason, a.horizon
               FROM news n
               {_BEST_ANALYSIS_JOIN}
               WHERE DATE(n.pub_time) BETWEEN %s AND %s
                 AND a.direction IS NOT NULL
               ORDER BY n.pub_time DESC""",
            (start, end),
        )
        news_rows = cur.fetchall()

        news_factors_map: Dict[int, List[Dict]] = defaultdict(list)
        if news_rows:
            news_ids = [r[0] for r in news_rows]
            placeholders = ",".join(["%s"] * len(news_ids))
            cur.execute(
                f"""SELECT nf.news_id, f.id, f.name, nf.direction, nf.model
                    FROM news_factor nf JOIN factor f ON nf.factor_id = f.id
                    WHERE nf.news_id IN ({placeholders})
                    ORDER BY nf.news_id,
                             {_FACTOR_MODEL_CASE},
                             f.id""",
                tuple(news_ids),
            )
            for nid, fid, fname, fdir, _model in cur.fetchall():
                if len(news_factors_map[nid]) >= 3:
                    continue
                fd_raw = str(fdir) if fdir else ""
                fd = "利多" if fd_raw in ("positive", "bullish", "利多") else (
                    "利空" if fd_raw in ("negative", "bearish", "利空") else ""
                )
                news_factors_map[nid].append({"id": fid, "name": fname or "", "direction": fd})

        news_by_date: Dict[str, List[Dict]] = defaultdict(list)
        for r in news_rows:
            direction_raw = str(r[4]) if r[4] else "中性"
            if direction_raw in ("positive", "bullish", "利多", "利好", "涨"):
                direction = "利多"
            elif direction_raw in ("negative", "bearish", "利空", "跌"):
                direction = "利空"
            else:
                direction = "中性"

            nid = r[0]
            pub_dt = r[2]
            ds = pub_dt.strftime("%Y-%m-%d") if hasattr(pub_dt, "strftime") else str(pub_dt)[:10]
            news_by_date[ds].append({
                "id": nid,
                "title": r[1] or "",
                "pub_time": pub_dt.strftime("%Y-%m-%d %H:%M:%S") if hasattr(pub_dt, "strftime") else str(pub_dt),
                "source": mask_news_source(r[3]),
                "direction": direction,
                "reason": r[5] or "",
                "horizon": r[6] or "",
                "factors": news_factors_map.get(nid, []),
            })

        # ── 5. 各月宏观数据 ──
        months = sorted({day.strftime("%Y%m") for day in week_days})
        macro_by_month: Dict[str, List[Dict]] = {}
        for m in months:
            try:
                cur.execute(
                    """SELECT zbcode, name, value, datestr
                       FROM macro_indicator_data
                       WHERE datestr = %s
                       ORDER BY zbcode""",
                    (m,),
                )
                macro_by_month[m] = [
                    {
                        "code": mr[0],
                        "name": mr[1] or "",
                        "value": float(mr[2]) if mr[2] is not None else None,
                        "datestr": mr[3],
                    }
                    for mr in cur.fetchall()
                ]
            except Exception as e:
                logger.warning("returns/calendar macro query failed for %s: %s", m, e)

        # ── 构建 days 数组 ──
        days = []
        for day in week_days:
            ds = day.strftime("%Y-%m-%d")
            dir_counts = day_dir.get(ds, {"利多": 0, "利空": 0, "中性": 0})
            days.append({
                "date": ds,
                "weekday": WEEKDAYS[day.weekday()],
                "bullish_count": dir_counts["利多"],
                "bearish_count": dir_counts["利空"],
                "neutral_count": dir_counts["中性"],
                "active_factors": day_factors.get(ds, []),
            })

    return {
        "days": days,
        "yields_by_date": dict(yields_by_date),
        "news_by_date": dict(news_by_date),
        "macro_by_month": macro_by_month,
        "query": {"start": start, "end": end},
    }
