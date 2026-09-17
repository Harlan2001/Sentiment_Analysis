from __future__ import annotations

from typing import Any

import pytest
from mcp import Client

from backend.mcp_server.server import StaticTokenVerifier, create_server


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, path: str, **query: Any) -> dict[str, Any]:
        self.calls.append((path, query))
        return {"path": path, "query": query}


@pytest.mark.asyncio
async def test_server_exposes_only_the_explicit_read_only_tools():
    server = create_server(FakeGateway())

    async with Client(server) as client:
        result = await client.list_tools()

    names = {tool.name for tool in result.tools}
    assert len(names) == 23
    assert {
        "search_news",
        "semantic_search_news",
        "get_macro_signal",
        "get_market_overview",
        "search_research_reports",
    } <= names
    assert not any("delete" in name or "upload" in name for name in names)


@pytest.mark.asyncio
async def test_search_news_enforces_safe_defaults_and_limits():
    gateway = FakeGateway()
    server = create_server(gateway)

    async with Client(server) as client:
        await client.call_tool(
            "search_news",
            {"keyword": "降息", "limit": 5000, "offset": -3},
        )

    assert gateway.calls == [
        (
            "/sapi/news",
            {
                "keyword": "降息",
                "start_date": None,
                "end_date": None,
                "source": None,
                "view": "best",
                "include_content": False,
                "limit": 50,
                "offset": 0,
            },
        )
    ]


@pytest.mark.asyncio
async def test_semantic_search_rejects_empty_query_without_calling_backend():
    gateway = FakeGateway()
    server = create_server(gateway)

    async with Client(server) as client:
        result = await client.call_tool("semantic_search_news", {"query": "  "})

    assert result.is_error
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_returns_calendar_rejects_oversized_range():
    gateway = FakeGateway()
    server = create_server(gateway)

    async with Client(server) as client:
        result = await client.call_tool(
            "get_returns_calendar",
            {"start": "2026-01-01", "end": "2026-03-01"},
        )

    assert result.is_error
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_macro_signal_normalizes_codes_and_forwards_query():
    gateway = FakeGateway()
    server = create_server(gateway)

    async with Client(server) as client:
        result = await client.call_tool(
            "get_macro_signal",
            {
                "factor_code": " A, B ",
                "start_time": "2026-09-01T00:00:00",
                "end_time": "2026-09-02T00:00:00",
                "signal_type": "directional",
            },
        )

    assert not result.is_error
    assert gateway.calls[0][0] == "/sapi/macro/signal"
    assert gateway.calls[0][1]["factor_code"] == "A,B"


@pytest.mark.asyncio
async def test_research_search_caps_page_size():
    gateway = FakeGateway()
    server = create_server(gateway)

    async with Client(server) as client:
        await client.call_tool(
            "search_research_reports",
            {"market_view": "bullish", "page": 0, "page_size": 100},
        )

    assert gateway.calls[0][0] == "/sapi/research/list"
    assert gateway.calls[0][1]["page"] == 1
    assert gateway.calls[0][1]["page_size"] == 50


@pytest.mark.asyncio
async def test_static_token_verifier_accepts_only_configured_token():
    verifier = StaticTokenVerifier("external-secret", "https://example.test/mcp")

    accepted = await verifier.verify_token("external-secret")
    rejected = await verifier.verify_token("wrong-secret")

    assert accepted is not None
    assert accepted.scopes == ["sentiment:read"]
    assert accepted.resource == "https://example.test/mcp"
    assert rejected is None


@pytest.mark.asyncio
async def test_macro_data_validates_month_range():
    gateway = FakeGateway()
    server = create_server(gateway)

    async with Client(server) as client:
        result = await client.call_tool(
            "get_macro_data",
            {
                "indicator_codes": "A010101",
                "start_month": "202501",
                "end_month": "202413",
            },
        )

    assert result.is_error
    assert gateway.calls == []
