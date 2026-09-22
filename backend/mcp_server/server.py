"""Explicit MCP facade over selected Sentiment REST endpoints."""

from __future__ import annotations

import hmac
import os
from datetime import date, datetime
from typing import Any
from urllib.parse import quote

from dotenv import load_dotenv
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver import MCPServer

from backend.mcp_server.gateway import SentimentBackendGateway

load_dotenv()

_API_PREFIX = os.environ.get("API_PREFIX", "/sapi").rstrip("/")


class StaticTokenVerifier:
    """Verify the deployment-level bearer token configured for the MCP facade."""

    def __init__(self, expected_token: str, resource: str) -> None:
        self._expected_token = expected_token
        self._resource = resource

    async def verify_token(self, token: str) -> AccessToken | None:
        if not hmac.compare_digest(token, self._expected_token):
            return None
        return AccessToken(
            token=token,
            client_id="sentiment-mcp-client",
            subject="sentiment-mcp-client",
            scopes=["sentiment:read"],
            resource=self._resource,
        )


def _bounded(value: int, *, minimum: int, maximum: int) -> int:
    return min(max(value, minimum), maximum)


def _validate_date_range(start: str, end: str, *, max_days: int) -> None:
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError as exc:
        raise ValueError("dates must use YYYY-MM-DD") from exc
    if start_date > end_date:
        raise ValueError("start date must not be later than end date")
    if (end_date - start_date).days > max_days:
        raise ValueError(f"date range must not exceed {max_days} days")


def _validate_time_range(start: str, end: str, *, max_days: int) -> None:
    try:
        start_time = datetime.fromisoformat(start)
        end_time = datetime.fromisoformat(end)
    except ValueError as exc:
        raise ValueError("timestamps must use ISO 8601 format") from exc
    if start_time > end_time:
        raise ValueError("start time must not be later than end time")
    if (end_time - start_time).days > max_days:
        raise ValueError(f"time range must not exceed {max_days} days")


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _validate_month_range(start: str | None, end: str | None, *, max_months: int) -> None:
    if not start and not end:
        return

    def parse_month(value: str) -> tuple[int, int]:
        if len(value) != 6 or not value.isdigit():
            raise ValueError("months must use YYYYMM")
        year, month = int(value[:4]), int(value[4:])
        if month < 1 or month > 12:
            raise ValueError("months must use YYYYMM")
        return year, month

    start_value = parse_month(start) if start else None
    end_value = parse_month(end) if end else None
    if start_value and end_value:
        start_index = start_value[0] * 12 + start_value[1]
        end_index = end_value[0] * 12 + end_value[1]
        if start_index > end_index:
            raise ValueError("start month must not be later than end month")
        if end_index - start_index > max_months:
            raise ValueError(f"month range must not exceed {max_months} months")


def create_server(
    gateway: SentimentBackendGateway | None = None,
    *,
    access_token: str | None = None,
    resource_url: str | None = None,
    issuer_url: str | None = None,
) -> MCPServer:
    """Build the server; dependency injection keeps tool calls testable in-process."""
    backend = gateway or SentimentBackendGateway()
    configured_token = access_token or os.environ.get("SENTIMENT_MCP_ACCESS_TOKEN")
    configured_resource = resource_url or os.environ.get(
        "SENTIMENT_MCP_RESOURCE_URL", "http://127.0.0.1:8002/mcp"
    )
    configured_issuer = issuer_url or os.environ.get(
        "SENTIMENT_MCP_ISSUER_URL", "http://127.0.0.1:8002"
    )

    verifier = None
    auth = None
    if configured_token:
        verifier = StaticTokenVerifier(configured_token, configured_resource)
        auth = AuthSettings(
            issuer_url=configured_issuer,
            resource_server_url=configured_resource,
            required_scopes=["sentiment:read"],
            validate_token_resource=True,
        )

    server = MCPServer(
        name="sentiment-market-intelligence",
        title="Sentiment Market Intelligence",
        description="Bond-market data tools and business-level analysis workflows.",
        instructions=(
            "Use these tools to retrieve evidence from the Sentiment platform. "
            "The original data tools are read-only; business tools may run analysis or generate reports. "
            "Results should be cited with their returned IDs, dates or URLs."
        ),
        token_verifier=verifier,
        auth=auth,
    )

    # Group A: existing, stable read-only endpoints.
    @server.tool(name="search_news", description="Filter bond-market news by date, source and keyword.")
    def search_news(
        keyword: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        source: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Any:
        if start_date and end_date:
            _validate_date_range(start_date, end_date, max_days=366)
        return backend.get(
            f"{_API_PREFIX}/news",
            keyword=_clean_optional(keyword),
            start_date=start_date,
            end_date=end_date,
            source=_clean_optional(source),
            view="best",
            include_content=False,
            limit=_bounded(limit, minimum=1, maximum=50),
            offset=max(offset, 0),
        )

    @server.tool(name="get_news_detail", description="Get one news item and its selected sentiment analysis.")
    def get_news_detail(news_id: int) -> Any:
        return backend.get(
            f"{_API_PREFIX}/news/{news_id}",
            include_all_models=False,
        )

    @server.tool(name="list_news_sources", description="List supported news sources.")
    def list_news_sources() -> Any:
        return backend.get(f"{_API_PREFIX}/news/sources")

    @server.tool(name="get_latest_news_date", description="Get the latest available news publication date.")
    def get_latest_news_date() -> Any:
        return backend.get(f"{_API_PREFIX}/news/latest-trading-day")

    @server.tool(name="find_similar_news", description="Find news semantically similar to one news item.")
    def find_similar_news(news_id: int, top_k: int = 5) -> Any:
        return backend.get(
            f"{_API_PREFIX}/news/similar",
            news_id=news_id,
            top_k=_bounded(top_k, minimum=1, maximum=10),
        )

    @server.tool(name="get_yield_series", description="Get a bond-yield time series for one maturity.")
    def get_yield_series(start: str, end: str, maturity: str = "10年") -> Any:
        _validate_date_range(start, end, max_days=366)
        return backend.get(f"{_API_PREFIX}/yields", start=start, end=end, type=maturity)

    @server.tool(name="get_news_yield_impact", description="Get the yield window around one news item.")
    def get_news_yield_impact(
        news_id: int,
        period: str = "10年",
        window_before: int = 10,
        window_after: int = 10,
    ) -> Any:
        return backend.get(
            f"{_API_PREFIX}/news/{news_id}/yield",
            period=period,
            window_before=_bounded(window_before, minimum=0, maximum=30),
            window_after=_bounded(window_after, minimum=0, maximum=30),
        )

    @server.tool(name="list_factors", description="List the platform's market factors.")
    def list_factors() -> Any:
        return backend.get(f"{_API_PREFIX}/factors")

    @server.tool(name="list_factors_by_category", description="List factors in one category.")
    def list_factors_by_category(category: str) -> Any:
        encoded = quote(category.strip(), safe="")
        return backend.get(f"{_API_PREFIX}/factors/by-category/{encoded}")

    @server.tool(name="get_macro_signal", description="Calculate presence or directional macro signals.")
    def get_macro_signal(
        factor_code: str,
        start_time: str,
        end_time: str,
        signal_type: str,
        decay_lambda: float = 0.1,
    ) -> Any:
        _validate_time_range(start_time, end_time, max_days=366)
        codes = [code.strip() for code in factor_code.split(",") if code.strip()]
        if not codes or len(codes) > 20:
            raise ValueError("factor_code must contain between 1 and 20 codes")
        if signal_type not in {"presence", "directional"}:
            raise ValueError("signal_type must be presence or directional")
        return backend.get(
            f"{_API_PREFIX}/macro/signal",
            factor_code=",".join(codes),
            start_time=start_time,
            end_time=end_time,
            signal_type=signal_type,
            decay_lambda=decay_lambda,
        )

    @server.tool(name="get_latest_forecast", description="Get the latest or date-specific forecast reports.")
    def get_latest_forecast(date: str | None = None, limit: int = 10) -> Any:
        return backend.get(
            f"{_API_PREFIX}/forecast",
            date=date,
            limit=_bounded(limit, minimum=1, maximum=20),
        )

    @server.tool(name="get_forecast_history", description="Get recent forecast-report history.")
    def get_forecast_history(limit: int = 10) -> Any:
        return backend.get(
            f"{_API_PREFIX}/forecast/history",
            limit=_bounded(limit, minimum=1, maximum=30),
        )

    @server.tool(name="list_change_snapshots", description="List recent market-change snapshots.")
    def list_change_snapshots(hours: int = 168) -> Any:
        return backend.get(
            f"{_API_PREFIX}/change/snapshots",
            hours=_bounded(hours, minimum=1, maximum=168),
        )

    # Group B: useful read-only endpoints not present in the legacy agent snapshot.
    @server.tool(name="semantic_search_news", description="Search news using keyword matching and semantic recall.")
    def semantic_search_news(
        query: str,
        start_date: str | None = None,
        end_date: str | None = None,
        top_k: int = 20,
    ) -> Any:
        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("query must not be empty")
        if start_date and end_date:
            _validate_date_range(start_date, end_date, max_days=366)
        return backend.get(
            f"{_API_PREFIX}/news/search",
            q=cleaned_query,
            start_date=start_date,
            end_date=end_date,
            top_k=_bounded(top_k, minimum=1, maximum=50),
        )

    @server.tool(name="list_factors_paged", description="List factors with bounded pagination.")
    def list_factors_paged(page: int = 1, page_size: int = 20) -> Any:
        return backend.get(
            f"{_API_PREFIX}/factors/paged",
            page=max(page, 1),
            page_size=_bounded(page_size, minimum=1, maximum=50),
        )

    @server.tool(name="list_macro_indicators", description="List available macroeconomic indicators.")
    def list_macro_indicators() -> Any:
        return backend.get(f"{_API_PREFIX}/macro-data/indicators")

    @server.tool(name="get_macro_data", description="Get monthly values for one or more macro indicators.")
    def get_macro_data(
        indicator_codes: str,
        start_month: str | None = None,
        end_month: str | None = None,
    ) -> Any:
        codes = [code.strip() for code in indicator_codes.split(",") if code.strip()]
        if not codes or len(codes) > 20:
            raise ValueError("indicator_codes must contain between 1 and 20 codes")
        _validate_month_range(start_month, end_month, max_months=120)
        return backend.get(
            f"{_API_PREFIX}/macro-data/data",
            zbcode=",".join(codes),
            start=start_month,
            end=end_month,
        )

    @server.tool(name="get_market_overview", description="Get the current market overview panel.")
    def get_market_overview() -> Any:
        return backend.get(f"{_API_PREFIX}/discover/market-panel")

    @server.tool(name="get_yield_detail", description="Get detailed yield information for one maturity.")
    def get_yield_detail(period: str = "10Y") -> Any:
        return backend.get(f"{_API_PREFIX}/discover/yield-detail", period=period)

    @server.tool(name="get_factor_detail", description="Get detailed information for one factor.")
    def get_factor_detail(factor_id: int) -> Any:
        return backend.get(f"{_API_PREFIX}/discover/factor-detail", factor_id=factor_id)

    @server.tool(name="get_returns_calendar", description="Get returns, news and factor aggregates for a date range.")
    def get_returns_calendar(start: str, end: str) -> Any:
        _validate_date_range(start, end, max_days=31)
        return backend.get(f"{_API_PREFIX}/returns/calendar", start=start, end=end)

    @server.tool(name="get_research_summary", description="Get aggregate research-report statistics.")
    def get_research_summary() -> Any:
        return backend.get(f"{_API_PREFIX}/research/summary")

    @server.tool(name="search_research_reports", description="Search and filter analyzed research reports.")
    def search_research_reports(
        keyword: str | None = None,
        institution: str | None = None,
        industry: str | None = None,
        market_view: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Any:
        if market_view and market_view not in {"bullish", "bearish", "neutral"}:
            raise ValueError("market_view must be bullish, bearish or neutral")
        return backend.get(
            f"{_API_PREFIX}/research/list",
            keyword=_clean_optional(keyword),
            institution=_clean_optional(institution),
            industry=_clean_optional(industry),
            market_view=market_view,
            status=_clean_optional(status),
            page=max(page, 1),
            page_size=_bounded(page_size, minimum=1, maximum=50),
        )

    # Group C: business-level capabilities.  These compose the stable atomic
    # tools above behind an explicit FastAPI contract; the original 23 tools
    # remain unchanged for backwards compatibility.
    @server.tool(
        name="analyze_bond_sentiment",
        description=(
            "Analyze one stored bond-market news item, reusing an existing analysis "
            "unless it is missing or force_refresh is true."
        ),
    )
    def analyze_bond_sentiment(news_id: int, force_refresh: bool = False) -> Any:
        if news_id <= 0:
            raise ValueError("news_id must be positive")
        return backend.post(
            f"{_API_PREFIX}/mcp-business/analyze-bond-sentiment",
            {"news_id": news_id, "force_refresh": force_refresh},
        )

    @server.tool(
        name="analyze_bond_market_sentiment",
        description=(
            "Summarize bullish, bearish and neutral bond-market sentiment for a date range or topic."
        ),
    )
    def analyze_bond_market_sentiment(
        start_date: str,
        end_date: str,
        keyword: str | None = None,
        source: str | None = None,
        limit: int = 100,
    ) -> Any:
        _validate_date_range(start_date, end_date, max_days=31)
        return backend.post(
            f"{_API_PREFIX}/mcp-business/analyze-market-sentiment",
            {
                "start_date": start_date,
                "end_date": end_date,
                "keyword": _clean_optional(keyword),
                "source": _clean_optional(source),
                "limit": _bounded(limit, minimum=1, maximum=200),
            },
        )

    @server.tool(
        name="explain_bond_market_move",
        description=(
            "Explain one day's bond-yield move using same-day analyzed news and active factors."
        ),
    )
    def explain_bond_market_move(trade_date: str, maturity: str = "10Y") -> Any:
        date.fromisoformat(trade_date)
        cleaned_maturity = maturity.strip()
        if not cleaned_maturity:
            raise ValueError("maturity must not be empty")
        return backend.post(
            f"{_API_PREFIX}/mcp-business/explain-market-move",
            {"trade_date": trade_date, "maturity": cleaned_maturity},
        )

    @server.tool(
        name="analyze_similar_event_impact",
        description=(
            "Compare one news event with semantically similar historical events and their yield moves."
        ),
    )
    def analyze_similar_event_impact(
        news_id: int,
        top_k: int = 5,
        maturity: str = "10年",
        window_before: int = 5,
        window_after: int = 5,
    ) -> Any:
        if news_id <= 0:
            raise ValueError("news_id must be positive")
        return backend.post(
            f"{_API_PREFIX}/mcp-business/analyze-similar-event-impact",
            {
                "news_id": news_id,
                "top_k": _bounded(top_k, minimum=1, maximum=10),
                "maturity": maturity.strip() or "10年",
                "window_before": _bounded(window_before, minimum=0, maximum=30),
                "window_after": _bounded(window_after, minimum=0, maximum=30),
            },
        )

    @server.tool(
        name="generate_bond_market_forecast",
        description=(
            "Generate or retrieve a date-specific bond-market forecast with scenarios and risks."
        ),
    )
    def generate_bond_market_forecast(
        report_date: str, force_refresh: bool = False
    ) -> Any:
        date.fromisoformat(report_date)
        return backend.post(
            f"{_API_PREFIX}/mcp-business/generate-market-forecast",
            {"report_date": report_date, "force_refresh": force_refresh},
        )

    @server.tool(
        name="generate_news_digest",
        description=(
            "Generate a structured pre-market, post-market or topic news digest for a bounded date range."
        ),
    )
    def generate_news_digest(
        start_date: str,
        end_date: str,
        focus: str | None = None,
        source: str | None = None,
        limit: int = 100,
    ) -> Any:
        _validate_date_range(start_date, end_date, max_days=31)
        return backend.post(
            f"{_API_PREFIX}/mcp-business/generate-news-digest",
            {
                "start_date": start_date,
                "end_date": end_date,
                "focus": _clean_optional(focus),
                "source": _clean_optional(source),
                "limit": _bounded(limit, minimum=1, maximum=200),
            },
        )

    return server


mcp = create_server()


def main() -> None:
    access_token = os.environ.get("SENTIMENT_MCP_ACCESS_TOKEN")
    if not access_token:
        raise RuntimeError(
            "SENTIMENT_MCP_ACCESS_TOKEN is required for the Streamable HTTP MCP server"
        )
    internal_token = os.environ.get("SENTIMENT_INTERNAL_API_TOKEN")
    if internal_token and hmac.compare_digest(access_token, internal_token):
        raise RuntimeError(
            "SENTIMENT_MCP_ACCESS_TOKEN must differ from SENTIMENT_INTERNAL_API_TOKEN"
        )
    host = os.environ.get("SENTIMENT_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("SENTIMENT_MCP_PORT", "8002"))
    mcp.run(
        transport="streamable-http",
        host=host,
        port=port,
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
