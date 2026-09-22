"""Internal HTTP boundary for business-level MCP orchestration."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from backend.business_mcp import service
from backend.common.api_response import ok
from backend.config.config import API_PREFIX

router = APIRouter(prefix=f"{API_PREFIX}/mcp-business", tags=["mcp-business"])


class _BoundedDateRangeRequest(BaseModel):
    start_date: date
    end_date: date
    source: str | None = Field(default=None, max_length=200)
    limit: int = Field(default=100, ge=1, le=200)

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must not be earlier than start_date")
        if (self.end_date - self.start_date).days > 31:
            raise ValueError("date range must not exceed 31 days")
        return self


class DateRangeRequest(_BoundedDateRangeRequest):
    keyword: str | None = Field(default=None, max_length=200)


class SentimentRequest(BaseModel):
    news_id: int = Field(gt=0)
    force_refresh: bool = False


class MarketMoveRequest(BaseModel):
    trade_date: date
    maturity: str = Field(default="10Y", min_length=1, max_length=10)


class SimilarEventRequest(BaseModel):
    news_id: int = Field(gt=0)
    top_k: int = Field(default=5, ge=1, le=10)
    maturity: str = Field(default="10年", min_length=1, max_length=10)
    window_before: int = Field(default=5, ge=0, le=30)
    window_after: int = Field(default=5, ge=0, le=30)


class ForecastRequest(BaseModel):
    report_date: date
    force_refresh: bool = False


class DigestRequest(_BoundedDateRangeRequest):
    focus: str | None = Field(default=None, max_length=200)


def _raise_failure(exc: Exception) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/analyze-bond-sentiment")
async def analyze_bond_sentiment(body: SentimentRequest):
    try:
        return ok(await service.analyze_bond_sentiment(body.news_id, body.force_refresh))
    except Exception as exc:
        _raise_failure(exc)


@router.post("/analyze-market-sentiment")
def analyze_market_sentiment(body: DateRangeRequest):
    return ok(
        service.analyze_bond_market_sentiment(
            body.start_date.isoformat(),
            body.end_date.isoformat(),
            keyword=body.keyword,
            source=body.source,
            limit=body.limit,
        )
    )


@router.post("/explain-market-move")
def explain_market_move(body: MarketMoveRequest):
    return ok(service.explain_bond_market_move(body.trade_date.isoformat(), body.maturity))


@router.post("/analyze-similar-event-impact")
def analyze_similar_event_impact(body: SimilarEventRequest):
    return ok(service.analyze_similar_event_impact(**body.model_dump()))


@router.post("/generate-market-forecast")
async def generate_market_forecast(body: ForecastRequest):
    try:
        return ok(
            await service.generate_bond_market_forecast(
                body.report_date.isoformat(), body.force_refresh
            )
        )
    except Exception as exc:
        _raise_failure(exc)


@router.post("/generate-news-digest")
def generate_news_digest(body: DigestRequest):
    return ok(
        service.generate_news_digest(
            body.start_date.isoformat(),
            body.end_date.isoformat(),
            focus=body.focus,
            source=body.source,
            limit=body.limit,
        )
    )
