"""Local stub backend for OFFLINE end-to-end tests.

Spins up a *real* HTTP server on 127.0.0.1 (random port) that emulates
the handful of endpoints the E2E suite touches. This removes every dependency
on the live internal "Bond Yield Backend" and on network egress, so the tests
run green:

  * inside the sandbox        (loopback is always reachable, no egress)
  * in CI                   (no secrets, no internal IP)
  * for the subprocess CLI   (the child inherits SENTIMENT_BASE_URL)

Only the behaviour the assertions rely on is faked — real HTTP status codes,
JSON bodies, and the streaming/error paths are exercised.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent          # sentiment-cli/
BUNDLE = ROOT / "sentiment_cli" / "data" / "openapi.json"


def _json(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload, ctype: str = "application/json") -> None:
        if isinstance(payload, (bytes, bytearray)):
            body = bytes(payload)
        elif isinstance(payload, (dict, list)):
            body = _json(payload)
        else:
            body = str(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _route(self, method: str, body=None):
        path = urlparse(self.path).path
        if method == "POST" and path == "/sapi/chat":
            msgs = (body or {}).get("messages")
            if not isinstance(msgs, list) or not msgs:
                return 422, {"detail": [{"loc": ["body", "messages"],
                                         "msg": "field required"}]}
            # Echo the whole request body + the Authorization header so tests
            # can assert the CLI sent the right messages / token.
            if any(isinstance(m, dict) and m.get("content") == "__boom__"
                   for m in msgs):
                return 500, {"error": "internal chat failure"}
            return 200, {
                "received": body,
                "content": "stub reply",
                "role": "assistant",
                "usage": {"total_tokens": 8},
                "auth_echo": self.headers.get("Authorization"),
            }
        if method == "GET" and path == "/health":
            return 200, {"status": "ok"}
        if method == "GET" and path == "/openapi.json":
            try:
                return 200, json.loads(BUNDLE.read_text(encoding="utf-8"))
            except OSError:
                return 500, {"error": "bundle missing"}
        if method == "GET" and path == "/sapi/news":
            return 200, [{"id": 1, "title": "stub news", "view": "best"}]
        if method == "GET" and path.startswith("/sapi/news/"):
            return 200, {"id": 1, "title": "stub news detail", "content": "..."}
        if method == "GET" and path == "/sapi/factors":
            return 200, {"factors": [{"code": "F1", "name": "stub factor"}]}
        if method == "POST" and path == "/sapi/auth/login":
            # Emulate a FastAPI 422 validation failure.
            return 422, {"detail": [{"loc": ["body"], "msg": "field required"}]}
        if method == "GET" and path.startswith("/sapi/report/files/"):
            # Emulate a binary PDF download (Content-Disposition: attachment).
            fname = path.rsplit("/", 1)[-1] or "report.pdf"
            pdf = b"%PDF-1.4\n% stub prediction report\n" + b"X" * 64
            self.send_response(200)
            self.send_header("Content-Type", "application/pdf")
            self.send_header("Content-Disposition", f"attachment; filename={fname}")
            self.send_header("Content-Length", str(len(pdf)))
            self.end_headers()
            self.wfile.write(pdf)
            return 200, None
        return 404, {"error": "not stubbed", "path": path}

    def do_GET(self):
        code, payload = self._route("GET")
        if payload is not None:
            self._send(code, payload)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        body = None
        if raw:
            try:
                body = json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                body = None
        code, payload = self._route("POST", body)
        if payload is not None:
            self._send(code, payload)

    def log_message(self, *args):  # silence stub chatter
        pass


def start_stub():
    """Start the stub server; return (server, base_url)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{port}"
