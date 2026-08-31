"""新闻表数据查询。"""

from typing import Any, Dict, List, Optional

from backend.common.database import get_db_connection


class NewsQueries:
    """新闻表查询。"""

    @staticmethod
    def get_pending_news(limit: int = 100) -> List[int]:
        """
        获取待分析的新闻ID列表（analysis表中不存在对应news_id）

        Args:
            limit: 最多返回的数量

        Returns:
            新闻ID列表
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT n.id
                    FROM news n
                    WHERE NOT EXISTS (
                        SELECT 1 FROM analysis a WHERE a.news_id = n.id
                    )
                    ORDER BY n.pub_time ASC, n.id ASC
                    LIMIT %s
                """,
                    (limit,),
                )
                results = cur.fetchall()
                return [row[0] for row in results]
    @staticmethod
    def get_pending_news_by_mode(
        mode: str,
        model: str,
        limit: Optional[int] = 100,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        news_ids: Optional[List[int]] = None,
    ) -> List[Dict[str, Any]]:
        """根据执行模式获取待处理新闻。"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                conditions: List[str] = []
                params: List[Any] = []

                if mode == "model_missing":
                    # 只挑完全没有分析记录的新闻（任何模型都没有），
                    # 避免历史旧新闻被反复 re-analysis
                    conditions.append(
                        "NOT EXISTS (SELECT 1 FROM analysis a WHERE a.news_id = n.id)"
                    )
                elif mode != "force_rerun":
                    raise ValueError(f"不支持的 mode: {mode}")

                if start_time:
                    conditions.append("n.pub_time >= %s")
                    params.append(start_time)
                if end_time:
                    conditions.append("n.pub_time <= %s")
                    params.append(end_time)

                if news_ids:
                    placeholders = ",".join(["%s"] * len(news_ids))
                    conditions.append(f"n.id IN ({placeholders})")
                    params.extend(news_ids)

                where_clause = " AND ".join(conditions) if conditions else "1=1"

                sql = f"""
                    SELECT n.id, n.pub_time
                    FROM news n
                    WHERE {where_clause}
                    ORDER BY n.pub_time ASC, n.id ASC
                """
                if limit is not None:
                    sql += "\n                    LIMIT %s"
                    params.append(limit)

                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
                return [{"news_id": r[0], "pub_time": r[1]} for r in rows]
    @staticmethod
    def get_news_by_id(news_id: int) -> Optional[Dict]:
        """从数据库获取新闻信息"""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, title, content, DATE(pub_time) as publish_date FROM news WHERE id = %s",
                (news_id,),
            )
            row = cur.fetchone()

        if not row:
            return None

        return {
            "id": row[0],
            "title": row[1],
            "content": row[2],
            "publish_date": row[3],
        }
    @staticmethod
    def get_news_pub_dates() -> List[str]:
        """获取新闻发布日期去重列表（升序）。"""
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT DATE(pub_time) AS news_date
                    FROM news
                    WHERE pub_time IS NOT NULL
                    ORDER BY news_date ASC
                    """)
                rows = cur.fetchall()

        results: List[str] = []
        for row in rows:
            news_date = row[0]
            results.append(news_date.strftime("%Y-%m-%d"))
        return results
    @staticmethod
    def get_news_pub_dates_in_range(
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[str]:
        """按日期范围获取新闻发布日期去重列表（升序，闭区间）。"""
        conditions: List[str] = ["pub_time IS NOT NULL"]
        params: List[Any] = []

        if start_date:
            conditions.append("DATE(pub_time) >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("DATE(pub_time) <= %s")
            params.append(end_date)

        where_clause = " AND ".join(conditions)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT DISTINCT DATE(pub_time) AS news_date
                    FROM news
                    WHERE {where_clause}
                    ORDER BY news_date ASC
                    """,
                    tuple(params),
                )
                rows = cur.fetchall()

        results: List[str] = []
        for row in rows:
            news_date = row[0]
            results.append(news_date.strftime("%Y-%m-%d"))
        return results
