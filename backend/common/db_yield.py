"""收益率（yield_data）数据查询。"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from backend.common.database import get_db_connection
from backend.config.config import PERIOD_MAP


class YieldQueries:
    """收益率数据查询。"""

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

            row_date_str = (
                row_date.strftime("%Y-%m-%d")
                if hasattr(row_date, "strftime")
                else str(row_date)
            )
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
            volatility = variance**0.5

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
