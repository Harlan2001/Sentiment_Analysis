"""美债收益率与中美利差仓储。

中美利差 = 中债 10Y − 美债 10Y，在查询时与 yield_data 相减计算。
**注意**：中美交易日不同（美国假日与中国的不同），利差**只在双方都有数据的日期计算，不插值**。
"""

from __future__ import annotations

from typing import Any

from backend.repositories.base import BaseRepository

# 中债期限码 → 美债期限码（两边命名一致，此处显式声明便于对照）
_TERM_MAP = {"2Y": "2Y", "10Y": "10Y", "30Y": "30Y"}
DEFAULT_TERM = "10Y"


class TreasuryYieldRepository(BaseRepository):
    """美债收益率仓储。"""

    def upsert_many(self, records: list[dict[str, Any]]) -> dict[str, int]:
        """批量写入（按 日期+期限 幂等）。"""
        if not records:
            return {"inserted": 0, "updated": 0}

        inserted = updated = 0
        with self._connection() as conn:
            with conn.cursor() as cursor:
                for record in records:
                    cursor.execute(
                        "SELECT id FROM treasury_yield WHERE trade_date = %s AND term = %s",
                        (record["trade_date"], record["term"]),
                    )
                    exists = cursor.fetchone()
                    cursor.execute(
                        """INSERT INTO treasury_yield (trade_date, term, value)
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
                cursor.execute("SELECT MAX(trade_date) AS latest FROM treasury_yield")
                row = cursor.fetchone()
        return row["latest"] if row else None

    def get_spread_series(self, term: str = DEFAULT_TERM, limit: int = 250) -> list[dict[str, Any]]:
        """中美利差序列（升序）。

        内连接 yield_data：**只在两边都有数据的日期计算**，不做插值 ——
        中美交易日不同，插值会引入不存在的价格。
        """
        db_term = _TERM_MAP.get(term, term)
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT t.trade_date, t.value AS us, y.value AS cn
                         FROM treasury_yield t
                         JOIN yield_data y
                           ON y.date = t.trade_date AND y.period = %s
                        WHERE t.term = %s
                        ORDER BY t.trade_date DESC
                        LIMIT %s""",
                    (db_term, db_term, limit),
                )
                rows = cursor.fetchall()

        series = []
        for row in reversed(rows):  # 翻正为时间升序
            cn = float(row["cn"])
            us = float(row["us"])
            # 利差以 bp 计（收益率为 %）
            series.append(
                {
                    "date": str(row["trade_date"]),
                    "cn": round(cn, 4),
                    "us": round(us, 4),
                    "spread_bp": round((cn - us) * 100, 2),
                }
            )
        return series

    def get_available_terms(self) -> list[str]:
        """库内已有数据的期限。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT DISTINCT term FROM treasury_yield ORDER BY term")
                rows = cursor.fetchall()
        return [row["term"] for row in rows]

    def get_curve(self) -> list[dict[str, Any]]:
        """最新日期的美债曲线（各期限），供右栏展示。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT term, value FROM treasury_yield
                        WHERE trade_date = (SELECT MAX(trade_date) FROM treasury_yield)
                        ORDER BY value""",
                    (),
                )
                rows = cursor.fetchall()
        return [{"term": row["term"], "value": float(row["value"])} for row in rows]