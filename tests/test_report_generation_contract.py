import os
from datetime import date
from types import SimpleNamespace

os.environ.setdefault("MYSQL_HOST", "127.0.0.1")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_USER", "test")
os.environ.setdefault("MYSQL_PASSWORD", "test")
os.environ.setdefault("MYSQL_DATABASE", "test")

import pytest
from pydantic import ValidationError

from backend.research_report import synthesis
from backend.routers.report_generation import ReportGenerationCreateRequest


def test_report_generation_request_cleans_and_deduplicates_ids():
    request = ReportGenerationCreateRequest(
        title="  利率债综述  ",
        requirement="  比较机构观点  ",
        report_ids=[3, 1, 3],
        date_start=date(2026, 8, 1),
        date_end=date(2026, 8, 10),
    )
    assert request.title == "利率债综述"
    assert request.requirement == "比较机构观点"
    assert request.report_ids == [3, 1]


def test_report_generation_request_rejects_invalid_range_and_empty_sources():
    with pytest.raises(ValidationError):
        ReportGenerationCreateRequest(
            title="测试",
            requirement="测试",
            report_ids=[],
        )
    with pytest.raises(ValidationError):
        ReportGenerationCreateRequest(
            title="测试",
            requirement="测试",
            report_ids=[1],
            date_start=date(2026, 8, 10),
            date_end=date(2026, 8, 1),
        )


def test_synthesis_reuses_research_client_and_returns_markdown(monkeypatch):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="# 核心结论\n内容 [来源1]"))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )
    calls = []

    class Completions:
        @staticmethod
        def create(**kwargs):
            calls.append(kwargs)
            return response

    monkeypatch.setattr(
        synthesis,
        "_client",
        SimpleNamespace(chat=SimpleNamespace(completions=Completions())),
    )
    content, usage, model = synthesis.generate_research_synthesis(
        title="测试综述",
        requirement="比较观点",
        sources=[
            {
                "id": 1,
                "title": "来源研报",
                "institution": "测试机构",
                "publish_date": "2026-08-01",
                "ai_summary": "摘要",
                "full_text": "正文",
            }
        ],
    )
    assert content.startswith("# 核心结论")
    assert usage["total_tokens"] == 15
    assert model
    assert calls[0]["messages"][0]["content"].find("研报 ID: 1") > 0
