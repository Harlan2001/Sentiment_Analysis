"""薄 HTTP client — 标准库 urllib 实现，零第三方依赖。

从 sentiment-cli-for-server/sentiment_cli/client.py 提取，
去掉了 Config 依赖、stream/fetch_openapi/chat_gateway 等 agent 不需要的方法。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple


class BackendError(Exception):
    """HTTP 4xx/5xx 响应。"""

    def __init__(self, status: int, body: Any, url: str):
        self.status = status
        self.body = body
        self.url = url
        super().__init__(f"backend returned HTTP {status} for {url}")


class NetworkError(Exception):
    """后端不可达（DNS/connect/timeout）。"""


class Client:
    """对后端 API 发起 HTTP 请求。"""

    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        # 直接连接，不走系统代理（后端在内网）
        self._opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # ── 内部 ──────────────────────────────────────────────────────────────

    def _build_url(self, path: str, query: Optional[Dict[str, Any]] = None) -> str:
        url = self.base_url + path
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
        headers = {"Accept": "application/json, */*"}
        if has_body:
            headers["Content-Type"] = "application/json"
        if self.token:
            token = self.token
            if not token.lower().startswith("bearer "):
                token = "Bearer " + token
            headers["Authorization"] = token
        return headers

    # ── 公共方法 ──────────────────────────────────────────────────────────

    def request(
        self,
        method: str,
        path: str,
        query: Optional[Dict[str, Any]] = None,
        body: Any = None,
    ) -> Tuple[int, Any]:
        """发起请求，返回 ``(status, parsed_body)``。
        4xx/5xx 抛 BackendError，不可达抛 NetworkError。
        """
        url = self._build_url(path, query)
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method=method.upper(),
            headers=self._headers(data is not None),
        )
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read()
                if _is_binary_response(resp.headers, raw):
                    return resp.status, raw
                return resp.status, _parse(raw, resp.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            raise BackendError(
                exc.code, _parse(raw, exc.headers.get("Content-Type", "")), url
            )
        except (urllib.error.URLError, OSError) as exc:
            raise NetworkError(f"cannot reach {url}: {exc}") from exc


# ── 内部辅助 ──────────────────────────────────────────────────────────────────


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
    ct = (headers.get("Content-Type") or "").lower()
    if any(p in ct for p in _BINARY_PREFIXES):
        return True
    cd = (headers.get("Content-Disposition") or "").lower()
    if "attachment" in cd:
        return True
    return False
