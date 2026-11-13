"""收益日历 API：按日期聚合新闻、收益率变动、活跃因子和宏观数据。"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Dict, List

from fastapi import APIRouter, HTTPException, Query

from backend.common.api_response import ok
from backend.common.database import build_in_placeholders, get_db_connection
from backend.common.db_analysis import AnalysisQueries
from backend.config.config import ANALYSIS_MODEL_PRIORITY, API_PREFIX, mask_news_source
from backend.recommend.importance import normalize_direction, parse_score_signals
from backend.repositories.news_importance_repository import NewsImportanceRepository
from backend.returns.rules import (
    build_yield_change_map,
    classify_market_alignment,
    direction_label,
    sort_news_by_importance,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix=API_PREFIX, tags=["returns"])

# 按新闻选最高优先级模型的 analysis 的关联子句（discover / returns 共用同一来源）
_BEST_ANALYSIS_JOIN = AnalysisQueries.best_analysis_join("JOIN")
# 因子关联的模型优先级 CASE（与分析模型优先级一致；历史 doubao 视为最高优先级）
_FACTOR_MODEL_CASE = (
    "CASE nf.model"
    + "".join(f" WHEN '{m}' THEN {i}" for i, m in enumerate(ANALYSIS_MODEL_PRIORITY))
    + " WHEN 'doubao' THEN 0 ELSE 999 END"
)

WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
PERIODS = ["3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "30Y"]
PERIOD_LABELS = {
    "3M": "3月", "6M": "6月", "1Y": "1年", "2Y": "2年", "3Y": "3年",
    "5Y": "5年", "7Y": "7年", "10Y": "10年", "30Y": "30年",
}


def _date_string(value) -> str:
    return value.strftime("%Y-%m-%d") if hasattr(value, "strftime") else str(value)[:10]


@router.get("/returns/calendar")
def returns_calendar(
    start: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end: str = Query(..., description="结束日期 YYYY-MM-DD"),
):
    """一次返回日期范围数据，前端本地选日；Top N 仅用于展示，不截断新闻。"""
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")
    if start_dt > end_dt:
        raise HTTPException(status_code=400, detail="start 不能晚于 end")

    calendar_days: List[date] = []
    current = start_dt
    while current <= end_dt:
        calendar_days.append(current)
        current += timedelta(days=1)
    end_exclusive = end_dt + timedelta(days=1)

    with get_db_connection() as conn:
        cur = conn.cursor()

        # 1. 每日新闻方向统计。半开时间范围与 DATE() 等价，并可利用 pub_time 索引。
        cur.execute(
            f"""SELECT DATE(n.pub_time) as d, a.direction, COUNT(*)
               FROM news n
               {_BEST_ANALYSIS_JOIN}
               WHERE n.pub_time >= %s AND n.pub_time < %s
               GROUP BY DATE(n.pub_time), a.direction""",
            (start_dt, end_exclusive),
        )
        day_dir: Dict[str, Dict[str, int]] = defaultdict(
            lambda: {"利多": 0, "利空": 0, "中性": 0}
        )
        for day, raw_direction, count in cur.fetchall():
            day_dir[_date_string(day)][direction_label(raw_direction)] += count

        # 2. 各期限以实际相邻行情记录计算 BP；start 前只取最近一个有效值。
        yields_by_date: Dict[str, Dict[str, Dict]] = defaultdict(dict)
        for period in PERIODS:
            cur.execute(
                """SELECT date, value FROM yield_data
                   WHERE period = %s AND date < %s
                   ORDER BY date DESC LIMIT 1""",
                (period, start_dt),
            )
            previous = cur.fetchone()
            cur.execute(
                """SELECT date, value FROM yield_data
                   WHERE period = %s AND date >= %s AND date <= %s
                   ORDER BY date ASC""",
                (period, start_dt, end_dt),
            )
            changes = build_yield_change_map(
                rows=cur.fetchall(),
                previous=previous,
                start=start_dt,
                end=end_dt,
                label=PERIOD_LABELS[period],
            )
            for day_string, point in changes.items():
                yields_by_date[day_string][period] = point

        # 3. 活跃因子：同一新闻的多模型关联只计一次。
        cur.execute(
            """SELECT DATE(n.pub_time) as d, f.id, f.name, f.category,
                      COUNT(DISTINCT nf.news_id) as cnt
               FROM news_factor nf
               JOIN factor f ON nf.factor_id = f.id
               JOIN news n ON nf.news_id = n.id
               WHERE n.pub_time >= %s AND n.pub_time < %s
               GROUP BY DATE(n.pub_time), f.id, f.name, f.category
               ORDER BY d, cnt DESC, f.id""",
            (start_dt, end_exclusive),
        )
        day_factors: Dict[str, List[Dict]] = defaultdict(list)
        for day, factor_id, name, category, count in cur.fetchall():
            day_string = _date_string(day)
            if len(day_factors[day_string]) < 5:
                day_factors[day_string].append({
                    "id": factor_id,
                    "name": name or "",
                    "category": category or "",
                    "news_count": count,
                })

        # 4. 全部已分析新闻；静态重要性在 Python  enrich，避免历史日期使用 NOW() 衰减。
        cur.execute(
            f"""SELECT n.id, n.title, n.pub_time, n.source, a.direction, a.reason, a.horizon
               FROM news n
               {_BEST_ANALYSIS_JOIN}
               WHERE n.pub_time >= %s AND n.pub_time < %s
                 AND a.direction IS NOT NULL
               ORDER BY n.pub_time DESC, n.id DESC""",
            (start_dt, end_exclusive),
        )
        news_rows = cur.fetchall()

        news_factors_map: Dict[int, List[Dict]] = defaultdict(list)
        seen_factors: Dict[int, set] = defaultdict(set)
        if news_rows:
            news_ids = [row[0] for row in news_rows]
            placeholders = build_in_placeholders(news_ids)
            cur.execute(
                f"""SELECT nf.news_id, f.id, f.name, nf.direction, nf.model
                    FROM news_factor nf JOIN factor f ON nf.factor_id = f.id
                    WHERE nf.news_id IN ({placeholders})
                    ORDER BY nf.news_id, {_FACTOR_MODEL_CASE}, f.id""",
                tuple(news_ids),
            )
            for news_id, factor_id, name, raw_direction, _model in cur.fetchall():
                if factor_id in seen_factors[news_id] or len(news_factors_map[news_id]) >= 3:
                    continue
                seen_factors[news_id].add(factor_id)
                normalized = normalize_direction(raw_direction)
                factor_direction = "利多" if normalized == "positive" else (
                    "利空" if normalized == "negative" else ""
                )
                news_factors_map[news_id].append({
                    "id": factor_id,
                    "name": name or "",
                    "direction": factor_direction,
                })

        # 5. 宏观数据保留原契约；单月失败不阻断日历主数据。
        months = sorted({day.strftime("%Y%m") for day in calendar_days})
        macro_by_month: Dict[str, List[Dict]] = {}
        for month in months:
            try:
                cur.execute(
                    """SELECT zbcode, name, value, datestr
                       FROM macro_indicator_data
                       WHERE datestr = %s ORDER BY zbcode""",
                    (month,),
                )
                macro_by_month[month] = [
                    {
                        "code": row[0],
                        "name": row[1] or "",
                        "value": float(row[2]) if row[2] is not None else None,
                        "datestr": row[3],
                    }
                    for row in cur.fetchall()
                ]
            except Exception as exc:
                logger.warning("returns/calendar macro query failed for %s: %s", month, exc)

    # 批量补静态分；空新闻不打开第二条连接，也不因缺分过滤任何候选。
    scores = {}
    if news_rows:
        scores = NewsImportanceRepository.from_environment().get_by_news_ids(
            [row[0] for row in news_rows]
        )

    news_by_date: Dict[str, List[Dict]] = defaultdict(list)
    for row in news_rows:
        news_id, title, pub_time, source, raw_direction, reason, horizon = row
        day_string = _date_string(pub_time)
        score = scores.get(news_id, {})
        importance_score = score.get("importance_score")
        benchmark = yields_by_date.get(day_string, {}).get("10Y", {})
        news_by_date[day_string].append({
            "id": news_id,
            "title": title or "",
            "pub_time": pub_time.strftime("%Y-%m-%d %H:%M:%S") if hasattr(pub_time, "strftime") else str(pub_time),
            "source": mask_news_source(source),
            "direction": direction_label(raw_direction),
            "reason": reason or "",
            "horizon": horizon or "",
            "factors": news_factors_map.get(news_id, []),
            "importance_score": float(importance_score) if importance_score is not None else None,
            "score_signals": parse_score_signals(score.get("signals_json")),
            "top_category": score.get("top_category"),
            "score_version": score.get("score_version"),
            "market_alignment": classify_market_alignment(
                benchmark.get("diff_bp"), raw_direction
            ),
        })

    days = []
    for day in calendar_days:
        day_string = day.isoformat()
        counts = day_dir.get(day_string, {"利多": 0, "利空": 0, "中性": 0})
        days.append({
            "date": day_string,
            "weekday": WEEKDAYS[day.weekday()],
            "bullish_count": counts["利多"],
            "bearish_count": counts["利空"],
            "neutral_count": counts["中性"],
            "active_factors": day_factors.get(day_string, []),
        })

    return ok({
        "days": days,
        "yields_by_date": dict(yields_by_date),
        "news_by_date": {
            day_string: sort_news_by_importance(items)
            for day_string, items in news_by_date.items()
        },
        "macro_by_month": macro_by_month,
        "query": {"start": start, "end": end},
    })
