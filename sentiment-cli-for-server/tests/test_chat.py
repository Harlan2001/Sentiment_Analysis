"""Tests for the `chat ask` operation (POST /sapi/chat).

Offline + stub-backed, no live backend, no network egress. Exercises the
full CLI round-trip: arg parsing -> body coercion -> HTTP POST -> JSON
envelope, plus the error / auth / escape-hatch paths.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from io import StringIO

from sentiment_cli import cli as cli_mod
from sentiment_cli.cli import (
    EXIT_BACKEND,
    EXIT_FAILURE,
    EXIT_OK,
    Skin,
    build_op_parser,
    cmd_call,
    run_operation,
)
from sentiment_cli.client import Client, NetworkError
from sentiment_cli.config import Config
from sentiment_cli.spec import load_spec

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from stub_backend import start_stub  # noqa: E402

MSG_OK = '[{"role":"user","content":"你好"}]'
MSG_BOOM = '[{"role":"user","content":"__boom__"}]'


def _capture(fn):
    """Run fn() with stdout redirected to a StringIO; return (rc, text)."""
    buf = StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        rc = fn()
    finally:
        sys.stdout = old
    return rc, buf.getvalue()


class ChatParseTests(unittest.TestCase):
    def test_op_is_registered(self):
        spec = load_spec()
        op = spec.find("chat", "ask")
        self.assertIsNotNone(op)
        self.assertEqual(op.method, "POST")
        self.assertEqual(op.path, "/sapi/chat")
        # messages is required, stream / enable_tools are optional.
        by_name = {p.name: p for p in op.params}
        self.assertIn("messages", by_name)
        self.assertTrue(by_name["messages"].required)
        self.assertEqual(by_name["messages"].type, "array")
        self.assertFalse(by_name["stream"].required)
        self.assertFalse(by_name["enable_tools"].required)

    def test_parser_requires_messages(self):
        op = load_spec().find("chat", "ask")
        parser = build_op_parser(op)
        with self.assertRaises(SystemExit):
            parser.parse_args([])  # missing required --messages

    def test_parser_coerces_array_and_flags(self):
        op = load_spec().find("chat", "ask")
        parser = build_op_parser(op)
        ns = parser.parse_args(
            ["--messages", MSG_OK, "--stream", "false", "--enable-tools", "false"]
        )
        # At the parser level values are still raw CLI strings; coercion to
        # (list / bool) happens later inside run_operation.
        self.assertEqual(ns.messages, MSG_OK)
        self.assertEqual(ns.stream, "false")   # raw string at parse time
        self.assertEqual(ns.enable_tools, "false")


class ChatStubTests(unittest.TestCase):
    """Success / error / auth paths against the local stub backend."""

    @classmethod
    def setUpClass(cls):
        cls.server, cls.base = start_stub()
        cls.spec = load_spec(None)
        cls.op = cls.spec.find("chat", "ask")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _ctx(self, token=None):
        return Client(Config(base_url=self.base, token=token)), Skin()

    def test_success_sends_body_and_parses(self):
        client, skin = self._ctx()
        rc, out = _capture(
            lambda: run_operation(
                self.op,
                ["--messages", MSG_OK, "--stream", "false",
                 "--enable-tools", "false", "--json"],
                client, skin, force_json=True,
            )
        )
        self.assertEqual(rc, EXIT_OK)
        env = json.loads(out)
        self.assertTrue(env["ok"])
        self.assertEqual(env["status"], 200)
        self.assertEqual(env["data"]["content"], "stub reply")
        self.assertEqual(env["data"]["usage"]["total_tokens"], 8)
        # Echo proves the CLI sent the messages + stream/enable_tools flags.
        received = env["data"]["received"]
        self.assertEqual(received["messages"], [{"role": "user", "content": "你好"}])
        self.assertIs(received.get("stream"), False)
        self.assertIs(received.get("enable_tools"), False)

    def test_omitting_stream_sends_no_field(self):
        # The server defaults stream=true; the CLI must NOT invent a field.
        client, skin = self._ctx()
        rc, out = _capture(
            lambda: run_operation(
                self.op, ["--messages", MSG_OK, "--json"],
                client, skin, force_json=True,
            )
        )
        self.assertEqual(rc, EXIT_OK)
        received = json.loads(out)["data"]["received"]
        self.assertNotIn("stream", received)

    def test_injects_bearer_token(self):
        client, skin = self._ctx(token="secret-token")
        rc, out = _capture(
            lambda: run_operation(
                self.op, ["--messages", MSG_OK, "--stream", "false", "--json"],
                client, skin, force_json=True,
            )
        )
        self.assertEqual(rc, EXIT_OK)
        auth = json.loads(out)["data"]["auth_echo"]
        self.assertEqual(auth, "Bearer secret-token")

    def test_server_error_500(self):
        client, skin = self._ctx()
        rc, out = _capture(
            lambda: run_operation(
                self.op, ["--messages", MSG_BOOM, "--stream", "false", "--json"],
                client, skin, force_json=True,
            )
        )
        self.assertEqual(rc, EXIT_BACKEND)
        env = json.loads(out)
        self.assertFalse(env["ok"])
        self.assertEqual(env["status"], 500)


class ChatEscapeHatchTests(unittest.TestCase):
    """The `call` escape-hatch bypasses argparse required-flag checks,
    so it is the only way to reach the server's 422 validation path."""

    @classmethod
    def setUpClass(cls):
        cls.server, cls.base = start_stub()
        cls.client = Client(Config(base_url=cls.base))

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_call_empty_body_422(self):
        rc, out = _capture(
            lambda: cmd_call(
                self.client,
                ["POST", "/sapi/chat", "--body", "{}", "--json"],
                Skin(), force_json=True,
            )
        )
        self.assertEqual(rc, EXIT_BACKEND)
        env = json.loads(out)
        self.assertFalse(env["ok"])
        self.assertEqual(env["status"], 422)


class ChatConnectErrorTests(unittest.TestCase):
    """Backend unreachable -> NetworkError -> EXIT_FAILURE (1)."""

    def test_connect_error(self):
        # Port 1 is never open; connection refused is immediate & offline.
        client = Client(Config(base_url="http://127.0.0.1:1"))
        rc, out = _capture(
            lambda: run_operation(
                load_spec().find("chat", "ask"),
                ["--messages", MSG_OK, "--stream", "false", "--json"],
                client, Skin(), force_json=True,
            )
        )
        self.assertEqual(rc, EXIT_FAILURE)


class ChatSubprocessTests(unittest.TestCase):
    """End-to-end through the actual `sentiment` entry point."""

    @classmethod
    def setUpClass(cls):
        cls.server, cls.base = start_stub()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _run(self, *args):
        env = dict(os.environ)
        env["SENTIMENT_BASE_URL"] = self.base
        env["SENTIMENT_USE_PROXY"] = "false"
        # disable the local gateway so this offline test exercises the
        # OpenAPI /sapi/chat stub path (not the live KingStar gateway).
        # load_dotenv() only skips a key already in the env, so an
        # empty value here prevents sentiment-cli/.env from overriding.
        env["SENTIMENT_CHAT_GATEWAY_URL"] = ""
        env["SENTIMENT_CHAT_GATEWAY_KEY"] = ""
        env.pop("SENTIMENT_TOKEN", None)
        return subprocess.run(
            [sys.executable, "-m", "sentiment_cli", *args],
            cwd=ROOT, capture_output=True, text=True, env=env,
        )

    def test_subprocess_chat_ask(self):
        r = self._run(
            "chat", "ask", "--messages", MSG_OK, "--stream", "false", "--json"
        )
        self.assertEqual(r.returncode, EXIT_OK, r.stderr)
        env = json.loads(r.stdout)
        self.assertTrue(env["ok"])
        self.assertEqual(env["data"]["content"], "stub reply")
        self.assertEqual(
            env["data"]["received"]["messages"],
            [{"role": "user", "content": "你好"}],
        )


if __name__ == "__main__":
    unittest.main()
