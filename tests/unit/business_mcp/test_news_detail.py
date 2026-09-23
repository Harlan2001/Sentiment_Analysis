from __future__ import annotations

import pytest

from backend.business_mcp import service


@pytest.mark.asyncio
async def test_analyze_bond_sentiment_returns_content_and_source_url(monkeypatch):
    monkeypatch.setattr(
        service,
        "get_news_detail",
        lambda *_args, **_kwargs: {
            "data": {
                "title": "政策新闻",
                "publish_time": "2026-09-23T09:00:00",
                "source": "第一财经",
                "source_url": "https://example.test/news/1",
                "content": "这是新闻原文。",
                "direction": "positive",
                "horizon": "medium",
                "reason": "政策支持",
                "factors": ["货币政策"],
                "model": "test-model",
            }
        },
    )

    result = await service.analyze_bond_sentiment(1)

    assert result["source_url"] == "https://example.test/news/1"
    assert result["content"] == "这是新闻原文。"
    assert result["direction"] == "利多"
    assert result["refreshed"] is False
