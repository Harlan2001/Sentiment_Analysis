"""信用利差仓储：写入信用债曲线，查询利差及其历史分位。

利差 = 同日期、同期限的【中短期票据收益率 − 国债收益率】，在查询时计算，
不落库 —— 避免冗余存储与口径漂移。
"""

from __future__ import annotations

from typing import Any

from backend.repositories.base import BaseRepository

# 与国债曲线共有的期限（国债为 3M/6M/1Y/2Y/3Y/5Y/7Y/10Y/30Y，信用债无 3M/6M）
COMMON_TERMS: tuple[str, ...] = ("1Y", "2Y", "3Y", "5Y", "7Y", "10Y")
# 默认展示期限
DEFAULT_TERM = "10Y"


class CreditCurveRepository(BaseRepository):
    """信用债曲线与利差仓储。"""

    def upsert_many(self, records: list[dict[str, Any]]) -> dict[str, int]:
        """批量写入曲线（按 (日期, 期限) 幂等），返回 {inserted, updated}。"""
        if not records:
            return {"inserted": 0, "updated": 0}

        inserted = updated = 0
        with self._connection() as conn:
            with conn.cursor() as cursor:
                for record in records:
                    cursor.execute(
                        "SELECT id FROM credit_curve WHERE trade_date = %s AND term = %s",
                        (record["trade_date"], record["term"]),
                    )
                    exists = cursor.fetchone()
                    cursor.execute(
                        """INSERT INTO credit_curve (trade_date, term, value)
                           VALUES (%s, %s, %s)
                           ON DUPLICATE KEY UPDATE value = VALUES(value)""",
                        (record["trade_date"], record["term"], record["value"]),
                    )
                    if exists:
                        updated += 1
                    else:
                        inserted += 1
            conn.commit()
        return {"inserted": inserted, "updated": updated}

    def latest_date(self) -> Any:
        """库内最新日期。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT MAX(trade_date) AS latest FROM credit_curve")
                row = cursor.fetchone()
        return row["latest"] if row else None

    def get_spread_series(self, term: str = DEFAULT_TERM, limit: int = 250) -> list[dict[str, Any]]:
        """某期限的信用利差序列（近 limit 条），升序返回。

        利差 = 信用债收益率 − 同日期同期限国债收益率（内连接，两边都有数据才计算）。
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT c.trade_date, c.value AS credit, y.value AS gov
                         FROM credit_curve c
                         JOIN yield_data y
                           ON y.date = c.trade_date AND y.period = c.term
                        WHERE c.term = %s
                        ORDER BY c.trade_date DESC
                        LIMIT %s""",
                    (term, limit),
                )
                rows = cursor.fetchall()

        series = []
        for row in reversed(rows):  # 翻正为时间升序
            credit = float(row["credit"])
            gov = float(row["gov"])
            # 收益率以 % 计，利差换算为 bp
            series.append(
                {
                    "date": str(row["trade_date"]),
                    "credit": round(credit, 4),
                    "gov": round(gov, 4),
                    "spread_bp": round((credit - gov) * 100, 2),
                }
            )
        return series

    def get_term_structure(self) -> list[dict[str, Any]]:
        """最新日期的期限结构（各期限的信用债/国债/利差）。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT c.term, c.value AS credit, y.value AS gov
                         FROM credit_curve c
                         JOIN yield_data y
                           ON y.date = c.trade_date AND y.period = c.term
                        WHERE c.trade_date = (SELECT MAX(trade_date) FROM credit_curve)
                        ORDER BY c.value""",
                    (),
                )
                rows = cursor.fetchall()

        result = []
        for row in rows:
            credit = float(row["credit"])
            gov = float(row["gov"])
            result.append(
                {
                    "term": row["term"],
                    "credit": round(credit, 4),
                    "gov": round(gov, 4),
                    "spread_bp": round((credit - gov) * 100, 2),
                }
            )
        return result

    def get_available_terms(self) -> list[str]:
        """库内有数据的期限列表（供前端切换）。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT DISTINCT term FROM credit_curve ORDER BY term"
                )
                rows = cursor.fetchall()
        terms = [row["term"] for row in rows]
        # 按固定顺序排列，保证前端展示稳定
        return [term for term in COMMON_TERMS if term in terms]