"""
发现页 API — 单页合并方案（新闻发现 + 市场数据）
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Query

from backend.common.database import get_db_connection
from backend.common.db_operations import DBOperations
from backend.config.config import API_PREFIX, NEWS_SOURCE_LABELS

logger = logging.getLogger(__name__)
router = APIRouter(prefix=API_PREFIX, tags=["discover"])

# 模型优先级 CASE 片段（glm > deepseek > qwen > default，历史 doubao 走 ELSE）
MODEL_PRIORITY_CASE = DBOperations.priority_case_sql()


def _map_direction(d, default=None):
    """把分析侧方向归一化为前端约定的 positive/negative；无方向/未知返回 default。"""
    if not d:
        return default
    dv = str(d).lower()
    if dv in ("bullish", "positive", "up", "涨", "利多", "利好"):
        return "positive"
    if dv in ("bearish", "negative", "down", "跌", "利空"):
        return "negative"
    return default
# 按新闻选最高优先级模型的 analysis 的关联子句
_BEST_ANALYSIS_JOIN = (
    "LEFT JOIN analysis a ON n.id = a.news_id"
    " AND a.model = (SELECT a2.model FROM analysis a2"
    " WHERE a2.news_id = n.id ORDER BY CASE a2.model"
    f" {MODEL_PRIORITY_CASE} ELSE 999 END LIMIT 1)"
)


# ── 1. 发现页新闻列表 ──────────────────────────────────────────────────


@router.get("/discover/news")
def discover_news(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    direction: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
):
    offset = (page - 1) * page_size

    dir_join = ""
    if direction:
        # 按最佳模型（glm 优先，历史 doubao 兜底）取每条新闻的方向做过滤
        dir_join = (
            "LEFT JOIN analysis a ON n.id = a.news_id"
            " AND a.model = (SELECT a2.model FROM analysis a2"
            " WHERE a2.news_id = n.id ORDER BY CASE a2.model"
            f" {MODEL_PRIORITY_CASE} ELSE 999 END LIMIT 1)"
        )

    where_clauses = ["1=1"]
    where_params: List[str] = []
    if source:
        where_clauses.append("n.source = %s")
        where_params.append(source)
    if direction:
        where_clauses.append("a.direction = %s")
        where_params.append(direction)

    with get_db_connection() as conn:
        cur = conn.cursor()
        # 无条件返回全部新闻，pub_time DESC 无限滚动
        cur.execute(f"""
            SELECT n.id, n.title, n.pub_time, n.source
            FROM news n {dir_join}
            WHERE {' AND '.join(where_clauses)}
            ORDER BY n.pub_time DESC
            LIMIT %s OFFSET %s
        """, where_params + [page_size, offset])
        news_rows = cur.fetchall()

        cur.execute(f"""
            SELECT COUNT(*) FROM news n {dir_join}
            WHERE {' AND '.join(where_clauses)}
        """, where_params)
        total = (cur.fetchone() or [0])[0]

    logger.info("discover/news: page=%d returned %d rows (total=%d)", page, len(news_rows), total)

    news_ids = [r[0] for r in news_rows]

    # 空页直接返回，避免 IN () 语法错误
    if not news_ids:
        return {
            "items": [],
            "total": total,
            "page": page,
            "page_size": page_size,
            "has_more": offset + page_size < total,
        }

    # 批量取缩略图
    with get_db_connection() as conn:
        cur = conn.cursor()
        ph = ",".join(["%s"] * len(news_ids))
        cur.execute(f"""
            SELECT news_id, image_url FROM news_content_blocks
            WHERE news_id IN ({ph}) AND block_type='image'
            ORDER BY news_id, block_order
        """, news_ids)
        thumb_rows = cur.fetchall()

    thumbs: Dict[int, str] = {}
    for nid, url in thumb_rows:
        if nid not in thumbs:
            thumbs[nid] = url

    # 批量取 analysis
    with get_db_connection() as conn:
        cur = conn.cursor()
        ph = ",".join(["%s"] * len(news_ids))
        cur.execute(f"""
            SELECT news_id, direction, reason
            FROM analysis
            WHERE news_id IN ({ph}) AND model IN ('doubao','glm')
            ORDER BY news_id, CASE model WHEN 'glm' THEN 1 ELSE 0 END
        """, news_ids)
        analysis_rows = cur.fetchall()

    analysis_map: Dict[int, tuple] = {}
    for nid, adir, areason in analysis_rows:
        analysis_map[nid] = (adir, areason)

    # 批量取因子
    with get_db_connection() as conn:
        cur = conn.cursor()
        ph = ",".join(["%s"] * len(news_ids))
        cur.execute(f"""
            SELECT nf.news_id, f.id, f.name
            FROM news_factor nf JOIN factor f ON nf.factor_id = f.id
            WHERE nf.news_id IN ({ph})
        """, news_ids)
        factor_rows = cur.fetchall()

    factors_map: Dict[int, List[Dict]] = {}
    for nid, fid, fname in factor_rows:
        factors_map.setdefault(nid, []).append({"id": fid, "name": fname})

    items = []
    for r in news_rows:
        nid, title, pub_time, src = r
        adir, areason = analysis_map.get(nid, (None, ""))
        items.append({
            "id": nid,
            "title": title or "",
            "summary": "",
            "pub_time": pub_time.strftime("%Y-%m-%d %H:%M:%S") if pub_time else "",
            "source": src or "",
            "source_name": NEWS_SOURCE_LABELS.get(src, src or ""),
            "thumbnail": thumbs.get(nid),
            "direction": adir,
            "reason": areason or "",
            "factors": factors_map.get(nid, []),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_more": offset + page_size < total,
    }


# ── 2. 市场数据面板 ────────────────────────────────────────────────────


@router.get("/discover/market-panel")
def market_panel():
    periods = ["3M", "6M", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "30Y"]
    labels = {
        "3M": "3月", "6M": "6月", "1Y": "1年", "2Y": "2年", "3Y": "3年",
        "5Y": "5年", "7Y": "7年", "10Y": "10年", "30Y": "30年",
    }

    # 收益率 + sparkline
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT period, date, value FROM yield_data
            WHERE period IN ({','.join(['%s'] * len(periods))})
              AND date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            ORDER BY period, date DESC
        """, periods)
        yrows = cur.fetchall()

    yd: Dict[str, List[Dict]] = {}
    for p, d, v in yrows:
        yd.setdefault(p, []).append({"date": d, "value": float(v)})

    yields = []
    for p in periods:
        pts = yd.get(p, [])
        if len(pts) < 2:
            continue
        latest = pts[0]
        prev = pts[1]
        diff = round((latest["value"] - prev["value"]) * 100, 1)
        dir_ = "up" if diff > 0 else ("down" if diff < 0 else "flat")
        spark_pts = sorted(pts, key=lambda x: x["date"])
        yields.append({
            "period": p, "label": labels.get(p, p),
            "value": latest["value"], "diff_bp": diff, "direction": dir_,
            "sparkline": {
                "dates": [sp["date"].strftime("%m-%d") if hasattr(sp["date"], "strftime") else str(sp["date"]) for sp in spark_pts],
                "values": [sp["value"] for sp in spark_pts],
            },
        })

    spread = None
    if "10Y" in yd and "2Y" in yd and len(yd["10Y"]) >= 2 and len(yd["2Y"]) >= 2:
        sv = round(yd["10Y"][0]["value"] - yd["2Y"][0]["value"], 4)
        sp = round(yd["10Y"][1]["value"] - yd["2Y"][1]["value"], 4)
        sd = round((sv - sp) * 100, 1)
        spread = {"value": sv, "diff_bp": sd, "direction": "up" if sd > 0 else ("down" if sd < 0 else "flat")}

    # 因子（近7天）
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT f.id, f.name, f.category, COUNT(nf.news_id) AS cnt
            FROM news_factor nf JOIN factor f ON nf.factor_id = f.id
            JOIN news n ON nf.news_id = n.id
            WHERE n.pub_time >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY f.id, f.name, f.category ORDER BY cnt DESC LIMIT 5
        """)
        fr = cur.fetchall()
    max_c = max((r[3] for r in fr), default=1)
    factors = [{"id": r[0], "name": r[1] or "", "category": r[2] or "", "news_count": r[3], "activity_score": round(r[3] / max_c, 2)} for r in fr]

    # AI 摘要：取 trade_date 最大 + id 最大的行
    ai_summary = None
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT trade_date, prediction FROM forecast_report ORDER BY trade_date DESC, id DESC LIMIT 1"
            )
            frr = cur.fetchone()
            logger.info("discover/market-panel ai_summary: trade_date=%s", frr[0] if frr else "None")

        if frr and frr[1]:
            raw = frr[1]
            pred = json.loads(raw) if isinstance(raw, str) else (raw or {})
            if isinstance(pred, dict):
                text = str(pred.get("市场概览") or pred.get("报告摘要") or "")
                drivers: List[str] = []
                overview = str(pred.get("市场概览", ""))
                if overview:
                    raw_drivers = re.findall(r"[1-9]\s*[、.)]\s*(.+?)(?=[\n\r]|$)", overview)
                    # 过滤掉数据统计行（包含 bp、波动率、收益率 等纯数据描述）
                    for d in raw_drivers:
                        d_clean = d.strip()
                        if re.search(r'[\d.]+\s*bp|变动.*bp|波动率[\d.]+$|^\d+\.?\d*%', d_clean):
                            continue
                        drivers.append(d_clean)
                if not drivers:
                    strategy = str(pred.get("策略建议", ""))
                    if strategy:
                        raw_drivers = re.findall(r"[1-9]\s*[、.)]\s*(.+?)(?=[\n\r]|$)", strategy)
                        for d in raw_drivers:
                            d_clean = d.strip()
                            if re.search(r'[\d.]+\s*bp|变动.*bp|波动率[\d.]+$', d_clean):
                                continue
                            drivers.append(d_clean)

                direction = "neutral"
                if text:
                    if any(w in text for w in ["收益率下行", "债市走强", "整体下行", "普遍下行"]):
                        direction = "bullish"
                    elif any(w in text for w in ["收益率上行", "债市走弱", "整体上行", "普遍上行"]):
                        direction = "bearish"

                # 过滤纯数据行（如"1.71%、5日变动+0.00bp..."）
                if text.strip():
                    cleaned_lines = []
                    for line in text.split('\n'):
                        stripped = line.strip()
                        if re.match(r'^[\d.]+%.*[\d.]+bp', stripped):
                            continue
                        cleaned_lines.append(stripped)
                    cleaned_text = '\n'.join(cleaned_lines).strip()
                    if not cleaned_text:
                        cleaned_text = str(pred.get("报告摘要") or "")
                    if cleaned_text:
                        ai_summary = {
                            "date": str(frr[0]) if frr[0] else "",
                            "text": cleaned_text[:600],
                            "direction": direction,
                            "drivers": drivers[:3],
                        }
    except Exception as e:
        logger.warning("discover/market-panel ai_summary failed: %s", e)

    # 策略信号（取最新推荐中的前3条）
    strategy_signals = []
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT outcome, analysis_date FROM ai_strategy_recommendation ORDER BY analysis_date DESC, id DESC LIMIT 1"
            )
            srr = cur.fetchone()

        if srr and srr[0]:
            out = json.loads(srr[0]) if isinstance(srr[0], str) else (srr[0] or {})
            if isinstance(out, dict):
                recs = out.get("recommendations") or []
                for rec in recs[:3]:
                    if not isinstance(rec, dict):
                        continue
                    strategy_name = (
                        (rec.get("strategy") or {}).get("name", "")
                        or rec.get("target", {}).get("name", "")
                    )
                    if not strategy_name:
                        strategy_name = str(rec.get("reason", ""))[:40]

                    reason = rec.get("reason", "")
                    risk = rec.get("risk_level", "")
                    drivers = [reason] if reason else []
                    if risk:
                        drivers.insert(0, f"风险等级：{risk}")

                    priority = rec.get("priority", 1)
                    confidence = max(0.3, round(1.0 - (priority - 1) * 0.2, 2))

                    if strategy_name:
                        strategy_signals.append({
                            "recommendation": strategy_name,
                            "confidence": confidence,
                            "reasons": drivers[:2],
                            "analysis_date": str(srr[1]) if srr[1] else "",
                        })
    except Exception as e:
        logger.warning("discover/market-panel strategy_signal failed: %s", e)

    return {
        "yields": {"items": yields, "spread_10y2y": spread, "update_date": datetime.now().strftime("%Y-%m-%d")},
        "factors": factors,
        "ai_summary": ai_summary,
        "strategy_signals": strategy_signals,
    }


# ── 3. 收益率详情 ────────────────────────────────────────────────────

@router.get("/discover/yield-detail")
def yield_detail(period: str = Query("10Y")):
    p_label = {
        "3M": "3月", "6M": "6月", "1Y": "1年", "2Y": "2年", "3Y": "3年",
        "5Y": "5年", "7Y": "7年", "10Y": "10年", "30Y": "30年",
    }.get(period, period)

    with get_db_connection() as conn:
        cur = conn.cursor()
        # 30 天 sparkline
        cur.execute(
            "SELECT date, value FROM yield_data WHERE period=%s AND date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY) ORDER BY date DESC",
            (period,),
        )
        pts = cur.fetchall()
        if not pts:
            return {"error": "No data"}

        latest = float(pts[0][1])
        prev = float(pts[1][1]) if len(pts) > 1 else latest
        diff = round((latest - prev) * 100, 1)
        direction = "up" if diff > 0 else ("down" if diff < 0 else "flat")
        spark_dates = [p[0].strftime("%m-%d") if hasattr(p[0], "strftime") else str(p[0]) for p in reversed(pts)]
        spark_vals = [float(p[1]) for p in reversed(pts)]

        # 关键指标：债券专用指标
        all_vals = [float(p[1]) for p in pts]
        prev_close = round(all_vals[1], 3) if len(all_vals) > 1 else None
        day_high = round(max(all_vals), 3)
        day_low = round(min(all_vals), 3)
        ma_30 = round(sum(all_vals) / len(all_vals), 3)
        # 30日波动率（标准差 / 均值）
        import math
        mean = ma_30
        variance = sum((v - mean) ** 2 for v in all_vals) / len(all_vals)
        volatility = round(math.sqrt(variance) * 100, 2)  # 以bp表示

        # 52 周高/低
        cur.execute(
            "SELECT MAX(value), MIN(value) FROM yield_data WHERE period=%s AND date >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)",
            (period,),
        )
        w52 = cur.fetchone()
        w52_high = round(float(w52[0]), 3) if w52 and w52[0] else None
        w52_low = round(float(w52[1]), 3) if w52 and w52[1] else None

        key_metrics = []
        if prev_close is not None:
            key_metrics.append({"label": "前一收盘", "value": f"{prev_close:.3f}%"})
        key_metrics.append({"label": "30日均值", "value": f"{ma_30:.3f}%"})
        key_metrics.append({"label": "日内波幅", "value": f"{(day_high - day_low):.3f}%"})
        key_metrics.append({"label": "30日波动率", "value": f"{volatility:.2f}bp"})
        if w52_high is not None:
            key_metrics.append({"label": "52周最高", "value": f"{w52_high:.3f}%"})
        if w52_low is not None:
            key_metrics.append({"label": "52周最低", "value": f"{w52_low:.3f}%"})

        # 显著变动日期：近7天每天bp变化绝对值，取top 5，关联当日方向性新闻
        cur.execute(
            "SELECT date, value FROM yield_data WHERE period=%s AND date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY) ORDER BY date",
            (period,),
        )
        all_pts = cur.fetchall()
        daily_changes = []
        for i in range(1, len(all_pts)):
            d = all_pts[i][0]
            v = float(all_pts[i][1])
            pv = float(all_pts[i - 1][1])
            ch = round((v - pv) * 100, 1)
            daily_changes.append({
                "date": d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d),
                "value": v,
                "diff_bp": ch,
                "direction": "up" if ch > 0 else ("down" if ch < 0 else "flat"),
            })
        daily_changes.sort(key=lambda x: abs(x["diff_bp"]), reverse=True)
        # 过滤掉 0bp 变化，取 top 5
        top_changes = [dc for dc in daily_changes if abs(dc["diff_bp"]) >= 0.1][:5]
        top_changes.sort(key=lambda x: x["date"], reverse=True)

        # 为显著日期关联新闻（含未分析新闻，LEFT JOIN；按最佳模型取方向）
        for tc in top_changes:
            cur.execute(
                f"""SELECT n.id, n.title, a.direction
                   FROM news n {_BEST_ANALYSIS_JOIN}
                   WHERE DATE(n.pub_time) BETWEEN DATE_SUB(%s, INTERVAL 1 DAY) AND DATE_ADD(%s, INTERVAL 1 DAY)
                   ORDER BY n.pub_time DESC LIMIT 5""",
                (tc["date"], tc["date"]),
            )
            news_rows = cur.fetchall()
            # 只保留明确的方向性新闻（过滤掉 neutral / 无方向）并映射为前端约定的 positive/negative
            filtered = []
            for r in news_rows:
                md = _map_direction(r[2])
                if not md:
                    continue
                filtered.append({"id": r[0], "title": r[1] or "", "direction": md})
            tc["news"] = filtered

    return {
        "period": period,
        "label": p_label,
        "value": latest,
        "diff_bp": diff,
        "direction": direction,
        "sparkline": {"dates": spark_dates, "values": spark_vals},
        "key_metrics": key_metrics,
        "significant_dates": top_changes,
        "update_date": datetime.now().strftime("%Y-%m-%d"),
    }


# ── 4. 因子详情 ────────────────────────────────────────────────────

@router.get("/discover/factor-detail")
def factor_detail(factor_id: int = Query(...)):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, code, name, category, factor_type FROM factor WHERE id=%s",
            (factor_id,),
        )
        fr = cur.fetchone()
        if not fr:
            return {"error": "Factor not found"}

        fid, fcode, fname, fcat, factor_type = fr

        # Use the factor's latest available news as the detail-window anchor.
        # This keeps historical datasets from rendering an empty detail panel.
        cur.execute(
            """SELECT MAX(DATE(nf.pub_time))
               FROM news_factor nf
               WHERE nf.factor_id=%s""",
            (fid,),
        )
        latest_news_date = cur.fetchone()[0]
        if latest_news_date is None:
            return {
                "id": fid,
                "code": fcode or "",
                "name": fname or "",
                "category": fcat or "",
                "factor_type": factor_type or "",
                "news_count": 0,
                "activity_score": 0,
                "activity_7d": 0,
                "activity_30d": 0,
                "activity_365d": 0,
                "activity_change_7d": 0,
                "current_direction": "中性",
                "heat_level": "低",
                "latest_event_at": None,
                "direction_counts": {"positive": 0, "negative": 0, "neutral": 0},
                "trend_series": {"7d": [], "30d": [], "365d": []},
                "insight": "暂无关联事件，暂时无法判断该因子的市场方向。",
                "daily_counts": [],
                "related_news": [],
                "related_factors": [],
            }

        # 7 天逐日新闻计数
        anchor_date = latest_news_date.date() if isinstance(latest_news_date, datetime) else latest_news_date
        if isinstance(anchor_date, str):
            anchor_date = date.fromisoformat(anchor_date[:10])

        cur.execute(
            f"""SELECT COALESCE(n.pub_time, nf.pub_time),
                       COALESCE(a.direction, nf.direction)
                FROM news_factor nf
                LEFT JOIN news n ON nf.news_id = n.id
                {_BEST_ANALYSIS_JOIN}
                WHERE nf.factor_id=%s
                  AND DATE(COALESCE(n.pub_time, nf.pub_time))
                      BETWEEN DATE_SUB(%s, INTERVAL 364 DAY) AND %s
                ORDER BY COALESCE(n.pub_time, nf.pub_time)""",
            (fid, anchor_date, anchor_date),
        )
        events = []
        for event_time, direction in cur.fetchall():
            event_date = event_time.date() if isinstance(event_time, datetime) else event_time
            if isinstance(event_date, str):
                event_date = date.fromisoformat(event_date[:10])
            events.append((event_date, _map_direction(direction, default="neutral")))

        def make_daily_series(days: int):
            start_date = anchor_date - timedelta(days=days - 1)
            buckets = {
                start_date + timedelta(days=offset): {"positive": 0, "negative": 0, "neutral": 0}
                for offset in range(days)
            }
            for event_date, direction in events:
                if event_date in buckets:
                    buckets[event_date][direction] += 1
            return [
                {"date": str(bucket_date), **counts, "total": sum(counts.values())}
                for bucket_date, counts in buckets.items()
            ]

        month_keys = []
        month_year, month_value = anchor_date.year, anchor_date.month
        for _ in range(12):
            month_keys.append(f"{month_year:04d}-{month_value:02d}")
            month_value -= 1
            if month_value == 0:
                month_value = 12
                month_year -= 1
        month_keys.reverse()
        monthly_buckets = {
            key: {"positive": 0, "negative": 0, "neutral": 0} for key in month_keys
        }
        for event_date, direction in events:
            month_key = event_date.strftime("%Y-%m")
            if month_key in monthly_buckets:
                monthly_buckets[month_key][direction] += 1
        yearly_series = [
            {"date": key, **counts, "total": sum(counts.values())}
            for key, counts in monthly_buckets.items()
        ]

        seven_day_series = make_daily_series(7)
        thirty_day_series = make_daily_series(30)
        activity_7d = sum(point["total"] for point in seven_day_series)
        activity_30d = sum(point["total"] for point in thirty_day_series)
        activity_365d = len(events)
        previous_7d_start = anchor_date - timedelta(days=13)
        previous_7d_end = anchor_date - timedelta(days=7)
        previous_7d = sum(
            1 for event_date, _ in events if previous_7d_start <= event_date <= previous_7d_end
        )
        activity_change_7d = (
            round((activity_7d - previous_7d) / previous_7d * 100)
            if previous_7d
            else (None if activity_7d else 0)
        )
        direction_counts = {
            key: sum(point[key] for point in thirty_day_series)
            for key in ("positive", "negative", "neutral")
        }
        if direction_counts["positive"] > direction_counts["negative"]:
            current_direction = "利多"
        elif direction_counts["negative"] > direction_counts["positive"]:
            current_direction = "利空"
        else:
            current_direction = "中性"
        heat_level = "低" if activity_30d == 0 else ("高" if activity_30d >= 5 else "中")
        max_daily = max((point["total"] for point in seven_day_series), default=1)
        activity_score = round(activity_7d / max(max_daily * 7, 1), 2)
        daily = [{"date": point["date"], "count": point["total"]} for point in seven_day_series]

        # 关联新闻（带方向 + 摘要）
        cur.execute(
            f"""SELECT nf.news_id,
                      COALESCE(NULLIF(n.title, ''), NULLIF(nf.driver, ''), CONCAT('关联事件 #', nf.news_id)),
                      COALESCE(n.pub_time, nf.pub_time),
                      COALESCE(a.direction, nf.direction),
                      COALESCE(a.reason, nf.driver)
               FROM news_factor nf
               LEFT JOIN news n ON nf.news_id = n.id
               {_BEST_ANALYSIS_JOIN}
               WHERE nf.factor_id=%s
               ORDER BY nf.pub_time DESC LIMIT 40""",
            (fid,),
        )
        # 映射方向为 front-end 使用的 positive/negative/neutral
        related_news = []
        seen_news_ids = set()
        for r in cur.fetchall():
            if r[0] in seen_news_ids:
                continue
            seen_news_ids.add(r[0])
            related_news.append({
                "id": r[0],
                "title": r[1],
                "pub_time": r[2].strftime("%Y-%m-%d %H:%M:%S") if r[2] else "",
                "direction": _map_direction(r[3], default="neutral"),
                "reason": r[4] or "",
            })
            if len(related_news) == 20:
                break

        # 同类别相关因子
        cur.execute(
            """SELECT f2.id, f2.name, f2.category,
                      COUNT(DISTINCT nf2.news_id) AS shared_count
               FROM news_factor nf1
               JOIN news_factor nf2
                 ON nf1.news_id = nf2.news_id AND nf2.factor_id != nf1.factor_id
               JOIN factor f2 ON f2.id = nf2.factor_id
               WHERE nf1.factor_id=%s
               GROUP BY f2.id, f2.name, f2.category
               ORDER BY shared_count DESC, f2.name
               LIMIT 5""",
            (fid,),
        )
        related_factors = [
            {"id": r[0], "name": r[1], "category": r[2], "shared_count": int(r[3] or 0)}
            for r in cur.fetchall()
        ]

        direction_label = {"利多": "偏利多", "利空": "偏利空", "中性": "以中性影响为主"}[
            current_direction
        ]
        category_label = {
            "MACRO": "宏观经济",
            "POLICY": "政策与监管",
            "MARKET": "市场交易",
            "INDUSTRY": "行业产业",
            "SENTIMENT": "市场情绪",
            "CREDIT": "信用风险",
            "LIQUIDITY": "资金流动性",
            "GLOBAL": "海外市场",
        }.get(fcat, fcat or "综合")
        factor_type_label = "量化" if factor_type == "quantitative" else "概念"
        if activity_change_7d is None:
            change_summary = "近7日开始出现新的活跃事件"
        elif activity_change_7d > 0:
            change_summary = f"近7日事件数较前7日上升 {activity_change_7d}%"
        elif activity_change_7d < 0:
            change_summary = f"近7日事件数较前7日下降 {abs(activity_change_7d)}%"
        else:
            change_summary = "近7日事件数与前7日持平"
        insight = (
            f"{fname}属于{category_label}类{factor_type_label}因子，主要用于跟踪相关政策、"
            f"产业及市场事件，并观察其对债券市场定价的潜在影响。"
            f"近30日共关联 {activity_30d} 条事件，其中利多 {direction_counts['positive']} 条、"
            f"利空 {direction_counts['negative']} 条、中性 {direction_counts['neutral']} 条，"
            f"整体{direction_label}。{change_summary}，最近一次事件更新于"
            f" {anchor_date.strftime('%m月%d日')}。"
        )

    return {
        "id": fid,
        "code": fcode or "",
        "name": fname or "",
        "category": fcat or "",
        "factor_type": factor_type or "",
        "news_count": activity_7d,
        "activity_score": activity_score,
        "activity_7d": activity_7d,
        "activity_30d": activity_30d,
        "activity_365d": activity_365d,
        "activity_change_7d": activity_change_7d,
        "current_direction": current_direction,
        "heat_level": heat_level,
        "latest_event_at": str(anchor_date),
        "direction_counts": direction_counts,
        "trend_series": {
            "7d": seven_day_series,
            "30d": thirty_day_series,
            "365d": yearly_series,
        },
        "insight": insight,
        "daily_counts": daily,
        "related_news": related_news,
        "related_factors": related_factors,
    }
