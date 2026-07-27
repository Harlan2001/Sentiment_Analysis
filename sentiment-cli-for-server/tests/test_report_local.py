"""report generate / download --local tests.

Offline contract tests (always green, no browser/network):
    * monkeypatch backend.push.pdf_generator so _report_generate_local
      and _report_download_local can be exercised without Playwright.

Local PDF integration test (gated):
    * SENTIMENT_LOCAL_REPORT=1  -> actually renders the server's
      prediction page with the LOCAL Playwright (chromium at
      PLAYWRIGHT_BROWSERS_PATH) and asserts a real PDF is
      produced. Skipped by default (needs browser + server frontend).
"""
import contextlib
import io
import json
import os
import sys
import types

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sentiment_cli.config import Config
from sentiment_cli.client import Client
from sentiment_cli.cli import (
    Skin,
    _report_download_local,
    _report_generate_local,
    run_operation,
)
from sentiment_cli.spec import load_spec


@pytest.fixture(scope="module")
def ctx():
    cfg = Config()
    spec = load_spec(cfg.spec_path)
    return cfg, Client(cfg), spec, Skin()


@pytest.fixture
def fake_pdf(tmp_path):
    """Inject a fake backend.push.pdf_generator into sys.modules so the
    local report helpers run WITHOUT Playwright. Torn down after the test
    so a later test (e.g. the live integration test) re-imports the REAL
    module instead of the fake."""
    mod = types.ModuleType("backend.push.pdf_generator")

    def fake(report_date=None, output_path=None, frontend_url=None):
        p = (
            __import__("pathlib").Path(output_path)
            if output_path
            else (tmp_path / "out.pdf")
        )
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"%PDF-1.4 fake-report\n")
        return p, "2026-07-15"

    mod.generate_prediction_pdf = fake
    push = types.ModuleType("backend.push")
    push.pdf_generator = mod
    backend = types.ModuleType("backend")
    backend.push = push
    # Only register a (fake) top-level `backend` if one isn't already
    # importable — otherwise keep the genuine package intact.
    injected_backend = "backend" not in sys.modules
    sys.modules.setdefault("backend", backend)
    sys.modules["backend.push"] = push
    sys.modules["backend.push.pdf_generator"] = mod
    yield
    # Restore: drop the injected fakes so a later test re-imports the
    # REAL backend.push.pdf_generator (the live integration test needs it).
    for _k in ("backend.push.pdf_generator", "backend.push"):
        sys.modules.pop(_k, None)
    if injected_backend:
        sys.modules.pop("backend", None)


def test_report_generate_local_offline(ctx, tmp_path, fake_pdf):
    _cfg, _client, spec, skin = ctx
    op = spec.find("report", "generate")
    out = tmp_path / "sample.pdf"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = _report_generate_local(op, {}, str(out), True, skin)
    assert rc == 0, buf.getvalue()
    env = json.loads(buf.getvalue())
    assert env["ok"] is True
    assert env["data"]["report_date"] == "2026-07-15"
    assert env["data"]["file_name"] == "sample.pdf"
    assert env["data"]["file_size_bytes"] == out.stat().st_size
    assert out.read_bytes()[:4] == b"%PDF"


def test_report_download_local_offline(ctx, tmp_path, fake_pdf, monkeypatch):
    local_pdf = tmp_path / "2026-07-15.pdf"
    local_pdf.write_bytes(b"%PDF-1.4 local\n")
    monkeypatch.chdir(tmp_path)  # 防 cwd 里残留的真实 PDF 抢候选 #1
    _cfg, _client, spec, skin = ctx
    op = spec.find("report", "download")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = _report_download_local(
            op, {"filename": "2026-07-15.pdf"}, str(tmp_path / "dl.pdf"), True, skin
        )
    assert rc == 0, buf.getvalue()
    env = json.loads(buf.getvalue())
    assert env["ok"] is True
    assert env["data"]["saved_to"].endswith("dl.pdf")
    assert env["data"]["bytes"] == local_pdf.stat().st_size


def test_report_generate_via_run_operation_offline(ctx, tmp_path, monkeypatch, fake_pdf):
    """End-to-end via run_operation with --local (offline fake)."""
    _cfg, client, spec, skin = ctx
    op = spec.find("report", "generate")
    out = tmp_path / "via.pdf"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = run_operation(
            op, ["--local", "--output", str(out), "--json"], client, skin, force_json=True
        )
    assert rc == 0, buf.getvalue()
    env = json.loads(buf.getvalue())
    assert env["ok"] is True
    assert env["data"]["report_date"] == "2026-07-15"


def test_report_download_via_run_operation_offline(ctx, tmp_path, monkeypatch):
    """`--filename` is a PATH param; via the real CLI parser it must
    reach the local handler through `query` (regression for the
    path-param -> query merge in run_operation)."""
    local_pdf = tmp_path / "2026-07-15.pdf"
    local_pdf.write_bytes(b"%PDF-1.4 local\n")
    monkeypatch.chdir(tmp_path)  # 防 cwd 里残留的真实 PDF 抢候选 #1
    _cfg, client, spec, skin = ctx
    op = spec.find("report", "download")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = run_operation(
            op,
            ["--local", "--filename", "2026-07-15.pdf",
             "--output", str(tmp_path / "dl.pdf"), "--json"],
            client, skin, force_json=True,
        )
    assert rc == 0, buf.getvalue()
    env = json.loads(buf.getvalue())
    assert env["ok"] is True
    assert env["data"]["saved_to"].endswith("dl.pdf")
    assert env["data"]["bytes"] == local_pdf.stat().st_size



@pytest.mark.skipif(
    not os.environ.get("SENTIMENT_LOCAL_REPORT"),
    reason="需 SENTIMENT_LOCAL_REPORT=1 且本地 Playwright+chromium 可用",
)
def test_report_generate_local_integration(ctx, tmp_path):
    """Real PDF generation via the server's frontend + local Playwright."""
    _cfg, _client, spec, skin = ctx
    op = spec.find("report", "generate")
    out = tmp_path / "live.pdf"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = _report_generate_local(op, {}, str(out), True, skin)
    assert rc == 0, buf.getvalue()
    assert out.exists(), "未生成 PDF"
    head = out.read_bytes()[:4]
    assert head == b"%PDF", f"不是 PDF: {head}"
    assert out.stat().st_size > 1000, "PDF 过小，可能为空"
