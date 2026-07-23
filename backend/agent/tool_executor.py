"""
工具执行器模块

将 tool name 映射到实际的数据库查询 / API 调用函数。
所有函数返回 dict，异常不抛出，返回 {"error": "..."} 。
"""

import logging
from datetime import datetime, timedelta

from backend.common.database import execute_query, get_db_connection
from backend.common.db_operations import DBOperations
from backend.common.vector_store import get_faiss_store
from backend.factor.factor_management import get_factors_from_db
from backend.macrosignal.macro_signal import get_macro_signal
from backend.config.config import PERIOD_MAP

logger = logging.getLogger(__name__)

# 工具结果截断上限
MAX_RESULT_ITEMS = 20


def _truncate_results(items: list, max_count: int = MAX_RESULT_ITEMS) -> dict:
    """截断结果列表，附带计数摘要。"""
    total = len(items)
    truncated = items[:max_count]
    if total > max_count:
        return {
            "items": truncated,
            "count": len(truncated),
            "total": total,
            "truncated": True,
            "summary": f"共 {total} 条结果，显示前 {max_count} 条",
        }
    return {"items": truncated, "count": total, "total": total, "truncated": False}


# ═══════════════════════════════════════════════════════════════════════
# 新闻类工具
# ═══════════════════════════════════════════════════════════════════════

def execute_search_news(keyword: str, limit: int = 10) -> dict:
    """按关键词搜索新闻（标题 + 内容模糊匹配）。"""
    try:
        effective_limit = min(max(1, limit), 30)
        keyword_pattern = f"%{keyword}%"

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT n.id, n.title, n.pub_time, n.source,
                       COALESCE(a.direction, '中性') AS direction,
                       COALESCE(a.horizon, '短期') AS horizon,
                       COALESCE(SUBSTRING(a.reason, 1, 200), '') AS reason_summary
                FROM news n
                LEFT JOIN analysis a ON a.news_id = n.id
                    AND a.model = (
                        SELECT a2.model FROM analysis a2 WHERE a2.news_id = n.id
                        ORDER BY CASE a2.model
                            WHEN 'doubao' THEN 0
                            WHEN 'deepseek' THEN 1
                            WHEN 'qwen' THEN 2
                            ELSE 3 END
                        LIMIT 1
                    )
                WHERE n.title LIKE %s OR n.content LIKE %s
                ORDER BY n.pub_time DESC
                LIMIT %s
                """,
                (keyword_pattern, keyword_pattern, effective_limit),
            )
            rows = cur.fetchall()

        results = [
            {
                "id": r[0],
                "title": r[1],
                "pub_time": str(r[2]) if r[2] else None,
                "source": r[3],
                "direction": r[4],
                "horizon": r[5],
                "reason_summary": r[6],
            }
            for r in rows
        ]
        return _truncate_results(results, effective_limit)
    except Exception as exc:
        logger.exception("search_news 执行失败")
        return {"error": f"新闻搜索失败: {str(exc)}"}


def execute_get_news_by_date(date: str, sources: list | None = None, limit: int = 20) -> dict:
    """获取指定日期的新闻列表。"""
    try:
        effective_limit = min(max(1, limit), 50)
        params: list = [date]

        source_filter = ""
        if sources:
            placeholders = ",".join(["%s" for _ in sources])
            source_filter = f"AND n.source IN ({placeholders})"
            params.extend(sources)

        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                SELECT n.id, n.title, n.pub_time, n.source,
                       COALESCE(a.direction, '中性') AS direction,
                       COALESCE(a.horizon, '短期') AS horizon,
                       COALESCE(SUBSTRING(a.reason, 1, 200), '') AS reason_summary
                FROM news n
                LEFT JOIN analysis a ON a.news_id = n.id
                    AND a.model = (
                        SELECT a2.model FROM analysis a2 WHERE a2.news_id = n.id
                        ORDER BY CASE a2.model
                            WHEN 'doubao' THEN 0
                            WHEN 'deepseek' THEN 1
                            WHEN 'qwen' THEN 2
                            ELSE 3 END
                        LIMIT 1
                    )
                WHERE DATE(n.pub_time) = %s {source_filter}
                ORDER BY n.pub_time DESC
                LIMIT %s
                """,
                (*params, effective_limit),
            )
            rows = cur.fetchall()

        results = [
            {
                "id": r[0],
                "title": r[1],
                "pub_time": str(r[2]) if r[2] else None,
                "source": r[3],
                "direction": r[4],
                "horizon": r[5],
                "reason_summary": r[6],
            }
            for r in rows
        ]
        return {
            "date": date,
            **_truncate_results(results, effective_limit),
        }
    except Exception as exc:
        logger.exception("get_news_by_date 执行失败")
        return {"error": f"获取新闻失败: {str(exc)}"}


def execute_get_news_detail(news_id: int) -> dict:
    """获取单条新闻的完整详情（含因子）。"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()

            # 获取新闻基本信息
            cur.execute(
                """
                SELECT n.id, n.title, n.content, n.pub_time, n.source, n.url
                FROM news n WHERE n.id = %s
                """,
                (news_id,),
            )
            row = cur.fetchone()
            if not row:
                return {"error": f"新闻 ID {news_id} 不存在"}

            news = {
                "id": row[0],
                "title": row[1],
                "content": (row[2] or "")[:2000],  # 截断长内容
                "pub_time": str(row[3]) if row[3] else None,
                "source": row[4],
                "url": row[5],
            }

            # 获取分析结果
            cur.execute(
                """
                SELECT direction, horizon, reason, model
                FROM analysis WHERE news_id = %s
                ORDER BY CASE model
                    WHEN 'doubao' THEN 0 WHEN 'deepseek' THEN 1
                    WHEN 'qwen' THEN 2 ELSE 3 END
                LIMIT 1
                """,
                (news_id,),
            )
            analysis_row = cur.fetchone()
            if analysis_row:
                news["analysis"] = {
                    "direction": analysis_row[0] or "中性",
                    "horizon": analysis_row[1] or "短期",
                    "reason": (analysis_row[2] or "")[:500],
                    "model": analysis_row[3],
                }

            # 获取关联因子
            cur.execute(
                """
                SELECT f.code, f.name, f.category, nf.direction
                FROM news_factor nf
                JOIN factor f ON nf.factor_id = f.id
                WHERE nf.news_id = %s
                """,
                (news_id,),
            )
            factor_rows = cur.fetchall()
            news["factors"] = [
                {"code": fr[0], "name": fr[1], "category": fr[2], "direction": fr[3]}
                for fr in factor_rows
            ]

        return news
    except Exception as exc:
        logger.exception("get_news_detail 执行失败")
        return {"error": f"获取新闻详情失败: {str(exc)}"}


def execute_find_similar_news(news_id: int, top_k: int = 5) -> dict:
    """通过 FAISS 向量搜索相似新闻。"""
    try:
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT content FROM news WHERE id=%s", (news_id,))
            row = cur.fetchone()
            if not row:
                return {"error": f"新闻 ID {news_id} 不存在"}

            content = row[0]
            if not content:
                return {"error": f"新闻 ID {news_id} 内容为空，无法进行语义搜索"}

            store = get_faiss_store()
            query_emb = store.model.encode(
                [content], normalize_embeddings=True, convert_to_numpy=True
            ).astype("float32")
            results = store.search_by_vector(query_emb, top_k + 1)

            out = []
            for item in results:
                nid = item["news_id"]
                score = item["score"]
                if nid == news_id:
                    continue
                cur.execute("SELECT title FROM news WHERE id=%s", (nid,))
                title_row = cur.fetchone()
                if title_row:
                    out.append({
                        "news_id": nid,
                        "title": title_row[0],
                        "similarity_score": round(float(score), 4),
                    })

        return _truncate_results(out[:top_k], top_k)
    except Exception as exc:
        logger.exception("find_similar_news 执行失败")
        return {"error": f"相似新闻搜索失败: {str(exc)}"}


# ═══════════════════════════════════════════════════════════════════════
# 因子类工具
# ═══════════════════════════════════════════════════════════════════════

def execute_list_factors(category: str | None = None) -> dict:
    """列出所有可用因子，可选按类别过滤。"""
    try:
        factors = get_factors_from_db()
        if category:
            category_upper = category.upper()
            factors = [f for f in factors if f.get("category", "").upper() == category_upper]

        result = [
            {
                "code": f["code"],
                "name": f["name"],
                "category": f["category"],
                "factor_type": f["factor_type"],
            }
            for f in factors
        ]
        return {
            "factors": result,
            "count": len(result),
            "category_filter": category,
        }
    except Exception as exc:
        logger.exception("list_factors 执行失败")
        return {"error": f"获取因子列表失败: {str(exc)}"}


def execute_get_news_by_factor(factor_code: str, limit: int = 20) -> dict:
    """获取与指定因子关联的新闻。"""
    try:
        effective_limit = min(max(1, limit), MAX_RESULT_ITEMS)

        with get_db_connection() as conn:
            cur = conn.cursor()

            # 查询因子信息
            cur.execute(
                "SELECT id, name, category FROM factor WHERE code = %s",
                (factor_code,),
            )
            factor_row = cur.fetchone()
            if not factor_row:
                return {"error": f"因子代码 {factor_code} 不存在"}

            factor_id = factor_row[0]

            # 查询关联新闻
            cur.execute(
                """
                SELECT n.id, n.title, n.pub_time,
                       COALESCE(a.direction, '中性') AS direction,
                       COALESCE(a.horizon, '短期') AS horizon
                FROM news_factor nf
                JOIN news n ON nf.news_id = n.id
                LEFT JOIN analysis a ON a.news_id = n.id
                    AND a.model = (
                        SELECT a2.model FROM analysis a2 WHERE a2.news_id = n.id
                        ORDER BY CASE a2.model
                            WHEN 'doubao' THEN 0 WHEN 'deepseek' THEN 1
                            WHEN 'qwen' THEN 2 ELSE 3 END
                        LIMIT 1
                    )
                WHERE nf.factor_id = %s
                ORDER BY n.pub_time DESC
                LIMIT %s
                """,
                (factor_id, effective_limit),
            )
            rows = cur.fetchall()

        return {
            "factor": {
                "code": factor_code,
                "name": factor_row[1],
                "category": factor_row[2],
            },
            **_truncate_results(
                [
                    {
                        "id": r[0],
                        "title": r[1],
                        "pub_time": str(r[2]) if r[2] else None,
                        "direction": r[3],
                        "horizon": r[4],
                    }
                    for r in rows
                ],
                effective_limit,
            ),
        }
    except Exception as exc:
        logger.exception("get_news_by_factor 执行失败")
        return {"error": f"获取因子关联新闻失败: {str(exc)}"}


# ═══════════════════════════════════════════════════════════════════════
# 宏观信号工具
# ═══════════════════════════════════════════════════════════════════════

def execute_compute_macro_signal(
    factor_code: str,
    start_time: str,
    end_time: str,
    signal_type: str = "directional",
    decay_lambda: float = 0.1,
) -> dict:
    """计算宏观信号。"""
    try:
        codes = [c.strip() for c in factor_code.split(",") if c.strip()]
        if not codes:
            return {"error": "factor_code 不能为空"}

        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)

        if signal_type not in ("presence", "directional"):
            return {"error": f"signal_type 必须是 presence 或 directional，收到: {signal_type}"}

        results = get_macro_signal(
            factor_codes=codes,
            start_time=start_dt,
            end_time=end_dt,
            signal_type=signal_type,
            decay_lambda=decay_lambda,
        )

        return {
            "signal_type": signal_type,
            "decay_lambda": decay_lambda,
            "results": results,
            "count": len(results),
        }
    except ValueError as exc:
        return {"error": f"时间格式错误，请使用 ISO 格式: {str(exc)}"}
    except Exception as exc:
        logger.exception("compute_macro_signal 执行失败")
        return {"error": f"计算宏观信号失败: {str(exc)}"}


# ═══════════════════════════════════════════════════════════════════════
# 市场数据工具
# ═══════════════════════════════════════════════════════════════════════

def execute_get_yield_curve(start_date: str, end_date: str, period: str = "10年") -> dict:
    """获取收益率曲线数据。"""
    try:
        data = DBOperations.get_yield_series_by_period(start_date, end_date, period)
        if not data:
            return {
                "period": period,
                "data": [],
                "count": 0,
                "note": "该时间范围内无数据，请检查日期范围或期限参数",
            }

        return {
            "period": period,
            "data": data,
            "count": len(data),
            "latest": data[-1] if data else None,
            "earliest": data[0] if data else None,
        }
    except Exception as exc:
        logger.exception("get_yield_curve 执行失败")
        return {"error": f"获取收益率数据失败: {str(exc)}"}


# ═══════════════════════════════════════════════════════════════════════
# 执行器调度表
# ═══════════════════════════════════════════════════════════════════════

TOOL_EXECUTORS: dict[str, callable] = {
    "search_news": execute_search_news,
    "get_news_by_date": execute_get_news_by_date,
    "get_news_detail": execute_get_news_detail,
    "find_similar_news": execute_find_similar_news,
    "list_factors": execute_list_factors,
    "get_news_by_factor": execute_get_news_by_factor,
    "compute_macro_signal": execute_compute_macro_signal,
    "get_yield_curve": execute_get_yield_curve,
}
