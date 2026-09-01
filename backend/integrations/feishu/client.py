from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from backend.config.config import get_requests_proxies
from backend.integrations.feishu.repository import (
    FeishuConnectionError,
    FeishuRefreshFailure,
)


class FeishuApiError(FeishuConnectionError):
    pass


class FeishuClient:
    API_BASE = "https://open.feishu.cn/open-apis"
    AUTHORIZE_URL = "https://accounts.feishu.cn/open-apis/authen/v1/authorize"

    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID", "").strip()
        self.app_secret = os.getenv("FEISHU_APP_SECRET", "").strip()
        self.redirect_uri = os.getenv("FEISHU_OAUTH_REDIRECT_URI", "").strip()

    def authorize_url(self, state: str) -> str:
        self._require_app_config()
        return f"{self.AUTHORIZE_URL}?{urlencode({'app_id': self.app_id, 'redirect_uri': self.redirect_uri, 'state': state})}"

    def exchange_code(self, code: str) -> dict[str, Any]:
        app_token = self._app_access_token()
        payload = self._post(
            "/authen/v1/oidc/access_token",
            {"grant_type": "authorization_code", "code": code},
            app_token,
        )
        return self._normalise_token(payload)

    def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        app_token = self._app_access_token()
        payload = self._post(
            "/authen/v1/oidc/refresh_access_token",
            {"grant_type": "refresh_token", "refresh_token": refresh_token},
            app_token,
        )
        return self._normalise_token(payload)

    def search_docs(self, token: str, query: str, page_size: int = 10) -> dict[str, Any]:
        return self._post(
            "/suite/docs-api/search/object",
            {"search_key": query, "count": min(page_size, 20), "offset": 0}, token,
        )

    def get_doc_content(self, token: str, document_id: str) -> dict[str, Any]:
        return self._get(f"/docx/v1/documents/{document_id}/raw_content", token)

    def get_bitable_metadata(self, token: str, app_token: str) -> dict[str, Any]:
        return self._get(f"/bitable/v1/apps/{app_token}/tables?page_size=100", token)

    def list_bitable_records(
        self, token: str, app_token: str, table_id: str, page_size: int = 100
    ) -> dict[str, Any]:
        return self._get(
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records?page_size={min(page_size, 100)}",
            token,
        )

    def list_chats(self, token: str, page_size: int = 50) -> dict[str, Any]:
        return self._get(f"/im/v1/chats?page_size={min(page_size, 100)}", token)

    def list_messages(self, token: str, chat_id: str, page_size: int = 50) -> dict[str, Any]:
        query = urlencode(
            {"container_id_type": "chat", "container_id": chat_id, "page_size": min(page_size, 100)}
        )
        return self._get(f"/im/v1/messages?{query}", token)

    def _app_access_token(self) -> str:
        self._require_app_config()
        response = requests.post(
            f"{self.API_BASE}/auth/v3/app_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=20,
            proxies=get_requests_proxies(),
        )
        payload = self._read_response(response)
        token = payload.get("app_access_token") or payload.get("data", {}).get("app_access_token")
        if not token:
            raise FeishuApiError("飞书未返回 app_access_token。")
        return str(token)

    def _get(self, path: str, token: str) -> dict[str, Any]:
        return self._request("GET", path, token=token)

    def _post(self, path: str, data: dict[str, Any], token: str) -> dict[str, Any]:
        return self._request("POST", path, token=token, data=data)

    def _request(
        self, method: str, path: str, *, token: str, data: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        response = requests.request(
            method,
            f"{self.API_BASE}{path}",
            json=data,
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
            proxies=get_requests_proxies(),
        )
        return self._read_response(response)

    @staticmethod
    def _normalise_token(payload: dict[str, Any]) -> dict[str, Any]:
        data = payload.get("data", payload)
        access_token = data.get("access_token") or data.get("user_access_token")
        refresh_token = data.get("refresh_token")
        if not access_token or not refresh_token:
            raise FeishuApiError("飞书授权未返回完整的访问令牌，请重新授权。")
        return {**data, "access_token": access_token, "refresh_token": refresh_token}

    @staticmethod
    def _read_response(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise FeishuApiError(f"飞书接口返回了无效响应（HTTP {response.status_code}）。") from exc
        if not response.ok or payload.get("code", 0) != 0:
            message = payload.get("msg") or payload.get("message") or f"HTTP {response.status_code}"
            raise FeishuApiError(f"飞书接口调用失败：{message}")
        return payload

    def _require_app_config(self) -> None:
        missing = [name for name, value in (("FEISHU_APP_ID", self.app_id), ("FEISHU_APP_SECRET", self.app_secret), ("FEISHU_OAUTH_REDIRECT_URI", self.redirect_uri)) if not value]
        if missing:
            raise FeishuConnectionError(f"飞书连接尚未配置：{', '.join(missing)}。")


def active_access_token(repository: Any, client: FeishuClient, username: str) -> str | None:
    """Return a working user access token, refreshing the stored connection when it nears expiry.

    Returns ``None`` when the user has never connected. Raises
    :class:`~backend.integrations.feishu.repository.FeishuRefreshFailure` if a previously
    stored connection disappears while its token is being refreshed.
    """
    connection = repository.get_connection(username, include_tokens=True)
    if connection is None:
        return None
    expires_at = connection.get("expires_at")
    if (
        isinstance(expires_at, datetime)
        and expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc) + timedelta(minutes=2)
    ):
        repository.upsert_connection(
            username, {**connection, **client.refresh_token(connection["refresh_token"])}
        )
        connection = repository.get_connection(username, include_tokens=True)
        if connection is None:
            raise FeishuRefreshFailure("飞书连接已失效，请重新连接。")
    return connection["access_token"]