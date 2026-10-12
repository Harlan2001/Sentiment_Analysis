"""板块二 综合研报生成契约测试（TDD）。

对应 docs/PRD-研报分析功能细化.md：
- P1-7 创建任务支持选择模型；POST /tasks/{id}/regenerate 改需求/来源再生成，
       历史版本保留（version_no 递增）
- P1-8 多研报综合必须包含结构化“观点矩阵”（分歧与共识基于矩阵，而非自由复述）

待实现用例 xfail(strict=True)：实现后删除标记。不连库、不发 LLM 请求。
"""

# ruff: noqa: E501

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.config.config import API_PREFIX

PREFIX = f"{API_PREFIX}/report-generation"


def _source(report_id: int, view: str = "bullish") -> dict:
    return {
        "id": report_id,
        "title": f"研报{report_id}",
        "institution": f"机构{report_id}",
        "publish_date": "2026-01-02",
        "industry": "固收",
        "report_type": "macro",
        "ai_summary": "摘要",
        "ai_key_points": [],
        "ai_evidence": [],
        "ai_market_view": view,
        "ai_time_horizon": "long",
        "full_text": "正文",
        "status": "analyzed",
    }


class _FakeGenRepository:
    def __init__(self):
        self.created_kwargs: dict | None = None
        self.old_task: dict | None = None

    @classmethod
    def from_environment(cls):
        return cls()

    def load_sources(self, report_ids):
        return [_source(rid) for rid in report_ids]

    def create_task(self, **kwargs):
        self.created_kwargs = kwargs
        return {
            "id": "t-new",
            "title": kwargs["title"],
            "requirement": kwargs["requirement"],
            "report_ids_json": [int(s["id"]) for s in kwargs["sources"]],
            "source_snapshot_json": [{"id": s["id"]} for s in kwargs["sources"]],
            "date_start": kwargs["date_start"],
            "date_end": kwargs["date_end"],
            "status": "queued",
            "version_no": kwargs.get("version_no", 1),
            "retry_count": 0,
        }

    def get_task(self, owner, task_id):
        if task_id == "t-old":
            return self.old_task
        return None

    def list_tasks(self, *a, **k):
        return []

    def list_sources(self, **k):
        return {"items": [], "filters": {}}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("backend.auth.dependencies.AUTH_ENABLED", False)
    repo = _FakeGenRepository()
    repository_cls = MagicMock(return_value=repo)
    # 生产代码通过 ReportGenerationRepository.from_environment() 取实例
    repository_cls.from_environment.return_value = repo
    monkeypatch.setattr(
        "backend.routers.report_generation.ReportGenerationRepository",
        repository_cls,
    )
    start = MagicMock()
    monkeypatch.setattr(
        "backend.routers.report_generation.start_report_generation", start
    )
    from backend.app import app

    return TestClient(app), repo, start


def _create_body(**overrides) -> dict:
    body = {
        "title": "利率债观点综述",
        "requirement": "比较机构分歧",
        "report_ids": [1],
        "date_start": "2026-01-01",
        "date_end": "2026-01-31",
    }
    body.update(overrides)
    return body


# ── P1-7 创建任务可指定模型 ──────────────────────────────────────────────


def test_create_task_accepts_model(client):
    test_client, _repo, start = client
    r = test_client.post(PREFIX + "/tasks", json=_create_body(model="deepseek"))
    assert r.status_code == 201
    call = start.call_args
    passed_model = call.kwargs.get("model") or (
        call.args[1] if len(call.args) > 1 else None
    )
    assert passed_model == "deepseek"


# ── P1-7 改需求再生成，保留来源/日期，版本递增 ───────────────────────────


def test_regenerate_creates_new_version_preserving_sources(client):
    test_client, repo, start = client
    repo.old_task = {
        "id": "t-old",
        "title": "利率债观点综述",
        "requirement": "旧需求",
        "report_ids_json": [1, 2],
        "source_snapshot_json": [{"id": 1}, {"id": 2}],
        "date_start": "2026-01-01",
        "date_end": "2026-01-31",
        "status": "completed",
        "retry_count": 0,
    }
    r = test_client.post(
        PREFIX + "/tasks/t-old/regenerate",
        json={"requirement": "新需求：重点看货币政策"},
    )
    assert r.status_code == 201
    data = r.json()["data"]

    # 新版本是新任务，需求更新
    assert data["id"] == "t-new"
    assert data["version_no"] == 2
    assert repo.created_kwargs["requirement"] == "新需求：重点看货币政策"
    # 来源与日期默认沿用原任务，未被清空
    assert repo.created_kwargs["title"] == "利率债观点综述"
    assert [int(s["id"]) for s in repo.created_kwargs["sources"]] == [1, 2]
    assert str(repo.created_kwargs["date_start"]) == "2026-01-01"
    assert str(repo.created_kwargs["date_end"]) == "2026-01-31"
    # 新版本进入异步生成
    start.assert_called_once()


def test_regenerate_allows_overriding_sources(client):
    test_client, repo, _start = client
    repo.old_task = {
        "id": "t-old",
        "title": "利率债观点综述",
        "requirement": "旧需求",
        "report_ids_json": [1, 2],
        "source_snapshot_json": [{"id": 1}, {"id": 2}],
        "date_start": None,
        "date_end": None,
        "status": "completed",
        "retry_count": 0,
    }
    r = test_client.post(
        PREFIX + "/tasks/t-old/regenerate",
        json={"requirement": "增删来源后重生成", "report_ids": [2, 3]},
    )
    assert r.status_code == 201
    assert [int(s["id"]) for s in repo.created_kwargs["sources"]] == [2, 3]


# ── P1-8 综合 prompt 必须包含结构化观点矩阵要求 ──────────────────────────


def test_synthesis_prompt_requires_viewpoint_matrix(monkeypatch):
    from backend.research_report import synthesis

    captured: dict = {}

    class _Completions:
        def create(self, **kwargs):
            captured["prompt"] = kwargs["messages"][0]["content"]
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content="# 综合报告"))],
                usage=SimpleNamespace(prompt_tokens=1, completion_tokens=1, total_tokens=2),
            )

    class _Client:
        def with_options(self, **kwargs):
            return SimpleNamespace(
                chat=SimpleNamespace(completions=_Completions())
            )

    monkeypatch.setattr(synthesis, "get_llm_client", lambda: _Client())

    synthesis.generate_research_synthesis(
        title="利率债综述",
        requirement="比较分歧",
        sources=[_source(1, "bullish"), _source(2, "bearish")],
    )
    assert "观点矩阵" in captured["prompt"]
