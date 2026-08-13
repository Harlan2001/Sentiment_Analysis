"""
收益日历 API — 按周聚合方向性新闻、收益率变动、活跃因子、宏观数据
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from backend.common.database import get_db_connection
from backend.config.config import API_PREFIX

logger = logging.getLogger(__name__)
router = APIRouter(prefix=API_PREFIX, tags=["returns"])

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


@router.get("/returns/calendar")
def returns_calendar(
    start: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end: str = Query(..., description="结束日期 YYYY-MM-DD"),
    selected: str = Query(None, description="选中日期 YYYY-MM-DD，默认取 start"),
):
    """
    收益日历聚合接口：
    - 每日利多/利空新闻计数
    - 每日收益率变动（各期限 bp 变化）
    - 每日活跃因子 top5
    - 本月宏观数据
    - 选中日期的方向性新闻列表
    """
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        return {"error": "日期格式错误，请使用 YYYY-MM-DD"}
    if start_dt > end_dt:
        return {"error": "start 不能晚于 end"}

    selected_dt = datetime.strptime(selected, "%Y-%m-%d").date() if selected else start_dt

    periods = ["3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "30Y"]
    period_labels = {
        "3M": "3月", "6M": "6月", "1Y": "1年", "2Y": "2年", "3Y": "3年",
        "5Y": "5年", "7Y": "7年", "10Y": "10年", "30Y": "30年",
    }

    with get_db_connection() as conn:
        cur = conn.cursor()

        # ── 1. 每日新闻方向统计 ──
        cur.execute(
            """SELECT DATE(n.pub_time) as d, a.direction, COUNT(*)
               FROM news n
               JOIN analysis a ON n.id = a.news_id AND a.model = 'doubao'
               WHERE DATE(n.pub_time) BETWEEN %s AND %s
               GROUP BY DATE(n.pub_time), a.direction""",
            (start, end),
        )
        dir_rows = cur.fetchall()

        day_dir: Dict[str, Dict[str, int]] = defaultdict(lambda: {"利多": 0, "利空": 0, "中性": 0})
        for d, direction, cnt in dir_rows:
            ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
            direction_str = str(direction) if direction else "中性"
            # 统一方向标签
            if direction_str in ("positive", "bullish", "利多", "利好", "涨"):
                day_dir[ds]["利多"] += cnt
            elif direction_str in ("negative", "bearish", "利空", "跌"):
                day_dir[ds]["利空"] += cnt
            else:
                day_dir[ds]["中性"] += cnt

        # ── 2. 收益率变动（每个期限当天 vs 前一天 bp 差异）──
        yield_changes: Dict[str, List[Dict]] = {}
        for p in periods:
            cur.execute(
                """SELECT date, value FROM yield_data
                   WHERE period = %s AND date >= DATE_SUB(%s, INTERVAL 1 DAY) AND date <= %s
                   ORDER BY date DESC""",
                (p, selected_dt - timedelta(days=1), selected_dt),
            )
            ypts = cur.fetchall()
            if len(ypts) >= 2:
                today_val = float(ypts[0][1])
                prev_val = float(ypts[1][1])
                diff_bp = round((today_val - prev_val) * 100, 1)
                direction = "up" if diff_bp > 0 else ("down" if diff_bp < 0 else "flat")
                yield_changes[p] = {
                    "label": period_labels.get(p, p),
                    "value": today_val,
                    "diff_bp": diff_bp,
                    "direction": direction,
                }
            elif len(ypts) == 1:
                yield_changes[p] = {
                    "label": period_labels.get(p, p),
                    "value": float(ypts[0][1]),
                    "diff_bp": 0,
                    "direction": "flat",
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
        factor_rows = cur.fetchall()

        day_factors: Dict[str, List[Dict]] = defaultdict(list)
        for d, fid, fname, fcat, cnt in factor_rows:
            ds = d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d)
            if len(day_factors[ds]) < 5:
                day_factors[ds].append({
                    "id": fid, "name": fname or "", "category": fcat or "",
                    "news_count": cnt,
                })

        # ── 4. 选中日期方向性新闻列表 ──
        cur.execute(
            """SELECT n.id, n.title, n.pub_time, n.source, a.direction, a.reason, a.horizon
               FROM news n
               JOIN analysis a ON n.id = a.news_id AND a.model = 'doubao'
               WHERE DATE(n.pub_time) = %s
                 AND a.direction IS NOT NULL
               ORDER BY n.pub_time DESC""",
            (selected_dt,),
        )
        selected_news = []
        for r in cur.fetchall():
            direction_raw = str(r[4]) if r[4] else "中性"
            if direction_raw in ("positive", "bullish", "利多", "利好", "涨"):
                direction = "利多"
            elif direction_raw in ("negative", "bearish", "利空", "跌"):
                direction = "利空"
            else:
                direction = "中性"

            nid = r[0]
            # 取该新闻的关联因子
            cur.execute(
                """SELECT f.id, f.name, nf.direction
                   FROM news_factor nf JOIN factor f ON nf.factor_id = f.id
                   WHERE nf.news_id = %s
                   ORDER BY CASE nf.model WHEN 'doubao' THEN 0 WHEN 'deepseek' THEN 1 ELSE 2 END
                   LIMIT 3""",
                (nid,),
            )
            factors = []
            for fr in cur.fetchall():
                fd_raw = str(fr[2]) if fr[2] else ""
                fd = "利多" if fd_raw in ("positive", "bullish", "利多") else (
                    "利空" if fd_raw in ("negative", "bearish", "利空") else ""
                )
                factors.append({"id": fr[0], "name": fr[1] or "", "direction": fd})

            selected_news.append({
                "id": nid,
                "title": r[1] or "",
                "pub_time": r[2].strftime("%Y-%m-%d %H:%M:%S") if r[2] else "",
                "source": r[3] or "",
                "direction": direction,
                "reason": r[5] or "",
                "horizon": r[6] or "",
                "factors": factors,
            })

        # ── 5. 本月宏观数据 ──
        current_month = selected_dt.strftime("%Y%m")
        macro_data = []
        try:
            cur.execute(
                """SELECT zbcode, name, value, datestr
                   FROM macro_indicator_data
                   WHERE datestr = %s
                   LIMIT 10""",
                (current_month,),
            )
            for mr in cur.fetchall():
                macro_data.append({
                    "code": mr[0],
                    "name": mr[1] or "",
                    "value": float(mr[2]) if mr[2] is not None else None,
                    "datestr": mr[3],
                })
        except Exception as e:
            logger.warning("returns/calendar macro_data query failed: %s", e)

        # ── 构建 days 数组 ──
        days = []
        current = start_dt
        while current <= end_dt:
            ds = current.strftime("%Y-%m-%d")
            wd_idx = current.weekday()  # 0=周一 ... 6=周日
            dir_counts = day_dir.get(ds, {"利多": 0, "利空": 0, "中性": 0})
            days.append({
                "date": ds,
                "weekday": WEEKDAYS[wd_idx],
                "bullish_count": dir_counts["利多"],
                "bearish_count": dir_counts["利空"],
                "neutral_count": dir_counts["中性"],
                "active_factors": day_factors.get(ds, []),
            })
            current += timedelta(days=1)

    return {
        "days": days,
        "selected_date": selected_dt.strftime("%Y-%m-%d"),
        "yields": yield_changes,
        "news": selected_news,
        "macro_data": macro_data,
        "query": {"start": start, "end": end},
    }
