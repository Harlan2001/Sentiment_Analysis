from __future__ import annotations

from fastapi import APIRouter, Query

from backend.common.api_response import ok
from backend.config.config import API_PREFIX
from backend.repositories.forecast_report_repository import ForecastReportRepository

router = APIRouter(prefix=f"{API_PREFIX}/forecast", tags=["forecast"])


def _repository() -> ForecastReportRepository:
    return ForecastReportRepository.from_environment()


@router.get("")
def get_forecast_report(date: str = Query(None), limit: int = Query(10)):
    repository = _repository()
    if date:
        reports = repository.list_reports(date)
    else:
        latest = repository.get_latest_trade_date()
        reports = repository.list_reports(latest, by_forecast_type=True) if latest else []
    return ok({"reports": reports, "count": len(reports)})


@router.get("/history")
def get_forecast_history(limit: int = Query(30)):
    repository = _repository()
    history = [
        {
            "date": trade_date,
            "reports": repository.list_reports_by_forecast_type(trade_date),
        }
        for trade_date in repository.list_recent_trade_dates(limit)
    ]
    return ok({"history": history})