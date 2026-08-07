"""复用旧认证与债券 Agent，不导入旧应用进程。"""

from __future__ import annotations

import json
from typing import AsyncIterator, Optional

import httpx

from backend.config.config import LEGACY_API_BASE_URL, LEGACY_API_TIMEOUT_SECONDS


class LegacyApiError(RuntimeError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class LegacyApiClient:
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=LEGACY_API_BASE_URL,
            timeout=httpx.Timeout(LEGACY_API_TIMEOUT_SECONDS),
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def get_current_user(self, authorization: Optional[str]) -> dict:
        headers = {"Authorization": authorization} if authorization else {}
        try:
            response = await self._client.get("/sapi/auth/status", headers=headers)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LegacyApiError(502, "LEGACY_AUTH_UNAVAILABLE", "旧认证服务暂时不可用") from exc
        if not payload.get("authenticated"):
            raise LegacyApiError(401, "AUTHENTICATION_REQUIRED", "请先登录")
        username = str(payload.get("username") or "admin")
        return {
            "id": username,
            "username": username,
            "display_name": str(payload.get("display_name") or username),
            "avatar": payload.get("avatar"),
            "authenticated": True,
            "role": str(payload.get("role") or "user"),
        }

    async def stream_chat(self, messages: list[dict[str, str]], authorization: Optional[str]) -> AsyncIterator[str]:
        headers = {"Accept": "text/event-stream"}
        if authorization:
            headers["Authorization"] = authorization
        try:
            async with self._client.stream("POST", "/sapi/chat", json={"messages": messages, "stream": True}, headers=headers) as response:
                if response.status_code in {401, 403}:
                    raise LegacyApiError(401, "LEGACY_CHAT_UNAUTHORIZED", "Agent 认证失败")
                if response.status_code >= 400:
                    raise LegacyApiError(502, "LEGACY_CHAT_FAILED", "Agent 服务生成失败")
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        break
                    if not raw:
                        continue
                    event = json.loads(raw)
                    if event.get("type") == "content" and event.get("content"):
                        yield str(event["content"])
                    if event.get("type") == "error":
                        raise LegacyApiError(502, "LEGACY_CHAT_FAILED", str(event.get("message") or "Agent 服务生成失败"))
        except LegacyApiError:
            raise
        except httpx.TimeoutException as exc:
            raise LegacyApiError(504, "LEGACY_CHAT_TIMEOUT", "Agent 服务响应超时") from exc
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            raise LegacyApiError(502, "LEGACY_CHAT_UNAVAILABLE", "Agent 服务暂时不可用") from exc

    # ── 策略会话代理 ──────────────────────────────────────────

    async def _strategy_request(self, method: str, path: str, authorization: Optional[str], json_body: Optional[dict] = None) -> dict:
        headers = {"Authorization": authorization} if authorization else {}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        try:
            response = await self._client.request(method, path, json=json_body, headers=headers)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, json.JSONDecodeError) as exc:
            status_code = getattr(exc, "response", None) and getattr(getattr(exc, "response", None), "status_code", None) or 502
            detail = getattr(exc, "response", None)
            body = {}
            if detail is not None:
                try:
                    body = detail.json() if hasattr(detail, "json") else {}
                except (ValueError, json.JSONDecodeError):
                    pass
            raise LegacyApiError(status_code, "LEGACY_STRATEGY_FAILED", str(body.get("detail") or "策略服务暂时不可用")) from exc
        if not payload.get("success"):
            raise LegacyApiError(502, "LEGACY_STRATEGY_FAILED", payload.get("detail") or "策略服务返回异常")
        return payload["data"]

    async def list_strategy_conversations(self, authorization: Optional[str], limit: int = 50) -> list[dict]:
        data = await self._strategy_request("GET", "/sapi/ai-strategy-generation/conversations", authorization)
        return data.get("items", [])

    async def get_strategy_conversation(self, conversation_id: int, authorization: Optional[str]) -> dict:
        return await self._strategy_request("GET", f"/sapi/ai-strategy-generation/conversations/{conversation_id}", authorization)

    async def create_strategy_conversation(self, title: str, authorization: Optional[str]) -> dict:
        return await self._strategy_request("POST", "/sapi/ai-strategy-generation/conversations", authorization, {"title": title})

    async def create_strategy_draft(self, conversation_id: int, requirement: str, lookback_days: int, authorization: Optional[str]) -> dict:
        return await self._strategy_request("POST", f"/sapi/ai-strategy-generation/conversations/{conversation_id}/draft", authorization, {"requirement": requirement, "lookback_days": lookback_days})

    async def confirm_strategy_draft(self, conversation_id: int, assistant_message_id: int, edited_prompt: str, authorization: Optional[str]) -> dict:
        return await self._strategy_request("POST", f"/sapi/ai-strategy-generation/conversations/{conversation_id}/drafts/{assistant_message_id}/confirm", authorization, {"edited_prompt": edited_prompt})

    async def archive_strategy_conversation(self, conversation_id: int, authorization: Optional[str]) -> dict:
        return await self._strategy_request("PATCH", f"/sapi/ai-strategy-generation/conversations/{conversation_id}/archive", authorization)
