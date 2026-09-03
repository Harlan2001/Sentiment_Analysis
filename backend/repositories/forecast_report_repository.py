"""forecast_report 表只读仓储（每日债券预测报告数据）。

收敛 push / dashboard 中重复的 forecast_report 查询（最新日期、全量报告、
报告摘要），并统一 prediction 列的 JSON 字符串解析。
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from backend.repositories.base import BaseRepository


def _parse_prediction(value: Any) -> Any:
    """将 prediction 列（可能是 JSON 字符串）统一解析为结构。"""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


class ForecastReportRepository(BaseRepository):
    """读取预测报告（forecast_report 表）的只读仓储。"""

    def get_latest_trade_date(self) -> date | None:
        """最新一期报告日期；预报表为空时返回 None。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT MAX(trade_date) AS latest_date FROM forecast_report"
                )
                row = cursor.fetchone()
        return row["latest_date"] if row else None

    def get_prediction(self, trade_date) -> dict[str, Any] | None:
        """指定日 full_report 的 prediction（JSON 已解析）；无记录或非 dict 时返回 None。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT prediction FROM forecast_report "
                    "WHERE trade_date = %s AND forecast_type = 'full_report' LIMIT 1",
                    (trade_date,),
                )
                row = cursor.fetchone()
        if not row:
            return None
        prediction = _parse_prediction(row["prediction"])
        return prediction if isinstance(prediction, dict) else None

    def get_full_report(self, trade_date) -> dict[str, Any] | None:
        """指定日 full_report 完整信息（prediction 已解析）；无记录时返回 None。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT trade_date, model_name, prompt_version, prediction, created_at "
                    "FROM forecast_report "
                    "WHERE trade_date = %s AND forecast_type = 'full_report' LIMIT 1",
                    (trade_date,),
                )
                row = cursor.fetchone()
        if not row:
            return None
        row["prediction"] = _parse_prediction(row["prediction"])
        return row

    def list_reports(
        self, trade_date, *, by_forecast_type: bool = False
    ) -> list[dict[str, Any]]:
        """指定交易日的全部预报表行（prediction 已解析）。

        收敛 forecast 路由的两条内联查询；``by_forecast_type`` 控制排序
        （更新序 / 类型序，与历史行为一致）。
        """
        order_by = "forecast_type" if by_forecast_type else "created_at DESC"
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""SELECT trade_date, model_name, prompt_version, forecast_type,
                               prediction, created_at
                          FROM forecast_report
                         WHERE trade_date = %s
                         ORDER BY {order_by}""",
                    (trade_date,),
                )
                rows = cursor.fetchall()
        for row in rows:
            row["prediction"] = _parse_prediction(row["prediction"])
        return rows

    def list_recent_trade_dates(self, limit: int) -> list[Any]:
        """最近 limit 个不重复交易日（倒序），供 /history 使用。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT DISTINCT trade_date FROM forecast_report
                        ORDER BY trade_date DESC LIMIT %s""",
                    (limit,),
                )
                rows = cursor.fetchall()
        return [row["trade_date"] for row in rows]

    def list_reports_by_forecast_type(self, trade_date) -> dict[str, Any]:
        """指定日 {forecast_type: prediction(已解析)}，供历史页按类型的展示。"""
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT forecast_type, prediction FROM forecast_report
                        WHERE trade_date = %s ORDER BY forecast_type""",
                    (trade_date,),
                )
                rows = cursor.fetchall()
        return {
            row["forecast_type"]: _parse_prediction(row["prediction"]) for row in rows
        }

    def get_latest_prediction(self) -> tuple[Any, Any] | None:
        """最新交易日（同日再按 id 倒序）行的 ``(trade_date, prediction已解析)``。

        与 discover 市场面板「取 trade_date 最大 + id 最大行」的原始语义一致；
        不限定 forecast_type（与 get_prediction 的 full_report 过滤不同）。
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT trade_date, prediction FROM forecast_report
                        ORDER BY trade_date DESC, id DESC LIMIT 1"""
                )
                row = cursor.fetchone()
        if not row:
            return None
        return row["trade_date"], _parse_prediction(row["prediction"])
