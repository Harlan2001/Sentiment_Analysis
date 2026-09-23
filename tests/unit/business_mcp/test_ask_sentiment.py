from __future__ import annotations

import pytest

from backend.business_mcp import service
from backend.routers.mcp_business import AskSentimentRequest
from backend.routers.mcp_business import ask_sentiment as ask_sentiment_route


@pytest.mark.asyncio
async def test_ask_sentiment_aggregates_streaming_markdown(monkeypatch):
    async def fake_stream(messages, username):
        assert messages == [{"role": "user", "content": "政策驱动对债市的影响"}]
        assert username == "anonymous"
        yield "## 结论\n\n"
        yield "[查看新闻原文](https://example.test/news/1)"

    monkeypatch.setattr(service, "agent_chat_stream", fake_stream)

    result = await service.ask_sentiment("政策驱动对债市的影响")

    assert result == {
        "markdown": "## 结论\n\n[查看新闻原文](https://example.test/news/1)"
    }


@pytest.mark.asyncio
async def test_ask_sentiment_rejects_empty_agent_reply(monkeypatch):
    async def fake_stream(_messages, _username):
        if False:
            yield ""

    monkeypatch.setattr(service, "agent_chat_stream", fake_stream)

    with pytest.raises(RuntimeError, match="未生成有效回复"):
        await service.ask_sentiment("测试问题")


@pytest.mark.asyncio
async def test_ask_sentiment_route_normalizes_question(monkeypatch):
    async def fake_ask_sentiment(question):
        assert question == "政策驱动对债市的影响"
        return {"markdown": "## 结论"}

    monkeypatch.setattr(service, "ask_sentiment", fake_ask_sentiment)

    response = await ask_sentiment_route(
        AskSentimentRequest(question="  政策驱动对债市的影响  ")
    )

    assert response == {"data": {"markdown": "## 结论"}}
