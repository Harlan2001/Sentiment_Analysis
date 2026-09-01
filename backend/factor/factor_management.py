"""
因子管理模块
负责因子的查询、提示词生成与新增。
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

from backend.common.database import get_repo_connection

logger = logging.getLogger(__name__)


def get_factors_from_db() -> list:
    """从MySQL加载所有因子（使用上下文管理器，自动关闭连接）。

    附带每个因子的新闻活跃度：news_count（总新闻数）与 recent_news_count（近30天新闻数），
    供前端按活跃度排序、分类聚合。
    """
    now = datetime.now()
    cutoff_7d = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_30d = (now - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    cutoff_365d = (now - timedelta(days=365)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with get_repo_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT f.id, f.code, f.name, f.category, f.factor_type,
                           COUNT(nf.factor_id) AS news_count,
                           SUM(CASE WHEN nf.pub_time >= %s THEN 1 ELSE 0 END) AS activity_7d,
                           SUM(CASE WHEN nf.pub_time >= %s THEN 1 ELSE 0 END) AS activity_30d,
                           SUM(CASE WHEN nf.pub_time >= %s THEN 1 ELSE 0 END) AS activity_365d,
                           SUM(CASE WHEN nf.pub_time >= %s AND LOWER(COALESCE(nf.direction, ''))
                               IN ('positive', 'bullish', '利多', '利好', '涨') THEN 1 ELSE 0 END) AS positive_count,
                           SUM(CASE WHEN nf.pub_time >= %s AND LOWER(COALESCE(nf.direction, ''))
                               IN ('negative', 'bearish', '利空', '跌') THEN 1 ELSE 0 END) AS negative_count,
                           SUM(CASE WHEN nf.pub_time >= %s AND LOWER(COALESCE(nf.direction, ''))
                               NOT IN ('positive', 'bullish', '利多', '利好', '涨', 'negative', 'bearish', '利空', '跌')
                               THEN 1 ELSE 0 END) AS neutral_count,
                           MAX(nf.pub_time) AS latest_event_at
                    FROM factor f
                    LEFT JOIN news_factor nf ON nf.factor_id = f.id
                    GROUP BY f.id, f.code, f.name, f.category, f.factor_type
                    ORDER BY f.category, f.code
                    """,
                    (cutoff_7d, cutoff_30d, cutoff_365d, cutoff_30d, cutoff_30d, cutoff_30d),
                )
                rows = list(cursor.fetchall())

                cursor.execute(
                    """SELECT factor_id, DATE(pub_time) AS event_date, COUNT(*) AS event_count
                       FROM news_factor
                       WHERE pub_time >= %s
                       GROUP BY factor_id, DATE(pub_time)""",
                    ((now - timedelta(days=6)).strftime("%Y-%m-%d 00:00:00"),),
                )
                daily_by_factor: dict[int, dict[str, int]] = defaultdict(dict)
                for daily_row in cursor.fetchall():
                    daily_by_factor[daily_row["factor_id"]][str(daily_row["event_date"])] = daily_row["event_count"]

                activity_values = sorted(int(row.get("activity_30d") or 0) for row in rows)
                medium_index = max(0, len(activity_values) // 3)
                high_index = max(0, (len(activity_values) * 2) // 3)
                medium_cutoff = activity_values[medium_index] if activity_values else 0
                high_cutoff = activity_values[high_index] if activity_values else 0
                trend_dates = [(now.date() - timedelta(days=offset)).isoformat() for offset in range(6, -1, -1)]
                for row in rows:
                    row["news_count"] = row.get("news_count") or 0
                    row["activity_7d"] = int(row.get("activity_7d") or 0)
                    row["activity_30d"] = int(row.get("activity_30d") or 0)
                    row["activity_365d"] = int(row.get("activity_365d") or 0)
                    row["recent_news_count"] = row["activity_30d"]
                    row["positive_count"] = int(row.get("positive_count") or 0)
                    row["negative_count"] = int(row.get("negative_count") or 0)
                    row["neutral_count"] = int(row.get("neutral_count") or 0)
                    if row["positive_count"] > row["negative_count"]:
                        row["current_direction"] = "利多"
                    elif row["negative_count"] > row["positive_count"]:
                        row["current_direction"] = "利空"
                    else:
                        row["current_direction"] = "中性"
                    activity = row["activity_30d"]
                    row["heat_level"] = (
                        "低" if activity == 0
                        else "高" if activity >= high_cutoff
                        else "中" if activity >= medium_cutoff
                        else "低"
                    )
                    row["trend_7d"] = [daily_by_factor[row["id"]].get(day, 0) for day in trend_dates]
                    latest = row.get("latest_event_at")
                    row["latest_event_at"] = latest.strftime("%Y-%m-%d %H:%M:%S") if latest else None
                return rows
    except Exception as e:
        logger.error("加载因子失败: %s", e, exc_info=True)
        raise


def get_factors_paged(page: int = 1, page_size: int = 20) -> dict:
    """分页加载因子基础信息（不做新闻活跃度聚合，查询更快）。

    用于因子库首屏快速展示：仅返回 code/name/category/factor_type + 总数。
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size
    try:
        with get_repo_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS total FROM factor")
                total = cursor.fetchone()["total"] or 0
                cursor.execute(
                    """SELECT id, code, name, category, factor_type
                       FROM factor
                       ORDER BY category, code
                       LIMIT %s OFFSET %s""",
                    (page_size, offset),
                )
                rows = list(cursor.fetchall())
    except Exception as e:
        logger.error("分页加载因子失败: %s", e, exc_info=True)
        raise
    return {"factors": rows, "total": total, "page": page, "page_size": page_size}


def get_factor_prompt_text() -> str:
    """生成AI可读的因子列表"""
    categorized = defaultdict(list)
    for f in get_factors_from_db():
        categorized[f["category"]].append((f["code"], f["name"], f["factor_type"]))

    lines = []
    for category, factors in categorized.items():
        lines.append(f"\n【{category}】")
        quant = [f"{c}({n})" for c, n, t in factors if t == "quantitative"]
        concept = [f"{c}({n})" for c, n, t in factors if t == "conceptual"]
        if quant:
            lines.append(f"  Quantitative（量化）: {', '.join(quant)}")
        if concept:
            lines.append(f"  Conceptual（非量化）: {', '.join(concept)}")
    return "\n".join(lines)


def add_new_factor(category: str, code: str, name: str, factor_type: str) -> bool:
    """添加新因子（依赖 factor.code 唯一索引判重，重复插入返回 False）"""
    try:
        with get_repo_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO factor (code, name, category, factor_type) VALUES (%s,%s,%s,%s)",
                    (code, name, category, factor_type),
                )
            conn.commit()
        return True
    except Exception as e:
        logger.error("添加因子失败: %s", e, exc_info=True)
        return False
