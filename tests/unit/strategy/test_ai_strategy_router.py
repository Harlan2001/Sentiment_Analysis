"""ai_strategy_generation 路由层测试：draft → confirm → 后台生成生命周期。

generate_strategy 是阻塞远端调用，这里整体 mock，只验证编排逻辑：
- 白名单非法标的在 draft 阶段 400；
- 账号级单飞：第二个会话的 confirm 拿到友好 409；
- 后台任务落库成功后释放单飞占位；
- abandon 只允许放弃待确认草稿；
- /instruments 给出白名单元数据。
"""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers import ai_strategy_generation as router_module
from backend.routers.ai_strategy_generation import router


@pytest.fixture
def client(monkeypatch):
    # 本地与 CI 默认无鉴权；显式固定，避免环境差异把 owner 解析打成 401。
    monkeypatch.setattr(router_module, "AUTH_ENABLED", False)
    app = FastAPI()
    app.include_router(router)
    # 必须用 context manager：否则 anyio portal 的事件循环线程是非守护线程，
    # pytest 退出时会挂住数分钟等待 join。
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def _reset_gate():
    yield
    # 上一个用例的后台任务必须正确释放占位，否则会污染后续用例。
    router_module._active_generation_owners.clear()
    router_module._background_generation_tasks.clear()


FAKE_CONTEXT = {
    "prompt": "[USER_EDITABLE_REQUIREMENT]\nx\n[/USER_EDITABLE_REQUIREMENT]",
    "events": [],
    "instrument": "中金所10年期国债期货",
    "instrument_code": "FCT_T_MAIN",
    "backtest_mode": "bar",
    "candle_interval": "1d",
    "frequency": "日频",
    "model_name": "glm",
    "lookback_days": 7,
    "window_start": None,
    "reference_time": None,
    "generated_at": "2026-10-30T12:00:00+08:00",
    "prompt_version": "sentiment-intel-pack-v1",
    "market_scope": {"label": "债券市场"},
    "factor_panel": None,
    "token_used": 100,
    "token_budget": 6000,
}


def _mock_repository(monkeypatch) -> MagicMock:
    repo = MagicMock()
    repo.get_conversation.return_value = {"id": 1, "remote_session_id": None}
    repo.get_prompt_draft.return_value = {
        "id": 2,
        "status": "pending_confirmation",
        "system_draft_prompt": FAKE_CONTEXT["prompt"],
        "context_json": {"instrument_code": "FCT_T_MAIN"},
    }
    repo.confirm_prompt_draft.return_value = True
    repo.create_prompt_draft.return_value = {
        "user_message_id": 1,
        "assistant_message_id": 2,
    }
    repo.abandon_prompt_draft.return_value = True
    monkeypatch.setattr(router_module, "_history_repository", lambda: repo)
    return repo


def _patch_draft_build(monkeypatch):
    monkeypatch.setattr(
        router_module, "build_dream_strategy_prompt", lambda *a, **kw: FAKE_CONTEXT
    )


def _wait_for(predicate, timeout: float = 3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met before timeout")


class TestDraftLifecycle:
    def test_draft_rejects_instrument_outside_whitelist(self, client, monkeypatch):
        _mock_repository(monkeypatch)
        response = client.post(
            "/sapi/ai-strategy-generation/conversations/1/draft",
            json={"requirement": "随便生成一个", "instrument_code": "EVIL_CODE"},
        )
        assert response.status_code == 400
        assert "白名单" in response.json()["detail"]

    def test_draft_then_confirm_runs_background_generation(self, client, monkeypatch):
        repo = _mock_repository(monkeypatch)
        _patch_draft_build(monkeypatch)
        monkeypatch.setattr(
            router_module, "apply_user_edited_requirement", lambda draft, edited: draft
        )

        done = threading.Event()

        def _fake_generate(*args, **kwargs):
            done.wait(timeout=5)
            return {
                "summary": "策略版本和回测结果已生成。",
                "strategy": {
                    "name": "demo",
                    "description": "demo",
                    "code": "self.MarketOrder('FCT_T_MAIN', 1)",
                },
                "backtest_passed": True,
                "backtest_exit_code": 0,
                "backtest_summary": "成交笔数: 3",
                "message_id": "m1",
            }

        monkeypatch.setattr(router_module, "generate_strategy", _fake_generate)

        draft_resp = client.post(
            "/sapi/ai-strategy-generation/conversations/1/draft",
            json={"requirement": "双均线策略"},
        )
        assert draft_resp.status_code == 200
        assert draft_resp.json()["data"]["status"] == "pending_confirmation"
        repo.create_prompt_draft.assert_called_once()
        # instrument 标签要带进会话列（历史上该列恒 NULL）。
        assert (
            repo.create_prompt_draft.call_args.kwargs["instrument_label"]
            == "中金所10年期国债期货"
        )

        confirm_resp = client.post(
            "/sapi/ai-strategy-generation/conversations/1/drafts/2/confirm",
            json={"edited_prompt": "x"},
        )
        assert confirm_resp.status_code == 200
        assert confirm_resp.json()["data"]["status"] == "running"
        assert router_module._active_generation_owners.get("admin") == 1

        done.set()
        _wait_for(lambda: repo.complete_generation.called)
        _wait_for(lambda: "admin" not in router_module._active_generation_owners)


class TestSingleFlight:
    def test_second_conversation_gets_friendly_409(self, client, monkeypatch):
        repo = _mock_repository(monkeypatch)

        def _conversation(owner, conversation_id, *, include_private=False):
            return {"id": conversation_id, "remote_session_id": None}

        repo.get_conversation.side_effect = _conversation
        monkeypatch.setattr(
            router_module, "apply_user_edited_requirement", lambda draft, edited: draft
        )

        release = threading.Event()

        def _fake_generate(*args, **kwargs):
            release.wait(timeout=5)
            return {
                "summary": "ok",
                "strategy": {"name": "n", "description": "d", "code": "self.Buy('x', 1)"},
            }

        monkeypatch.setattr(router_module, "generate_strategy", _fake_generate)

        first = client.post(
            "/sapi/ai-strategy-generation/conversations/11/drafts/10/confirm",
            json={"edited_prompt": "x"},
        )
        assert first.status_code == 200

        second = client.post(
            "/sapi/ai-strategy-generation/conversations/12/drafts/20/confirm",
            json={"edited_prompt": "x"},
        )
        try:
            assert second.status_code == 409
            detail = second.json()["detail"]
            assert "同一时间只允许运行一个" in detail
            assert "#11" in detail
        finally:
            release.set()
            _wait_for(lambda: "admin" not in router_module._active_generation_owners)

    def test_confirmed_draft_cannot_be_confirmed_again(self, client, monkeypatch):
        repo = _mock_repository(monkeypatch)
        repo.get_prompt_draft.return_value = {
            "id": 2,
            "status": "succeeded",
            "system_draft_prompt": "x",
            "context_json": {},
        }
        response = client.post(
            "/sapi/ai-strategy-generation/conversations/1/drafts/2/confirm",
            json={"edited_prompt": "x"},
        )
        assert response.status_code == 409
        repo.confirm_prompt_draft.assert_not_called()


class TestAbandonDraft:
    def test_abandon_pending_draft(self, client, monkeypatch):
        _mock_repository(monkeypatch)
        response = client.post(
            "/sapi/ai-strategy-generation/conversations/1/drafts/2/abandon"
        )
        assert response.status_code == 200
        assert response.json()["data"]["status"] == "cancelled"

    def test_abandon_confirmed_draft_is_409(self, client, monkeypatch):
        repo = _mock_repository(monkeypatch)
        repo.get_prompt_draft.return_value = {
            "id": 2,
            "status": "running",
            "system_draft_prompt": "x",
            "context_json": {},
        }
        response = client.post(
            "/sapi/ai-strategy-generation/conversations/1/drafts/2/abandon"
        )
        assert response.status_code == 409
        repo.abandon_prompt_draft.assert_not_called()

    def test_abandon_unknown_draft_is_404(self, client, monkeypatch):
        repo = _mock_repository(monkeypatch)
        repo.get_prompt_draft.return_value = None
        response = client.post(
            "/sapi/ai-strategy-generation/conversations/1/drafts/99/abandon"
        )
        assert response.status_code == 404


class TestInstruments:
    def test_lists_whitelist_and_exclusions(self, client):
        response = client.get("/sapi/ai-strategy-generation/instruments")
        assert response.status_code == 200
        data = response.json()["data"]
        codes = {item["code"] for item in data["instruments"]}
        assert {"FCT_T_MAIN", "100040", "IBK_CDB10_ACTV"} <= codes
        assert data["default"] == "FCT_T_MAIN"
        assert any(item["code"] == "FCT_AU_MAIN" for item in data["excluded"])
