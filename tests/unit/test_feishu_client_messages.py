"""FeishuClient 机器人消息能力单测：monkeypatch requests，不发起真实 HTTP。

覆盖：tenant_access_token 获取/失败、上传文件、发文本、发文件、
以及缺凭据时的连接错误。
"""

import json

import pytest

from backend.integrations.feishu.client import (
    FeishuApiError,
    FeishuClient,
    FeishuConnectionError,
)

API_BASE = "https://open.feishu.cn/open-apis"


class _Resp:
    """最小化的 requests.Response 替身（.json() / .ok / status_code / .text）。"""

    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.text = json.dumps(payload, ensure_ascii=False)

    @property
    def ok(self):
        return 200 <= self.status_code < 400

    def json(self):
        return self._payload


def _client(monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "cli_test_app")
    monkeypatch.setenv("FEISHU_APP_SECRET", "secret")
    return FeishuClient()


def _stub_requests(monkeypatch, payload):
    """把 requests.post / requests.request 都替换为返回固定 payload，并记录调用 (args, kwargs)。"""
    calls = []

    def _handler(*args, **kwargs):
        calls.append((args, kwargs))
        return _Resp(payload)

    monkeypatch.setattr("requests.post", _handler)
    monkeypatch.setattr("requests.request", _handler)
    return calls


# ---- tenant_access_token ----

def test_tenant_access_token_extracts_token(monkeypatch):
    client = _client(monkeypatch)
    calls = _stub_requests(monkeypatch, {"code": 0, "tenant_access_token": "tok-1"})

    assert client.tenant_access_token() == "tok-1"
    args, kwargs = calls[0]
    assert args[0].endswith("/auth/v3/tenant_access_token/internal")
    assert kwargs["json"] == {"app_id": "cli_test_app", "app_secret": "secret"}


def test_tenant_access_token_missing_token_raises(monkeypatch):
    client = _client(monkeypatch)
    _stub_requests(monkeypatch, {"code": 0})
    with pytest.raises(FeishuApiError):
        client.tenant_access_token()


def test_tenant_access_token_error_code_raises(monkeypatch):
    client = _client(monkeypatch)
    _stub_requests(monkeypatch, {"code": 1, "msg": "bad app_secret"})
    with pytest.raises(FeishuApiError, match="bad app_secret"):
        client.tenant_access_token()


def test_tenant_access_token_requires_app_credentials(monkeypatch):
    monkeypatch.setenv("FEISHU_APP_ID", "")
    monkeypatch.setenv("FEISHU_APP_SECRET", "")
    with pytest.raises(FeishuConnectionError):
        FeishuClient().tenant_access_token()


# ---- 消息与文件 ----

def test_send_text_posts_text_message(monkeypatch):
    client = _client(monkeypatch)
    calls = _stub_requests(monkeypatch, {"code": 0})

    client.send_text("tok-1", "oc_group", "今日摘要")

    args, kwargs = calls[0]
    assert args[1].endswith("/im/v1/messages")
    assert kwargs["params"] == {"receive_id_type": "chat_id"}
    assert json.loads(kwargs["json"]["content"]) == {"text": "今日摘要"}
    assert kwargs["json"]["msg_type"] == "text"
    assert kwargs["headers"]["Authorization"] == "Bearer tok-1"


def test_send_file_posts_file_message(monkeypatch):
    client = _client(monkeypatch)
    calls = _stub_requests(monkeypatch, {"code": 0})

    client.send_file("tok-1", "oc_group", "file_key_1")

    args, kwargs = calls[0]
    assert args[1].endswith("/im/v1/messages")
    assert json.loads(kwargs["json"]["content"]) == {"file_key": "file_key_1"}
    assert kwargs["json"]["msg_type"] == "file"


def test_upload_file_returns_file_key(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    pdf = tmp_path / "2026-09-01.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")
    calls = _stub_requests(monkeypatch, {"code": 0, "data": {"file_key": "file_9"}})

    assert client.upload_file("tok-1", str(pdf)) == "file_9"

    args, kwargs = calls[0]
    assert args[1].endswith("/im/v1/files")
    assert kwargs["data"] == {"file_name": "2026-09-01.pdf", "file_type": "pdf"}
    assert "file" in kwargs["files"]


def test_upload_file_missing_path_raises(monkeypatch, tmp_path):
    client = _client(monkeypatch)
    with pytest.raises(FeishuApiError, match="文件不存在"):
        client.upload_file("tok-1", str(tmp_path / "nope.pdf"))


def test_send_text_error_code_raises(monkeypatch):
    client = _client(monkeypatch)
    _stub_requests(monkeypatch, {"code": 999, "msg": "group not found"})
    with pytest.raises(FeishuApiError, match="group not found"):
        client.send_text("tok-1", "oc_group", "今日摘要")
