"""板块二《功能与交互修复》研报路由契约测试（TDD）。

对应 docs/PRD-研报分析功能细化.md：
- P0-2 研报库发布日期区间筛选（GET /sapi/research/list 支持 date_start/date_end）
- P0-3 已分析研报可用 force=true 重新分析；批量重跑端点
- P1-5 单篇深度拆解导出 PDF/DOCX（GET /sapi/research/{id}/export）
- P1-6 failed 状态可重新触发分析（锁定既有行为）
- P2-10 关键词检索覆盖正文与 AI 分析字段

不连库：Repository / get_db_connection / 后台线程全部 mock。
"""

from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.config.config import API_PREFIX

PREFIX = f"{API_PREFIX}/research"


# ── 公共夹具 ─────────────────────────────────────────────────────────────


class _FakeResearchRepository:
    """记录查询参数的假仓储。"""

    count_kwargs: dict | None = None
    query_kwargs: dict | None = None
    candidate_rows: list[dict] = []

    @classmethod
    def from_environment(cls):
        return cls()

    def count_reports(self, **kwargs):
        type(self).count_kwargs = kwargs
        return len(self.candidate_rows) or 1

    def query_reports(self, **kwargs):
        type(self).query_kwargs = kwargs
        if self.candidate_rows:
            return self.candidate_rows
        return [
            {col: None for col in (
                "id", "title", "institution", "publish_date", "industry",
                "report_type", "ai_summary", "ai_market_view", "ai_view_strength",
                "ai_symbols", "ai_industries", "ai_key_points", "page_count",
                "file_size_kb", "status", "source", "created_at",
            )}
            | {"id": 1, "title": "示例研报", "status": "analyzed"}
        ]

    def get_filter_facets(self, *args, **kwargs):
        return {"institutions": ["XX 证券"], "industries": ["固收"]}

    def reset_for_reanalysis(self, report_id):
        return None


def _status_cursor(status: str):
    cursor = MagicMock()
    cursor.fetchone.return_value = (1, status)
    return cursor


def _mock_connection(cursor):
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    conn.__enter__.return_value = conn
    conn.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=conn)


@pytest.fixture
def client(monkeypatch):
    # 测试环境默认放行（中间件注入 admin）；显式关掉避免本地 .env 开启鉴权
    monkeypatch.setattr("backend.auth.dependencies.AUTH_ENABLED", False)
    monkeypatch.setattr(
        "backend.routers.research.ResearchReportRepository", _FakeResearchRepository
    )
    _FakeResearchRepository.count_kwargs = None
    _FakeResearchRepository.query_kwargs = None
    from backend.app import app

    return TestClient(app)


# ── P0-2 发布日期区间筛选 ────────────────────────────────────────────────


def test_list_accepts_and_passes_publish_date_range(client):
    r = client.get(
        PREFIX + "/list",
        params={"date_start": "2026-01-01", "date_end": "2026-01-31"},
    )
    assert r.status_code == 200
    assert _FakeResearchRepository.count_kwargs is not None
    assert _FakeResearchRepository.count_kwargs["date_start"] == date(2026, 1, 1)
    assert _FakeResearchRepository.count_kwargs["date_end"] == date(2026, 1, 31)
    assert _FakeResearchRepository.query_kwargs["date_start"] == date(2026, 1, 1)


def test_list_rejects_inverted_date_range(client):
    r = client.get(
        PREFIX + "/list",
        params={"date_start": "2026-02-01", "date_end": "2026-01-01"},
    )
    assert r.status_code == 400


# ── P2-10 关键词检索覆盖正文与 AI 观点字段 ───────────────────────────────


def test_keyword_search_covers_fulltext_and_ai_fields(client):
    r = client.get(PREFIX + "/list", params={"keyword": "降息"})
    assert r.status_code == 200
    cols = _FakeResearchRepository.count_kwargs["keyword_columns"]
    assert "full_text" in cols
    assert "ai_summary" in cols
    assert "ai_key_points" in cols


# ── P0-3 重新分析（force）与 P1-6 失败重试 ──────────────────────────────


def _patch_analyze(monkeypatch, status: str):
    """mock 数据库状态查询与后台分析启动，返回启动 mock 的 spy。"""
    cursor = _status_cursor(status)
    monkeypatch.setattr(
        "backend.routers.research.get_db_connection", _mock_connection(cursor)
    )
    start = MagicMock()
    monkeypatch.setattr("backend.routers.research.run_analysis_async", start)
    return start


def test_failed_report_can_retrigger_analysis(client, monkeypatch):
    """P1-6：failed 状态必须能直接重新分析（当前已支持，锁定行为）。"""
    start = _patch_analyze(monkeypatch, "failed")
    r = client.post(PREFIX + "/1/analyze", params={"model": "glm"})
    assert r.status_code == 200
    start.assert_called_once()


def test_analyzed_report_without_force_is_not_re_run(client, monkeypatch):
    """P0-3：默认不得静默覆盖已有分析（需要显式 force 二次确认）。"""
    start = _patch_analyze(monkeypatch, "analyzed")
    r = client.post(PREFIX + "/1/analyze", params={"model": "glm"})
    assert r.status_code == 200
    start.assert_not_called()


def test_analyzed_report_can_be_reanalyzed_with_force(client, monkeypatch):
    """P0-3：force=true 时允许对 analyzed 研报重新分析。"""
    start = _patch_analyze(monkeypatch, "analyzed")
    r = client.post(PREFIX + "/1/analyze", params={"model": "glm", "force": "true"})
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "processing"
    start.assert_called_once()


def test_batch_reanalyze_endpoint(client, monkeypatch):
    """P0-3：按筛选批量重跑，返回触发/跳过计数，逐份排队。"""
    _FakeResearchRepository.candidate_rows = [
        {"id": 1, "status": "analyzed"},
        {"id": 2, "status": "analyzed"},
    ]
    start = MagicMock()
    monkeypatch.setattr("backend.routers.research.run_analysis_async", start)
    # 单篇状态查询同样放行
    monkeypatch.setattr(
        "backend.routers.research.get_db_connection", _mock_connection(_status_cursor("analyzed"))
    )

    r = client.post(PREFIX + "/reanalyze/batch", json={"institution": "XX 证券"})
    assert r.status_code in (200, 202)
    payload = r.json()["data"]
    assert payload["triggered"] == 2
    assert start.call_count == 2
    _FakeResearchRepository.candidate_rows = []


# ── P1-5 单篇深度拆解导出 ────────────────────────────────────────────────

# 导出端点 SELECT (title, status, ai_deep_markdown)
_EXPORT_ROW = ("测试研报", "analyzed", "# 测试研报 · 深度拆解\n## 一、核心论点（作者观点）\n内容（原文：“……”，第1页）")


def test_export_single_report_pdf(client, monkeypatch):
    cursor = MagicMock()
    cursor.fetchone.return_value = _EXPORT_ROW
    monkeypatch.setattr(
        "backend.routers.research.get_db_connection", _mock_connection(cursor)
    )
    monkeypatch.setattr(
        "backend.report.export_service.generate_pdf",
        lambda *a, **k: b"%PDF-1.4 fake",
    )
    r = client.get(PREFIX + "/1/export", params={"format": "pdf"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_export_rejects_unknown_format(client, monkeypatch):
    cursor = MagicMock()
    cursor.fetchone.return_value = _EXPORT_ROW
    monkeypatch.setattr(
        "backend.routers.research.get_db_connection", _mock_connection(cursor)
    )
    r = client.get(PREFIX + "/1/export", params={"format": "xlsx"})
    assert r.status_code in (400, 422)


def test_export_unanalyzed_report_conflicts(client, monkeypatch):
    cursor = MagicMock()
    cursor.fetchone.return_value = ("测试研报", "parsed", None)
    monkeypatch.setattr(
        "backend.routers.research.get_db_connection", _mock_connection(cursor)
    )
    r = client.get(PREFIX + "/1/export", params={"format": "pdf"})
    assert r.status_code == 409
