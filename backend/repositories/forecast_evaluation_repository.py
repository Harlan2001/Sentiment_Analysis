"""预测诊断数据访问：读取全量预测报告与国债收益率序列。

预测诊断是纯查询 + 计算，**不新增任何表**；本仓储只做只读读取，
为 ``backend.evaluation.forecast_evaluation`` 提供原始数据。
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from backend.repositories.base import BaseRepository

# 预测评估使用的国债期限（口径统一为 10Y）
EVALUATION_PERIOD = "10Y"


def _parse_prediction(value: Any) -> dict[str, Any] | None:
    """prediction 列统一解析为 dict；非 dict / 解析失败返回 None。"""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


class ForecastEvaluationRepository(BaseRepository):
    """预测诊断的只读仓储。"""

    def list_full_reports(self) -> list[dict[str, Any]]:
        """全部 full_report 报告，按交易日升序。

        返回每项 {trade_date, model_name, prompt_version, prediction(已解析)}；
        prediction 无法解析为 dict 的记录被丢弃（无法评估）。
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT trade_date, model_name, prompt_version, prediction
                         FROM forecast_report
                        WHERE forecast_type = 'full_report'
                        ORDER BY trade_date ASC"""
                )
                rows = cursor.fetchall()

        reports: list[dict[str, Any]] = []
        for row in rows:
            prediction = _parse_prediction(row["prediction"])
            if prediction is None:
                continue
            reports.append(
                {
                    "trade_date": row["trade_date"],
                    "model_name": row["model_name"],
                    "prompt_version": row["prompt_version"],
                    "prediction": prediction,
                }
            )
        return reports

    def list_yield_series(
        self, period: str = EVALUATION_PERIOD
    ) -> list[tuple[date, float]]:
        """指定期限的国债收益率全量序列（按日期升序）。

        该序列同时充当**交易日历**：yield_data 的日期集合即中债估值发布日历
        （含调休补班日），无需引入节假日依赖。
        """
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT date, value FROM yield_data
                        WHERE period = %s
                        ORDER BY date ASC""",
                    (period,),
                )
                rows = cursor.fetchall()
        return [(row["date"], float(row["value"])) for row in rows]