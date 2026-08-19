"""
因子管理模块
负责因子的查询、提示词生成与新增。
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

import pymysql

from backend.config.config import MYSQL_CONFIG

logger = logging.getLogger(__name__)


def get_factors_from_db() -> list:
    """从MySQL加载所有因子（使用上下文管理器，自动关闭连接）。

    附带每个因子的新闻活跃度：news_count（总新闻数）与 recent_news_count（近30天新闻数），
    供前端按活跃度排序、分类聚合。
    """
    recent_cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        with pymysql.connect(**MYSQL_CONFIG) as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                cursor.execute(
                    """
                    SELECT f.id, f.code, f.name, f.category, f.factor_type,
                           COUNT(nf.factor_id) AS news_count,
                           SUM(CASE WHEN nf.pub_time >= %s THEN 1 ELSE 0 END) AS recent_news_count
                    FROM factor f
                    LEFT JOIN news_factor nf ON nf.factor_id = f.id
                    GROUP BY f.id, f.code, f.name, f.category, f.factor_type
                    ORDER BY f.category, f.code
                    """,
                    (recent_cutoff,),
                )
                rows = list(cursor.fetchall())
                for row in rows:
                    row["news_count"] = row.get("news_count") or 0
                    row["recent_news_count"] = row.get("recent_news_count") or 0
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
        with pymysql.connect(**MYSQL_CONFIG) as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
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
        with pymysql.connect(**MYSQL_CONFIG) as conn:
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
