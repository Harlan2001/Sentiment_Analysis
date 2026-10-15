from backend.agent.references import cited_news_references, extract_news_references


def test_extracts_deduplicated_news_references_from_news_tool_result():
    result = {
        "data": {
            "items": [
                {
                    "id": 7,
                    "title": "政策新闻",
                    "publish_time": "2026-09-24T09:00:00",
                    "source": "第一财经",
                    "source_url": "https://example.test/news/7",
                },
                {"news_id": 7, "title": "政策新闻"},
            ]
        }
    }

    assert extract_news_references("news_get_news", result) == [{
        "news_id": 7,
        "title": "政策新闻",
        "publish_time": "2026-09-24T09:00:00",
        "source": "第一财经",
        "source_url": "https://example.test/news/7",
    }]


def test_rejects_dangerous_urls_and_only_keeps_cited_tool_results():
    references = extract_news_references(
        "news_get_news",
        {"data": [
            {"id": 1, "title": "被引用新闻", "source_url": "javascript:alert(1)"},
            {"id": 2, "title": "未引用新闻", "source_url": "https://example.test/2"},
        ]},
    )

    assert cited_news_references("结论来自被引用新闻", references) == [{
        "index": 1,
        "news_id": 1,
        "title": "被引用新闻",
        "publish_time": None,
        "source": None,
        "source_url": None,
    }]


def test_ignores_news_shaped_data_from_non_news_tools():
    assert extract_news_references(
        "feishu_search_docs", {"id": 1, "title": "不是新闻"}
    ) == []
