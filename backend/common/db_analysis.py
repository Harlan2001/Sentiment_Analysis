"""新闻 AI 分析结果与模型优先级查询。"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import pymysql

from backend.common.database import get_db_connection
from backend.config.config import ANALYSIS_MODEL_PRIORITY, MYSQL_CONFIG


class AnalysisQueries:
    """AI 分析结果与模型优先级查询。"""

    @staticmethod
    def save_analysis_result(
        news_id: int,
        analysis_result: Dict[str, Any],
        model: str,
        conn: Optional[Any] = None,
    ) -> bool:
        """
        保存分析结果到analysis表

        Args:
            news_id: 新闻ID
            analysis_result: 分析结果字典
            model: 模型名称
            conn: 外部数据库连接，用于事务

        Returns:
            是否保存成功
        """
        external_conn = conn is not None
        if conn is None:
            conn = pymysql.connect(**MYSQL_CONFIG)

        try:
            with conn.cursor() as cur:
                direction = analysis_result.get("direction", "中性")
                horizon = analysis_result.get("horizon", "短期")
                reason = analysis_result.get("reason", "")

                cur.execute(
                    """
                    INSERT INTO analysis
                    (news_id, direction, horizon, reason, model, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        direction = VALUES(direction),
                        horizon = VALUES(horizon),
                        reason = VALUES(reason),
                        created_at = VALUES(created_at)
                """,
                    (news_id, direction, horizon, reason, model, datetime.now()),
                )

                if not external_conn:
                    conn.commit()
                return True

        except Exception as e:
            if not external_conn:
                conn.rollback()
            raise e
        finally:
            if not external_conn:
                conn.close()
    @staticmethod
    def get_analysis_exists(news_id: int, model: Optional[str] = None) -> bool:
        """
        检查新闻是否已有对应模型的分析结果（model 为空时检查任意模型）。

        Args:
            news_id: 新闻ID
            model: 模型名称，指定时只判断该模型是否已分析过
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                if model:
                    cur.execute(
                        """
                        SELECT 1 FROM analysis WHERE news_id = %s AND model = %s
                    """,
                        (news_id, model),
                    )
                else:
                    cur.execute(
                        """
                        SELECT 1 FROM analysis WHERE news_id = %s
                    """,
                        (news_id,),
                    )
                return cur.fetchone() is not None
    @staticmethod
    def get_news_analysis_by_date(report_date: str) -> List[Dict[str, Any]]:
        """按日期读取新闻与分析信息，不做文本裁剪。"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT n.title, n.content, a.direction, a.reason, a.horizon
                    FROM news n
                    LEFT JOIN analysis a ON n.id = a.news_id
                    WHERE DATE(n.pub_time) = %s
                    ORDER BY n.pub_time DESC
                    """,
                    (report_date,),
                )
                rows = cur.fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "title": row[0],
                    "content": row[1] or "",
                    "direction": row[2] or "中性",
                    "reason": row[3] or "",
                    "horizon": row[4] or "短期",
                }
            )
        return results
    @staticmethod
    def get_news_analysis_by_date_range(
        start_date: str,
        end_date: str,
        limit: int = 30,
    ) -> List[Dict[str, Any]]:
        """按日期范围读取新闻与分析信息，每条新闻取最高优先级模型的结果。

        使用 ANALYSIS_MODEL_PRIORITY 排序取最佳模型，自动去重（一条新闻一条分析）。
        返回按 pub_time 倒序排列。

        Args:
            start_date: 起始日期 YYYY-MM-DD（闭区间）
            end_date: 结束日期 YYYY-MM-DD（闭区间）
            limit: 最多返回条数

        Returns:
            新闻分析列表，每条含 title/content/pub_date/direction/horizon/reason/model
        """
        priority_cases = AnalysisQueries.priority_case_sql()

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT n.title, n.content, DATE(n.pub_time) AS pub_date,
                           COALESCE(a.direction, '中性') AS direction,
                           COALESCE(a.horizon, '短期') AS horizon,
                           COALESCE(a.reason, '') AS reason,
                           a.model
                    FROM news n
                    LEFT JOIN analysis a ON a.news_id = n.id
                        AND a.model = (
                            SELECT a2.model
                            FROM analysis a2
                            WHERE a2.news_id = n.id
                            ORDER BY CASE a2.model
                                {priority_cases}
                                ELSE 999
                            END
                            LIMIT 1
                        )
                    WHERE DATE(n.pub_time) BETWEEN %s AND %s
                    ORDER BY n.pub_time DESC
                    LIMIT %s
                    """,
                    (start_date, end_date, limit),
                )
                rows = cur.fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            pub_date = row[2]
            if hasattr(pub_date, "strftime"):
                pub_date = pub_date.strftime("%Y-%m-%d")
            results.append(
                {
                    "title": row[0],
                    "content": row[1] or "",
                    "pub_date": str(pub_date),
                    "direction": row[3],
                    "horizon": row[4],
                    "reason": row[5] or "",
                    "model": row[6] or "",
                }
            )
        return results
    @staticmethod
    def priority_case_sql() -> str:
        """生成模型优先级排序的 SQL CASE 子句。

        从 ANALYSIS_MODEL_PRIORITY 列表构建 CASE WHEN ... THEN ... 表达式，
        用于在关联查询中选取最高优先级模型的 analysis 记录。

        Returns:
            SQL CASE 片段，如 "WHEN 'glm' THEN 0 WHEN 'deepseek' THEN 1 ..."
        """
        return " ".join(
            [f"WHEN '{m}' THEN {i}" for i, m in enumerate(ANALYSIS_MODEL_PRIORITY)]
        )
