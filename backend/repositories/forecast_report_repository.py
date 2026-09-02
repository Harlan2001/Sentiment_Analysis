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
