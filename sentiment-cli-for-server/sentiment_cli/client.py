"""Thin HTTP client over the running backend — standard library only."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterator, Optional, Tuple

from .config import Config


class BackendError(Exception):
    """Raised for HTTP 4xx/5xx responses. Carries status + parsed body."""

    def __init__(self, status: int, body: Any, url: str):
        self.status = status
        self.body = body
        self.url = url
        super().__init__(f"backend returned HTTP {status} for {url}")


class NetworkError(Exception):
    """Raised when the backend is unreachable (DNS/connect/timeout)."""


class Client:
    def __init__(self, config: Config):
        self.config = config
        if config.use_proxy:
            self._opener = urllib.request.build_opener()
        else:
            # Explicitly disable proxies: internal backend must be reached direct.
            self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # ---- url helpers ---------------------------------------------------------
    def build_url(self, path: str, query: Optional[Dict[str, Any]] = None) -> str:
        url = self.config.base_url + path
        if query:
            pairs = []
            for key, value in query.items():
                if value is None:
                    continue
                if isinstance(value, bool):
                    value = "true" if value else "false"
                pairs.append((key, str(value)))
            if pairs:
                url += "?" + urllib.parse.urlencode(pairs)
        return url

    def _headers(self, has_body: bool) -> Dict[str, str]:
        headers = {"Accept": "application/json, application/pdf, */*"}
        if has_body:
            headers["Content-Type"] = "application/json"
        if self.config.token:
            token = self.config.token
            if not token.lower().startswith("bearer "):
                token = "Bearer " + token
            headers["Authorization"] = token
        return headers

    # ---- core request --------------------------------------------------------
    def request(
        self,
        method: str,
        path: str,
        query: Optional[Dict[str, Any]] = None,
        body: Any = None,
    ) -> Tuple[int, Any]:
        """Perform a request and return (status, parsed_body).

        Raises BackendError on 4xx/5xx and NetworkError when unreachable.
        """
        url = self.build_url(path, query)
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method=method.upper(), headers=self._headers(data is not None)
        )
        try:
            with self._opener.open(req, timeout=self.config.timeout) as resp:
                raw = resp.read()
                # Binary / file responses (PDF, images, zips...) must be
                # returned as raw bytes, never decoded as text — decoding
                # corrupts them.
                if _is_binary_response(resp.headers, raw):
                    return resp.status, raw
                return resp.status, _parse(raw, resp.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            raise BackendError(exc.code, _parse(raw, exc.headers.get("Content-Type", "")), url)
        except (urllib.error.URLError, OSError) as exc:
            raise NetworkError(f"cannot reach {url}: {exc}") from exc

    def stream(
        self,
        method: str,
        path: str,
        query: Optional[Dict[str, Any]] = None,
        body: Any = None,
    ) -> Iterator[str]:
        """Yield decoded lines from a streaming endpoint (SSE / chunked)."""
        url = self.build_url(path, query)
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method=method.upper(), headers=self._headers(data is not None)
        )
        try:
            resp = self._opener.open(req, timeout=self.config.timeout)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            raise BackendError(exc.code, _parse(raw, exc.headers.get("Content-Type", "")), url)
        except (urllib.error.URLError, OSError) as exc:
            raise NetworkError(f"cannot reach {url}: {exc}") from exc
        with resp:
            for line in resp:
                yield line.decode("utf-8", "replace").rstrip("\n")

    def health(self) -> Tuple[int, Any]:
        return self.request("GET", "/health")

    def fetch_openapi(self) -> Dict[str, Any]:
        _status, body = self.request("GET", "/openapi.json")
        if not isinstance(body, dict):
            raise NetworkError("openapi.json was not a JSON object")
        return body

    # ---- chat gateway (client-side direct call, bypasses /sapi/chat) -----
    def chat_gateway(
        self,
        messages: Any,
        model: Optional[str] = None,
        stream: bool = False,
        enable_tools: bool = False,
        timeout: Optional[float] = None,
    ) -> Tuple[str, Dict[str, int]]:
        """Direct client-side call to the KingStar OpenAI-compatible gateway.

        Bypasses the (currently broken) ``/sapi/chat`` server endpoint.
        The gateway URL + key are READ from the server's ``/opt/sentiment/.env``
        and configured into the local CLI environment (``SENTIMENT_CHAT_GATEWAY_*``).

        Returns ``(content:str, usage:dict)``. Raises ``NetworkError``
        (unreachable) or ``BackendError`` (gateway 4xx/5xx or upstream error).
        """
        if not self.config.chat_gateway_url or not self.config.chat_gateway_key:
            raise NetworkError(
                "chat gateway not configured — set SENTIMENT_CHAT_GATEWAY_URL/KEY "
                "(see .env.example). Falling back requires a working /sapi/chat."
            )
        base = self.config.chat_gateway_url.rstrip("/")
        url = base + "/chat/completions"
        # Always request a non-streamed completion: the CLI does not parse SSE,
        # and the server's /sapi/chat proved streaming is not the issue.
        payload = {
            "model": model or self.config.chat_gateway_model,
            "messages": messages,
            "temperature": 0.7,
            "stream": False,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.config.chat_gateway_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        req = urllib.request.Request(url, data=data, method="POST", headers=headers)
        try:
            with self._opener.open(req, timeout=timeout or self.config.timeout) as resp:
                raw = resp.read()
                status = resp.status
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            raise BackendError(
                exc.code, _parse(raw, exc.headers.get("Content-Type", "")), url
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise NetworkError(f"cannot reach gateway {url}: {exc}") from exc
        if status >= 400:
            raise BackendError(status, _parse(raw, ""), url)
        data_obj = _parse(raw, "application/json")
        if isinstance(data_obj, dict) and data_obj.get("error"):
            raise BackendError(200, data_obj["error"], url)
        return self._extract_chat_content(data_obj), self._extract_usage(data_obj)

    @staticmethod
    def _extract_chat_content(data_obj: Any) -> str:
        if not isinstance(data_obj, dict):
            return ""
        try:
            return data_obj["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            return ""

    @staticmethod
    def _extract_usage(data_obj: Any) -> Dict[str, int]:
        if not isinstance(data_obj, dict):
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        u = data_obj.get("usage") or {}
        return {
            "prompt_tokens": int(u.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(u.get("completion_tokens", 0) or 0),
            "total_tokens": int(u.get("total_tokens", 0) or 0),
        }


def _parse(raw: bytes, content_type: str) -> Any:
    if not raw:
        return None
    text = raw.decode("utf-8", "replace")
    if "application/json" in content_type or text[:1] in "{[":
        try:
            return json.loads(text)
        except ValueError:
            return text
    return text


# Content-Type prefixes that denote a binary / file payload (not JSON/text).
_BINARY_PREFIXES = (
    "application/pdf",
    "application/octet-stream",
    "application/zip",
    "application/x-tar",
    "application/x-gzip",
    "application/msword",
    "application/vnd.openxmlformats",
    "application/vnd.ms-excel",
    "image/",
    "audio/",
    "video/",
)


def _is_binary_response(headers, raw: bytes) -> bool:
    """True when the response should be handed back as raw bytes (a file)."""
    ct = (headers.get("Content-Type") or "").lower()
    if any(p in ct for p in _BINARY_PREFIXES):
        return True
    # Server hints an attachment via Content-Disposition.
    cd = (headers.get("Content-Disposition") or "").lower()
    if "attachment" in cd:
        return True
    return False
