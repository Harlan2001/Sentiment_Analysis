"""Tests for binary/file-download support (the bug that broke `report download`).

Pure + stub-backed, no live backend, no network egress.
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
    EXIT_OK,
    Skin,
    _default_download_name,
    run_operation,
)
from sentiment_cli.client import Client, _is_binary_response
from sentiment_cli.config import Config
from sentiment_cli.spec import load_spec

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from stub_backend import start_stub  # noqa: E402


class BinaryDetectTests(unittest.TestCase):
    def _hdr(self, ct=None, cd=None):
        h = {}
        if ct is not None:
            h["Content-Type"] = ct
        if cd is not None:
            h["Content-Disposition"] = cd
        return h

    def test_pdf_is_binary(self):
        self.assertTrue(_is_binary_response(self._hdr("application/pdf"), b"%PDF-1.4"))

    def test_octet_stream_is_binary(self):
        self.assertTrue(_is_binary_response(self._hdr("application/octet-stream"), b"xx"))

    def test_attachment_is_binary(self):
        self.assertTrue(
            _is_binary_response(self._hdr(cd="attachment; filename=x.pdf"), b"%PDF")
        )

    def test_json_text_not_binary(self):
        self.assertFalse(_is_binary_response(self._hdr("application/json"), b"{}"))
        self.assertFalse(_is_binary_response(self._hdr("text/html"), b"<html>"))

    def test_request_returns_bytes_for_pdf(self):
        server, base = start_stub()
        try:
            c = Client(Config(base_url=base))
            status, data = c.request("GET", "/sapi/report/files/test.pdf")
            self.assertEqual(status, 200)
            self.assertIsInstance(data, (bytes, bytearray))
            self.assertTrue(data.startswith(b"%PDF"))
        finally:
            server.shutdown()


class DownloadNameTests(unittest.TestCase):
    def test_basename(self):
        self.assertEqual(
            _default_download_name("/sapi/report/files/foo.pdf"), "foo.pdf"
        )

    def test_all_param_falls_back(self):
        self.assertEqual(_default_download_name("/{id}"), "download.bin")

    def test_rendered_path_keeps_filename(self):
        # run_operation substitutes path params before calling _save_response,
        # so the rendered URL already carries the real file name.
        self.assertEqual(
            _default_download_name("/sapi/report/files/2026-07-15.pdf"),
            "2026-07-15.pdf",
        )


class ReportDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server, cls.base = start_stub()
        cls.spec = load_spec(None)
        cls.op = cls.spec.find("report", "download")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def _ctx(self):
        return Client(Config(base_url=self.base)), Skin()

    def test_download_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = os.path.join(d, "out.pdf")
            client, skin = self._ctx()
            rc = run_operation(
                self.op,
                ["--filename", "test.pdf", "-o", tmp],
                client, skin, force_json=False,
            )
            self.assertEqual(rc, EXIT_OK)
            self.assertTrue(os.path.exists(tmp))
            with open(tmp, "rb") as fh:
                self.assertTrue(fh.read().startswith(b"%PDF"))

    def test_download_json_envelope(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = os.path.join(d, "out2.pdf")
            buf = StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                client, skin = self._ctx()
                rc = run_operation(
                    self.op,
                    ["--filename", "test.pdf", "-o", tmp, "--json"],
                    client, skin, force_json=True,
                )
            finally:
                sys.stdout = old
            self.assertEqual(rc, EXIT_OK)
            env = json.loads(buf.getvalue())
            self.assertTrue(env["ok"])
            self.assertEqual(env["data"]["saved_to"], tmp)
            self.assertGreater(env["data"]["bytes"], 0)
            self.assertTrue(os.path.exists(tmp))

    def test_call_escape_hatch_binary(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = os.path.join(d, "call.pdf")
            buf = StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                client, skin = self._ctx()
                rc = cli_mod.cmd_call(
                    client,
                    ["GET", "/sapi/report/files/test.pdf", "-o", tmp, "--json"],
                    skin, force_json=True,
                )
            finally:
                sys.stdout = old
            self.assertEqual(rc, EXIT_OK)
            env = json.loads(buf.getvalue())
            self.assertTrue(env["ok"])
            self.assertTrue(os.path.exists(tmp))


class ReportDownloadSubprocessTests(unittest.TestCase):
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
        env.pop("SENTIMENT_TOKEN", None)
        return subprocess.run(
            [sys.executable, "-m", "sentiment_cli", *args],
            cwd=ROOT, capture_output=True, text=True, env=env,
        )

    def test_subprocess_report_download(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "out.pdf")
            r = self._run("report", "download", "--filename", "test.pdf",
                          "-o", out, "--json")
            self.assertEqual(r.returncode, EXIT_OK, r.stderr)
            env = json.loads(r.stdout)
            self.assertTrue(env["ok"])
            self.assertTrue(os.path.exists(out))
            with open(out, "rb") as fh:
                self.assertTrue(fh.read().startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
