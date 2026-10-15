from __future__ import annotations

from typing import Any

import pytest
from mcp import Client
from mcp.types import ResourceLink

from backend.mcp_server.server import StaticTokenVerifier, create_server

# This is the public, read-only MCP surface.  Keep the contract explicit: a
# tool addition/removal is a compatibility and security review, not a silent
# consequence of adding a decorator in the server implementation.
EXPECTED_READ_ONLY_TOOLS = {
    "ask_sentiment",
    "analyze_bond_market_sentiment",
    "analyze_bond_sentiment",
    "analyze_similar_event_impact",
    "explain_bond_market_move",
    "find_similar_news",
    "generate_bond_market_forecast",
    "generate_news_digest",
    "get_factor_detail",
    "get_forecast_history",
    "get_latest_forecast",
    "get_latest_news_date",
    "get_macro_data",
    "get_macro_signal",
    "get_market_overview",
    "get_news_detail",
    "get_news_yield_impact",
    "get_research_summary",
    "get_returns_calendar",
    "get_yield_detail",
    "get_yield_series",
    "list_change_snapshots",
    "list_factors",
    "list_factors_by_category",
    "list_factors_paged",
    "list_macro_indicators",
    "list_news_sources",
    "search_news",
    "search_research_reports",
    "semantic_search_news",
}


class FakeGateway:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get(self, path: str, **query: Any) -> dict[str, Any]:
        self.calls.append((path, query))
        return {"path": path, "query": query}

    def post(self, path: str, body: Any = None, **query: Any) -> dict[str, Any]:
        self.calls.append((path, {"body": body, **query}))
        return {"path": path, "body": body, "query": query}


@pytest.mark.asyncio
async def test_server_exposes_expected_tools():
    server = create_server(FakeGateway())

    async with Client(server) as client:
        result = await client.list_tools()

    names = {tool.name for tool in result.tools}
    assert names == EXPECTED_READ_ONLY_TOOLS
    assert not any("delete" in name or "upload" in name for name in names)
    ask_tool = next(tool for tool in result.tools if tool.name == "ask_sentiment")
    assert ask_tool.meta == {"ui": {"resourceUri": "ui://sentiment/answer"}}


@pytest.mark.asyncio
async def test_server_exposes_sentiment_answer_mcp_app():
    server = create_server(FakeGateway())

    async with Client(server) as client:
        resources = await client.list_resources()
        result = await client.read_resource("ui://sentiment/answer")

    app_resource = next(item for item in resources.resources if item.uri == "ui://sentiment/answer")
    assert app_resource.mime_type == "text/html;profile=mcp-app"
    html = result.contents[0].text
    assert "app.ontoolresult" in html
    assert "app.readServerResource" in html
    assert "sentiment://news/${newsId}" in html


@pytest.mark.asyncio
async def test_ask_sentiment_returns_markdown_as_text_and_structured_content():
    class AskSentimentGateway(FakeGateway):
        def post(self, path: str, body: Any = None, **query: Any) -> dict[str, Any]:
            self.calls.append((path, {"body": body, **query}))
            return {
                "markdown": "## 新闻依据\n\n政策新闻（新闻ID：1）",
                "references": [{"index": 1, "news_id": 1, "title": "政策新闻"}],
            }

    gateway = AskSentimentGateway()
    server = create_server(gateway)

    async with Client(server) as client:
        result = await client.call_tool(
            "ask_sentiment",
            {"question": "  政策驱动对下半年债市的影响  "},
        )

    assert not result.is_error
    assert result.content[0].text == "## 新闻依据\n\n政策新闻（新闻ID：1）"
    assert isinstance(result.content[1], ResourceLink)
    assert result.content[1].title == "新闻ID：1｜政策新闻"
    assert result.content[1].uri == "sentiment://news/1"
    assert result.meta["ui"] == {"resourceUri": "ui://sentiment/answer"}
    assert result.structured_content == {
        "markdown": "## 新闻依据\n\n政策新闻（新闻ID：1）",
        "references": [{"index": 1, "news_id": 1, "title": "政策新闻"}],
    }
    assert gateway.calls == [
        (
            "/sapi/mcp-business/ask-sentiment",
            {"body": {"question": "政策驱动对下半年债市的影响"}},
        )
    ]


@pytest.mark.asyncio
async def test_news_resource_renders_analysis_before_article_content():
    class NewsResourceGateway(FakeGateway):
        def get(self, path: str, **query: Any) -> dict[str, Any]:
            self.calls.append((path, query))
            return {
                "id": 42,
                "title": "政策新闻",
                "publish_time": "2026-09-24T09:00:00",
                "source": "测试来源",
                "source_url": "https://example.test/news/42",
                "direction": "利多",
                "horizon": "短期",
                "reason": "流动性改善。",
                "factors": [{"name": "流动性", "category": "LIQUIDITY", "direction": "positive", "driver": "资金面转松"}],
                "content": "这是新闻正文。",
                "content_blocks": [
                    {"block_type": "heading", "block_order": "1", "heading_level": "h2", "content": "正文标题"},
                    {"block_type": "paragraph", "block_order": "2", "content": "这是新闻正文。"},
                ],
            }

    gateway = NewsResourceGateway()
    server = create_server(gateway)

    async with Client(server) as client:
        templates = await client.list_resource_templates()
        result = await client.read_resource("sentiment://news/42")

    assert any(item.uri_template == "sentiment://news/{news_id}" for item in templates.resource_templates)
    text = result.contents[0].text
    assert text.index("## AI 分析") < text.index("## 新闻内容")
    assert "流动性改善。" in text
    assert "## 正文标题" in text
    assert "这是新闻正文。" in text
    assert "查看新闻原文" not in text
    assert "https://example.test/news/42" not in text
    assert gateway.calls == [
        ("/sapi/news/42", {"include_all_models": False})
    ]


@pytest.mark.asyncio
async def test_business_sentiment_tool_posts_to_explicit_backend_contract():
    gateway = FakeGateway()
    server = create_server(gateway)

    async with Client(server) as client:
        result = await client.call_tool(
            "analyze_bond_sentiment",
            {"news_id": 42, "force_refresh": True},
        )

    assert not result.is_error
    assert gateway.calls == [
        (
            "/sapi/mcp-business/analyze-bond-sentiment",
            {"body": {"news_id": 42, "force_refresh": True}},
        )
    ]


@pytest.mark.asyncio
async def test_business_date_range_is_validated_before_backend_call():
    gateway = FakeGateway()
    server = create_server(gateway)

    async with Client(server) as client:
        result = await client.call_tool(
            "analyze_bond_market_sentiment",
            {"start_date": "2026-01-01", "end_date": "2026-03-01"},
        )

    assert result.is_error
    assert gateway.calls == []


@pytest.mark.asyncio
async def test_similar_event_tool_bounds_external_parameters():
    gateway = FakeGateway()
    server = create_server(gateway)

    async with Client(server) as client:
        result = await client.call_tool(
            "analyze_similar_event_impact",
            {
                "news_id": 7,
                "top_k": 999,
                "window_before": 999,
                "window_after": -2,
            },
        )

    assert not result.is_error
    body = gateway.calls[0][1]["body"]
    assert body["top_k"] == 10
    assert body["window_before"] == 30
    assert body["window_after"] == 0


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
