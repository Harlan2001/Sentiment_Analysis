"""Offline end-to-end tests driven by a LOCAL stub backend.

No live "Bond Yield Backend" and no network egress required: a real HTTP
server on 127.0.0.1 (see stub_backend.py) emulates the endpoints the suite
needs, so these run green inside the sandbox and in CI. Both the in-process
``Client`` and the subprocess-launched CLI point at the stub through
``SENTIMENT_BASE_URL``.
"""
import json
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # make stub_backend importable

from stub_backend import start_stub  # noqa: E402

from sentiment_cli.client import BackendError, Client  # noqa: E402
from sentiment_cli.config import Config  # noqa: E402

PKG_DIR = os.path.dirname(HERE)


@pytest.fixture(scope="module")
def base_url():
    server, url = start_stub()
    yield url
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def client(base_url):
    return Client(Config(base_url=base_url))


# ---- direct client ---------------------------------------------------------
def test_health(client):
    status, data = client.health()
    assert status == 200
    assert data.get("status") == "ok"


def test_openapi_fetch_matches_bundled(client):
    raw = client.fetch_openapi()
    assert raw["info"]["title"] == "Bond Yield Backend"
    assert len(raw["paths"]) >= 40


def test_news_list_returns_list(client):
    status, data = client.request("GET", "/sapi/news")
    assert status == 200
    assert isinstance(data, list)


def test_factors_list(client):
    status, data = client.request("GET", "/sapi/factors")
    assert status == 200
    assert "factors" in data and isinstance(data["factors"], list)


def test_news_detail_path_param(client):
    status, data = client.request("GET", "/sapi/news/1")
    assert status == 200
    assert isinstance(data, dict)


def test_backend_validation_error_is_422(client):
    with pytest.raises(BackendError) as exc:
        client.request("POST", "/sapi/auth/login", body={})
    assert exc.value.status == 422


# ---- CLI subprocess (real exit codes + JSON envelope) ------------------------
def _run(args, base_url):
    env = dict(os.environ)
    env["SENTIMENT_BASE_URL"] = base_url
    env["SENTIMENT_USE_PROXY"] = "false"
    proc = subprocess.run(
        [sys.executable, "-m", "sentiment_cli", *args],
        cwd=PKG_DIR, capture_output=True, text=True, env=env,
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_cli_health_json_exit0(base_url):
    code, out, _ = _run(["--json", "health"], base_url)
    assert code == 0
    env = json.loads(out.strip())
    assert env["ok"] is True and env["status"] == 200


def test_cli_describe_check_exit0(base_url):
    code, out, _ = _run(["describe", "--check"], base_url)
    assert code == 0
    doc = json.loads(out)
    assert doc["operation_total"] == 33
    assert doc["backend"]["reachable"] is True


def test_cli_backend_error_exit4(base_url):
    code, out, _ = _run(
        ["--json", "call", "POST", "/sapi/auth/login", "--body", "{}"], base_url
    )
    assert code == 4
    env = json.loads(out.strip())
    assert env["ok"] is False and env["status"] == 422


def test_cli_usage_error_exit2(base_url):
    code, _out, _err = _run(["macro", "signal"], base_url)  # missing required
    assert code == 2


def test_cli_unknown_command_exit2(base_url):
    code, _out, _err = _run(["frobnicate"], base_url)
    assert code == 2


def test_cli_news_list_json_envelope(base_url):
    code, out, _ = _run(["--json", "news", "list"], base_url)
    assert code == 0
    env = json.loads(out.strip())
    assert env["command"] == "news list"
    assert isinstance(env["data"], list)
