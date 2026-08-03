"""
数据库操作层
提供原子化的数据库操作接口，支持事务
"""

import json
import pymysql
from typing import List, Dict, Any, Optional, Tuple
from datetime import date, datetime, timedelta
from backend.common.database import get_db_connection
from backend.config.config import MYSQL_CONFIG, PERIOD_MAP, ANALYSIS_MODEL_PRIORITY
from backend.tools.portfolio_utils import format_datetime


class DBOperations:
    """数据库操作类
    """
    
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
                cur.execute("""
                    SELECT n.id
                    FROM news n
                    WHERE NOT EXISTS (
                        SELECT 1 FROM analysis a WHERE a.news_id = n.id
                    )
                    ORDER BY n.pub_time ASC, n.id ASC
                    LIMIT %s
                """, (limit,))
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
    def get_factor_id_by_code(factor_code: str) -> Optional[int]:
        """
        根据因子代码获取因子ID
        
        Args:
            factor_code: 因子代码
            
        Returns:
            因子ID，如果不存在返回None
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM factor WHERE code = %s
                """, (factor_code,))
                result = cur.fetchone()
                return result[0] if result else None
    
    @staticmethod
    def save_analysis_result(
        news_id: int, 
        analysis_result: Dict[str, Any], 
        model: str,
        conn: Optional[Any] = None
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
                
                cur.execute("""
                    INSERT INTO analysis 
                    (news_id, direction, horizon, reason, model, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        direction = VALUES(direction),
                        horizon = VALUES(horizon),
                        reason = VALUES(reason),
                        created_at = VALUES(created_at)
                """, (
                    news_id,
                    direction,
                    horizon,
                    reason,
                    model,
                    datetime.now()
                ))
                
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
    def save_news_factor_relation(
        news_id: int,
        factor_id: int,
        factor_data: Dict[str, Any],
        model: str,
        conn: Any
    ) -> bool:
        """
        保存新闻与因子的关联关系到news_factor表
        
        Args:
            news_id: 新闻ID
            factor_id: 因子ID
            factor_data: 因子数据字典
            model: 模型名称
            conn: 数据库连接（必须提供，用于事务）
        
        Returns:
            是否保存成功
        """
        try:
            with conn.cursor() as cur:
                direction = factor_data.get("direction", "neutral")
                logic_impact = factor_data.get("logic_impact", "")

                # 查询新闻发布时间用于冗余存储
                cur.execute("SELECT pub_time FROM news WHERE id = %s", (news_id,))
                row = cur.fetchone()
                pub_time = row[0] if row else None

                cur.execute("""
                    INSERT INTO news_factor 
                    (news_id, factor_id, direction, driver, model, created_at, pub_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        direction = VALUES(direction),
                        driver = VALUES(driver),
                        model = VALUES(model),
                        created_at = VALUES(created_at),
                        pub_time = VALUES(pub_time)
                """, (
                    news_id,
                    factor_id,
                    direction,
                    logic_impact,
                    model,
                    datetime.now(),
                    pub_time
                ))

            return True
        except Exception as e:
            raise e


    @staticmethod
    def get_analysis_exists(news_id: int, model: Optional[str] = None) -> bool:
        """
        检查新闻是否已经有分析结果
        
        Args:
            news_id: 新闻ID
            model: 模型名称（兼容参数，当前未使用）
            
        Returns:
            是否已存在分析结果
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 FROM analysis WHERE news_id = %s
                """, (news_id,))
                return cur.fetchone() is not None

    @staticmethod
    def get_news_by_id(news_id: int) -> Optional[Dict]:
        """从数据库获取新闻信息"""
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, title, content, DATE(pub_time) as publish_date FROM news WHERE id = %s", (news_id,)
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
                cur.execute(
                    """
                    SELECT DISTINCT DATE(pub_time) AS news_date
                    FROM news
                    WHERE pub_time IS NOT NULL
                    ORDER BY news_date ASC
                    """
                )
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
        priority_cases = DBOperations.priority_case_sql()

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
    def get_yield_series_by_period(
        start_date: str,
        end_date: str,
        period: str,
    ) -> List[Dict[str, Any]]:
        """获取指定时间范围和期限的收益率序列。"""
        db_period = PERIOD_MAP.get(period, period)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT date, value FROM yield_data
                    WHERE date >= %s AND date <= %s AND period = %s
                    ORDER BY date ASC
                    """,
                    (start_date, end_date, db_period),
                )
                rows = cur.fetchall()

        return [{"date": row[0], "value": float(row[1])} for row in rows]

    @staticmethod
    def get_yield_data_and_market_summary(
        end_date: str,
        lookback_days: int = 30,
        summary_days: int = 5,
        periods: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        一次查询同时返回收益率序列与市场摘要，避免重复读取 yield_data。

        - yield_data: [end_date-lookback_days, end_date]
        - market_summary: [end_date-summary_days, end_date]
        - periods: 支持中文名（如 "10年"）或 DB 码（如 "10Y"），自动通过 PERIOD_MAP 转换
        """
        if periods is None:
            periods = ["10年", "5年", "2年", "1年"]

        # 将期限名映射为数据库中的代码（如 "10年" → "10Y"），已为代码的保持不变
        db_periods = [PERIOD_MAP.get(p, p) for p in periods]
        # 反向映射：查询结果中 DB 码 → 中文名，用于返回一致的键名
        period_label_map = {db_p: p for p, db_p in zip(periods, db_periods)}

        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        lookback_start = (end_dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        summary_start = (end_dt - timedelta(days=summary_days)).strftime("%Y-%m-%d")

        placeholders = ",".join(["%s"] * len(db_periods))

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT period, date, value
                    FROM yield_data
                    WHERE date BETWEEN %s AND %s
                      AND period IN ({placeholders})
                    ORDER BY period ASC, date ASC
                    """,
                    tuple([lookback_start, end_date] + db_periods),
                )
                rows = cur.fetchall()

        yield_data: Dict[str, List[Dict[str, float]]] = {}
        summary_bucket: Dict[str, List[float]] = {p: [] for p in periods}

        for period, row_date, value in rows:
            # PyMySQL 返回 Decimal，转为 float 以便后续数学运算
            value_f = float(value)
            label = period_label_map.get(period, period)
            if label not in yield_data:
                yield_data[label] = []
            yield_data[label].append({"date": row_date, "value": value_f})

            row_date_str = row_date.strftime("%Y-%m-%d") if hasattr(row_date, "strftime") else str(row_date)
            if row_date_str >= summary_start:
                summary_bucket.setdefault(label, []).append(value_f)

        market_summary: Dict[str, Any] = {}
        for period in periods:
            values = summary_bucket.get(period, [])
            if len(values) < 2:
                continue

            latest = values[-1]
            first = values[0]
            change = latest - first
            change_pct = (change / first) * 100 if first != 0 else 0

            avg = sum(values) / len(values)
            variance = sum((v - avg) ** 2 for v in values) / len(values)
            volatility = variance ** 0.5

            market_summary[period] = {
                "latest": round(latest, 4),
                "change": round(change, 4),
                "change_pct": round(change_pct, 2),
                "volatility": round(volatility, 4),
                "trend": "上行" if change > 0 else "下行" if change < 0 else "平稳",
            }

        return {
            "yield_data": yield_data,
            "market_summary": market_summary,
        }

    # ====================== 投资组合策略缓存操作 ======================

    @staticmethod
    def priority_case_sql() -> str:
        """生成模型优先级排序的 SQL CASE 子句。

        从 ANALYSIS_MODEL_PRIORITY 列表构建 CASE WHEN ... THEN ... 表达式，
        用于在关联查询中选取最高优先级模型的 analysis 记录。

        Returns:
            SQL CASE 片段，如 "WHEN 'doubao' THEN 0 WHEN 'deepseek' THEN 1 ..."
        """
        return " ".join([f"WHEN '{m}' THEN {i}" for i, m in enumerate(ANALYSIS_MODEL_PRIORITY)])

    @staticmethod
    def get_news_reason_rows(
        target_news_date: date,
    ) -> Tuple[List[Dict[str, Any]], Optional[datetime]]:
        """按日期查询新闻及其 AI 分析原因（取最高优先级模型的结果）。

        从 news 与 analysis 表联表查询，按 ANALYSIS_MODEL_PRIORITY 取每条新闻
        的最高优先级模型的分析记录，仅返回 reason 非空的记录。

        Args:
            target_news_date: 目标新闻日期（date 对象）

        Returns:
            (新闻行列表, 最新新闻发布时间) 元组
                每条新闻行为 dict: news_id, title, pub_time, direction, reason, model
        """
        priority_cases = DBOperations.priority_case_sql()
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT n.id, n.title, n.pub_time,
                           COALESCE(a.direction, '') AS direction,
                           COALESCE(a.reason, '') AS reason,
                           a.model
                    FROM news n
                    JOIN analysis a ON a.news_id = n.id
                    WHERE DATE(n.pub_time) = %s
                      AND a.reason IS NOT NULL
                      AND TRIM(a.reason) <> ''
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
                    ORDER BY n.pub_time ASC
                    """,
                    (target_news_date,),
                )
                rows = cur.fetchall()

        items: List[Dict[str, Any]] = []
        latest_pub_time: Optional[datetime] = None
        for row in rows:
            pub_time = row[2]
            if isinstance(pub_time, datetime):
                latest_pub_time = pub_time if latest_pub_time is None else max(latest_pub_time, pub_time)
            items.append(
                {
                    "news_id": row[0],
                    "title": row[1],
                    "pub_time": row[2],
                    "direction": row[3],
                    "reason": row[4],
                    "model": row[5],
                }
            )
        return items, latest_pub_time

    @staticmethod
    def load_portfolio_strategy_cache(cache_key: str) -> Optional[Dict[str, Any]]:
        """从缓存表加载已成功的组合策略分析结果。

        Args:
            cache_key: 缓存键（MD5 哈希）

        Returns:
            命中的缓存数据字典（含 data/meta），未命中则返回 None
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT output_json, model_name, news_count, window_start, window_end,
                           latest_news_pub_time, latency_ms, request_id
                    FROM portfolio_strategy_analysis_cache
                    WHERE cache_key = %s AND status = 'success'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (cache_key,),
                )
                row = cur.fetchone()

        if not row:
            return None

        # 数据库中存储为 JSON 字符串，需要反序列化
        output_json = row[0]
        if isinstance(output_json, str):
            output_json = json.loads(output_json)

        return {
            "data": output_json,
            "meta": {
                "cache_hit": True,
                "model_name": row[1],
                "news_count": row[2] or 0,
                "window_start": format_datetime(row[3]),
                "window_end": format_datetime(row[4]),
                "latest_news_pub_time": format_datetime(row[5]),
                "latency_ms": row[6],
                "request_id": row[7],
            },
        }

    @staticmethod
    def upsert_portfolio_strategy_running(
        cache_key: str,
        target_news_date: date,
        model_name: str,
        request_id: str,
        news_ids: List[int],
        news_count: int,
        window_start: datetime,
        window_end: datetime,
        latest_news_pub_time: Optional[datetime],
    ) -> None:
        """写入或更新组合策略分析缓存状态为 'running'。

        使用 INSERT ... ON DUPLICATE KEY UPDATE 实现幂等写入，
        已存在相同 cache_key 的行将重置为 running 状态。

        Args:
            cache_key: 缓存键
            target_news_date: 目标新闻日期
            model_name: 使用的模型名称
            request_id: 本次请求 UUID
            news_ids: 新闻 ID 列表
            news_count: 新闻数量
            window_start: 时间窗口起始
            window_end: 时间窗口结束
            latest_news_pub_time: 最新新闻发布时间
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO portfolio_strategy_analysis_cache (
                        cache_key, target_news_date, model_name, status, output_json,
                        news_count, news_ids_json, window_start, window_end,
                        latest_news_pub_time, request_id, error_message,
                        started_at, finished_at, latency_ms
                    ) VALUES (%s, %s, %s, 'running', NULL, %s, %s, %s, %s, %s, %s, NULL, NOW(), NULL, NULL)
                    ON DUPLICATE KEY UPDATE
                        target_news_date = VALUES(target_news_date),
                        model_name = VALUES(model_name),
                        status = 'running',
                        output_json = NULL,
                        news_count = VALUES(news_count),
                        news_ids_json = VALUES(news_ids_json),
                        window_start = VALUES(window_start),
                        window_end = VALUES(window_end),
                        latest_news_pub_time = VALUES(latest_news_pub_time),
                        request_id = VALUES(request_id),
                        error_message = NULL,
                        started_at = NOW(),
                        finished_at = NULL,
                        latency_ms = NULL
                    """,
                    (
                        cache_key,
                        target_news_date,
                        model_name,
                        news_count,
                        json.dumps(news_ids, ensure_ascii=False),
                        window_start,
                        window_end,
                        latest_news_pub_time,
                        request_id,
                    ),
                )
            conn.commit()

    @staticmethod
    def finish_portfolio_strategy_success(
        cache_key: str,
        output_data: Dict[str, Any],
        latency_ms: int,
    ) -> None:
        """更新组合策略缓存状态为 'success'，写入输出数据。

        Args:
            cache_key: 缓存键
            output_data: 分析结果 JSON 数据
            latency_ms: 耗时毫秒数
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE portfolio_strategy_analysis_cache
                    SET status = 'success',
                        output_json = %s,
                        error_message = NULL,
                        finished_at = NOW(),
                        latency_ms = %s
                    WHERE cache_key = %s
                    """,
                    (json.dumps(output_data, ensure_ascii=False), latency_ms, cache_key),
                )
            conn.commit()

    @staticmethod
    def finish_portfolio_strategy_fail(
        cache_key: str,
        error_message: str,
        latency_ms: int,
    ) -> None:
        """更新组合策略缓存状态为 'fail'，记录错误信息。

        Args:
            cache_key: 缓存键
            error_message: 错误描述（超过 65535 字符将被截断）
            latency_ms: 耗时毫秒数
        """
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE portfolio_strategy_analysis_cache
                    SET status = 'fail',
                        error_message = %s,
                        finished_at = NOW(),
                        latency_ms = %s
                    WHERE cache_key = %s
                    """,
                    (error_message[:65535], latency_ms, cache_key),
                )
            conn.commit()