"""政策分析要求从 multipart 上传一直到提示词的契约测试。"""

from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.policy_document import llm
from backend.routers import policy_documents


def test_custom_focus_is_included_in_real_prompt(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        llm, "get_analysis_model_info", lambda _: {"provider_model": "provider/glm"}
    )

    def fake_chat(messages, **kwargs):
        captured["prompt"] = messages[0]["content"]
        return json.dumps(
            {
                "summary": "摘要",
                "key_points": ["要点"],
                "domains": ["货币政策"],
                "impact_direction": "neutral",
                "impact_reason": "依据不足",
                "evidence": [],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(llm, "llm_chat", fake_chat)
    result = llm.analyze_policy_document(
        "政策正文",
        focus_title="长端利率影响",
        analysis_requirement="重点关注收益率下行传导",
    )
    assert result["impact_direction"] == "neutral"
    assert "长端利率影响" in captured["prompt"]
    assert "重点关注收益率下行传导" in captured["prompt"]
    assert "政策正文" in captured["prompt"]


def test_upload_passes_focus_and_returns_real_queued_state(monkeypatch):
    captured = {}

    def ingest(pdf_bytes, filename, username, **kwargs):
        captured.update(kwargs)
        return {
            "document_id": 9,
            "title": "政策",
            "status": "uploaded",
            "is_duplicate": False,
        }

    queued = []
    monkeypatch.setattr(policy_documents, "ingest_policy_pdf", ingest)
    monkeypatch.setattr(policy_documents, "start_analysis_async", lambda *args: queued.append(args))
    app = FastAPI()

    @app.middleware("http")
    async def identity(request, call_next):
        request.state.username = "alice"
        return await call_next(request)

    app.include_router(policy_documents.router)
    client = TestClient(app)
    response = client.post(
        "/sapi/policy-documents/upload",
        files={"file": ("policy.pdf", b"%PDF-test", "application/pdf")},
        data={"focus_title": "债市影响", "requirement": "关注长端"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "queued"
    assert captured == {"focus_title": "债市影响", "analysis_requirement": "关注长端"}
    assert queued == [(9, "alice")]


def test_duplicate_upload_does_not_restart_llm(monkeypatch):
    monkeypatch.setattr(
        policy_documents,
        "ingest_policy_pdf",
        lambda *args, **kwargs: {
            "document_id": 9,
            "title": "已有政策",
            "status": "completed",
            "is_duplicate": True,
        },
    )
    def start(*args):
        raise AssertionError("不得自动重跑")

    monkeypatch.setattr(policy_documents, "start_analysis_async", start)
    app = FastAPI()
    app.include_router(policy_documents.router)
    response = TestClient(app).post(
        "/sapi/policy-documents/upload",
        files={"file": ("policy.pdf", b"%PDF-test", "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "completed"
    assert "未自动重新分析" in response.json()["data"]["message"]
