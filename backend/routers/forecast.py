from __future__ import annotations

import json
from fastapi import APIRouter, Query

from backend.common.database import get_db_connection

router = APIRouter(prefix="/api/forecast", tags=["forecast"])


@router.get("")
def get_forecast_report(date: str = Query(None), limit: int = Query(10)):
    with get_db_connection() as conn:
        cur = conn.cursor()
        if date:
            cur.execute(
                """
                SELECT trade_date, model_name, prompt_version, forecast_type,
                       prediction, created_at
                FROM forecast_report
                WHERE trade_date = %s
                ORDER BY created_at DESC
                """,
                (date,),
            )
        else:
            cur.execute(
                """
                SELECT trade_date, model_name, prompt_version, forecast_type,
                       prediction, created_at
                FROM forecast_report
                WHERE trade_date = (
                    SELECT trade_date FROM forecast_report
                    ORDER BY trade_date DESC LIMIT 1
                )
                ORDER BY forecast_type
                """
            )
        rows = cur.fetchall()

    reports = []
    for row in rows:
        prediction = row[4]
        if isinstance(prediction, str):
            try:
                prediction = json.loads(prediction)
            except json.JSONDecodeError:
                pass
        reports.append(
            {
                "trade_date": row[0],
                "model_name": row[1],
                "prompt_version": row[2],
                "forecast_type": row[3],
                "prediction": prediction,
                "created_at": row[5],
            }
        )
    return {"reports": reports, "count": len(reports)}


@router.get("/history")
def get_forecast_history(limit: int = Query(30)):
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT trade_date
            FROM forecast_report
            ORDER BY trade_date DESC
            LIMIT %s
            """,
            (limit,),
        )
        dates = [row[0] for row in cur.fetchall()]

        history = []
        for trade_date in dates:
            cur.execute(
                """
                SELECT forecast_type, prediction
                FROM forecast_report
                WHERE trade_date = %s
                ORDER BY forecast_type
                """,
                (trade_date,),
            )
            date_reports = {}
            for row in cur.fetchall():
                prediction = json.loads(row[1]) if row[1] else {}
                date_reports[row[0]] = prediction
            history.append({"date": trade_date, "reports": date_reports})

    return {"history": history}
