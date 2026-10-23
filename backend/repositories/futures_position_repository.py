"""国债期货持仓仓储：写入每日快照 + 查询排名与多空比。

数据源为中金所公开 CSV，每日快照逐步积累（可在交易日盘中/收盘后抓取）。
"""

from __future__ import annotations

import uuid
from typing import Any

from backend.repositories.base import BaseRepository, serialize_row
from backend.tools.futures_source import VARIETIES, VARIETY_LABELS

_FIELDS = (
    "trade_date",
    "variety",
    "contract",
    "rank_no",
    "volume_trader",
    "volume",
    "volume_change",
    "long_trader",
    "long_position",
    "long_change",
    "short_trader",
    "short_position",
    "short_change",
)


class FuturesPositionRepository(BaseRepository):
    """国债期货持仓排名仓储。"""

    def upsert_many(self, records: list[dict[str, Any]]) -> dict[str, int]:
        """批量写入（按 日期+合约+排名 幂等），返回 {inserted, updated}。"""
        if not records:
            return {"inserted": 0, "updated": 0}

        columns = ", ".join(_FIELDS)
        placeholders = ", ".join(["%s"] * len(_FIELDS))
        assignments = ", ".join(f"{field} = VALUES({field})" for field in _FIELDS)

        inserted = updated = 0
        with self._connection() as conn:
            with conn.cursor() as cursor:
                for record in records:
                    values = [record.get(field) for field in _FIELDS]
                    # 先探是否已存在，区分新增/更新，便于前端给出明确反馈
                    cursor.execute(
                        "SELECT id FROM futures_position "
                        "WHERE trade_date = %s AND contract = %s AND rank_no = %s",
                        (record.get("trade_date"), record.get("contract"), record.get("rank_no")),
                    )
                    exists = cursor.fetchone()
                    cursor.execute(
                        f"INSERT INTO futures_position (id, {columns}) "
                        f"VALUES (%s, {placeholders}) "
                        f"ON DUPLICATE KEY UPDATE {assignments}",
                        (str(uuid.uuid4()), *values),
                    )
                    if exists:
                        updated += 1
                    else:
                        inserted += 1
            conn.commit()
        return {"inserted": inserted, "updated": updated}

    def latest_trade_date(self) -> Any:
        """库内最新交易日；无数据返回 None。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT MAX(trade_date) AS latest FROM futures_position")
                row = cursor.fetchone()
        return row["latest"] if row else None

    def list_contracts(self, trade_date: Any) -> list[str]:
        """指定交易日有哪些合约（用于前端选合约）。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT DISTINCT contract, variety FROM futures_position "
                    "WHERE trade_date = %s ORDER BY variety",
                    (trade_date,),
                )
                rows = cursor.fetchall()
        return [
            {"contract": row["contract"], "variety": row["variety"],
             "label": VARIETY_LABELS.get(row["variety"], row["variety"])}
            for row in rows
        ]

    def get_ranking(self, trade_date: Any, contract: str) -> dict[str, Any]:
        """指定合约的持仓排名（前 20 会员）+ 多空合计。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT rank_no, volume_trader, volume, volume_change,
                              long_trader, long_position, long_change,
                              short_trader, short_position, short_change
                         FROM futures_position
                        WHERE trade_date = %s AND contract = %s
                        ORDER BY rank_no""",
                    (trade_date, contract),
                )
                rows = [serialize_row(row) or {} for row in cursor.fetchall()]

        long_total = sum(int(r.get("long_position") or 0) for r in rows)
        short_total = sum(int(r.get("short_position") or 0) for r in rows)
        long_trader_total = sum(int(r.get("long_change") or 0) for r in rows)
        short_trader_total = sum(int(r.get("short_change") or 0) for r in rows)

        return {
            "trade_date": str(trade_date),
            "contract": contract,
            "rows": rows,
            "summary": {
                "long_total": long_total,
                "short_total": short_total,
                # 多空比 = 前 20 名多头合计 / 空头合计
                "long_short_ratio": round(long_total / short_total, 4) if short_total else None,
                "long_change_total": long_trader_total,
                "short_change_total": short_trader_total,
            },
        }

    def get_ratio_trend(self, variety: str, limit: int = 60) -> list[dict[str, Any]]:
        """某品种的多空比走势（近 limit 个交易日），供趋势图。

        每个交易日**只取该品种的主力合约**（当日持仓合计最大的合约），
        否则次主力合约会被并入合计，导致多空比失真。
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT t.trade_date, t.long_total, t.short_total
                         FROM (
                             SELECT trade_date, contract,
                                    SUM(long_position) AS long_total,
                                    SUM(short_position) AS short_total,
                                    ROW_NUMBER() OVER (
                                        PARTITION BY trade_date
                                        ORDER BY SUM(long_position) + SUM(short_position) DESC
                                    ) AS rn
                               FROM futures_position
                              WHERE variety = %s
                              GROUP BY trade_date, contract
                         ) t
                        WHERE t.rn = 1
                        ORDER BY t.trade_date DESC
                        LIMIT %s""",
                    (variety, limit),
                )
                rows = cursor.fetchall()

        series = []
        for row in reversed(rows):  # 倒序取出后翻正，保证时间升序
            long_total = int(row["long_total"] or 0)
            short_total = int(row["short_total"] or 0)
            series.append(
                {
                    "date": str(row["trade_date"]),
                    "long_total": long_total,
                    "short_total": short_total,
                    "ratio": round(long_total / short_total, 4) if short_total else None,
                }
            )
        return series

    def get_variety_comparison(self, trade_date: Any) -> list[dict[str, Any]]:
        """指定交易日四品种的多空比横向对比（每品种只取主力合约）。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT t.variety, t.long_total, t.short_total
                         FROM (
                             SELECT variety, contract,
                                    SUM(long_position) AS long_total,
                                    SUM(short_position) AS short_total,
                                    ROW_NUMBER() OVER (
                                        PARTITION BY variety
                                        ORDER BY SUM(long_position) + SUM(short_position) DESC
                                    ) AS rn
                               FROM futures_position
                              WHERE trade_date = %s
                              GROUP BY variety, contract
                         ) t
                        WHERE t.rn = 1""",
                    (trade_date,),
                )
                rows = cursor.fetchall()

        by_variety = {row["variety"]: row for row in rows}
        result = []
        for variety in VARIETIES:  # 固定顺序，保证前端展示稳定
            row = by_variety.get(variety)
            if not row:
                continue
            long_total = int(row["long_total"] or 0)
            short_total = int(row["short_total"] or 0)
            result.append(
                {
                    "variety": variety,
                    "label": VARIETY_LABELS.get(variety, variety),
                    "long_total": long_total,
                    "short_total": short_total,
                    "ratio": round(long_total / short_total, 4) if short_total else None,
                }
            )
        return result